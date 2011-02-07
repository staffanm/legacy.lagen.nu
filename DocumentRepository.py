#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Base class for handling a repository of documents. This inludes
downloading them from a remote source, parsing the raw data into a
structured XHTML+RDFa representation, transforming them to
browser-ready HTML, and some other stuff."""
# this replaces the LegalSource classes with a single class that has
# sensible logging, layered config handling (file + command line args)
# and in general does a lot of heavy lifting

# system
import os,sys
import logging
import logging.handlers
import multiprocessing # either get python 2.6 or the backported multiprocessing module
from tempfile import mktemp
import codecs
from time import time
import functools
import xml.etree.cElementTree as ET
import xml.dom.minidom
from datetime import datetime
import re
import urllib

# 3rd party
import BeautifulSoup
from configobj import ConfigObj
from mechanize import Browser, LinkNotFoundError, RobustFactory, URLError
from genshi.template import TemplateLoader
from rdflib import Literal, Namespace, URIRef, RDF, RDFS
# Assume RDFLib 3.0
from rdflib import Graph, ConjunctiveGraph
from rdflib.plugins.parsers.ntriples import unquote as ntriple_unquote

# mine
import Util
from LegalRef import LegalRef, Link
from DataObjects import UnicodeStructure, CompoundStructure, \
     MapStructure, IntStructure, DateStructure, PredicateType, \
     UnicodeSubject, Paragraph, Section, \
     serialize
from SesameStore import SesameStore

__version__ = (1,6)
__author__  = u"Staffan Malmgren <staffan@tomtebo.org>"

# Magicality to make sure printing of unicode objects work no matter
# what platform we're running on
if sys.platform == 'win32':
    if sys.stdout.encoding:
        defaultencoding = sys.stdout.encoding
    else:
        # print "sys.stdout.encoding not set"
        defaultencoding = 'cp850'
else:
    if sys.stdout.encoding:
        defaultencoding = sys.stdout.encoding
        if defaultencoding == 'ANSI_X3.4-1968': # really?!
            defaultencoding = 'iso-8859-1'
    else:
        import locale
        locale.setlocale(locale.LC_ALL,'')
        defaultencoding = locale.getpreferredencoding()

# for some reason, resetting sys.stdout to a more forgiving writer on
# OSX (builtin python 2.6) results in a strict ascii
# writer. Investigate further...
if (sys.platform != "darwin" and sys.platform != "linux2"):
    sys.stdout = codecs.getwriter(defaultencoding)(sys.__stdout__, 'replace')
    sys.stderr = codecs.getwriter(defaultencoding)(sys.__stderr__, 'replace')


# Global/static functions - global_init and global_run are used when
# running actions in parallel using multiprocessing.Pool. The argument
# to Pool.map needs to be a single picklabe method (i.e. not an
# instance method), which takes a single argument. We use a
# initializer (global_init) to set up some other arguments that the
# method (global_run) needs.
#
# I wonder if it has to be this complicated?
__execute_module = None
__execute_class = None
__execute_args = None

def global_init(modulename,classname,args):
    """This is a helper function to make L{multiprocessing} work nice under Windows"""
    global __execute_module, __execute_class, __execute_args
    __execute_module = modulename
    __execute_class = classname
    __execute_args = args
    #log = multiprocessing.get_logger()
    #if log.handlers == []:
    #    h = logging.StreamHandler()
    #    h.setLevel(logging.INFO)
    #    h.setFormatter(logging.Formatter("[%(levelname)s/%(process)d] %(message)s"))
    #    log.addHandler(h)
    #    log.setLevel(logging.INFO)
    #log.info("initializing %s %r" % (__execute_class, __execute_args))


def global_run(argument):
    """This is a helper function to make L{multiprocessing} work nice under Windows"""
    global __execute_module, __execute_class, __execute_args
    #log = multiprocessing.get_logger()
    #log.info("running %s %r %s" % (__execute_class, __execute_args, argument))

    mod = __import__(__execute_module)
    cls = getattr(mod, __execute_class)
    return cls.run(__execute_args, argument)

#class SaneNamespaceManager(NamespaceManager):
#   def compute_qname(self, uri):
#        if not uri in self.__cache:
#            namespace, name = split_uri(uri)
#            namespace = URIRef(namespace)
#            prefix = self.store.prefix(namespace)
#            if prefix is None:
#                raise Exception("Prefix for %s not bound" % namespace)
#            self.__cache[uri] = (prefix, namespace, name)
#        return self.__cache[uri]

class DocumentRepository(object):
    """Base class for downloadning, parsing and generating HTML
    versions of a repository of documents.

    If you want to do stuff with a set of documents (particularly
    documents that can be fetched over the web), like downloading
    them, parsing the data into some structured format, and
    (re-)generating HTML versions of them, this class contains lots of
    stuff to help you.

    You use it by creating a new class that inherits from this class,
    and overriding methods in that class. To get a very simple example
    going, you only need to specify start_url and document_url

    To get more control over parsing and HTML generation, you override
    additional methods. There are eight main entry points into the
    module, with the following principal call chains:

    download_new
        download_everything
            download_single
                downloaded_path
                download_if_needed
                remote_url
    parse
        parsed_path
        soup_from_basefile
        parse_from_soup
        render_xhtml
        
    relate

    generate
        generated_file
        prep_annotation_file
            graph_to_annotation_file

    toc 
        toc_navigation
        toc_title
        toc_style
            toc_style_list | toc_style_table | toc_style_multicol
        toc_page

    news
        news_selections
        news_selection

    frontpage_content

    tabs
    """
    
    module_dir = "base"
    """The directory where this module will store downloaded, parsed
    and generated files. You need to override this."""

    genshi_tempate = "genshi/generic.xhtml"
    """The U{Genshi<http://genshi.edgewall.org/>} template used to
    transform the parsed object structure into a standard XML file. If
    your data is complex, you might want to override this (and write
    your own Genshi template). If you prefer other ways of
    transforming your data into a serialized XML file, you might want
    to override L{render_xhtml} altogether."""
    
    xslt_template = "xsl/generic.xsl"
    """A template used to transform the XML file into browser-ready
    HTML. If your document type is complex, you might want to override
    this (and write your own XSLT transform). You should include
    base.xslt in that template, though."""

    rdf_type = Namespace(Util.ns['rinfo'])['Rattsinformationsdokument']
    """The RDF type of the documents you are handling (expressed as a RDFLib URIRef)."""

    source_encoding = "iso-8859-1"
    """The character set that the source HTML documents use (if applicable)"""
    
    lang = "en"
    """The language that the source documents are written in (unless
    otherwise specified, and that output document should use"""

    start_url = "http://example.org/"
    """The main entry page for the remote web store of documents. May
    be a list of documents, a search form or whatever. If it's
    something more complicated than a simple list of documents, you
    need to override download_everything in order to tell which
    documents are to be downloaded."""

    document_url = "http://example.org/docs/%s.html"

    basefile_template = ".*"

    # If set, uses BeautifulSoup as parser even for downloading
    # (parsing the navigation/search/index pages). It's more robust
    # aginst invalid HTML, but might be slower and seems to return
    # incorrect results for link.text if the link text contain markup
    browser_use_robustfactory = False
    
    # this is a replacement for DispatchMixin.dispatch with built-in
    # support for running the *_all methods (parse_all, relate_all and
    # generate_all) in parallell using multiprocessing
    @classmethod
    def run(cls,argv=sys.argv[1:],*extra):
        """Method for running individual methods in a consistent and
        multiprocessing-friendly manner. You don't need to override or
        call this."""
        # OptionParser seems to require that we define each and every
        # possible option beforehand. Since each module may have it's
        # own settings, this is not really possible
        from collections import defaultdict
        options = defaultdict(lambda:defaultdict(dict))
        args = []
        for arg in argv:
            if arg.startswith("--"):
                if "=" in arg:
                    (key,value) = arg.split("=",1)
                else:
                    (key,value) = (arg, 'True')
                # Note: Options may not contains hyphens (ie they can't
                # be called "parse-force")
                parts = key[2:].split("-")
                if len(parts) == 1:
                    options[parts[0]] = value
                elif len(parts) == 2:
                    print "options[%s][%s] = %r" % (parts[0], parts[1], value)
                    options[parts[0]][parts[1]] = value
                elif len(parts) == 3:
                    options[parts[0]][parts[1]][parts[2]] = value
            else:
                args.append(arg)

        for arg in extra:
            args.append(arg)
            
        (configfile,config,moduleconfig) = cls.initialize_config(options)
        from pprint import pprint
        #pprint(config)
        #pprint(moduleconfig)
        
        if len(args) == 0:
            cls.print_valid_commands()
        elif args[0].endswith("_all"):
            cls.run_all(args[0],argv,config)
        else:
            c = cls(options)
            func = getattr(c,args[0])
            return func(*args[1:])

    @classmethod
    def print_valid_commands(cls):
        internal_commands = ("run", "print_valid_commands")
        print "Valid commands are:", ", ".join(
            [str(m) for m in dir(cls) if (m not in internal_commands and
                                           not m.startswith("_") and
                                           callable(getattr(cls, m)))]
            )

    # how should download_all and relate_all be parallelizable (if at
    # all?) For relate_all in particular we need to collect the
    # results from each relate call in the end and do some custom
    # processing on them.
    @classmethod
    def run_all(cls, func_name_all, argv, config):
        start = time()
        # replace "foo_all" with "foo" in the argument array we provide run()
        func_name = func_name_all[:-4]
        argv[argv.index(func_name_all)] = func_name
        argv.append("--logfile=%s" % mktemp())
        # FIXME: find out which module this class belongs to
        global_init_args = (cls.__module__,cls.__name__, argv)
        cls.setup(func_name_all, config)
        iterable = cls.get_iterable_for(func_name_all,config['datadir'])
        if 'processes' in config and int(config['processes']) > 1:
            print "Running multiprocessing"
            p = multiprocessing.Pool(int(config['processes']),global_init,global_init_args)
            results = p.map(global_run,iterable)
        else:
            print "Not running multiprocessing"
            global_init(*global_init_args)
            results = []
            for basefile in iterable:
                results.append(global_run(basefile))
        cls.teardown(func_name_all, config)
        # FIXME: This should use the logging infrastructure, but
        # _setup_logger is a instancemethod
        # ret = cls.collect_results_for(func_name_all, results)
        print u'%s: OK (%.3f sec)' % (func_name_all,time()-start)
        
    @classmethod
    def get_iterable_for(cls,funcname,base_dir):
        if funcname == "parse_all":
            directory = os.path.sep.join((base_dir, cls.module_dir, u"downloaded"))
            suffix = ".html"
        elif funcname in ("generate_all", "relate_all"):
            directory = os.path.sep.join((base_dir, cls.module_dir, u"parsed"))
            suffix = ".xhtml"

        for x in Util.listDirs(directory,suffix,reverse=True):
            yield cls.basefile_from_path(x)

    @classmethod
    def setup(cls,funcname,config):
        """Runs before any of the *_all methods starts executing"""
        cbl = getattr(cls, funcname + "_setup")
        cbl(config)

    @classmethod
    def teardown(cls,funcname,config):
        """Runs after any of the *_all methods has finished executing"""
        cbl = getattr(cls, funcname + "_teardown")
        cbl(config)

#    @classmethod
#    def collect_results_for(cls,funcname,results):
#        if funcname == "relate_all":
#            # results will be an array of NT files. Combine them into
#            # one big NT file, submit it to sesame, and store it as a
#            # NT file. Things to find out: the sesame server location
#            # the context URI the name of the NT file
#            for f in results:
#                pass
#        else:
#            pass # nothin' to do

    @classmethod
    def initialize_config(cls,options):
        configfile = ConfigObj(os.path.dirname(__file__)+"/ferenda.conf")
        # Normally, you should read from self.config rather than
        # self.configfile as this will make sure command line
        # arguments take precedence over config file parameters. The
        # exception is if you wish to save some sort of state
        # (eg. "last-processed-id-number") in the config file.
        config = DocumentRepository.merge_dict_recursive(dict(configfile), options)
        if cls.module_dir not in config:
            config[cls.module_dir] = {}

        moduleconfig = config[cls.module_dir]
        return (configfile,config,moduleconfig)
    
    @classmethod
    def basefile_from_path(cls,path):
        seg = os.path.splitext(path)[0].split(os.sep)
        return "/".join(seg[seg.index(cls.module_dir)+2:])

    @classmethod
    def context(cls):
        """Return the context URI under which RDF statements should be stored."""
        return "http://example.org/ctx/%s" % (cls.module_dir)

    @staticmethod
    def merge_dict_recursive(base,other):
        for (key,value) in other.items():
            if (isinstance(value,dict) and
                (key in base) and
                (isinstance(base[key],dict))):
                base[key] = DocumentRepository.merge_dict_recursive(base[key],value)
            else:
                base[key] = value
        return base


    def __init__(self,options):
        (self.configfile,self.config,self.moduleconfig) = self.initialize_config(options)
        # If we have a particular log level for this module, use that,
        # otherwise use the global log level. If that isn't defined
        # either, use the INFO loglevel.
        if 'log' in self.moduleconfig:
            loglevel = self.moduleconfig['log']
        else:
            loglevel = self.config.get('log','INFO')
        self.log = self.setup_logger(self.module_dir,loglevel)

        self.base_dir = self.config['datadir']

        if self.browser_use_robustfactory:
            self.browser = Browser(factory=RobustFactory())
        else:
            self.browser = Browser()
        self.browser.addheaders = [('User-agent', 'lagen.nu-bot (staffan@lagen.nu)')]

        # logger = logging.getLogger("mechanize")
        # logger.addHandler(logging.StreamHandler(sys.stdout))
        # logger.setLevel(logging.DEBUG)
        # self.browser.set_debug_http(True)
        # self.browser.set_debug_responses(True)
        # self.browser.set_debug_redirects(True)


        self.ns = {'rinfo':  Namespace(Util.ns['rinfo']),
                   'rinfoex':Namespace(Util.ns['rinfoex']),
                   'dct':    Namespace(Util.ns['dct'])}

    def get_globals(self):
        """If your submodule defines classes or functions which your
        genshi template expects to find, you need to implement this
        (with a single "return globals()" statement. This is in order to
        feed your modules global bindings to Genshi"""
        return globals()
        
    def canonical_uri(self,basefile):
        """return the canonical URI for this particular document/resource."""
        # Note that there might not be a 1:1 mappning between
        # documents and URIs -- don't know what we should do in those
        # cases.
        #
        # It might also be impossible to provide the canonical_uri
        # without actually parse()ing the document
        return "http://example.org/res/%s/%s" % (self.module_dir, basefile)

    def get_logger(self,name):
        """Create an additional logger (which can be turned on or off
        in the config file) for debug messages in particular areas of
        the code"""
        # By default, don't really log anything (we'd like to create a
        # logger with no handlers, but that prints out a warning
        # message)
        loglevel = self.moduleconfig[name].get('log','CRITICAL')
        return self.setup_logger(name,loglevel)

    def setup_logger(self,name,loglevel):
        loglevels = {'DEBUG':logging.DEBUG,
                     'INFO':logging.INFO,
                     'WARNING':logging.WARNING,
                     'ERROR':logging.ERROR,
                     'CRITICAL':logging.CRITICAL}

        if not isinstance(loglevel,int):
            loglevel = loglevels[loglevel]

        l = logging.getLogger(name)
        if l.handlers == []:
            h = logging.StreamHandler()
            h.setLevel(loglevel)
            h.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s",
                                             datefmt="%Y-%m-%d %H:%M:%S"))
            l.addHandler(h)
        l.setLevel(loglevel)
        return l

    def store_triple(self,subj,pred,obj):
        # store this changelog under a different context than the
        # actual content, since that gets blown away by relate_all
        store = SesameStore(self.config['triplestore'],self.config['repository'],self.context()+"/modified")
        store.add_triple((subj,pred,obj))
        store.commit()
        
    
    ################################################################
    #
    # STEP 1: Download documents from the web
    #
    ################################################################

    # This is a very simple generic implementation. Assumes all
    # documents are linked from a single page, that they all have URLs
    # matching the document_url template, and that the link text is
    # always equal to basefile. If these assumptions don't hold, you
    # need to override this method.
    def download_everything(self,usecache=False):
        self.log.info("Starting at %s" % self.start_url)
        self.browser.open(self.start_url)
        url_regex = self.document_url.replace("%s", "(.*)")
        # self.log.info("url_regex: %s" % url_regex)
        for link in self.browser.links(predicate=lambda l:re.match(url_regex,l.absolute_url)):
            # self.log.debug("Found link (%r)" % (link))
            try:
                basefile = re.search(self.basefile_template, link.text).group(0)
                # self.log.debug("Transformed into basefile %s" % (basefile))
                self.download_single(basefile,usecache,link.absolute_url)
            except AttributeError:
                self.log.error("Couldn't find basefile information in link text %s" % link.text)

    def download_new(self):
        self.download_everything(usecache=True)


    def download_single(self,basefile,usecache=False,url=None):
        """Downloads the document from the web (unless explicitly
        specified, the URL to download is determined by
        self.document_url combined with basefile, the location on disk
        is determined by the function self.download_path). If usecache
        is set and the document exists on disk no download is
        attempted.

        Otherwise, if the document exists on disk, but the version on
        the web is unchanged, the file on disk is left unchanged
        (i.e. the timestamp is not modified).

        Returns True if the document was downloaded and stored on
        disk, False if the file on disk was not updated.
        """
        if not url:
            url = self.remote_url(basefile)
        filename = self.downloaded_path(basefile)
        # self.log.debug("Usecache is %s, existance of %s is %s" % (usecache, filename,os.path.exists(filename)))
        if not usecache or not os.path.exists(filename):
            existed = os.path.exists(filename)
            if self.download_if_needed(url,filename):
                # the downloaded file was updated (or created) --
                # let's make a note of this in the RDF graph!
                uri = self.canonical_uri(basefile)
                self.store_triple(URIRef(uri), self.ns['dct']['modified'], Literal(datetime.now()))
                if existed:
                    self.log.debug("%s existed, but a new version was downloaded" % filename)
                else:
                    self.log.debug("%s did not exist, so it was downloaded" % filename)
                return True
            else:
                self.log.debug("%s exists and is unchanged" % filename)
        else:
            self.log.debug("%s already exists" % (filename))
        return False


    def download_if_needed(self,url,filename):
        """Downloads the url to local filename if it's needed. The
        default implementation always downloads the url, and if the
        local file is already present, replaces it."""
        # FIXME: Check the timestamp of filename (if it exists), and
        # do a if-modified-since request.
        tmpfile = mktemp()
        # self.log.debug("Retrieving %s to %s" % (url,filename))
        try:
            self.browser.retrieve(url,tmpfile)
            return Util.replace_if_different(tmpfile,filename)
        except URLError, e:
            self.log.error("Failed to fetch %s: %s" % (url, e))

    def remote_url(self,basefile):
        return self.document_url % urllib.quote(basefile)

    # Splits the basefile on a few common delimiters (/, : and space)
    # and constructs a path from the segments
    def generic_path(self,basefile,maindir,suffix):
        segments = [self.base_dir, self.module_dir, maindir]
        segments.extend(re.split("[/: ]", basefile))
        return os.path.sep.join(segments)+suffix
        
    
    def downloaded_path(self,basefile):
        return self.generic_path(basefile,u'downloaded','.html')


    ################################################################
    #
    # STEP 2: Parse the downloaded data into a structured XML document
    # with RDFa metadata.
    #
    ################################################################

    @classmethod
    def parse_all_setup(cls, config):
        pass

    @classmethod
    def parse_all_teardown(cls, config):
        pass
    
    # The boilerplate code for handling exceptions and logging time
    # duration might be extracted to decorator functions (generate
    # uses the same boilerplate code, as might other functions). Maybe
    # even the parce_force handling?
    def parse(self,basefile):
        """Takes the raw data downloaded by the download functions and
        parses it into a structured XML document with RDFa sprinkled
        throughout. It will also save the same RDF statements in a
        separate RDF/XML file.

        You will need to provide your own parsing logic, but often
        it's easier to just override parse_from_soup (assuming your
        indata is in a HTML format parseable by BeautifulSoup) and let
        the base class read and write the files."""
        try:
            start = time()
            infile = self.downloaded_path(basefile)
            outfile = self.parsed_path(basefile)
            force = ('parseforce' in self.moduleconfig and
                     self.moduleconfig['parseforce'] == 'True')
            if not force and Util.outfile_is_newer([infile],outfile):
                self.log.debug(u"%s: Överhoppad", basefile)
                return
            self.log.debug(u"%s: Starting", basefile)

            # the actual function code
            soup = self.soup_from_basefile(basefile,self.source_encoding)
            doc = self.parse_from_soup(soup,basefile)
            self.render_xhtml(self.genshi_tempate, doc,
                              self.parsed_path(basefile), self.get_globals())

            # Check to see that all metadata contained in doc.meta is
            # present in the serialized file.
            
            #print "doc['meta']:"
            #print doc['meta'].serialize(format="nt")
            #print
            distilled_graph = Graph()
            distilled_graph.parse(outfile,format="rdfa")
            #print "distilled_graph:"
            #print distilled_graph.serialize(format="nt")
            #print
            distilled_file = self.distilled_path(basefile)
            Util.ensureDir(distilled_file)
            distilled_graph.serialize(distilled_file,format="pretty-xml", encoding="utf-8")
            self.log.debug(u'%s: %s triples extracted', basefile, len(distilled_graph))
            
            for triple in distilled_graph:
                len_before = len(doc['meta'])
                doc['meta'].remove(triple)
                len_after = len(doc['meta'])
                # should this even be a warning? The parse step may add extra metadata in the text (eg inserting links, which may become dct:references triples)
                #if len_before == len_after:
                #    (s,p,o) = triple
                #    self.log.warning("The triple '%s %s %s .' from the XHTML file was not found in the original metadata" % (s.n3(),p.n3(), o.n3()))

            if doc['meta']:
                self.log.warning("%d triple(s) from the original metadata was not found in the serialized XHTML file:" % len(doc['meta']))
                print doc['meta'].serialize(format="nt")

            self.log.info(u'%s: OK (%.3f sec)', basefile,time()-start)

        except KeyboardInterrupt:
            raise
        except:
            self.log.exception("parse of %s failed" % basefile)
            if 'fatalexceptions' in self.config:
                raise

    def soup_from_basefile(self,basefile,encoding='iso-8859-1'):
        """Helper function."""
        filename = self.downloaded_path(basefile)
        return BeautifulSoup.BeautifulSoup(
            codecs.open(filename,encoding=encoding,errors='replace').read(),
            convertEntities='html')

    def parse_from_soup(self,soup,basefile):
        """Returns a dict with the keys 'meta', 'body', 'uri' and
        'lang'.

        body should be an iterable object, but in particular
        it must be compatible with whatever template you've set
        genshi_template to (the default generic.xhtml assumes a tree
        of iterable objects built upon the DataObjects base
        classes).

        meta should be a RDFLib graph.

        uri should be the canonical uri for this document, as used by
        the above graph.

        lang should be a ISO language code, eg 'sv' or 'en'.

        The default implementation creates a simple representation of
        the page body, a small metadatagraph containing the title, and
        a generic uri based on the module_dir and basefile.
        """

        # Default language unless we can find out from source doc?
        # Check html/@xml:lang || html/@lang
        root = soup.find('html')
        try:
            lang = root['xml:lang']
        except KeyError:
            try:
                lang = root['lang']
            except KeyError:
                lang = self.lang
        
        title = soup.find('title').string
        # self.log.info("Title: %s" % title)

        uri = self.canonical_uri(basefile)
        # self.log.info("URI: %s" % uri)

        meta = Graph()
        meta.bind('dct',self.ns['dct'])
        meta.add((URIRef(uri), self.ns['dct']['title'], Literal(title,lang=lang)))
        meta.add((URIRef(uri), self.ns['dct']['identifier'], Literal(basefile)))

        # remove all HTML comments, script tags
        comments = soup.findAll(text=lambda text:isinstance(text, BeautifulSoup.Comment))
        [comment.extract() for comment in comments]        
        scripts = soup.findAll('script')
        [script.extract() for script in scripts]
        
        # block-level elements that commonly directly contain text
        body = CompoundStructure()
        for block in soup.findAll(['blockquote', 'center','dt','dd','li','th','td','h1','h2','h3','h4','h5','h6','p', 'pre']):
            t = Util.normalizeSpace(''.join(block.findAll(text=True)))
            block.extract() # to avoid seeing it again
            if t:
                # self.log.info("Paragraph (%s %s): '%s...'" % (block.name, id(block), t[:20]))
                body.append(Paragraph([t]))
            
        return {'body':body,
                'meta':meta,
                'uri':uri,
                'lang':lang}
    
    def render_xhtml(self,template,doc,outfile,globals):
        """Serializes the parsed object structure into a XML file with
        RDFa attributes, by using Genshi with a suitable template."""
        # only look in cwd and this file's directory
        loader = TemplateLoader(['.' , os.path.dirname(__file__)],
                                variable_lookup='lenient') 
        
        tmpl = loader.load(template)
        stream = tmpl.generate(doc=doc,**globals)
        try:
            tmpfile = mktemp()
            res = stream.render()
            fp = open(tmpfile,"w")
            fp.write(res)
            fp.close()
            Util.replace_if_different(tmpfile,outfile)

        except Exception, e:
            self.log.error(u'Fel vid templaterendring: %r' % (sys.exc_info()[1]))
            raise
        if 'class="warning"' in res:
            start = res.index('class="warning">')
            end = res.index('</',start+16)
            msg = Util.normalizeSpace(res[start+16:end].decode('utf-8'))
            self.log.error(u'templatefel \'%s\'' % (msg[:80]))
        return res


    def parsed_path(self,basefile):
        return self.generic_path(basefile,u'parsed','.xhtml')

    def distilled_path(self,basefile):
        return self.generic_path(basefile,u'distilled','.rdf')

    ################################################################
    #
    # STEP 3: Extract and store the RDF data
    #
    ################################################################
    @classmethod
    def relate_all_setup(cls, config):
        store = SesameStore(config['triplestore'],config['repository'],cls.context())
        print "Clearing context %s at repository %s" % (cls.context(), config['repository'])
        store.clear()

    @classmethod
    def relate_all_teardown(cls, config):
        pass

    def relate(self,basefile):
        """Insert the (previously distilled) RDF statements into the triple store"""
        self.log.debug("Adding %s to triple store" % self.distilled_path(basefile))
        data = open(self.distilled_path(basefile)).read()
        store = SesameStore(self.config['triplestore'],self.config['repository'],self.context())
        store.add_serialized(data,format="xml")

    def extract_rdfa(self,filename):
        """Helper function to extract RDF data from any XML document
        containing RDFa attributes. Returns a RDFlib graph of the
        triples found."""

        
        dom  = xml.dom.minidom.parse(filename)
        o = pyRdfa.Options(space_preserve=False)
        o.warning_graph = None
        g = pyRdfa.parseRDFa(dom, "http://example.org/", options=o)
        # clean up whitespace for Literals
        #for tup in g:
        #    (o,p,s) = tup
        #    if isinstance(s,Literal):
        #        g.remove(tup)
        #        l = Literal(u' '.join(s.split()), lang=s.language, datatype=s.datatype)
        #        g.add((o,p,l))
        return g
        

    ################################################################
    #
    # STEP 4: Generate browser-ready HTML with navigation panels,
    # information about related documents and so on.
    #
    ################################################################
    @classmethod
    def generate_all_setup(cls, config):
        pass
    
    @classmethod
    def generate_all_teardown(cls, config):
        pass

    def generate(self,basefile):
        """Generate a browser-ready HTML file from the structured XML
        file constructed by parse. The generation is done by XSLT, and
        normally you won't need to override this, but you might want
        to provide your own xslt file and set self.xslt_template to
        the name of that file. If you want to generate your
        browser-ready HTML by any other means than XSLT, you should
        override this method."""
        try:
            start = time()
            infile = self.parsed_path(basefile)
            outfile = self.generated_path(basefile)
            force = ('generateforce' in self.moduleconfig and
                    self.moduleconfig['generateforce'] == 'True')
            if not force and Util.outfile_is_newer([infile],outfile):
                self.log.debug(u"%s: Överhoppad", basefile)
                return
            self.log.debug(u"%s: Starting", basefile)

            # The actual function code
            annotation_file = self.prep_annotation_file(basefile)
            if annotation_file:
                # params = {'annotationfile':'../data/sfs/intermediate/%s.ann.xml' % basefile}
                params = {'annotationfile':'../'+annotation_file.replace("\\","/")}
            else:
                params = {}
            Util.transform(self.xslt_template,
                           infile,
                           outfile,
                           parameters = params,
                           validate=False)

            self.log.info(u'%s: OK (%.3f sec)', basefile, time()-start)
        except KeyboardInterrupt:
            raise
        except:
            self.log.exception("parse of %s failed" % basefile)
            

    def prep_annotation_file(self, basefile):
        """Helper function used by generate -- prepares a RDF/XML file
        containing statements that in some way annotates the
        information found in the document that generate handles, like
        URI/title of other documents that refers to this one."""
        return None


    # helper for the prep_annotation_file helper -- it expects a
    # RDFLib graph, and returns (the path to a file with) the same in
    # Grit format.
    def graph_to_annotation_file(self,graph,basename):
        infile = mktemp()
        fp = open(infile,"w")
        fp.write(graph.serialize(format="pretty-xml"))
        fp.close()
        outfile = self.annotation_path(basename)
        Util.transform("xsl/rdfxml-grit.xslt",
                       infile,
                       outfile,
                       validate=False)
        return outfile
    
    def generated_path(self,basefile):
        return self.generic_path(basefile,u'generated','.html')

    def annotation_path(self,basefile):
        return self.generic_path(basefile,u'intermediate','.ann.xml')

    ################################################################
    #
    # STEP 5: Generate HTML pages for a TOC of a all documents, news
    # pages of new/updated documents, and other odds'n ends.
    #
    ################################################################

    
    
    def toc(self):
        """Creates a set of pages that together acts as a table of
        contents for all documents in the repository. For smaller
        repositories a single page might be enough, but for
        repositoriees with a few hundred documents or more, there will
        usually be one page for all documents starting with A,
        starting with B, and so on. There might be different ways of
        browseing/drilling down, i.e. both by title, publication year,
        keyword and so on."""

        # Step 1: Select a table that contains most of the interesting
        # info, eg:
        #
        # URI dct:title dct:issued dct:identifier
        #
        # and convert it to a list of dicts

        # GENERALIZE: Subclasses should be able to change the query by
        # implementing eg self.toc_query()
        sq = """PREFIX dct:<http://purl.org/dc/terms/>
                SELECT ?uri ?title ?id
                WHERE {?uri dct:title ?title .
                       ?uri dct:identifier ?id  }"""
        store = SesameStore(self.config['triplestore'],
                            self.config['repository'],
                            self.context())
        data = store.select(sq,"python")
        
        # Step 2: For each criterion (a criterion is a rdf predicate +
        # selector function like first_letter or year_part + sort
        # function) defined for the class:

        # GENERALIZE: criteria should be initalized from a list in
        # self.toc_categories. The list should be able to be very sparse,
        # like [self.ns['dct']['title'],self.ns['dct']['issued']], and
        # the initialization routine should add the appropriate
        # bindning, label, selector and sorter (at least for standard
        # DCT predicates. 
        criteria = ({'predicate':self.ns['dct']['title'],
                     'binding':'title', # must match sparql query
                     'label':'Sorted by title', # GENERALIZE: This string must me controllable/localizable
                     'selector':lambda x: x[0].lower(),
                     'sorter':cmp,
                     'pages': []},
                    {'predicate':self.ns['dct']['identifier'],
                     'binding':'id',
                     'label':'Sorted by identifier',
                     'selector':lambda x: x[0].lower(),
                     'sorter':cmp,
                     'pages': []})

        g = Graph()
        for qname in self.ns:
            g.bind(qname, self.ns[qname])
                
        for criterion in criteria:
        # 2.1 Create the list of possible values from the selector
        # function and...
            selector_values = {}
            selector = criterion['selector']
            binding = criterion['binding']
            qname = g.qname(criterion['predicate'])
            for row in data:
                selector_values[selector(row[binding])] = True
            
            # 2.1 cont: For each value:
            for value in sorted(selector_values.keys(),cmp=criterion['sorter']):
                # 2.1.1 Prepare a filename based on the rdf predicate and the selector
                #       func value, eg. toc/dct/title/a.xhtml
                tmpfile = os.path.sep.join((self.base_dir,
                                           self.module_dir,
                                           u'toc',
                                           qname.split(":")[0],
                                           qname.split(":")[1],
                                           value.lower()+u".xhtml"))

                # 2.1.2 Collate all selector func values into a list of dicts:
                # [{'label':'A','outfile':'toc/dct/title/a.xhtml',...},
                #   'label':'B:,'outfile':'toc/dct/title/b.xhtml',...}
                criterion['pages'].append({'label':value,
                                           # GENERALIZE: make localizable
                                           # (toc_page(predicate,value))
                                           'title':'Documents starting with "%s"' % value, 
                                           'tmpfile':tmpfile,
                                           'outfile':tmpfile.replace(".xhtml",".html")})
            selector_values = {}

        # 4: Now that we've created neccessary base data for criterion,
        #    iterate through it again

        # GENERALIZE: from this point, criteria is fully loaded and
        # not neccessarily structured around RDF predicates. Sources
        # with more specialized toc requirements (such as having each
        # possible dct:creator as a primary criterion, and years in
        # dct:issued as a secondary) can construct the criteria
        # structure themselves. Therefore, all code above should be a
        # call to toc_criteria() or maybe toc_navigation()
        for criterion in criteria:
            selector = criterion['selector']
            binding = criterion['binding']
            selector_values = [x['label'] for x in criterion['pages']]
            # 4.1 For each selector value (reuse list from 2.1):
            for page in criterion['pages']:
                label = page['label']
                title = page['title']
                content = []
                # Find documents that match this particular selector value
                for row in data:
                    if selector(row[binding]) == label:
                        # 4.1.2 Prepare a list of dicts called content, like:
                        #   [{'uri':'http://example.org/res/basefile',
                        #     'title':'Basefile title'}]
                        content.append({'uri':row['uri'],
                                        'label':row[binding]})
                # 4.1.4 Prepare a non-browser ready XHTML page using
                #       genshi/generic-toc.xhtml and navigation (3), title
                #       (4.1.1) and content (4.1.2)

                # GENERALIZE: Allow for other genshi templates
                # implementing eg table, column or tag-cloud based
                # layouts
                self.log.debug("Rendering XHTML to %s" % page['tmpfile'])
                self.render_xhtml("genshi/generic-toc.xhtml",
                                  {'navigation':criteria,
                                   'title':title,
                                   'content':content,
                                   'lang':self.lang},
                                  page['tmpfile'],
                                  self.get_globals())
                # 4.1.5 Prepare a browser-ready HTML page using generic.xsl
                self.log.debug("Rendering HTML to %s" % page['tmpfile'])
                Util.transform('xsl/generic.xsl',page['tmpfile'],page['outfile'], validate=False)
                self.log.info("Created %s" % page['outfile'])

        # 5. as a final step, make an index.html by copying the very first page
        mainindex = os.path.sep.join((self.base_dir,
                                      self.module_dir,
                                      u'toc',
                                      u'index.html'))
        Util.copy_if_different(criteria[0]['pages'][0]['outfile'], mainindex)
                               


    def news(self):
        """Creates a set of pages where each page contains a list of
        new/updated documents. Each page gets created in HTML and Atom
        formats. To control the set of pages, see news_selections."""
        for selection in self.news_selections():
            result = self.news_selection(selection,some_cutoff_date)
            tmpfile = mktemp()
            self.render_xhtml('genshi/news.xhtml',None,tmpfile,{title:selection,
                                                                entries:result})
            Util.transform('xsl/news.xsl',tmpfile,outfile)

            self.render_atom('genshi/news.atom')


    def news_selections(self):
        """Returns a list of news page titles. Each one will be used
        as an argument to news_selection."""
        return ("Nya och ändrade dokument")


    def news_selection(self, selection_name, cutoff_date):
        """Returns a list of news entries for a particular news page."""
        if selection_name == "Nya och ändrade dokument":
            # FIXME: This should either be a list of RDF graphs or a
            # list of Atom-Entry objects
            return ({'title': 'Lag (2009:123) om blahonga',
                     'date': '2009-11-27', # published or updated
                     'uri':'urn:lex:sv:sfs:2009:123',
                     'body':'<p>A typical text with some <b>HTML</b> and <a href="urn:lex:sfs:2009:123">canonical linkz</a></p>',
                     'readmore':'Författningstext'})
    

    def frontpage_content(self, primary=False):
        """If the module wants to provide any particular content on
        the frontpage, it can do so by returning a XHTML fragment (in
        text form) here. If primary is true, the caller wants the
        module to take primary responsibility for the frontpage
        content. If primary is false, the caller only expects a
        smaller amount of content (like a smaller presentation of the
        repository and the document it contains)."""
        return "<div><h2>Module %s</h2><p>Handles %s documents</p></div>" % (module_dir, rdf_type)


    def tabs(self,primary=False):
        """returns a list of tuples, where each tuple will be rendered
        as a tab in the main UI. Normally, a module will only return a
        single tab."""
        return ([rdf_type,module_dir])
