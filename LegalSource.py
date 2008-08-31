#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Base classes for Downloaders and Parsers. Also utility classes (should be moved?)"""
from collections import defaultdict
from tempfile import mktemp
from time import time
import datetime
import codecs
import difflib
import locale
import logging
import os
import re
import sys
import traceback
import types
import unicodedata
import xml.etree.cElementTree as ET

# 3rd party modules
import BeautifulSoup
from configobj import ConfigObj
from mechanize import Browser, LinkNotFoundError
from genshi.template import TemplateLoader
from rdflib import Literal, Namespace, URIRef, RDF, RDFS
from rdflib import plugin
from rdflib.Graph import Graph, ConjunctiveGraph
from rdflib.store import Store
# from rdflib.syntax import NamespaceManager

# my own code
import Util


# Do required codec/locale magic right away, since this is included by
# all runnable scripts
locale.setlocale(locale.LC_ALL,'') 
if sys.platform == 'win32':
    if sys.stdout.encoding:
        defaultencoding = sys.stdout.encoding
    else:
        defaultencoding = 'cp850'
else:
    if sys.stdout.encoding:
        defaultencoding = sys.stdout.encoding
        if defaultencoding == 'ANSI_X3.4-1968': # really?!
            defaultencoding = 'iso-8859-1'
    else:
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
        # FIXME: Set user-agent header somehow. Also, if we could make
        # it support Robot.ThrottlingProcessor it would be cool

        moduledir = self._get_module_dir()
        self.download_dir = config['datadir'] + "/%s/downloaded" % moduledir
        self.download_log = logging.getLogger('%s/download' % moduledir)
        logfile = self.download_dir+"/downloaded.log"
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
        self.authority_rec = self.load_authority_rec("etc/authrec.n3")
    
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
            msg = Util.normalizeSpace(res[start+16:end].decode('utf-8'))
            log.error(u'%s: templatefel \'%s\'' % (self.id, msg[:80]))
        return res

    def load_authority_rec(self, file):
        """Ladda in en RDF-graf som innehåller auktoritetsposter i n3-format"""
        graph = Graph()
        graph.load(file, format='n3')
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
        self.config = ConfigObj("conf.ini")
        self.baseDir = self.config['datadir']

    re_ntriple = re.compile(r'<([^>]+)> <([^>]+)> (<([^>]+)>|"([^"]*)")(@\d{2}|).')
    XHT2NS = '{http://www.w3.org/2002/06/xhtml2/}' 
    ####################################################################
    # Manager INTERFACE DEFINITION - a subclass must implement these
    ####################################################################
    
    def Download(self,id):
        """Download a specific Legal source document. The id is
        source-dependent and will often be a web service specific id, not the
        most commonly used ID for that legal source document (ie '4674', not
        'NJA 1984 s. 673' or 'SÖ478-84')"""
        raise NotImplementedError

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
        raise NotImplementedError

    def IndexAll(self):
        raise NotImplementedError

    def Generate(self):
        """Generate displayable HTML from a legal source document in XML form"""
        raise NotImplementedError
    
    def GenerateAll(self):
        """Generate HTML for all legal source documents"""
        raise NotImplementedError
    

    ####################################################################
    # GENERIC DIRECTLY-CALLABLE METHODS - a subclass might want to override some of these
    ####################################################################

    def DumpTriples(self, filename, format="turtle"):
        """Given a XML file (any file), extract RDFa embedded triples
        and display them - useful for debugging"""
        g = self.__load_rdfa(filename)
        print unicode(g.serialize(format=format, encoding="utf-8"), "utf-8")

    def RelateAll(self,file=None):
        """Sammanställer all metadata för alla dokument i rättskällan
        och bygger en stor RDF-fil i NTriples-format. """
        files = list(Util.listDirs(os.path.sep.join([self.baseDir, self.moduleDir, u'parsed']), '.xht2'))
        rdffile = os.path.sep.join([self.baseDir, self.moduleDir, u'parsed', u'rdf.nt']) 
        if self._outfile_is_newer(files,rdffile):
            log.info("%s is newer than all .xht2 files, no need to extract" % rdffile)
            return
        
        c = 0
        triples = 0
        f = open(rdffile,'w')
        f.close()
        for f in Util.listDirs(os.path.sep.join([self.baseDir, self.moduleDir, u'parsed']), '.xht2'):
            c += 1
            graph = self.__get_default_graph()
            self.__load_rdfa(f,graph)
            triples += len(graph)
            f = open(os.path.sep.join([self.baseDir, self.moduleDir, u'parsed', u'rdf.nt']),'a')
            f.write(graph.serialize(format="nt"))
            f.close()
            # graph.commit()
            if c % 100 == 0:
                log.info("Related %d documents (%d triples total)" % (c, triples))

        log.info("All documents related: %d documents, %d triples" % (c, triples))
        # f = open(os.path.sep.join([self.baseDir, self.moduleDir, u'parsed', u'rdf.xml']),'w')
        # f.write(graph.serialize(format="pretty-xml"))
        # f.close()
        # print unicode(g.serialize(format="nt", encoding="utf-8"), 'utf-8')
    
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
        rdf_nt ="%s/%s/parsed/rdf.nt"%(self.baseDir,self.moduleDir)
        if not os.path.exists(rdf_nt):
            log.warning("Could not find RDF dump %s" % rdf_nt)
            return
        # Egentligen vill vi öppna .n3-filen som en riktig RDF-graf med rdflib, like so:
        #
        # g = Graph()
        # log.info("Start RDF loading from %s" % rdffile)
        # start = time()
        # g.load(rdffile, format="nt")
        # log.info("RDF loaded (%.3f sec)", time()-start)
        #
        # men eftersom det tar över två minuter att ladda
        # sfs/parsed/rdf.nt är det inte ett alternativ - det får vänta
        # tills all RDF-data är i en sesame-db. Ladda bara in alla
        # triples i två stora dicts (nycklade på predikat + objekt
        # respektive subjekt + predikat -- det verkar vara de två
        # strukturerna vi behöver för att skapa alla filer vi behöver)
        
        by_pred_obj = defaultdict(lambda:defaultdict(list))
        by_subj_pred = defaultdict(dict)
        log.info("Reading triples from %s" % rdf_nt)
        start = time()
        fp = codecs.open(rdf_nt, encoding='utf-8')
        count = 0
        for line in fp:
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
                # are not used for indexpage generation - filter these
                # out to cut down on memory usage
                if pred != 'http://dublincore.org/documents/dcmi-terms/references':
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
        log.info("RDF loaded (%.3f sec)", time()-start)

        self._build_indexpages(by_pred_obj, by_subj_pred)

    def News(self):
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
        self._build_newspages(entries)
        
    ################################################################
    # CONVENIENCE FUNCTIONS FOR SUBCLASSES (can be overridden if needed)
    ################################################################

    def _do_for_all(self,dir,suffix,method):
        for f in Util.listDirs(dir, suffix, reverse=True):
            #print "listdirs: %s" % f
            basefile = self._file_to_basefile(f)
            if not basefile:
                continue
            # regardless of any errors in calling this method, we just
            # want to log it and go on
            try:
                method(basefile)
            except KeyboardInterrupt:
                raise
            except:
                # Handle traceback-loggning ourselves since the
                # logging module can't handle source code containing
                # swedish characters (iso-8859-1 encoded).
                formatted_tb = [x.decode('iso-8859-1') for x in traceback.format_tb(sys.exc_info()[2])]
                if isinstance(sys.exc_info()[1].message, unicode):
                    msg = sys.exc_info()[1].message
                else:
                    msg = unicode(sys.exc_info()[1].message,'iso-8859-1')
                log.error(u'%r: %s:\nMyTraceback (most recent call last):\n%s%s [%s]' %
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
        for f in infiles:
            # print "Testing whether %s is newer than %s" % (f, outfile)
            if os.path.exists(f) and os.stat(f).st_mtime > outfile_mtime:
                # print "%s was newer than %s" % (f, outfile)
                return False
        # print "%s is newer than %r" % (outfile, infiles)
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

    def _build_indexpages(self,by_pred_obj, by_subj_pred):
        displaypredicates = {'http://dublincore.org/documents/dcmi-terms/title':
                             u'titel',
                             'http://dublincore.org/documents/dcmi-terms/identifier':
                             u'identifierare',
                             'http://www.w3.org/2000/01/rdf-schema#label':
                             u'beteckning'}
        
        documents = defaultdict(lambda:defaultdict(list))
        pagetitles = {} # used for title on a specific page
        pagelabels = {} # used for link label in the navigation 
        for predicate in by_pred_obj.keys():
            if predicate in displaypredicates.keys():
                # shorten
                # 'http://dublincore.org/documents/dcmi-terms/title' to
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
                outfile = "%s/%s/generated/index/%s.html" % (self.baseDir, self.moduleDir, pageid)
                title = pagetitles[pageid]
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
        tmpfilename = mktemp()
        fp = open(tmpfilename,"w")
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
        self._render_newspage(htmlfile, atomfile, u'Nyheter', entries)

    def _render_newspage(self,htmlfile,atomfile,title,entries):
        # only look in cwd and this file's directory
        loader = TemplateLoader(['.' , os.path.dirname(__file__)], 
                                variable_lookup='lenient') 
        tmpl = loader.load("etc/newspage.template.xht2")
        stream = tmpl.generate(title=title,
                               entries=entries)
        # tmpfilename = mktemp()
        tmpfilename = htmlfile.replace(".html",".xht2")
        assert(tmpfilename != htmlfile)
        fp = open(tmpfilename,"w")
        fp.write(stream.render())
        fp.close()
        Util.ensureDir(htmlfile)
        Util.transform("xsl/static.xsl", tmpfilename, htmlfile, validate=False)
        
        tmpl = loader.load("etc/newspage.template.atom")
        stream = tmpl.generate(title=title,
                               entries=entries)
        tmpfilename = mktemp()
        fp = open(tmpfilename,"w")
        fp.write(stream.render())
        fp.close()
        Util.ensureDir(atomfile)
        Util.replace_if_different(tmpfilename, atomfile)

        log.info("rendered %s (%s)" % (htmlfile, atomfile))

                            
    
    ################################################################
    # PURELY INTERNAL FUNCTIONS
    ################################################################

    def __tidy_graph(self,graph):
        """remove unneccesary whitespace and XMLLiteral typing from
        literals in the graph"""
        for tup in graph:
            (o,p,s) = tup
            if (isinstance(s,Literal) and
                s.datatype == URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#XMLLiteral')):
                graph.remove(tup)
                l = Literal(u' '.join(s.split()))
                graph.add((o,p,l))

    def __get_default_graph(self):
        """Returns an initialized RDFLib graph object (eg using a
        in-memory store, or a mysql store, depending on the phase of
        the moon or whatever)"""
        use_mysql_store = False
        if (use_mysql_store):
            configString = "host=localhost,user=rdflib,password=rdflib,db=rdfstore"
            store = plugin.get('MySQL', Store)('rdfstore')
            rt = store.open(configString,create=False)
            print "MySQL triple store opened: %s" % rt
            graph = Graph(store, identifier = URIRef("http://lagen.nu/rdfstore"))
        else: 
            graph = Graph(identifier = URIRef("http://lagen.nu/rdfstore"))
        for key, value in Util.ns.items():
            graph.bind(key,  Namespace(value));
        return graph

    def __load_rdfa(self, filename, graph=None):
        import xml.dom.minidom
        import pyRdfa
        dom  = xml.dom.minidom.parse(filename)
        o = pyRdfa.Options()
        o.warning_graph = None
        g = pyRdfa.parseRDFa(dom, None, options=o)
        self.__tidy_graph(g)
        if not graph is None:
            graph += g
            #print "Adding to graph, now %d triples" % len(graph)
        else:
            graph = g
            #print "New graph, %d triples" % len(g)
        return graph
