#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Modul f�r att �vers�tta inneh�llet i en Mediawikiinstans till RDF-triples"""

# system
import sys, os, re
import xml.etree.cElementTree as ET
import xml.etree.ElementTree as PET
import logging
from time import time
from tempfile import mktemp
from urllib import quote

# 3rdparty
from configobj import ConfigObj
from rdflib import Namespace
import wikimarkup

# mine
import Util
import LegalSource
from DispatchMixin import DispatchMixin
from LegalRef import LegalRef, Link
from SFS import FilenameToSFSnr
from SesameStore import SesameStore

log = logging.getLogger(u'ls')

__version__   = (1,6)
__author__    = u"Staffan Malmgren <staffan@tomtebo.org>"
__shortdesc__ = u"Wikikommentarer"
__moduledir__ = "wiki"
log = logging.getLogger(__moduledir__)


MW_NS = "{http://www.mediawiki.org/xml/export-0.3/}"
class WikiDownloader(LegalSource.Downloader):
    def __init__(self,config):
        super(WikiDownloader,self).__init__(config) # sets config, logging, initializes browser

    def _get_module_dir(self):
        return __moduledir__

    def DownloadAll(self):
        wikinamespaces = []
        # this file is regenerated hourly
        url = "http://wiki.lagen.nu/pages-articles.xml"
        self.browser.open(url)
        xml = ET.parse(self.browser.response())

        for ns_el in xml.findall("//"+MW_NS+"namespace"):
            wikinamespaces.append(ns_el.text)

        
        for page_el in xml.findall(MW_NS+"page"):
            title = page_el.find(MW_NS+"title").text
            if title == "Huvudsida":
                continue
            if ":" in title and title.split(":")[0] in wikinamespaces:
                continue # only process pages in the main namespace
            outfile = "%s/%s.xml" % (self.download_dir, title.replace(":","/"))
            log.debug("Dumping %s" % outfile)
            Util.ensureDir(outfile)
            f = open(outfile,"w")
            f.write(ET.tostring(page_el,encoding="utf-8"))
            f.close()
                
    def DownloadNew(self):
        self.DownloadAll()

    def _downloadSingle(self,term):
        # download a single term, for speed
        if isinstance(term,unicode):
            encodedterm = quote(term.encode('utf-8'))
        else:
            encodedterm = quote(term)
        url = "http://wiki.lagen.nu/index.php/Special:Exportera/%s" % encodedterm
        # FIXME: if outfile already exist, only save if wiki resource is modified since
        outfile = "%s/%s.xml" % (self.download_dir, term.replace(":","/"))
        Util.ensureDir(outfile)
        log.info("Downloading wiki text for term %s to %s ", term, outfile)
        self.browser.retrieve(url,outfile)


class LinkedWikimarkup(wikimarkup.Parser):
    def __init__(self, show_toc=True):
        super(wikimarkup.Parser, self).__init__()
        self.show_toc = show_toc

    def parse(self,text):
        #print "Running subclassed parser!"
        utf8 = isinstance(text, str)
        text = wikimarkup.to_unicode(text)
        if text[-1:] != u'\n':
            text = text + u'\n'
            taggedNewline = True
        else:
            taggedNewline = False

        text = self.strip(text)
        text = self.removeHtmlTags(text)
        text = self.doTableStuff(text)
        text = self.parseHorizontalRule(text)
        text = self.checkTOC(text)
        text = self.parseHeaders(text)
        text = self.parseAllQuotes(text)
        text = self.replaceExternalLinks(text)
        if not self.show_toc and text.find(u"<!--MWTOC-->") == -1:
            self.show_toc = False
        text = self.formatHeadings(text, True)
        text = self.unstrip(text)
        text = self.fixtags(text)
        text = self.doBlockLevels(text, True)
        text = self.unstripNoWiki(text)
        text = self.replaceWikiLinks(text)
        
        text = text.split(u'\n')
        text = u'\n'.join(text)
        if taggedNewline and text[-1:] == u'\n':
            text = text[:-1]
        if utf8:
            return text.encode("utf-8")
        return text
        
    re_labeled_wiki_link = re.compile(r'\[\[([^\]]*?)\|(.*?)\]\](\w*)') # is the trailing group really needed?
    re_wiki_link = re.compile(r'\[\[([^\]]*?)\]\](\w*)')

    def capitalizedLink(self,m):
        if m.group(1).startswith('SFS/'):
            uri = 'http://rinfo.lagrummet.se/publ/%s' % m.group(1).lower()
        else:
            uri = 'http://lagen.nu/concept/%s' % m.group(1).capitalize().replace(' ','_')
        
        if len(m.groups()) == 3:
            # lwl = "Labeled WikiLink"
            return '<a class="lwl" href="%s">%s%s</a>' % (uri, m.group(2), m.group(3))
        else:
            return '<a class="wl" href="%s">%s%s</a>' % (uri, m.group(1), m.group(2))
        
    
    def replaceWikiLinks(self,text):
        # print "replacing wiki links: %s" % text[:30]
        # FIXME: Ideally, we should only link those segments that have
        # defined corresponding pages. Or maybe that could be done in
        # the XSLT transform?
        text = self.re_labeled_wiki_link.sub(self.capitalizedLink, text)
        text = self.re_wiki_link.sub(self.capitalizedLink, text)
        return text


