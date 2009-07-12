#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Metamodul som korsrefererar nyckelord som hittats i domslut, andra
beslut, lagkommentarswikitext, osv"""

# system libraries
import logging
import sys, os, re, shutil
from collections import defaultdict
from pprint import pprint
from time import time
from tempfile import mktemp
import xml.etree.cElementTree as ET
import xml.etree.ElementTree as PET

# 3rdparty libs
from configobj import ConfigObj
from genshi.template import TemplateLoader
from rdflib.Graph import Graph
from rdflib import Literal, Namespace, URIRef, RDF, RDFS

# my libs
import Util
import LegalSource
from DispatchMixin import DispatchMixin
from SesameStore import SesameStore



__version__   = (1,6)
__author__    = u"Staffan Malmgren <staffan@tomtebo.org>"
__shortdesc__ = u"Nyckelord/sökord"
__moduledir__ = "keyword"
log = logging.getLogger(__moduledir__)
if not os.path.sep in __file__:
    __scriptdir__ = os.getcwd()
else:
    __scriptdir__ = os.path.dirname(__file__)

MW_NS = "{http://www.mediawiki.org/xml/export-0.3/}"
class KeywordDownloader(LegalSource.Downloader):
    def _get_module_dir(self):
        return __moduledir__

    def DownloadAll(self):
        # Get all "term sets" (used dct:subject Objects, wiki pages
        # describing legal concepts, swedish wikipedia pages...)
        terms = defaultdict(dict)

        # 1) Query the RDF DB for all dct:subject triples (is this
        # semantically sensible for a "download" action -- the
        # content isn't really external?) -- term set "subjects"
        sq = """
        PREFIX dct:<http://purl.org/dc/terms/>
        
        SELECT DISTINCT ?subject  WHERE { ?uri dct:subject ?subject }
        """
        store = SesameStore(self.config['triplestore'], self.config['repository'])
        results = store.select(sq)
        tree = ET.fromstring(results)
        for row in tree.findall(".//{http://www.w3.org/2005/sparql-results#}result"):
            for element in row: # should be only one
                subj = element[0].text
                subj = subj[0].upper() + subj[1:] # uppercase first letter and leave the rest alone
                terms[subj][u'subjects'] = True

        log.debug("Retrieved terms from RDF store, got %s terms" % len(terms))

        # 2) Download the wiki.lagen.nu dump from
        # http://wiki.lagen.nu/pages-articles.xml -- term set "wiki"
        self.browser.open("http://wiki.lagen.nu/pages-articles.xml")
        xml = ET.parse(self.browser.response())
        wikinamespaces = []
        for ns_el in xml.findall("//"+MW_NS+"namespace"):
            wikinamespaces.append(ns_el.text)
        for page_el in xml.findall(MW_NS+"page"):
            title = page_el.find(MW_NS+"title").text
            if title == "Huvudsida":
                continue
            if ":" in title and title.split(":")[0] in wikinamespaces:
                continue # only process pages in the main namespace
            if title.startswith("SFS/"):
                continue
            terms[title][u'wiki'] = True

        log.debug("Retrieved terms from wiki, now have %s terms" % len(terms))
        # 3) Download the Wikipedia dump from
        # http://download.wikimedia.org/svwiki/latest/svwiki-latest-all-titles-in-ns0.gz
        # -- term set "wikipedia"
        #
        # 4) Download all pages from Jureka, probably by starting at
        # pageid = 1 and incrementing until done -- term set "jureka"
        #
        # Possible future term sets: EUROVOC, Rikstermdatabasen (or a
        # subset thereof), various gov websites... Lawtext also
        # contains a number of term definitions, maybe marked up as
        # dct:defines.
        #
        # Store all terms under downloaded/[t]/[term] (for wikipedia,
        # store only those terms that occur in any of the other term
        # sets). The actual content of each text file contains one
        # line for each term set the term occurs in.
        for term in terms:
            if not term:
                continue
            outfile = u"%s/%s/%s.txt" % (self.download_dir, term[0], term)
            if sys.platform != "win32":
                outfile = outfile.replace(u'\u2013','--').replace(u'\u2014','---').replace(u'\u2022',u'·').replace(u'\u201d', '"').replace(u'\x96','--').encode("latin-1")
            try: 
                Util.ensureDir(outfile)
                f = open(outfile,"w")
                for termset in sorted(terms[term]):
                    f.write(termset+"\n")
                f.close()
            except IOError:
                log.warning("IOError: Could not write term set file for term '%s'" % term)
            #except WindowsError:
            #    log.warning("WindowsError: Could not write term set file for term '%s'" % term)
            

    def DownloadNew():
        # Same as above, except use http if-modified-since to avoid
        # downloading swedish wikipedia if not updated. Jureka uses a
        # page id parameter, so check if there are any new ones.
        
        pass 

class KeywordParser(LegalSource.Parser):
    def Parse(self,basefile,infile,config):
        # for a base name (term), create a skeleton xht2 file
        # containing a element of some kind for each term set this
        # term occurs in.
        baseuri = "http://lagen.nu/concept/%s" % basefile.replace(" ","_")
        
        root = ET.Element("html")
        root.set("xml:base", baseuri)
        root.set("xmlns", 'http://www.w3.org/2002/06/xhtml2/')
        root.set("xmlns:dct", Util.ns['dct'])
        head = ET.SubElement(root, "head")
        title = ET.SubElement(head, "title")
        title.text = basefile
        body = ET.SubElement(root,"body")
        heading = ET.SubElement(body,"h")
        heading.set("property", "dct:title")
        
        heading.text = basefile
        return ET.tostring(root,encoding='utf-8')
    

class KeywordManager(LegalSource.Manager):
    __parserClass = KeywordParser
    
    def __init__(self):
        super(KeywordManager,self).__init__()
        # self.moduleDir = "dv" # to fake Indexpages to load dv/parsed/rdf.nt -- will do for now
        
    def _get_module_dir(self):
        return __moduledir__

    def _file_to_basefile(self,f):
        return os.path.splitext(os.path.normpath(f).split(os.sep)[-1])[0]
        
    def _build_mini_rdf(self):
        termdir = os.path.sep.join([self.baseDir, self.moduleDir, u'parsed'])
        minixmlfile = os.path.sep.join([self.baseDir, self.moduleDir, u'parsed', u'rdf-mini.xml'])
        files = list(Util.listDirs(termdir, ".xht2"))

        if self._outfile_is_newer(files,minixmlfile):
            log.info(u"Not regenerating RDF/XML files")
            return

        log.info("Making a mini graph")
        SKOS = Namespace(Util.ns['skos'])
        mg = Graph()
        for key, value in Util.ns.items():
            mg.bind(key,  Namespace(value));
        
        for f in files:
            basefile = os.path.splitext(os.path.normpath(f).split(os.sep)[-1])[0]
            termuri = "http://lagen.nu/concept/%s" % basefile.replace(" ", "_")
            mg.add((URIRef(termuri), RDF.type, SKOS['Concept']))

        log.info("Serializing the minimal graph")
        f = open(minixmlfile, 'w')
        f.write(mg.serialize(format="pretty-xml"))
        f.close()
        
    def _htmlFileName(self,basefile):
        """Returns the generated, browser-ready XHTML 1.0 file name for the given basefile"""
        if not isinstance(basefile, unicode):
            raise Exception("WARNING: _htmlFileName called with non-unicode name")
        return u'%s/%s/generated/%s.html' % (self.baseDir, self.moduleDir,basefile.replace(" ","_"))         

    def DownloadAll(self):
        d = KeywordDownloader(self.config)
        d.DownloadAll()

    def ParseAll(self):
        intermediate_dir = os.path.sep.join([self.baseDir, __moduledir__, u'downloaded'])
        self._do_for_all(intermediate_dir, '.txt',self.Parse)

    def Parse(self,basefile,verbose=False):
        if verbose:
            print "Setting verbosity"
            log.setLevel(logging.DEBUG)
        start = time()
        basefile = basefile.replace(":","/")
        infile = os.path.sep.join([self.baseDir, __moduledir__, 'downloaded', basefile]) + ".xml"
        outfile = os.path.sep.join([self.baseDir, __moduledir__, 'parsed', basefile]) + ".xht2"
        force = self.config[__moduledir__]['parse_force'] == 'True'
        if not force and self._outfile_is_newer([infile],outfile):
            log.debug(u"%s: Överhoppad", basefile)
            return
        p = self.__parserClass()
        p.verbose = verbose
        parsed = p.Parse(basefile,infile,self.config)
        Util.ensureDir(outfile)

        tmpfile = mktemp()
        out = file(tmpfile, "w")
        out.write(parsed)
        out.close()
        Util.replace_if_different(tmpfile,outfile)
        log.info(u'%s: OK (%.3f sec)', basefile,time()-start)


    def Generate(self,basefile):
        start = time()
        infile = Util.relpath(self._xmlFileName(basefile))
        outfile = Util.relpath(self._htmlFileName(basefile))
        # Use SPARQL queries to create a rdf graph (to be used by the
        # xslt transform) containing enough information about all
        # cases using this term, as well as the wiki authored
        # dct:description for this term.

        # For proper SPARQL escaping, we need to change å to \u00E5
        # etc (there probably is a neater way of doing this).
        escbasefile = ''
        for c in basefile:
            if ord(c) > 127:
                escbasefile += '\u%04X' % ord(c)
            else:
                escbasefile += c
        
        sq = """
