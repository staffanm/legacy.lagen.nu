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

# 3rd party
import BeautifulSoup
from configobj import ConfigObj
from mechanize import Browser, LinkNotFoundError
from genshi.template import TemplateLoader
from rdflib import Literal, Namespace, URIRef, RDF, RDFS
from rdflib.Graph import Graph, ConjunctiveGraph
from rdflib.syntax.parsers.ntriples import unquote as ntriple_unquote
import pyRdfa

# mine
import Util
from LegalRef import LegalRef, Link
from DataObjects import UnicodeStructure, CompoundStructure, \
     MapStructure, IntStructure, DateStructure, PredicateType, \
     UnicodeSubject, Stycke, Sektion, \
     serialize

__version__ = (1,6)
__author__  = u"Staffan Malmgren <staffan@tomtebo.org>"

# Magicality to make sure printing of unicode objects work no matter
# what platform we're running on
# 
# if sys.platform == 'win32':
#     if sys.stdout.encoding:
#         defaultencoding = sys.stdout.encoding
#     else:
#         print "sys.stdout.encoding not set"
#         defaultencoding = 'cp850'
# else:
#     if sys.stdout.encoding:
#         defaultencoding = sys.stdout.encoding
#         if defaultencoding == 'ANSI_X3.4-1968': # really?!
#             defaultencoding = 'iso-8859-1'
#     else:
#         import locale
#         locale.setlocale(locale.LC_ALL,'')
#         defaultencoding = locale.getpreferredencoding()
#         
# print "setting sys.stdout to a '%s' writer" % defaultencoding
# sys.stdout = codecs.getwriter(defaultencoding)(sys.__stdout__, 'replace')
# sys.stderr = codecs.getwriter(defaultencoding)(sys.__stderr__, 'replace')

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
    additional methods.
    """
    
    
    module_dir = "base"
    """The directory where this module will store downloaded, parsed
    and generated files. You need to override thi.s"""

    genshi_tempate = "etc/generic.template.xht2"
    """The U{Genshi<http://genshi.edgewall.org/>} template used to
    transform the parsed object structure into a standard XML file. If
    your data is complex, you might want to override this (and write
    your own Genshi template). If you prefer other ways of
    transforming your data into a serialized XML file, you might want
    to override L{parse] altogether."""
    
    xslt_template = "xsl/generic.xsl"
    """A template used to transform the XML file into browser-ready
    HTML. If your document type is complex, you might want to override
    this (and write your own XSLT transform). You should include
    base.xslt in that template, though."""
    
    # this is a replacement for DispatchMixin.dispatch with built-in
    # support for running the *_all methods (parse_all and
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
                (key,value) = arg.split("=",1)
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

        if args[0].endswith("_all"):
            cls.run_all(args[0],argv,config)
        else:
            c = cls(options)
            func = getattr(c,args[0])
            return func(*args[1:])

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
        global_init_args = ("ExampleRepo",cls.__name__, argv)
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

        # FIXME: This should use the logging infrastructure, but
        # _setup_logger is a instancemethod
        ret = cls.collect_results_for(func_name_all, results)
        print results
        print u'%s: OK (%.3f sec)' % (func_name_all,time()-start)
        
    @classmethod
    def get_iterable_for(cls,funcname,base_dir):
        if funcname == "parse_all":
            directory = os.path.sep.join((base_dir, cls.module_dir, u"downloaded"))
            suffix = ".html"
        elif funcname in ("generate_all", "relate_all"):
            directory = os.path.sep.join((base_dir, cls.module_dir, u"parsed"))
            suffix = ".xht2"

        return [cls.basefile_from_path(x) for x in Util.listDirs(directory,suffix)]

    @classmethod
    def collect_results_for(cls,funcname,results):
        if funcname == "relate_all":
            # results will be an array of NT files. Combine them into
            # one big NT file, submit it to sesame, and store it as a
            # NT file. Things to find out: the sesame server location
            # the context URI the name of the NT file
            for f in results:
                pass
        else:
            pass # nothin' to do

    @classmethod
    def initialize_config(cls,options):
        configfile = ConfigObj(os.path.dirname(__file__)+"/ferenda.conf")
        # Normally, you should read from self.config rather than
        # self.configfile as this will make sure command line
        # arguments take precedence over config file parameters. The
        # exception is if you wish to save some sort of state
        # (eg. "last-processed-id-number") in the config file.
        config = DocumentRepository.merge_dict_recursive(dict(configfile), options)
        moduleconfig = config[cls.module_dir]
        return (configfile,config,moduleconfig)
    
    @classmethod
    def basefile_from_path(cls,path):
        seg = os.path.splitext(path)[0].split(os.sep)
        return "/".join(seg[seg.index(cls.module_dir)+2:])

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
        if 'log' in self.moduleconfig:
            loglevel = self.moduleconfig['log']
        else:
            loglevel = self.config.get('log','INFO')
        self.log = self.setup_logger(self.module_dir,loglevel)

        self.base_dir = self.config['datadir']

        self.browser = Browser()
        self.browser.addheaders = [('User-agent', 'lagen.nu-bot (staffan@lagen.nu)')]

    def download_everything(self,cache=False):
        log.error("You need to implement download_everything in your subclass")

    def download_new(self):
        self.download_everything(cache=True)

    def download_single(self,basefile,cache=False):
        url = self.document_url % basefile
        filename = self.downloaded_path(basefile)
        if not cache or not os.path.exists(filename):
            self.download_if_needed(url,filename)

    def download_if_needed(self,url,filename):
        # FIXME: Check the timestamp of filename (if it exists), and
        # do a if-modified-since request.
        tmpfile = mktemp()
        self.log.info("Retrieving %s to %s" % (url,filename))
        self.browser.retrieve(url,tmpfile)
        Util.replace_if_different(tmpfile,filename)

    def downloaded_path(self,basefile):
        return os.path.sep.join((self.base_dir, self.module_dir, u'downloaded', '%s.html' % basefile))

    def parsed_path(self,basefile):
        return os.path.sep.join((self.base_dir, self.module_dir, u'parsed', '%s.xht2' % basefile))

    def generated_path(self,basefile):
        return os.path.sep.join((self.base_dir, self.module_dir, u'generated', '%s.html' % basefile))

 
    def getlogger(self,name):
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
            h.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
            l.addHandler(h)
        l.setLevel(loglevel)
        return l

    def soup_from_basefile(self,basefile,encoding='iso-8859-1'):
        filename = self.downloaded_path(basefile)
        return BeautifulSoup.BeautifulSoup(
            codecs.open(filename,encoding=encoding,errors='replace').read(),
            convertEntities='html')

    def render_xhtml(self,template,doc,outfile,globals):
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

    # The boilerplate code for handling exceptions and logging time
    # duration might be extracted to decorator functions (generate
    # uses the same boilerplate code, as might other functions). Maybe
    # even the parce_force handling?
    def parse(self,basefile):
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
            soup = self.soup_from_basefile(basefile)
            doc = self.parse_from_soup(soup)
            self.render_xhtml(self.genshi_tempate, doc,
                              self.parsed_path(basefile), globals())

            self.log.info(u'%s: OK (%.3f sec)', basefile,time()-start)
        except KeyboardInterrupt:
            raise
        except:
            self.log.exception("parse of %s failed" % basefile)

    
    def prep_annotation_file(self, basefile):
        return None
        
    def generate(self,basefile):
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
            
    def relate(self,basefile):
        infile = self.parsed_path(basefile)
        graph = self.extract_rdfa(infile)
        outfile = mktemp()
        fp = open(outfile,"w")
        fp.write(graph.serialize(format="nt"))
        fp.close()
        print "returning %s for %s" % (outfile,basefile)
        return outfile

    def extract_rdfa(self,filename):
        dom  = xml.dom.minidom.parse(filename)
        o = pyRdfa.Options()
        o.warning_graph = None
        g = pyRdfa.parseRDFa(dom, "http://example.org/", options=o)
        # clean up whitespace for Literals
        for tup in g:
            (o,p,s) = tup
            if isinstance(s,Literal):
                g.remove(tup)
                l = Literal(u' '.join(s.split()), lang=s.language)
                g.add((o,p,l))
        return g


    def toc(self):
        # Generalized algorithm for creating TOC pages
        #
        # Step 1: find out what criteria(s) we should create pages from, ex:
        #  - By Title (dct:title, rdfs:label or a similar pred)
        #  - By Year (dct:published or some other date pred)
        #  - By Court (rinfo:rattsfallspublikation)
        #  - By Area (rinfoex:rattsomrade) - might be around 40 areas
        #
        # return a list of tuples (displaytitle, predicate, selector_function)
        # example ("Efter titel", dct:title, first_letter)
        #  
        # Step 2: For each criteria:
        #  - find out pages we should create, eg ("a","b","c",...), (2009,2008,2007,...)
        #  - by doing some sort of SPARQL query
        #  - return a list of tuples (pagename, pagetitle) example:
        #      (("a", "Lagar som börjar på 'A'"))
        #
        # Step 3: From the data collected in step 1 and 2, create a
        # data struct that can generate the TOC page index to the left
        # (together with toc.template.xht2)
        #
        # Step 4: For each page (returned in step 2):
        #  - create the page
        
        # final: Create a index.html (or copy some existing page to it
        pass
        

    # this is crap old code. we want to replace it with crap shiny new code!
    def index(self):
        rdffile = Util.relpath("%s/%s/parsed/rdf.nt"%(self.baseDir,self.moduleDir))
        if not os.path.exists(rdffile):
            log.warning("Could not find RDF dump %s" % rdffile)
            return
        log.info("Start RDF loading from %s" % rdffile)
        # Ladda över alla triples i två stora dicts (nycklade på
        # predikat + objekt respektive subjekt + predikat -- det
        # verkar vara de två strukturerna vi behöver för att skapa
        # alla filer vi behöver)
        by_pred_obj = defaultdict(lambda:defaultdict(list))
        by_subj_pred = defaultdict(dict)
        start = time()

        use_rdflib = False # tar för mycket tid+processor
        if use_rdflib:
            g = Graph()
            g.load(rdffile, format="nt")

            log.info("RDF loaded (%.3f sec)", time()-start)
            for (subj,pred,obj) in g:
                # most of the triples are dct:references, and these
                # are not used for tocpage generation - filter these
                # out to cut down on memory usage
                subj = unicode(subj)
                pred = unicode(pred)
                obj  = unicode(obj)
                if pred != self.DCT['references']:
                    by_pred_obj[pred][obj].append(subj)
                    by_subj_pred[subj][pred] = obj
        else:
            fp = open(rdffile)
            count = 0
            for qline in fp:
                line = ntriple_unquote(qline)
                count += 1
                if count % 10000 == 0:
                    sys.stdout.write(".")
                m = self.re_ntriple.match(line)
                if m:
                    subj = m.group(1)
                    pred = m.group(2)
                    objUri = m.group(4)
                    objLiteral = m.group(5)
                    # most of the triples are dct:references, and these
                    # are not used for tocpage generation - filter these
                    # out to cut down on memory usage
                    if pred != 'http://purl.org/dc/terms/references':
                        if objLiteral:
                            by_pred_obj[pred][objLiteral].append(subj)
                            by_subj_pred[subj][pred] = objLiteral
                        elif objUri:
                            by_pred_obj[pred][objUri].append(subj)
                            by_subj_pred[subj][pred] = objUri
                        else:
                            pass
                else:
                    log.warning("Couldn't parse line %s" % line)
        sys.stdout.write("\n")
    
        log.info("RDF structured (%.3f sec)", time()-start)
        self.build_tocpages(by_pred_obj, by_subj_pred)

    def build_tocpages(self,by_pred_obj, by_subj_pred):
        displaypredicates = {'http://purl.org/dc/terms/title':
                             u'titel',
                             'http://purl.org/dc/terms/identifier':
                             u'identifierare',
                             'http://www.w3.org/2000/01/rdf-schema#label':
                             u'beteckning'}
        
        documents = defaultdict(lambda:defaultdict(list))
        pagetitles = {} # used for title on a specific page
        pagelabels = {} # used for link label in the navigation 
        for predicate in by_pred_obj.keys():
            if predicate in displaypredicates.keys():
                # shorten
                # 'http://purl.org/dc/terms/title' to
                # 'dct-title' etc for usage in filenames
                pred_id = predicate
                for (k,v) in Util.ns.items():
                    pred_id = pred_id.replace(v,k+"-")
                pred_label = "Ordnade efter %s" % displaypredicates[predicate]

                log.info("creating toc pages ordered by %s" % pred_id)
                # generate a list of all lowercase letters using the unicode db
                letters = [unichr(i) for i in range(255) if unicodedata.category(unichr(i)) == 'Ll']
                for letter in letters:
                    pageid = "%s-%s" % (pred_id, letter)

                    pagetitles[pageid] = u"Dokument vars %s börjar på '%s'" % (displaypredicates[predicate], letter)
                    pagelabels[pageid] = letter.upper()
                    for obj in by_pred_obj[predicate]:
                        if obj.lower().startswith(letter):
                            for subject in by_pred_obj[predicate][obj]:
                                # normally, the title of a document is
                                # unique and thus there will only be a
                                # single subject with this particular
                                # object, but in some special cases
                                # different documents can have the
                                # same title
                                documents[pred_label][pageid].append({'uri':subject,
                                                                      'sortkey':obj,
                                                                      'title':obj})

        for category in documents.keys():
            for pageid in documents[category].keys():
                outfile = Util.relpath("%s/%s/generated/toc/%s.html" % (self.baseDir, self.moduleDir, pageid))
                title = pagetitles[pageid]
                self.render_tocpage(outfile,title,documents,pagelabels,category,pageid)
                if pageid.endswith("-a"):
                    outfile = Util.relpath("%s/%s/generated/toc/index.html" % (self.baseDir, self.moduleDir))
                    self.render_tocpage(outfile,title,documents,pagelabels,category,pageid)
                    

    def render_tocpage(self,outfile,title,documents,pagelabels,category,page,keyword=None,compactlisting=False, docsorter=cmp):
        # only look in cwd and this file's directory
        loader = TemplateLoader(['.' , os.path.dirname(__file__)], 
                                variable_lookup='lenient') 
        tmpl = loader.load("etc/tocpage.template.xht2")

        stream = tmpl.generate(title=title,
                               documents=documents,
                               pagelabels=pagelabels,
                               currentcategory=category,
                               currentpage=page,
                               currentkeyword=keyword,
                               compactlisting=compactlisting,
                               docsorter=docsorter)

        tmpfilename = outfile.replace(".html",".xht2")
        Util.ensureDir(tmpfilename)
        fp = open(tmpfilename,"w")
        fp.write(stream.render())
        fp.close()
        Util.ensureDir(outfile)
        Util.transform("xsl/static.xsl", tmpfilename, outfile, validate=False)
        log.info("rendered %s" % outfile)
        
    def news(self):
        """Creates one or more pages containing updated and new documents for the datasource"""
        startdate = datetime.datetime.now() - datetime.timedelta(30)
        logfilename = "%s/%s/downloaded/downloaded.log" % (self.baseDir, self.moduleDir)
        if not os.path.exists(logfilename):
            log.warning("Could not find download log %s" % logfilename)
            return 
        logfp = codecs.open(logfilename, encoding = "utf-8")
        entries = []
        for line in logfp:
            (timestr, message) = line.strip().split(": ", 1)
            timestamp = datetime.datetime.strptime(timestr, "%Y-%m-%d %H:%M:%S")
            if timestamp > startdate:
                entries.append([timestamp,message])
        entries.reverse()
        self.build_newspages(entries)

    def build_newspages(self,messages):
        entries = []
        for (timestamp,message) in messages:
            entry = {'title':message,
                     'timestamp':timestamp}
            entries.append(entry)
        htmlfile = "%s/%s/generated/news/index.html" % (self.baseDir, self.moduleDir)
        atomfile = "%s/%s/generated/news/index.atom" % (self.baseDir, self.moduleDir)
        self.render_newspage(htmlfile, atomfile, u'Nyheter', 'Nyheter de senaste 30 dagarna', entries)

    def render_newspage(self,htmlfile,atomfile,title,subtitle,entries):
        # only look in cwd and this file's directory
        loader = TemplateLoader(['.' , os.path.dirname(__file__)], 
                                variable_lookup='lenient') 
        tmpl = loader.load("etc/newspage.template.xht2")
        stream = tmpl.generate(title=title,
                               entries=entries)
        # tmpfilename = mktemp()
        tmpfilename = htmlfile.replace(".html",".xht2")
        assert(tmpfilename != htmlfile)
        Util.ensureDir(tmpfilename)
        fp = open(tmpfilename,"w")
        fp.write(stream.render())
        fp.close()
        Util.ensureDir(htmlfile)
        Util.transform("xsl/static.xsl", tmpfilename, htmlfile, validate=False)
        
        tmpl = loader.load("etc/newspage.template.atom")
        stream = tmpl.generate(title=title,
                               subtitle=subtitle,
                               entries=entries,
                               feeduri=u'https://lagen.nu/%s' % atomfile,
                               pageuri=u'https://lagen.nu/%s' % htmlfile)
                               
        tmpfilename = mktemp()
        fp = open(tmpfilename,"w")
        fp.write(stream.render())
        fp.close()
        Util.ensureDir(atomfile)
        Util.replace_if_different(tmpfilename, atomfile)

        log.info("rendered %s (%s)" % (htmlfile, atomfile))

