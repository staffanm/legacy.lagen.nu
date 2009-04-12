#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Modul för att översätta innehållet i en Mediawikiinstans till RDF-triples"""

# system
import sys, os, re
import xml.etree.cElementTree as ET
import xml.etree.ElementTree as PET
import logging
from time import time
from tempfile import mktemp

# 3rdparty
from configobj import ConfigObj

# mine
import Util
import LegalSource
from DispatchMixin import DispatchMixin
from LegalRef import LegalRef
from SFS import FilenameToSFSnr

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
        xml = ET.parse(open("pages-articles.xml"))
        for ns_el in xml.findall("//"+MW_NS+"namespace"):
            wikinamespaces.append(ns_el.text)

        for page_el in xml.findall(MW_NS+"page"):
            title = page_el.find(MW_NS+"title").text
            if title == "Huvudsida":
                continue
            if ":" in title and title.split(":")[0] in wikinamespaces:
                continue
            outfile = "%s/%s.xml" % (self.download_dir, title.replace(":","/"))
            print "Dumping %s to %s" % (title,outfile)
            Util.ensureDir(outfile)
            f = open(outfile,"w")
            f.write(ET.tostring(page_el,encoding="utf-8"))
            f.close()
                
    def DownloadNew(self):
        self.DownloadAll()

    def _downloadSingle(self,term):
        # download a single term, for speed
        pass

class WikiParser(LegalSource.Parser):
    
    def Parse(self,basefile,infile,config):
        xml = ET.parse(open(infile))
        wikitext = xml.find("//"+MW_NS+"text").text
        import wikimarkup
        html = wikimarkup.parse(wikitext,showToc=False)
        # the output from wikimarkup is less than ideal...
        html = html.replace("&", "&amp;");
        html = '<div>'+html+'</div>';
        # FIXME: we should also
        #
        # 1) resolve those wikilinks that lead to defined terms (and
        # possibly remove those that lead to undefined terms)
        #
        # 2) run LegalRef on the textual content of each node (that
        # isn't a heading)
        #
        # 3) Make sure that whatever wikimarkup.parse returns is valid
        # XHTML2
        #
        # 4) Separate the trailing [[Kategori:Blahonga]] links
        xhtml = ET.fromstring(html.encode('utf-8'))

        p = LegalRef(LegalRef.LAGRUM)
        # find out the URI that this wikitext describes
        if basefile.startswith("SFS/"):
            sfs = FilenameToSFSnr(basefile.split("/",1)[1])
            nodes = p.parse(sfs)
            uri = nodes[0].uri
        else:
            # FIXME: What is the best URI strategy for term URIs?
            uri = "http://lagen.nu/terms/" + basefile.replace(" ","_")

        log.debug("    URI: %s" % uri)

        root = ET.Element("html")
        root.set("xmlns", 'http://www.w3.org/2002/06/xhtml2/')
        root.set("xmlns:dct", Util.ns['dct'])
        root.set("xmlns:rdf", Util.ns['rdf'])
        head = ET.SubElement(root,"head")
        title = ET.SubElement(head,"title")
        title.text = basefile
        body = ET.SubElement(root,"body")
        body.set("about", uri)
        body.set("property", "dct:desc")
        body.set("datatype", "rdf:XMLLiteral")
        current = body
        for child in xhtml:
            if child.tag in ('h1','h2','h3','h4','h5','h6'):
                nodes = p.parse(child.text,uri)
                try:
                    suburi = nodes[0].uri
                    log.debug("    Sub-URI: %s" % suburi)
                    h = ET.SubElement(body, child.tag)
                    h.text = child.text
                    current = ET.SubElement(body,"div")
                    current.set("about", suburi)
                    current.set("property", "dct:desc")
                    current.set("datatype", "rdf:XMLLiteral")
                except KeyError:
                    log.warning(u'%s är uppmärkt som en rubrik, men verkar inte vara en lagrumshänvisning' % child.text)
            else:
                current.append(child)
        res = ET.tostring(root,encoding='utf-8')
        return res
    
class WikiManager(LegalSource.Manager):
    __parserClass = WikiParser
    def _get_module_dir(self):
        return __moduledir__

    def __init__(self):
        super(WikiManager,self).__init__()
        self.moduleDir = "wiki"

    def DownloadAll(self):
        d = WikiDownloader(self.config)
        d.DownloadAll()

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
        # Util.indentXmlFile(tmpfile)
        Util.replace_if_different(tmpfile,outfile)
        log.info(u'%s: OK (%.3f sec)', basefile,time()-start)

if __name__ == "__main__":
    import logging.config
    logging.config.fileConfig('etc/log.conf')
    WikiManager.__bases__ += (DispatchMixin,)
    mgr = WikiManager()
    mgr.Dispatch(sys.argv)