class WikiParser(LegalSource.Parser):
    
    def Parse(self,basefile,infile,config):
        xml = ET.parse(open(infile))
        wikitext = xml.find("//"+MW_NS+"text").text

        # remove links to lagen.nu itself - they are not needed as
        # they will be automagically inferred, and may mess up things
        # wikitext = re.sub('\[https?://lagen.nu/(\S*) ([^\]]*)]','\\2',wikitext)

        p = LinkedWikimarkup(show_toc=False)
        html = p.parse(wikitext)

        # the output from wikimarkup is less than ideal...
        html = html.replace("&", "&amp;");
        html = '<div>'+html+'</div>';
        # FIXME: we should also
        #
        # 4) Separate the trailing [[Kategori:Blahonga]] links
        try: 
            xhtml = ET.fromstring(html.encode('utf-8'))
        except SyntaxError:
            log.warn("%s: wikiparser did not return well-formed markup (working around)" % basefile)
            tidied = Util.tidy(html.encode('utf-8')).replace(' xmlns="http://www.w3.org/1999/xhtml"','')
            xhtml = ET.fromstring(tidied.encode('utf-8')).find("body")

        # p = LegalRef(LegalRef.LAGRUM)
        p = LegalRef(LegalRef.LAGRUM, LegalRef.KORTLAGRUM, LegalRef.FORARBETEN, LegalRef.RATTSFALL)
        # find out the URI that this wikitext describes
        if basefile.startswith("SFS/"):
            sfs = FilenameToSFSnr(basefile.split("/",1)[1])
            nodes = p.parse(sfs)
            uri = nodes[0].uri
            rdftype = None
        else:
            # concept == "begrepp"
            uri = "http://lagen.nu/concept/" + basefile.replace(" ","_")
            rdftype = "skos:Concept"

        log.debug("    URI: %s" % uri)

        root = ET.Element("html")
        root.set("xmlns", 'http://www.w3.org/2002/06/xhtml2/')
        root.set("xmlns:dct", Util.ns['dct'])
        root.set("xmlns:rdf", Util.ns['rdf'])
        root.set("xmlns:rdfs", Util.ns['rdfs'])
        root.set("xmlns:skos", Util.ns['skos'])
        root.set("xml:lang", "sv")
        head = ET.SubElement(root,"head")
        title = ET.SubElement(head,"title")
        title.text = basefile
        body = ET.SubElement(root,"body")
        body.set("about", uri)
        if rdftype:
            body.set("typeof", "skos:Concept")
            heading = ET.SubElement(body, "h")
            heading.set("property", "rdfs:label")
            heading.text = basefile
            
        main = ET.SubElement(body, "div")
        main.set("property", "dct:description")
        main.set("datatype", "rdf:XMLLiteral")
        current = main
        currenturi = uri

        for child in xhtml:
            if not rdftype and child.tag in ('h1','h2','h3','h4','h5','h6'):
                nodes = p.parse(child.text,uri)
                try:
                    suburi = nodes[0].uri
                    currenturi = suburi
                    log.debug("    Sub-URI: %s" % suburi)
                    h = ET.SubElement(body, child.tag)
                    h.text = child.text
                    current = ET.SubElement(body,"div")
                    current.set("about", suburi)
                    current.set("property", "dct:description")
                    current.set("datatype", "rdf:XMLLiteral")
                except AttributeError:
                    log.warning(u'%s �r uppm�rkt som en rubrik, men verkar inte vara en lagrumsh�nvisning' % child.text)
            else:
                
                serialized = ET.tostring(child,'latin-1')
                res = ""
                # split serialized into tags and pcdata. don't feed tags to p.parse.
                for groups in re.findall('((?:</?[^>]*>|))([^<*]*)', serialized):
                    #print "'%s' is a start-or-end tag, not parsing" % groups[0].decode('latin-1')
                    res += groups[0].decode('latin-1')
                    #print "'%s' is plain text, parsing" % groups[1].decode('latin-1')
                    parts = p.parse(groups[1])
                    for part in parts:
                        if isinstance(part, Link):
                            res += u'<a class="lr" href="%s">%s</a>' % (part.uri, part)
                        else: # just a text fragment
                            res += part

                res = res.encode('latin-1')
                #print ET.fromstring(res)
                #print "RES:\n"
                #print repr(res)
                current.append(ET.fromstring(res))
        res = ET.tostring(root,encoding='utf-8')
        return res
    
