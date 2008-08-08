#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Base classes for Downloaders and Parsers. Also utility classes (should be moved?)"""
from collections import defaultdict
from tempfile import mktemp
from time import time
import codecs
import difflib
import locale
import logging
import os
import re
import sys
import traceback
import types
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

    Apart from naming the resulting files, and constructing a
    index.xml file, subclasses should do as little modification to the
    data as possible."""

    TIME_FORMAT = "%Y-%m-%d %H:%M:%S %Z"

    def __init__(self,config):
        self.config = config
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
        c = 0
        triples = 0
        # graph = self.__get_default_graph()
        f = open(os.path.sep.join([self.baseDir, self.moduleDir, u'parsed', u'rdf.nt']),'w')
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
        #f.write(graph.serialize(format="pretty-xml"))
        #f.close()
        #print unicode(g.serialize(format="nt", encoding="utf-8"), 'utf-8')
    
    def Indexpages(self):
        """Creates index pages for all documents for a particular
        legalsource. Subclasses can override _indexpages_for_predicate
        and _indexpages_navigation to control exactly which index pages are created"""

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
        # tills all RDF-data är i en sesame-db. Sen måste vi:
        # 
        # * lista alla som börjar på 'a' (kräver ev nya
        #   rdf-statements, rinfoex:sorterinsgtitel), 'b' etc
        # * skapa en enkel xht2 med genshi eller tom elementtree
        # * transformera till html mha static.xslt
        # * gör samma för alla som har SFS-nummer som börjar på 1600-1700 etc
        # * porta nyckelbegreppskoden
        triples = defaultdict(lambda:defaultdict(list))
        subjects = defaultdict(dict)
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
                if pred != 'http://dublincore.org/documents/dcmi-terms/references':
                    if objLiteral != "":
                        triples[pred][objLiteral].append(subj)
                        subjects[subj][pred] = objLiteral
                    elif objUri != "":
                        triples[pred][objUri].append(subj)
                        subjects[subj][pred] = objUri
            else:
                log.warning("Couldn't parse line %s" % line)
        log.info("RDF loaded (%.3f sec)", time()-start)

        for predicate in triples.keys():
            self._indexpages_for_predicate(predicate, triples[predicate],subjects)
        
        self._indexpages_for_legalsource()
        
    ################################################################
    # CONVENIENCE FUNCTIONS FOR SUBCLASSES (can be overridden if needed)
    ################################################################

    def _indexpages_for_predicate(self,predicate,predtriples,subjects):
        print "Default implementation of IndexpagesForPredicate"
        # provide sensible default implementation of this
        pass

    def _indexpages_for_legalsource(self):
        # provide sensible default implementation of this
        print "Default implementation of IndexpagesForLegasource"
        pass


    def _do_for_all(self,dir,suffix,method):
        for f in Util.listDirs(dir, suffix, reverse=True):
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
        """check to see if the outfile is newer than all ingoing files"""
        if not os.path.exists(outfile): return False
        outfileMTime = os.stat(outfile).st_mtime
        newer = True
        for f in infiles:
            if os.path.exists(f) and os.stat(f).st_mtime > outfileMTime: newer = False
        return newer

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

    def _elementtree_to_html(self, title, tree, outfile):
        """Helper function that takes a ET fragment (which should be
        using the xhtml2 namespace), puts it in a skeleton xht2 page,
        then renders that page to browser-ready xhtml1, to the
        filename specified"""
        tmpfilename = mktemp()
        root = ET.Element(self.XHT2NS+"html")
        head = ET.SubElement(root, self.XHT2NS+"head")
        titleelem = ET.SubElement(head, self.XHT2NS+"title")
        titleelem.text = title
        bodyelem = ET.SubElement(root, self.XHT2NS+"body")
        headline = ET.SubElement(bodyelem, self.XHT2NS+"h")
        headline.text = title
        bodyelem.append(tree)

        fp = open(tmpfilename,"w")
        fp.write(ET.tostring(root))
        fp.close()
        Util.ensureDir(outfile)
        Util.transform("xsl/static.xsl", tmpfilename, outfile, validate=False)
        os.unlink(tmpfilename)

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
