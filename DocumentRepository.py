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

# 3rd party
import BeautifulSoup
from configobj import ConfigObj
from mechanize import Browser, LinkNotFoundError
from genshi.template import TemplateLoader
from rdflib import Literal, Namespace, URIRef, RDF, RDFS
from rdflib.Graph import Graph, ConjunctiveGraph
from rdflib.syntax.parsers.ntriples import unquote as ntriple_unquote
from rdflib.syntax import NamespaceManager
import pyRdfa

# mine
import Util
from LegalRef import LegalRef, Link
from DataObjects import UnicodeStructure, CompoundStructure, \
     MapStructure, IntStructure, DateStructure, PredicateType, \
     UnicodeSubject, Stycke, Sektion, \
     serialize
from SesameStore import SesameStore

__version__ = (1,6)
__author__  = u"Staffan Malmgren <staffan@tomtebo.org>"

# Magicality to make sure printing of unicode objects work no matter
# what platform we're running on
# 
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
        
# print "setting sys.stdout to a '%s' writer" % defaultencoding
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
    going, you don't need to override anything other than the
    L{download_everything} function.

    To get more control over parsing and HTML generation, you override
    additional methods. There are eight main entry points into the
    module, with the following principal call chains:

    download_new
        download_everything
            download_single
                downloaded_path
                download_if_needed
    parse
        parsed_path
        soup_from_basefile
        parse_from_soup
        render_xhtml
            extract_rdfa -> .rdf
        
    relate

    generate
        generated_file
        prep_annotation_file

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
                parts = key[2:].split("-")
                if len(parts) == 1:
                    options[parts[0]] = value
                elif len(parts) == 2:
                    options[parts[0]][parts[1]] = value
                elif len(parts) == 3:
                    options[parts[0]][parts[1]][parts[2]] = value
            else:
                args.append(arg)

        for arg in extra:
            args.append(arg)
            
        (configfile,config,moduleconfig) = cls.initialize_config(options)
        #from pprint import pprint
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
        # If we have a particular log level for this method, use that,
        # otherwise use the global log level. If that isn't defined
        # either, use the INFO loglevel.
        if 'log' in self.moduleconfig:
            loglevel = self.moduleconfig['log']
        else:
            loglevel = self.config.get('log','INFO')
        self.log = self.setup_logger(self.module_dir,loglevel)

        self.base_dir = self.config['datadir']

        self.browser = Browser()
        self.browser.addheaders = [('User-agent', 'lagen.nu-bot (staffan@lagen.nu)')]

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

    def download_everything(self,cache=False):
        log.error("You need to implement download_everything in your subclass")


    def download_new(self):
        self.download_everything(cache=True)


    def download_single(self,basefile,cache=False):
        url = self.document_url % basefile
        filename = self.downloaded_path(basefile)
        if not cache or not os.path.exists(filename):
            if self.download_if_needed(url,filename):
                # the downloaded file was updated (or created) --
                # let's make a note of this in the RDF graph!
                uri = self.canonical_uri(basefile)
                self.store_triple(URIRef(uri), self.ns['dct']['modified'], Literal(datetime.now()))
            else:
                self.log.info("Don't need to store info about %s" % basefile)


    def download_if_needed(self,url,filename):
        # FIXME: Check the timestamp of filename (if it exists), and
        # do a if-modified-since request.
        tmpfile = mktemp()
        #self.log.debug("Retrieving %s to %s" % (url,filename))
        self.browser.retrieve(url,tmpfile)
        return Util.replace_if_different(tmpfile,filename)


    def downloaded_path(self,basefile):
        return os.path.sep.join((self.base_dir, self.module_dir, u'downloaded', '%s.html' % basefile))


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
        indata is in a HTML format parseable by BeautifulSoup)."""
        try:
            start = time()
            infile = self.downloaded_path(basefile)
            outfile = self.parsed_path(basefile)
            force = ('parse_force' in self.moduleconfig and
                     self.moduleconfig['parse_force'] == 'True')
            if not force and Util.outfile_is_newer([infile],outfile):
                self.log.debug(u"%s: Överhoppad", basefile)
                return
            self.log.debug(u"%s: Starting", basefile)

            # the actual function code
            soup = self.soup_from_basefile(basefile,self.source_encoding)
            doc = self.parse_from_soup(soup,basefile)
            self.render_xhtml(self.genshi_tempate, doc,
                              self.parsed_path(basefile), self.get_globals())

            # Check to see that all metadata contained in doc.meta is present in the serialized file
            distilled_graph = self.extract_rdfa(outfile)
            distilled_file = self.distilled_path(basefile)
            Util.ensureDir(distilled_file)
            distilled_graph.serialize(distilled_file,format="rdf/xml", encoding="utf-8")
            self.log.debug(u'%s: %s triples extracted', basefile, len(distilled_graph))
            for triple in distilled_graph:
                doc['meta'].remove(triple)

            if doc['meta']:
                self.log.warning("%d triple(s) from the original metadata was not found in the serialized XHTML file (possibly due to incorrect language tags or typed literals)" % len(doc['meta']))
                print unicode(doc['meta'].serialize(format="nt", encoding="utf-8"), "utf-8")

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
        """Returns a dict with the keys meta, body, uri and lang"""
        return {'doc':{},
                'meta':{},
                'uri':self.canonical_uri()}
    
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
        return os.path.sep.join((self.base_dir, self.module_dir, u'parsed', '%s.xhtml' % basefile))

    def distilled_path(self,basefile):
        return os.path.sep.join((self.base_dir, self.module_dir, u'distilled', '%s.rdf' % basefile))

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
        self.log.debug("About to add %s to triple store" % self.distilled_path(basefile))
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
            force = ('generate_force' in self.moduleconfig and
                    self.moduleconfig['generate_force'] == 'True')
            if not force and Util.outfile_is_newer([infile],outfile):
                self.log.debug(u"%s: Överhoppad", basefile)
                return
            self.log.debug(u"%s: Starting", basefile)

            # The actual function code
            annotation_file = self.prep_annotation_file(basefile)
            if annotation_file:
                params = {'annotationfile':'../data/sfs/intermediate/%s.ann.xml' % basefile}
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


    def generated_path(self,basefile):
        return os.path.sep.join((self.base_dir, self.module_dir, u'generated', '%s.html' % basefile))

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
        keyword and so on.

        Normally you don't have to overide toc to get better control
        over TOC page generation -- override toc_navigation and
        toc_page instead."""
        nav = self.toc_navigation()
        used_nav = []
        for section in nav:
            used_criteria = []
            criteria_type = section[0]
            criteria = section[1:]
            for criterium in criteria:
                lines = self.toc_style(criteria_type, criterium)
                title = self.toc_title(criteria_type,criterium)
                if lines != False:
                    used_critera.append([criteria,lines,title])
            if used_criteria:
                used_nav.append(used_criteria)


        # OK, used_nav now contains good stuff. Now to instansiate it!
        for section in used_criteria:
            for criterium in section:
                # Step 1 is to serialize our stuff into the simplest
                # XHTML that could possibly work (one section that
                # contains the entire 2-level navigation structure, one
                # that contains all documents for a particular
                # type and criteria
                tmpfile = mktemp()
                page = toc_page(section, criterium)
                self.render_xhtml('genshi/toc.xhtml',None,tmpfile,{nav:used_nav,
                                                                   page:page})

                # Step 2 is to create a browser-ready HTML file from
                # that XHTML.
                outfile = "%s/generated/index/%s.html" % self.module_dir, criterium
                Util.transform('xsl/toc.xsl',tmpfile, outfile)

        return "AWESOME!"


    # The default implementation will find the title of each resource
    # that has the relevant rdf:type (self.rdf_type)
    #
    # You might want to do a SPARQL query to find out possible values
    # for criteria, but it's probably easier if you enumerate all of
    # them, and let toc_page return False when there are no hits.
    def toc_navigation(self):
        """Returns a list of lists, where the first element in each list is
        the name or description of a certain selection criterium, and the
        remaining elements are instances of that criterium, e.g.
        (('By title', 'A','B','C'...)"""
        return (('Efter titel','A','B','C','D','E','F','G','H','I'),
                ('Efter år',2009,2008,2007,2006))


    # this might be called as .tocpage('Efter titel', 'A'), or
    # .tocpage('Högsta domstolen', '2009')
    #
    # You probably want to do a SPARQL query, then filter/massage the
    # results somewhat as you create your list of dicts.
    def toc_page(self, criterium_type, criterium):
        """Returns a list of dict, where each dict represents one
        document. The two required fields are 'uri', which is the
        (relative) uri of the document, and 'title' is the display
        title of the document (the text of which will be linked). You
        can also provide the optional 'leader' and 'trailer' fields,
        which contains text that will be presented before and after
        the linked title, respectively.

        If you return a empty list, the criterium appears in the
        navigation list. If you return False, it's removed. That way,
        you can easily make your tocnavigation return every possible
        value (e.g. all years from 2009 to 1600), and still have a
        compact navigation list as unused criteria gets removed."""

        return ({'uri':'/publ/sfs/1995:1331',
                 'title':'Oskäliga avtalsvillkor',
                 'leader':'Lag (1995:1331) om '})


    # is called just like tocpage, but only returns a string
    def toc_title(self, section, idx):
        return "Dokument som börjar på %s" % idx

    # called with the lines from tocpage to provide a HTML blob. Is
    # that really a good idea?
    def toc_style(self,lines):
        """A formatting function for displaying the list of documents
        on an individual page. The default implementation styles them
        as a simple unordered list (toc_style_list), but you can
        choose from other formatters (toc_style_table,
        toc_style_multicol) or implement your own."""
        return self.tocstyle_list(lines)


    def toc_style_list(self,lines):
        """Styles the list of documents as a simple unordered HTML list."""
        pass


    def toc_style_table(self,lines):
        """Styles the list of documents as a table, one row per
        element, and a column for eacch field."""
        pass


    def toc_style_multicol(self,lines,columns):
        """Styles the list of documents as a series of columns
        (implemented as a HTML table)."""
        pass


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
            return ({'title': 'Lag (2009:123) om blahonga',
                     'date': '2009-11-27',
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
