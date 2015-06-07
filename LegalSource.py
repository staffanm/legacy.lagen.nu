#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Base classes for Downloaders and Parsers. Also utility classes (should be moved?)"""
from collections import defaultdict
from tempfile import mktemp
from time import time,sleep
import datetime
import codecs
import difflib
import filecmp
import logging
import os
import re
import sys
import traceback
import types
import unicodedata
# 2.5
import xml.etree.cElementTree as ET
import xml.dom.minidom
# 2.6
try:
    import multiprocessing
except:
    pass
    #print "Multiprocessing module not available, running single instance"

# 3rd party modules
import BeautifulSoup
from configobj import ConfigObj
from mechanize import Browser, LinkNotFoundError
from genshi.template import TemplateLoader
from rdflib import Literal, Namespace, URIRef, RDF, RDFS
from rdflib import plugin
from rdflib.store import Store

# rdflib 2.4 v 3.0
try:
    from rdflib.Graph import Graph, ConjunctiveGraph
    from rdflib.syntax.parsers.ntriples import unquote as ntriple_unquote
except ImportError:
    from rdflib import Graph, ConjunctiveGraph
    from rdflib.plugins.parsers.ntriples import unquote as ntriple_unquote
    

try:
    import pyRdfa
except ImportError:
    pass

# my own code
import Util
from SesameStore import SesameStore

if not os.path.sep in __file__:
    __scriptdir__ = os.getcwd()
else:
    __scriptdir__ = os.path.dirname(__file__)

# Do required codec/locale magic right away, since this is included by
# all runnable scripts
# Magicality seems to harm more than it helps nowadays

if sys.version_info < (2,6,0):
    if sys.platform == 'win32':
        if sys.stdout.encoding:
            defaultencoding = sys.stdout.encoding
        else:
            print "sys.stdout.encoding not set"
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





log = logging.getLogger(u'ls')


class ParseError(Exception):
    pass

class IdNotFound(Exception):
    """thrown whenever we try to lookup a URI/displayid/basefile but can't find it"""
    pass

# class CustomNamespaceManager(NamespaceManager):
#     def __init__(self, graph):
#         super(CustomNamespaceManager, self).__init__(graph)
# 
#     def compute_qname(self, uri):
#         if not uri in self.__cache:
#             namespace, name = split_uri(uri)
#             namespace = URIRef(namespace)
#             prefix = self.store.prefix(namespace)
#             if prefix is None:
#                 raise Exception("Prefix for %s not bound" % namespace)
#             self.__cache[uri] = (prefix, namespace, name)
#         return self.__cache[uri]
    
    
class Downloader(object):
    """Abstract base class for downloading legal source documents
    (statues, cases, etc).

    Apart from naming the resulting files, subclasses should do as
    little modification to the data as possible."""

    def __init__(self,config):
        self.config = config
        self.browser = Browser()
        self.browser.addheaders = [('User-agent', 'lagen.nu-bot (staffan@lagen.nu)')]
        # FIXME: Set user-agent header somehow. Also, if we could make
        # it support Robot.ThrottlingProcessor it would be cool

        moduledir = self._get_module_dir()
        self.download_dir = __scriptdir__ + "/" + config['datadir'] + "/%s/downloaded" % moduledir
        self.download_log = logging.getLogger('%s/download' % moduledir)
        logfile = self.download_dir+"/downloaded.log"
        Util.ensureDir(logfile)
        handler = logging.FileHandler(logfile)
        handler.setFormatter(logging.Formatter("%(asctime)s: %(message)s","%Y-%m-%d %H:%M:%S"))
        self.download_log.addHandler(handler)

 
    def DownloadAll():
        raise NotImplementedError
    
    def DownloadNew():
        raise NotImplementedError


