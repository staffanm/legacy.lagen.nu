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
XHT2_NS = "{http://www.w3.org/2002/06/xhtml2/}"

# module global utility functions
def keyword_to_uri(keyword):
    return "http://lagen.nu/concept/%s" % keyword.replace(" ", "_")

def uri_to_keyword(uri):
    return uri.replace("http://lagen.nu/concept/","").replace("_", " ")
    
re_firstchar = re.compile(r'(\w)', re.UNICODE).search

class KeywordDownloader(LegalSource.Downloader):
    def _get_module_dir(self):
        return __moduledir__

    def DownloadAll(self):
        # Get all "term sets" (used dct:subject Objects, wiki pages
        # describing legal concepts, swedish wikipedia pages...)
        terms = defaultdict(dict)

        # 1) Query the RDF DB for all dct:subject triples (is this
        # semantically sensible for a "download" action -- the content
        # isn't really external?) -- term set "subjects" (these come
        # from both court cases and legal definitions in law text)
        sq = """
        PREFIX dct:<http://purl.org/dc/terms/>
        
        SELECT DISTINCT ?subject  WHERE { GRAPH <urn:x-local:sfs> { ?uri dct:subject ?subject } }
        """
        store = SesameStore(self.config['triplestore'], self.config['repository'])
        results = store.select(sq)

        # this is based on LegalSource._store_select -- maybe we
        # should work that into SesameStore?
        tree = ET.fromstring(results)
        for row in tree.findall(".//{http://www.w3.org/2005/sparql-results#}result"):
            for element in row: # should be only one
                subj = element[0].text
                if subj.startswith("http://"):
                    # we should really select ?uri rdfs:label ?label instead of munging the URI
                    subj = uri_to_keyword(subj)
                else:
                    # legacy triples
                    subj = subj[0].upper() + subj[1:] # uppercase first letter and leave the rest alone

                # for sanity: set max length of a subject to 100 chars
                subj = subj[:100] 

                terms[subj][u'subjects'] = True

        log.debug("Retrieved subject terms from RDF graph <urn:x-local:sfs>, got %s terms" % len(terms))

        # for the dv and arn contexts, we should only use subjects
        # that appears more than once:
        sq = """
        PREFIX dct:<http://purl.org/dc/terms/>
        
        SELECT ?subject  WHERE { ?uri dct:subject ?subject }
        """
        store = SesameStore(self.config['triplestore'], self.config['repository'])
        results = store.select(sq)
        tree = ET.fromstring(results)
        potential_subj = defaultdict(int)
        for row in tree.findall(".//{http://www.w3.org/2005/sparql-results#}result"):
            for element in row: # should be only one
                subj = element[0].text
                if subj.startswith("http://"):
                    # we should really select ?uri rdfs:label ?label instead of munging the URI
                    subj = uri_to_keyword(subj)
                else:
                    # legacy triples
                    subj = subj[0].upper() + subj[1:] # uppercase first letter and leave the rest alone

                # for sanity: set max length of a subject to 100 chars
                subj = subj[:100] 

                potential_subj[subj] += 1

        
        for (subj,cnt) in potential_subj.items():
            if cnt > 1:
                terms[subj][u'subjects'] = True
                

        log.debug("Retrieved non-unique subject terms from other RDF graphs, got %s terms" % len(terms))
        # print repr(terms.keys()[:10])
        # 2) Download the wiki.lagen.nu dump from
        # http://wiki.lagen.nu/pages-articles.xml -- term set "wiki"

        self.browser.set_handle_robots(False) # we can ignore our own robots.txt
        self.browser.open("https://lagen.nu/wiki-pages-articles.xml")
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

        log.debug("Retrieved subject terms from wiki, now have %s terms" % len(terms))
        # 3) Download the Wikipedia dump from
        # http://download.wikimedia.org/svwiki/latest/svwiki-latest-all-titles-in-ns0.gz
        # -- term set "wikipedia"
        # FIXME: only download when needed
        self.browser.retrieve("http://download.wikimedia.org/svwiki/latest/svwiki-latest-all-titles-in-ns0.gz", self.download_dir+"/svwiki-latest-all-titles-in-ns0.gz")
        from gzip import GzipFile
        wikipediaterms = GzipFile(self.download_dir+"/svwiki-latest-all-titles-in-ns0.gz")
        for utf8_term in wikipediaterms:
            term = utf8_term.decode('utf-8').strip()
            if term in terms:
                #log.debug(u"%s found in wikipedia" % term)
                terms[term][u'wikipedia'] = True

        log.debug("Retrieved terms from wikipedia, now have %s terms" % len(terms))
        # 4) Download all pages from Jureka, probably by starting at
        # pageid = 1 and incrementing until done -- term set "jureka"
        #
        # Possible future term sets:
        # * EUROVOC,
        # * Rikstermdatabasen
        # * various gov websites
        #   - SKV: http://www.skatteverket.se/funktioner/ordforklaringar/ordforklaringarac
        #
        # Store all terms under downloaded/[t]/[term] (for wikipedia,
        # store only those terms that occur in any of the other term
        # sets). The actual content of each text file contains one
        # line for each term set the term occurs in.
        for term in terms:
            if not term:
                continue
            firstletter = re_firstchar(term).group(0)
            outfile = u"%s/%s/%s.txt" % (self.download_dir, firstletter, term)
            if sys.platform != "win32":
                outfile = outfile.replace(u'\u2013','--').replace(u'\u2014','---').replace(u'\u2022',u'·').replace(u'\u201d', '"').replace(u'\x96','--').encode("latin-1")
            
            tmpfile = mktemp()
            f = open(tmpfile,"w")
            for termset in sorted(terms[term]):
                f.write(termset+"\n")
            f.close()
            try:
                Util.replace_if_different(tmpfile,outfile)
            except IOError:
                log.warning("IOError: Could not write term set file for term '%s'" % term)
            except WindowsError:
                log.warning("WindowsError: Could not write term set file for term '%s'" % term)
            

    def DownloadNew(self):
        # Same as above, except use http if-modified-since to avoid
        # downloading swedish wikipedia if not updated. Jureka uses a
        # page id parameter, so check if there are any new ones.
        self.DownloadAll()

