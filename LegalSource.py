#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Base classes for Downloaders and Parsers. Also utility classes (should be moved?)"""
import sys, os, re, codecs, types
import pickle
from time import time
import locale
import xml.etree.cElementTree as ET
import logging
import difflib

# 3rd party modules
import BeautifulSoup
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
    else:
        defaultencoding = locale.getpreferredencoding()
# print "setting sys.stdout to a '%s' writer" % defaultencoding
sys.stdout = codecs.getwriter(defaultencoding)(sys.__stdout__, 'replace')
sys.stderr = codecs.getwriter(defaultencoding)(sys.__stderr__, 'replace')

log = logging.getLogger(u'ls')


class ParseError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class IdNotFound(Exception):
    """thrown whenever we try to lookup a URI/displayid/basefile but can't find it"""
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

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
    
    
class Downloader:
    TIME_FORMAT = "%Y-%m-%d %H:%M:%S %Z"
    """Abstract base class for downloading legal source documents
    (statues, cases, etc).

    Apart from naming the resulting files, and constructing a
    index.xml file, subclasses should do as little modification to the
    data as possible."""

    def __init__():
        self.browser = Browser()
        # FIXME: Set user-agent header somehow. Also, if we could make
        # it support Robot.ThrottlingProcessor it would be cool
        self.ids = {}
 
    def DownloadAll():
        raise NotImplementedError
    
    def DownloadNew():
        raise NotImplementedError

    def _saveIndex(self):
        indexroot = ET.Element("index")
        for k in self.ids.keys():
            resource = ET.SubElement(indexroot, "resource")
            resource.set("id", k)
            resource.set("url", self.ids[k].url)
            resource.set("localFile", self.ids[k].localFile)
            resource.set("fetched", time.strftime(self.TIME_FORMAT,self.ids[k].fetched))
        tree = ET.ElementTree(indexroot)
        tree.write(self.dir + "/index.xml")

    def _loadIndex(self):
        self.ids.clear()
        tree = ET.ElementTree(file=self.dir + "/index.xml")
        for node in tree.getroot():
            id = node.get("id")
            resource = LegalSource.DownloadedResource(id)
            resource.url = node.get("url")
            resource.localFile = node.get("localFile")
            resource.fetched = time.strptime(node.get("fetched"), self.TIME_FORMAT)
            self.ids[id] = resource


class Parser:
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
            log.warning(u'%s: templatefel \'%s\'' % (self.id, msg[:80]))
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

class Manager:
    def __init__(self,baseDir,moduleDir):
        """basedir is the top-level directory in which all file-based data is
        stored and handled. moduledir is a sublevel directory that is unique
        for each LegalSource.Manager subclass."""
        self.baseDir = baseDir
        self.moduleDir = moduleDir


    def _outfileIsNewer(self,infiles,outfile):
        """check to see if the outfile is newer than all ingoing files"""
        if not os.path.exists(outfile): return False
        outfileMTime = os.stat(outfile).st_mtime
        newer = True
        for f in infiles:
            if os.path.exists(f) and os.stat(f).st_mtime > outfileMTime: newer = False
        return newer

    def _htmlFileName(self,basefile):
        if not isinstance(basefile, unicode):
            raise Exception("WARNING: _htmlFileName called with non-unicode name")
        # will typically never be overridden 
        """Returns the full path of the GENERATED HTML fragment that represents a legal document""" 
        return u'%s/%s/generated/%s.html' % (self.baseDir, self.moduleDir,basefile)         
 
    def _xmlFileName(self,basefile): 
        if not isinstance(basefile, unicode):
            raise Exception("WARNING: _xmlFileName called with non-unicode name")
        # will typically never be overridden 
        """Returns the full path of the XHTML2/RDFa doc that represents the parsed legal document""" 
        return u'%s/%s/parsed/%s.xht2' % (self.baseDir, self.moduleDir,basefile)     

    def __tidy_graph(self,graph):
        # remove unneccesary whitespace and xmlliteral typing
        for tup in graph:
            (o,p,s) = tup
            if (isinstance(s,Literal) and
                s.datatype == URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#XMLLiteral')):
                graph.remove(tup)
                l = Literal(u' '.join(s.split()))
                graph.add((o,p,l))

    def __get_default_graph(self):
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


    ####################################################################
    # Manager INTERFACE DEFINITION
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
    # GENERIC DIRECTLY-CALLABLE METHODS
    ####################################################################
    def DumpTriples(self, filename, format="turtle"):
        g = self.__load_rdfa(filename)
        print unicode(g.serialize(format=format, encoding="utf-8"), "utf-8")

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

    def RelateAll(self,file=None):
        """Sammanställer all metadata för alla dokument i rättskällan
        och bygger en stor RDF-graf. """
        c = 0
        graph = self.__get_default_graph()
        
        for f in Util.listDirs(os.path.sep.join([self.baseDir, self.moduleDir, u'parsed']), '.xht2'):
            c += 1
            self.__load_rdfa(f,graph)
            graph.commit()
            if c % 100 == 0:
                log.info("Related %d documents (%d triples total)" % (c, len(graph)))

        f = open(os.path.sep.join([self.baseDir, self.moduleDir, u'parsed', u'rdf.xml']),'w')
        f.write(graph.serialize(format="pretty-xml"))
        f.close()

        #print unicode(g.serialize(format="nt", encoding="utf-8"), 'utf-8')
            
            
    
    def Index(self,basefile):
        start = time()
        sys.stdout.write("Index: %s" % basefile)
        xmlFileName = self._xmlFileName(basefile)
        root = ET.ElementTree(file=xmlFileName).getroot()

        urn = root.get('urn')
        try:
            displayid = self._findDisplayId(root,basefile)
        except LegalSource.ParseError, e:
            print "error for basefile %s" % basefile
            raise e
        sys.stdout.write("\t%r (displayid: %r)\t" % (urn,displayid))
        (d,created) = Document.objects.get_or_create(urn = urn.encode('utf-8'),
                                                     displayid = displayid.encode('utf-8'),
                                                     basefile = basefile.encode('utf-8'))


        try:
            # build paralell index structure in the form of an xml file
            docElement = ET.SubElement(self.indexroot, "document")
            docElement.set('id', str(d.id))
            docElement.set('urn',urn)
            docElement.set('displayid',displayid)
            docElement.set('basefile',basefile)
        except AttributeError:
            pass # probably b/c self.indexroot doesn't exist
            
        sys.stdout.write(" %s sec\n" % (time() - start))
    
    def Publish(self):
        cmd = "tar czf - %s/%s | ssh staffan@minimac.tomtebo.org \"cd /Library/WebServer/Documents/ferenda.lagen.nu && tar xvzf - && chmod -R go+r %s/%s\"" % (self.baseDir, self._getModuleDir(),self.baseDir, self._getModuleDir())
        print "executing %s" % cmd
        os.system(cmd)

#    def Test(self,testname = None):
#        """Runs a named test for the Parser of this module. If no testname is
#        given, run all available tests"""
#        sys.path.append("test")
#        from test_Parser import TestParser
#        if testname:
#            TestParser.Run(testname,self.parserClass,"test/data/sfs")
#        else:
#            TestParser.RunAll(self.parserClass,"test/data/sfs")
    