class Parser(object):
    """Abstract base class for a legal source document"""
    re_NormalizeSpace  = re.compile(r'\s+',).sub

    def __init__(self):
        self.authority_rec = self.load_authority_rec(__scriptdir__ + "/etc/authrec.n3")
    
    def Parse(self):
        raise NotImplementedError

    def generate_xhtml(self,meta,body,registry,module,globals):
        """Skapa en XHTML2-representation av ett rättsinformationsdokument"""
        loader = TemplateLoader(['.' , os.path.dirname(__file__)], # only look in cwd and this file's directory
                                variable_lookup='lenient') 
        tmpl = loader.load("etc/%s.template.xht2"%module)
        stream = tmpl.generate(meta=meta, body=body, registry=registry, **globals)
        try:
            res = stream.render()
        except Exception, e:
            log.error(u'%s: Fel vid templaterendring: %r' % (self.id, sys.exc_info()[1]))
            raise
        if 'class="warning"' in res:
            start = res.index('class="warning">')
            end = res.index('</',start+16)
            msg = res[start+16:end]
            if not isinstance(msg, unicode):
                msg = msg.decode("utf-8")
            msg = Util.normalizeSpace(msg)
            log.error(u'%s: templatefel \'%s\'' % (self.id, msg[:80]))
        return res

    def load_authority_rec(self, n3file):
        """Ladda in en RDF-graf som innehåller auktoritetsposter i n3-format"""
        graph = Graph()
        n3file = Util.relpath(n3file)

        #print "loadling %s" % n3file
        graph.load(n3file, format='n3')
        d = {}
        for uri, label in graph.subject_objects(RDFS.label):
            d[unicode(label)] = unicode(uri)
        return d

    def find_authority_rec(self, label):
        """Givet en textsträng som refererar till någon typ av
        organisation, person el. dyl (exv 'Justitiedepartementet
        Gransk', returnerar en URI som är auktoritetspost för denna."""
        keys = []
        for (key, value) in self.authority_rec.items():
            if label.lower().startswith(key.lower()):
                return self.storage_uri_value(value)
            else:
                keys.append(key)

        fuzz = difflib.get_close_matches(label, keys, 1, 0.8)
        if fuzz:
            log.warning(u"%s: Antar att '%s' ska vara '%s'?" % (self.id, label, fuzz[0]))
            return self.find_authority_rec(fuzz[0])
        else:
            log.warning(u"%s: Ingen exakt match för '%s'" % (self.id, label))
            raise KeyError(label)

    def storage_uri_value(self, value):
        return value.replace(" ", '_')