class KeywordParser(LegalSource.Parser):
    def Parse(self,basefile,infile,config):
        # for a base name (term), create a skeleton xht2 file
        # containing a element of some kind for each term set this
        # term occurs in.
        baseuri = keyword_to_uri(basefile)
        fp = open(infile,"r")
        termsets = fp.readlines()
        fp.close()
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
        if 'wikipedia\n' in termsets:
            p =  ET.SubElement(body,"p")
            p.attrib['class'] = 'wikibox'
            p.text = 'Begreppet '
            a = ET.SubElement(p,"a")
            a.attrib['href'] = 'http://sv.wikipedia.org/wiki/' + basefile.replace(" ","_")
            a.text = basefile
            a.tail = ' finns även beskrivet på '
            a = ET.SubElement(p,"a")
            a.attrib['href'] = 'http://sv.wikipedia.org/'
            a.text = 'svenska Wikipedia'
        
        return ET.tostring(root,encoding='utf-8')
    

class KeywordManager(LegalSource.Manager):
    __parserClass = KeywordParser

    re_tagstrip = re.compile(r'<[^>]*>')
    
    def __init__(self):
        super(KeywordManager,self).__init__()
        # we use the display_title function
        import SFS
        self.sfsmgr = SFS.SFSManager()
        
    def _get_module_dir(self):
        return __moduledir__

    def _file_to_basefile(self,f):
        return os.path.splitext(f.split(os.sep,3)[3])[0].replace("\\","/")
        #return os.path.splitext(os.path.normpath(f).split(os.sep)[-1])[0]
        
    def _build_mini_rdf(self):
        termdir = os.path.sep.join([self.baseDir, self.moduleDir, u'parsed'])
        minixmlfile = os.path.sep.join([self.baseDir, self.moduleDir, u'parsed', u'rdf-mini.xml'])
        ntfile = os.path.sep.join([self.baseDir, self.moduleDir, u'parsed', u'rdf.nt'])
        files = list(Util.listDirs(termdir, ".xht2"))

        if self._outfile_is_newer(files,minixmlfile):
            log.info(u"Not regenerating RDF/XML files")
            return

        log.info("Making a mini graph")
        SKOS = Namespace(Util.ns['skos'])
        DCT = Namespace(Util.ns['dct'])
        mg = Graph()
        for key, value in Util.ns.items():
            mg.bind(key,  Namespace(value));
        
        for f in files:
            basefile = os.path.splitext(os.path.normpath(f).split(os.sep)[-1])[0]
            termuri = keyword_to_uri(basefile)
            mg.add((URIRef(termuri), RDF.type, SKOS['Concept']))
            mg.add((URIRef(termuri), DCT['title'], Literal(basefile, lang="sv")))
            # Check to see if we have a data/wiki/parsed/[term].xht2 file, and if so, read it's first line
            wikifile = Util.relpath(os.path.sep.join([self.baseDir, 'wiki', u'parsed', basefile + '.xht2']))
            if os.path.exists(wikifile):
                # log.debug("%s exists" % wikifile)
                # use the first <p> of the wiki page as a short description
                tree = ET.parse(wikifile)
                firstpara = tree.find("//"+XHT2_NS+"p")
                if firstpara != None: # redirects and empty pages lack <p> tags alltogether. Which works out just fine
                    xmldesc = ET.tostring(firstpara, encoding='utf-8').decode('utf-8')
                    textdesc = Util.normalizeSpace(self.re_tagstrip.sub('',xmldesc))
                    # log.debug(u"%s has desc %s" % (basefile, textdesc))
                    mg.add((URIRef(termuri), DCT['description'], Literal(textdesc, lang="sv")))

        log.info("Serializing the minimal graph")
        f = open(minixmlfile, 'w')
        f.write(mg.serialize(format="pretty-xml"))
        f.close()
        log.info("Serializing to NTriples")
        
        f = open(ntfile, 'w')
        # The nt serializer is broken (http://code.google.com/p/rdflib/issues/detail?id=78)
        nt_utf8 = mg.serialize(format="nt").decode('utf-8')
        #nt_stringliterals = ''
        for c in nt_utf8:
            if ord(c) > 127:
                #nt_stringliterals += '\u%04X' % ord(c)
                f.write('\u%04X' % ord(c))
            else:
                #nt_stringliterals += c
                f.write(c)

        f.close()
        
    def _htmlFileName(self,basefile):
        """Returns the generated, browser-ready XHTML 1.0 file name for the given basefile"""
        if not isinstance(basefile, unicode):
            raise Exception("WARNING: _htmlFileName called with non-unicode name")
        return u'%s/%s/generated/%s.html' % (self.baseDir, self.moduleDir,basefile.replace(" ","_"))         

    def DownloadAll(self):
        d = KeywordDownloader(self.config)
        d.DownloadAll()

    def DownloadNew(self):
        d = KeywordDownloader(self.config)
        d.DownloadNew()

    def ParseAll(self):
        intermediate_dir = os.path.sep.join([self.baseDir, __moduledir__, u'downloaded'])
        self._do_for_all(intermediate_dir, '.txt',self.Parse)

    def Parse(self,basefile,verbose=False, wiki_keyword=False):
        if verbose:
            print "Setting verbosity"
            log.setLevel(logging.DEBUG)
        start = time()
        basefile = basefile.replace(":","/")
        infile = os.path.sep.join([self.baseDir, __moduledir__, 'downloaded', basefile]) + ".txt"
        if (not os.path.exists(infile)) and wiki_keyword:
            fp = open(infile,"w")
            fp.write("wiki\n")
            fp.close()
        outfile = os.path.sep.join([self.baseDir, __moduledir__, 'parsed', basefile]) + ".xht2"
        force = self.config[__moduledir__]['parse_force'] == 'True'
        if not force and self._outfile_is_newer([infile],outfile):
            return
        p = self.__parserClass()
        p.verbose = verbose
        keyword = basefile.split("/",1)[1]
        parsed = p.Parse(keyword,infile,self.config)
        Util.ensureDir(outfile)

        tmpfile = mktemp()
        out = file(tmpfile, "w")
        out.write(parsed)
        out.close()
        Util.replace_if_different(tmpfile,outfile)
        os.utime(outfile,None)
        log.info(u'%s: OK (%.3f sec)', basefile,time()-start)


    def Generate(self,basefile):
        start = time()
        keyword = basefile.split("/",1)[1]
        # note: infile is e.g. parsed/K/Konsument.xht2, but outfile is generated/Konsument.html
        infile = Util.relpath(self._xmlFileName(basefile))
        outfile = Util.relpath(self._htmlFileName(keyword))
        # Use SPARQL queries to create a rdf graph (to be used by the
        # xslt transform) containing enough information about all
        # cases using this term, as well as the wiki authored
        # dct:description for this term.

        # For proper SPARQL escaping, we need to change å to \u00E5
        # etc (there probably is a neater way of doing this).
        esckeyword = ''
        for c in keyword:
            if ord(c) > 127:
                esckeyword += '\u%04X' % ord(c)
            else:
                esckeyword += c

        escuri = keyword_to_uri(esckeyword)
        
        sq = """
PREFIX dct:<http://purl.org/dc/terms/>
PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
PREFIX rinfo:<http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#>

SELECT ?desc
WHERE { ?uri dct:description ?desc . ?uri rdfs:label "%s"@sv }
""" % esckeyword
        wikidesc = self._store_select(sq)
        log.debug(u'%s: Selected %s descriptions (%.3f sec)', basefile, len(wikidesc), time()-start)

        sq = """
PREFIX dct:<http://purl.org/dc/terms/>
PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
PREFIX rinfo:<http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#>

SELECT DISTINCT ?uri ?label
WHERE {
    GRAPH <urn:x-local:sfs> {
       { ?uri dct:subject <%s> .
         ?baseuri dct:title ?label .
         ?uri dct:isPartOf ?x . ?x dct:isPartOf ?baseuri
       }
       UNION {
         ?uri dct:subject <%s> .
         ?baseuri dct:title ?label .
         ?uri dct:isPartOf ?x . ?x dct:isPartOf ?y . ?y dct:isPartOf ?baseuri
       }
       UNION {
         ?uri dct:subject <%s> .
         ?baseuri dct:title ?label .
         ?uri dct:isPartOf ?x . ?x dct:isPartOf ?y . ?x dct:isPartOf ?z . ?z dct:isPartOf ?baseuri
       }
       UNION {
         ?uri dct:subject <%s> .
         ?baseuri dct:title ?label .
         ?uri dct:isPartOf ?x . ?x dct:isPartOf ?y . ?x dct:isPartOf ?z . ?z dct:isPartOf ?w . ?w dct:isPartOf ?baseuri
       }
    }
}

""" % (escuri,escuri,escuri,escuri)
        #print sq
        legaldefinitioner = self._store_select(sq)
        log.debug(u'%s: Selected %d legal definitions (%.3f sec)', basefile, len(legaldefinitioner), time()-start)

        sq = """
PREFIX dct:<http://purl.org/dc/terms/>
PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
PREFIX rinfo:<http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#>
PREFIX rinfoex:<http://lagen.nu/terms#>

SELECT ?uri ?id ?desc
WHERE {
    {
        GRAPH <urn:x-local:dv> {
            {
                ?uri dct:description ?desc .
                ?uri dct:identifier ?id .
                ?uri dct:subject <%s>
            }
            UNION {
                ?uri dct:description ?desc .
                ?uri dct:identifier ?id .
                ?uri dct:subject "%s"@sv
            }
        }
    } UNION {
        GRAPH <urn:x-local:arn> {
                ?uri dct:description ?desc .
                ?uri rinfoex:arendenummer ?id .
                ?uri dct:subject "%s"@sv
        }
    }  
}
""" % (escuri,esckeyword,esckeyword)

        # Maybe we should handle <urn:x-local:arn> triples here as well?
        
        rattsfall = self._store_select(sq)
        log.debug(u'%s: Selected %d legal cases (%.3f sec)', basefile, len(rattsfall), time()-start)

        root_node = PET.Element("rdf:RDF")
        for prefix in Util.ns:
            PET._namespace_map[Util.ns[prefix]] = prefix
            root_node.set("xmlns:" + prefix, Util.ns[prefix])

        main_node = PET.SubElement(root_node, "rdf:Description")
        main_node.set("rdf:about", keyword_to_uri(keyword))

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

        for l in legaldefinitioner:
            subject_node = PET.SubElement(main_node, "rinfoex:isDefinedBy")
            rattsfall_node = PET.SubElement(subject_node, "rdf:Description")
            rattsfall_node.set("rdf:about",l['uri'])
            id_node = PET.SubElement(rattsfall_node, "rdfs:label")
            #id_node.text = "%s %s" % (l['uri'].split("#")[1], l['label'])
            id_node.text = self.sfsmgr.display_title(l['uri'])

        Util.indent_et(root_node)
        tree = PET.ElementTree(root_node)
        tmpfile = mktemp()
        tree.write(tmpfile, encoding="utf-8")

        annotations = "%s/%s/intermediate/%s.ann.xml" % (self.baseDir, self.moduleDir, basefile)
        terms = "%s/%s/parsed/rdf-mini.xml" % (self.baseDir, self.moduleDir)
        log.debug("Saving annotation file %s "% annotations)

        Util.replace_if_different(tmpfile,annotations)

        force = (self.config[__moduledir__]['generate_force'] == 'True')
        if not force and self._outfile_is_newer([infile,annotations,terms],outfile):
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