class WikiManager(LegalSource.Manager):
    __parserClass = WikiParser
    def _get_module_dir(self):
        return __moduledir__

    def __init__(self):
        super(WikiManager,self).__init__()
        self.moduleDir = "wiki"

    def Download(self,term):
        d = WikiDownloader(self.config)
        d._downloadSingle(term)

    def DownloadAll(self):
        d = WikiDownloader(self.config)
        d.DownloadAll()

    def DownloadNew(self):
        d = WikiDownloader(self.config)
        d.DownloadNew()

    def ParseAll(self):
        intermediate_dir = os.path.sep.join([self.baseDir, __moduledir__, u'downloaded'])
        self._do_for_all(intermediate_dir, '.xml',self.Parse)

    def _file_to_basefile(self,f):
        seg = os.path.splitext(f)[0].split(os.sep)
        return "/".join(seg[seg.index(__moduledir__)+2:])

    def Parse(self, basefile, verbose=False):
        if verbose:
            print "Setting verbosity"
            log.setLevel(logging.DEBUG)
        start = time()
        basefile = basefile.replace(":","/")
        infile = os.path.sep.join([self.baseDir, __moduledir__, 'downloaded', basefile]) + ".xml"
        outfile = os.path.sep.join([self.baseDir, __moduledir__, 'parsed', basefile]) + ".xht2"
        force = self.config[__moduledir__]['parse_force'] == 'True'
        if not force and self._outfile_is_newer([infile],outfile):
            log.debug(u"%s: �verhoppad", basefile)
            return
        p = self.__parserClass()
        p.verbose = verbose
        parsed = p.Parse(basefile,infile,self.config)
        Util.ensureDir(outfile)

        tmpfile = mktemp()
        out = file(tmpfile, "w")
        out.write(parsed)
        out.close()
        # Util.indentXmlFile(tmpfile)
        Util.replace_if_different(tmpfile,outfile)
        log.info(u'%s: OK (%.3f sec)', basefile,time()-start)

    def Generate(self,basefile):
        # No pages to generate for this src (pages for
        # keywords/concepts are done by Keyword.py)
        pass

    def GenerateAll(self):
        pass
    
    def Relate(self, basefile):
        basefile = basefile.replace(":","/")

        # each wiki page gets a unique context - this is so that we
        # can easily delete its statements once we re-parse and
        # re-relate it's content
        context = "<urn:x-local:%s:%s>" % (self.moduleDir, quote(basefile.encode('utf-8').replace(" ","_")))
        store = SesameStore(self.config['triplestore'], self.config['repository'],context)

        infile = os.path.sep.join([self.baseDir, __moduledir__, 'parsed', basefile]) + ".xht2"
        # print "loading triples from %s" % infile
        graph = self._extract_rdfa(infile)
        store.clear()
        triples = 0
        triples += len(graph)
        for key, value in Util.ns.items():
            store.bind(key, Namespace(value));
        store.add_graph(graph)
        store.commit()
        log.info("Related %s: %d triples" % (basefile, triples))

    def RelateAll(self,file=None):
        # we override LegalSource.RelateAll since we want a different
        # context for each wiki page
        """Sammanst�ller alla wiki-baserade beskrivningstriples och
        laddar in dem i systemets triplestore"""
        files = list(Util.listDirs(os.path.sep.join([self.baseDir, self.moduleDir, u'parsed']), '.xht2'))
        rdffile = os.path.sep.join([self.baseDir, self.moduleDir, u'parsed', u'rdf.nt']) 


        if self._outfile_is_newer(files,rdffile):
            log.info("%s is newer than all .xht2 files, no need to extract" % rdffile)
            return

        for f in files:
            basefile = self._file_to_basefile(f)
            self.Relate(basefile)

        # should we serialize everything to a big .nt file like the
        # other LegalSources does? It's a bit more difficult since we
        # have different contexts


if __name__ == "__main__":
    import logging.config
    logging.config.fileConfig('etc/log.conf')
    WikiManager.__bases__ += (DispatchMixin,)
    mgr = WikiManager()
    mgr.Dispatch(sys.argv)