class Manager(object):
    def __init__(self):
        """basedir is the top-level directory in which all file-based data is
        stored and handled. moduledir is a sublevel directory that is unique
        for each LegalSource.Manager subclass."""
        self.moduleDir = self._get_module_dir()
        self.config = ConfigObj(os.path.dirname(__file__)+"/conf.ini")
        self.baseDir = os.path.dirname(__file__)+os.path.sep+self.config['datadir']

    # FIXME: This does not handle escaped double quotes (\")
    # correctly. That *should* be possible to express in a regex,
    # right?
    re_ntriple = re.compile(r'<([^>]+)> <([^>]+)> (<([^>]+)>|"([^"]*)")(@\d{2}|).')
    XHT2NS = '{http://www.w3.org/2002/06/xhtml2/}' 
    DCT = Namespace("http://purl.org/dc/terms/")
    ####################################################################
    # Manager INTERFACE DEFINITION - a subclass must implement these
    ####################################################################
    
    def Download(self,id):
        """Download a specific Legal source document. The id is
        source-dependent and will often be a web service specific id, not the
        most commonly used ID for that legal source document (ie '4674', not
        'NJA 1984 s. 673' or 'SÖ478-84')"""
        raise NotImplementedError

    def DownloadSome(self,listfile):
        f = codecs.open(listfile,encoding="utf-8")
        for line in f:
            self.Download(line.strip())

    def DownloadAll(self):
        """Download all documents for this legal source. This is typically a
        very expensive operation that takes hours."""
        raise NotImplementedError
    
    def DownloadNew(self):
        """Download just new documents for this legal source. This is
        typically very tightly coupled to the web service where the documents
        can be found"""
        raise NotImplementedError

    def Parse(self,basefile):
        """Parse a single legal source document, i.e. convert it from whatever
        downloaded resource(s) we have into a single XML document"""
        raise NotImplementedError
     
    def ParseAll(self):
        """Parse all legal source documents for which we have downloaded
        resource documents on disk"""
        download_dir = os.path.sep.join([self.baseDir,self.moduleDir, u'downloaded'])
        self._do_for_all(download_dir,'.html',self.Parse)

    def ParseSome(self,listfile):
        f = codecs.open(listfile,encoding="utf-8")
        for line in f:
            self.Parse(line.strip())
            

    def IndexAll(self):
        raise NotImplementedError

    def Generate(self,basefile):
        """Generate displayable HTML from a legal source document in XML form"""
        raise NotImplementedError
    
    def GenerateAll(self):
        parsed_dir = os.path.sep.join([self.baseDir, self.moduleDir, u'parsed'])
        self._do_for_all(parsed_dir, '.xht2',self.Generate)
        return
    
    def GenerateSome(self,listfile):
        f = codecs.open(listfile,encoding="utf-8")
        for line in f:
            self.Generate(line.strip())

    ####################################################################
    # GENERIC DIRECTLY-CALLABLE METHODS - a subclass might want to override some of these
    ####################################################################

    def DumpTriples(self, filename, format="turtle"):
        """Given a XML file (any file), extract RDFa embedded triples
        and display them - useful for debugging"""
        g = self._extract_rdfa(filename)
        print unicode(g.serialize(format=format, encoding="utf-8"), "utf-8")

    def RelateAll(self,file=None):
        """Sammanställer all metadata för alla dokument i rättskällan
        och laddar in det i systemets triplestore"""
        xht2_dir = os.path.sep.join([self.baseDir, self.moduleDir, u'parsed'])
        if not os.path.exists(xht2_dir):
            log.warning("Dir %s does not exist" % xht2_dir)
            return

        rdffile = os.path.sep.join([self.baseDir, self.moduleDir, u'parsed', u'rdf.nt']) 

        context = "<urn:x-local:%s>" % self.moduleDir
        files = list(Util.listDirs(xht2_dir, '.xht2'))
        #import pprint
        #pprint.pprint(files)
        if self._outfile_is_newer(files,rdffile):
            log.info("%s is newer than all .xht2 files, no need to extract" % rdffile)
            # 1. download rdfdump to tmpfile
            # 2. if tmpfile == rdffile: continue
            store = SesameStore(self.config['triplestore'], self.config['repository'],context)
            tmpfilename = mktemp()
            with open(tmpfilename, "w") as fp:
                pass
            store.get_serialized_file(tmpfilename,"nt")
            if filecmp.cmp(tmpfilename,rdffile):
                log.info("Store hasn't changed, not reloading it")
            else: 
                log.info("Fast-loading store %s, repo %s, context %s" % (self.config['triplestore'], self.config['repository'],context))
                for key, value in Util.ns.items():
                    store.bind(key, Namespace(value));

                log.info("Clearing context %s" % context)
                store.clear()
                store.add_serialized_file(rdffile)
                # FIXME: We need to regenerate the .deps files in this
                # code branch as well, preferably in a really cheap
                # way. Or make Manager.RelateAll smart about when .deps
                # files are removed.
        else:
            log.info("Connecting to store %s, repo %s, context %s" % (self.config['triplestore'], self.config['repository'],context))
            store = SesameStore(self.config['triplestore'], self.config['repository'],context)
            for key, value in Util.ns.items():
                store.bind(key, Namespace(value));

            log.info("Clearing context %s" % context)
            store.clear()
            c = 0
            triples = 0
            log.info("Relating %d documents" % len(files))
            # FIXME: Consider using do_for_all with this to
            # parallelize things.
            for f in files:
                #if not u'HFD/1458-11' in f:
                #    continue
                c += 1
                x = f.replace("/parsed/", "/intermediate/").replace(".xht2",".rdf")
                if os.path.exists(x) and self._outfile_is_newer([f],x):
                    log.debug("%s: Fast-loading rdf" % f)
                    graph = Graph()
                    try:
                        graph.parse(open(x))
                    except: # when the filename x contains non-ascii chars
                        log.debug("%s: Couldn't parse from source, working around by parsing from string" % f)
                        graph.parse(data=open(x).read()) # new rdflib (3.x?) required
                else:
                    log.debug("%s: extracting rdfa" % f)
                    graph = self._extract_rdfa(f)
                    Util.ensureDir(x)
                    log.debug("%s: serializing rdf/xml" % x)
                    try:
                        graph.serialize(x,format="pretty-xml", encoding="utf-8")
                    except:
                        log.debug("%s: Working around" % f)
                        fp = open(x,"w")
                        fp.write(graph.serialize(None,format="pretty-xml", encoding="utf-8"))
                        fp.close()
                relfile = Util.relpath(f)
                # log.debug("Processing %s " % relfile)
                self._add_deps(relfile,graph)
                
                triples += len(graph)
                start = time()
                store.add_graph(graph)
                store.commit()
                sleep(0.1)
                if time()-start > 2:
                    log.info("openrdf-sesame got slow after %s (%s triples), reloading" % (relfile,len(graph)))
                    cmd = "curl -u %s:%s http://localhost:8080/manager/reload?path=/openrdf-sesame" % (self.config['tomcatuser'], self.config['tomcatpassword'])
                if c % 100 == 0:
                    log.info("Related %d documents (%d triples total)" % (c, triples))

            log.info("Serializing to %s" % rdffile)
            store.get_serialized_file(rdffile,"nt")

            log.info("All documents related: %d documents, %d triples" % (c, triples))
        
    
    def Indexpages(self):
        """Creates index pages for all documents for a particular
        legalsource. A typical set of index pages are one page that
        lists all document who's title start with 'A', one page that
        lists all documents who's title start with 'B', and so on. On
        each such page there is also a meta-index (a list of all index
        pages) placed in the right hand column. 
        
        Subclasses can override _build_indexpages to control exactly
        which index pages are created"""
        # read the RDF dump (NTriples format) created by RelateAll
        rdffile = Util.relpath("%s/%s/parsed/rdf.nt"%(self.baseDir,self.moduleDir))
        mainindex = "%s/%s/generated/index/index.html" % (self.baseDir, self.moduleDir)
        if self._outfile_is_newer([rdffile],mainindex):
            log.info("%s is newer than last RDF dump, not building index pages" % mainindex)
            return
        
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
        preds = self._indexpages_predicates()
        start = time()

        use_rdflib = False # tar för mycket tid+processor
        if use_rdflib:
            g = Graph()
            g.load(rdffile, format="nt")


            log.info("RDF loaded (%.3f sec)", time()-start)
            for (subj,pred,obj) in g:
                # most of the triples are dct:references, and these
                # are not used for indexpage generation - filter these
                # out to cut down on memory usage
                subj = unicode(subj)
                pred = unicode(pred)
                obj  = unicode(obj)
                if str(pred) in preds:
                    by_pred_obj[pred][obj].append(subj)
                    by_subj_pred[subj][pred] = obj
        else:
            fp = open(rdffile)
            count = 0
            mcount = 0
            for qline in fp:
                count += 1
                if not any(pred in qline for pred in preds):
                    continue
                mcount += 1
                line = ntriple_unquote(qline)
                if count % 10000 == 0:
                    sys.stdout.write(".")
                m = self.re_ntriple.match(line)
                if m:
                    subj = m.group(1)
                    pred = m.group(2)
                    objUri = m.group(4)
                    objLiteral = m.group(5)
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
    
        log.info("RDF structured (%s triples, %s kept, %.3f sec)" % (count, mcount, time()-start))
        self._build_indexpages(by_pred_obj, by_subj_pred)

    def News(self):
        """Creates one or more pages containing updated and new documents for the datasource"""
        startdate = datetime.datetime.now() - datetime.timedelta(90)
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
        self._build_newspages(entries)
        
    ################################################################
    # CONVENIENCE FUNCTIONS FOR SUBCLASSES (can be overridden if needed)
    ################################################################

    def _apply_basefile_transform(self,files):
        for f in files:
            basefile = self._file_to_basefile(Util.relpath(f))
            if not basefile:
                continue
            else:
                yield basefile


        
    def _do_for_all(self,dir,suffix,method):
        
        basefiles = self._apply_basefile_transform(Util.listDirs(dir, suffix, reverse=True))
        if 'poolsize' in self.config:
            logger = multiprocessing.log_to_stderr()
            logger.setLevel(logging.INFO)
            logger.info("MP logging init")

            p = multiprocessing.Pool(int(self.config['poolsize']))
            print p.map(method,basefiles,10)
        else:
            for basefile in basefiles:
                try:
                    method(basefile)
                except KeyboardInterrupt:
                    raise
                except:
                    # Handle traceback-loggning ourselves since the
                    # logging module can't handle source code containing
                    # swedish characters (iso-8859-1 encoded).
                    formatted_tb = [x.decode('iso-8859-1') for x in traceback.format_tb(sys.exc_info()[2])]
                    exception = sys.exc_info()[1]
                    msg = exception
                    if not msg:
                        if isinstance(exception,OSError):
                            msg = "[Errno %s] %s: %s" % (exception.errno, exception.strerror, exception.filename)
                        else:
                            msg = "(Message got lost)"
                            
                            
                    log.error(u'%r: %s:\nMyTraceback (most recent call last):\n%s%s [%r]' %
                              (basefile,
                               sys.exc_info()[0].__name__, 
                               u''.join(formatted_tb),
                               sys.exc_info()[0].__name__,
                               msg))

    def _file_to_basefile(self,f):
        """Given a full physical filename, transform it into the
        logical id-like base of that filename, or None if the filename
        shouldn't be processed."""
        # this transforms 'foo/bar/baz/HDO/1-01.doc' to 'HDO/1-01'
        return "/".join(os.path.split(os.path.splitext(os.sep.join(os.path.normpath(f).split(os.sep)[-2:]))[0]))

    def _outfile_is_newer(self,infiles,outfile):
        """check to see if the outfile is newer than all ingoing files
        (which means there's no need to regenerate outfile)"""
        if not os.path.exists(outfile): return False
        outfile_mtime = os.stat(outfile).st_mtime
        #log.debug("Checking!")
        for f in infiles:
            #log.debug("Testing whether %s is newer than %s" % (f, outfile))
            if os.path.exists(f) and os.stat(f).st_mtime > outfile_mtime:
                #log.debug("%s was newer than %s" % (f, outfile))
                return False
        #log.debug("%s is newer than all of %r" % (outfile, infiles))
        return True

    def _htmlFileName(self,basefile):
        """Returns the generated, browser-ready XHTML 1.0 file name for the given basefile"""
        if not isinstance(basefile, unicode):
            raise Exception("WARNING: _htmlFileName called with non-unicode name")
        return u'%s/%s/generated/%s.html' % (self.baseDir, self.moduleDir,basefile)         
 
    def _xmlFileName(self,basefile): 
        """Returns the generated, browser-ready XHTML 1.0 file name for the given basefile"""
        if not isinstance(basefile, unicode):
            raise Exception("WARNING: _xmlFileName called with non-unicode name")
        return u'%s/%s/parsed/%s.xht2' % (self.baseDir, self.moduleDir,basefile)     

    def _depsFileName(self,basefile): 
        return u'%s/%s/intermediate/%s.deps' % (self.baseDir, self.moduleDir,basefile)     

    def _indexpages_predicates(self):
        return [Util.ns['dct']+"title",
                Util.ns['dct']+"identifier",
                Util.ns['rdfs']+"label"]

    def _build_indexpages(self,by_pred_obj, by_subj_pred):
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

                log.info("creating index pages ordered by %s" % pred_id)
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
                outfile = Util.relpath("%s/%s/generated/index/%s.html" % (self.baseDir, self.moduleDir, pageid))
                title = pagetitles[pageid]
                self._render_indexpage(outfile,title,documents,pagelabels,category,pageid)
                if pageid.endswith("-a"):
                    outfile = Util.relpath("%s/%s/generated/index/index.html" % (self.baseDir, self.moduleDir))
                    self._render_indexpage(outfile,title,documents,pagelabels,category,pageid)
                    

    def _render_indexpage(self,outfile,title,documents,pagelabels,category,page,keyword=None,compactlisting=False, docsorter=cmp):
        # only look in cwd and this file's directory
        loader = TemplateLoader(['.' , os.path.dirname(__file__)], 
                                variable_lookup='lenient') 
        tmpl = loader.load("etc/indexpage.template.xht2")
        # stream = tmpl.generate(**locals()) result: "got multiple values for keyword argument 'self'"

        stream = tmpl.generate(title=title,
                               documents=documents,
                               pagelabels=pagelabels,
                               currentcategory=category,
                               currentpage=page,
                               currentkeyword=keyword,
                               compactlisting=compactlisting,
                               docsorter=docsorter)
        #tmpfilename = mktemp()
        tmpfilename = outfile.replace(".html",".xht2")
        Util.ensureDir(tmpfilename)
        fp = codecs.open(tmpfilename,"w", encoding="utf-8")
        fp.write(stream.render())
        fp.close()
        Util.ensureDir(outfile)
        Util.transform("xsl/static.xsl", tmpfilename, outfile, validate=False)
        log.info("rendered %s" % outfile)
        
    def _build_newspages(self,messages):
        entries = []
        for (timestamp,message) in messages:
            entry = {'title':message,
                     'timestamp':timestamp}
            entries.append(entry)
        htmlfile = "%s/%s/generated/news/index.html" % (self.baseDir, self.moduleDir)
        atomfile = "%s/%s/generated/news/index.atom" % (self.baseDir, self.moduleDir)
        self._render_newspage(htmlfile, atomfile, u'Nyheter', 'Nyheter de senaste 30 dagarna', entries)

    def _render_newspage(self,htmlfile,atomfile,title,subtitle,entries):
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
        fp = codecs.open(tmpfilename,"w", encoding="utf-8")
        x = stream.render()
        fp.write(x)
        fp.close()
        Util.ensureDir(htmlfile)
        Util.transform("xsl/static.xsl", tmpfilename, htmlfile, validate=False)
        
        tmpl = loader.load("etc/newspage.template.atom")
        stream = tmpl.generate(title=title,
                               subtitle=subtitle,
                               entries=entries,
                               feeduri=u'https://lagen.nu/%s' % atomfile.replace("data/", ""),
                               pageuri=u'https://lagen.nu/%s' % htmlfile.replace("data/", ""))
                               
        tmpfilename = mktemp()
        fp = codecs.open(tmpfilename,"w", encoding="utf-8")
        fp.write(stream.render())
        fp.close()
        Util.ensureDir(atomfile)
        Util.replace_if_different(tmpfilename, atomfile)

        log.info("rendered %s (%s)" % (htmlfile, atomfile))

    def _extract_rdfa(self, filename):
        g = Graph()
        g.parse(open(filename),format="rdfa",
                rdfa_version="1.0")
        self.__tidy_graph(g)

        return g

    _rf_lookup = {}
    def _add_deps(self, dependency, graph):
        # Step 1: Filter all triples that has a URIRef object
        filenames = {}
        for (o,p,s) in graph:
            if type(s) != URIRef:
                continue
            uri = unicode(s)
            
            # Step 2: Depending on the URI, transform into a
            # dependency file name for that URI (eg
            # "http://rinfo.lagrummet.se/publ/sfs/1973:877#P4" ->
            # "data/sfs/intermediate/1973/877.deps")
            # log.debug("Adding %s as dep for %s" % (dependency,uri))
            filename = None
            if uri.startswith("http://rinfo.lagrummet.se/publ/sfs/"):
                basefile = uri.split("/")[-1].split("#")[0].replace(":","/")
                #log.debug("Basefile: %s, comparison: %s" %
                #          (basefile,"/".join(dependency.split("/")[-2:])[:-5]))
                if "/" not in basefile:
                    # avoid non-resource refs
                    # log.debug("  Skipping non-resource ref %s"%basefile)
                    pass
                elif basefile == "/".join(dependency.split("/")[-2:])[:-5]:
                    # avoid self refs
                    pass
                else:
                    filename = "data/sfs/intermediate/%s.deps" % basefile
            elif uri.startswith("http://rinfo.lagrummet.se/publ/rattsfall/"):
                if not self._rf_lookup:
                    log.debug("Loading uri.map")
                    self._load_rf_lookup("data/dv/generated/uri.map")
                    log.debug("%s items in mapping" % len(self._rf_lookup))

                if uri[41:] in self._rf_lookup:
                    basefile = self._rf_lookup[uri[41:]]
                    filename = "data/dv/intermediate/%s.deps" % basefile
            elif uri.startswith("http://lagen.nu/concept/"):
                basefile = uri[24:].replace("_"," ")
                firstletter = basefile[0]
                filename = "data/keyword/intermediate/%s/%s.deps" % (firstletter,basefile)
            if not filename:
                continue
            if filename in filenames:
                continue

            filenames[filename] = True
            log.debug("Adding %r as dep for %r" % (dependency,filename))
                
            # Step 3: Open file, add dependency if not already present
            present = False
            if os.path.exists(filename):
                for line in codecs.open(filename,encoding="utf-8"):
                    if line.strip() == dependency:
                        present = True
            if not present:
                Util.ensureDir(filename)
                fp = codecs.open(filename,"a",encoding="utf-8")
                fp.write(dependency+"\n")
                fp.close()
            
    def _load_rf_lookup(self,mapfile):
        for line in open(mapfile):
            line = line.strip()
            (baseuri,basefile) = line.split("\t")
            self._rf_lookup[baseuri] = basefile
            
    def _load_deps(self,basefile):
        depsfile = self._depsFileName(basefile)
        deps = []
        if os.path.exists(depsfile):
            for dep in codecs.open(depsfile,encoding="utf-8"):
                deps.append(dep.strip())
        return deps
    
    def _store_select(self,query):
        """Send a SPARQL formatted SELECT query to the Sesame
           store. Returns the result as a list of dicts"""
        # res will be a list of dicts, like
        # [{'uri':    u'http://rinfo.lagrummet.se/dom/rh/2004:24',
        #   'id':     u'RH 2004:24',
        #   'desc':   u'Beskrivining av rättsfallet',
        #   'lagrum': u'http://rinfo.lagrummet.se/publ/sfs/1998:204#P7'},
        #  {'uri': ...}]

        # Note that the difference between uris and string literals
        # are gone, and that string literals aren't language
        # typed. Should we use DataObjects instead?
        store = SesameStore(self.config['triplestore'], self.config['repository'])
        results = store.select(query)
        res = []
        # return res
        tree = ET.fromstring(results)
        for row in tree.findall(".//{http://www.w3.org/2005/sparql-results#}result"):
            d = {}
            for element in row:
                #print element.tag # should be "binding"
                key = element.attrib['name']
                value = element[0].text
                d[key] = value
            res.append(d)
        return res

    def _store_run_query(self, queryfile, **kwargs):
        if not os.path.exists(queryfile):
            queryfile = os.path.dirname(__file__) + os.path.sep + queryfile
        sq = open(queryfile).read() % kwargs
        return self._store_select(sq)
    
    ################################################################
    # PURELY INTERNAL FUNCTIONS
    ################################################################

    def __tidy_graph(self,graph):
        """remove unneccesary whitespace and XMLLiteral typing from
        literals in the graph"""
        for tup in graph:
            (o,p,s) = tup
            if isinstance(s,Literal):
                graph.remove(tup)
                l = Literal(u' '.join(s.split()), lang=s.language, datatype=s.datatype)
                graph.add((o,p,l))