#    not yet ready for prime time
#
#    def _build_indexpages(self, by_pred_obj, by_subj_pred):
#        documents = defaultdict(lambda:defaultdict(list))
#        pagetitles = {}
#        pagelabels = {}
#        type_pred  = Util.ns['rdf']+'type'
#        type_obj   = Util.ns['skos']+'Concept'
#        title_pred = Util.ns['dct']+'title'
#        for subj in by_pred_obj[type_pred][type_obj]:
#            title = by_subj_pred[subj][title_pred]
#            letter = title[0].lower()
#
#            pagetitles[letter] = u'Begrepp som börjar på "%s"' % letter.upper()
#            pagelabels[letter] = letter.upper()
#            documents[u'Inledningsbokstav'][letter].append({'uri':subj,
#                                                            'sortkey':title.lower(),
#                                                            'title':title})
#
#        for category in documents.keys():
#            for pageid in documents[category].keys():
#                outfile = "%s/%s/generated/index/%s.html" % (self.baseDir, self.moduleDir, pageid)
#                title = pagetitles[pageid]
#                self._render_indexpage(outfile,title,documents,pagelabels,category,pageid)
#                if pageid == 'a': # make index.html
#                    outfile = "%s/%s/generated/index/index.html" % (self.baseDir, self.moduleDir)
#                    self._render_indexpage(outfile,title,documents,pagelabels,category,pageid)
#                        
                                                 

        
if __name__ == "__main__":
    import logging.config
    logging.config.fileConfig('etc/log.conf')
    KeywordManager.__bases__ += (DispatchMixin,)
    mgr = KeywordManager()
    mgr.Dispatch(sys.argv)