PREFIX dct:<http://purl.org/dc/terms/>
PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
PREFIX rinfo:<http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#>

SELECT ?desc
WHERE { ?uri dct:description ?desc . ?uri rdfs:label "%s"@sv }
""" % escbasefile

        wikidesc = self._store_select(sq)
        log.debug(u'%s: Selected description cases (%.3f sec)', basefile, time()-start)

        sq = """
PREFIX dct:<http://purl.org/dc/terms/>
PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
PREFIX rinfo:<http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#>

SELECT ?uri ?id ?desc
WHERE { ?uri dct:description ?desc .
        ?uri dct:identifier ?id .
        ?uri dct:subject "%s"@sv }
""" % escbasefile
        
        rattsfall = self._store_select(sq)
        log.debug(u'%s: Selected %d legal cases (%.3f sec)', basefile, len(rattsfall), time()-start)

        root_node = PET.Element("rdf:RDF")
        for prefix in Util.ns:
            PET._namespace_map[Util.ns[prefix]] = prefix
            root_node.set("xmlns:" + prefix, Util.ns[prefix])

        main_node = PET.SubElement(root_node, "rdf:Description")
        main_node.set("rdf:about", "http://lagen.nu/concept/%s" % basefile.replace(" ","_"))
        
        for d in wikidesc:
            desc_node = PET.SubElement(main_node, "dct:description")
            xhtmlstr = "<xht2:div xmlns:xht2='%s'>%s</xht2:div>" % (Util.ns['xht2'], d['desc'])
            xhtmlstr = xhtmlstr.replace(' xmlns="http://www.w3.org/2002/06/xhtml2/"','')
            desc_node.append(PET.fromstring(xhtmlstr.encode('utf-8')))

        for r in rattsfall:
            subject_node = PET.SubElement(main_node, "dct:subject")
            rattsfall_node = PET.SubElement(subject_node, "rdf:Description")
            rattsfall_node.set("rdf:about",r['uri'])
            id_node = PET.SubElement(rattsfall_node, "dct:identifier")
            id_node.text = r['id']
            desc_node = PET.SubElement(rattsfall_node, "dct:description")
            desc_node.text = r['desc']

        Util.indent_et(root_node)
        tree = PET.ElementTree(root_node)
        tmpfile = mktemp()
        tree.write(tmpfile, encoding="utf-8")

        annotations = "%s/%s/intermediate/%s.ann.xml" % (self.baseDir, self.moduleDir, basefile)
        
        Util.replace_if_different(tmpfile,annotations)

        force = (self.config[__moduledir__]['generate_force'] == 'True')
        if not force and self._outfile_is_newer([infile,annotations],outfile):
            log.debug(u"%s: Överhoppad", basefile)
            return

        Util.mkdir(os.path.dirname(outfile))

        # xsltproc silently fails to open files through the document()
        # functions if the filename has non-ascii
        # characters. Therefore, we copy the annnotation file to a
        # separate temp copy first.
        tmpfile = mktemp()
        shutil.copy2(annotations,tmpfile)
        
        # FIXME: create a relative version of annotations, instead of
        # hardcoding self.baseDir like below
        params = {'annotationfile':tmpfile.replace("\\","/")}
        Util.transform(__scriptdir__ + "/xsl/keyword.xsl",
                       infile,
                       outfile,
                       parameters = params,
                       validate=False)

        Util.robust_remove(tmpfile)
        
        log.info(u'%s: OK (%s, %.3f sec)', basefile, outfile, time()-start)
        return

    def GenerateAll(self):
        parsed_dir = os.path.sep.join([self.baseDir, __moduledir__, u'parsed'])
        self._do_for_all(parsed_dir,'xht2',self.Generate)
        
    def RelateAll(self):
        # This LegalSource have no triples of it's own
        # super(KeywordManager,self).RelateAll()
        self._build_mini_rdf()

        
if __name__ == "__main__":
    import logging.config
    logging.config.fileConfig('etc/log.conf')
    KeywordManager.__bases__ += (DispatchMixin,)
    mgr = KeywordManager()
    mgr.Dispatch(sys.argv)
