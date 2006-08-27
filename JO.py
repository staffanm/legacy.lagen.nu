#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Hanterar beslut från Riksdagens Ombudsmän, www.jo.se

Modulen hanterar hämtande av beslut från JOs webbplats samt
omvandlande av dessa till XML.
"""
import unittest
import sys
import time
import re
import os
import md5
import datetime
import urllib

import LegalSource
import Robot
import Util

sys.path.append('3rdparty')
import BeautifulSoup
import elementtree.ElementTree as ET

__version__ = (0,1)
__author__ = "Staffan Malmgren <staffan@tomtebo.org>"
__shortdesc__ = "Beslut från JO"
__moduledir__ = "jo"

class JODownloader(LegalSource.Downloader):
    
    def __init__(self,baseDir="data"):
        self.dir = baseDir + "/jo/downloaded"
        if not os.path.exists(self.dir):
            Util.mkdir(self.dir)
        self.ids = {}
    
    def DownloadAll(self):
        """Hämtar alla avgöranden"""
        # we should think about clearing (part of) the cache here, or
        # make noncached requests -- a stale index page would not be
        # good. Alternatively just request descisions for the current
        # year or similar.
        html = Robot.Get("http://www.jo.se/Page.aspx?MenuId=106&MainMenuId=106&Language=sv&ObjectClass=DynamX_SFS_Decisions&Action=Search&Reference=&Category=0&Text=&FromDate=&ToDate=&submit=S%F6k")
        soup = BeautifulSoup.BeautifulSoup(html)
        self._downloadDecisions(soup)
        self._saveIndex()
        
    def DownloadNew(self):
        pass
        
    def _downloadDecisions(self,soup):
        re_descPattern = re.compile('Beslutsdatum: (\d+-\d+-\d+) Diarienummer: (.*)')
        for result in soup.first('div', {'class': 'SearchResult'}):
            if result.a['href']:
                url = urllib.basejoin("http://www.jo.se/",result.a['href'])
                # Seems to be a bug in BeautifulSoup - properly
                # escaped & entities are not de-escaped
                url = url.replace('&amp;','&')
                desc = result.contents[-1].string
                m = re_descPattern.match(desc)
                beslutsdatum = m.group(1)
                id = m.group(2)
                filename = id.replace('/','-') + ".html"
                
                resource = LegalSource.DownloadedResource(id)
                resource.url = url
                resource.localFile = filename
                print "Storing %s as %s" % (url,filename)
                Robot.Store(url, None, self.dir + "/" + id.replace('/','-') + ".html")
                resource.fetched = time.localtime()
                if id in self.ids:
                    print "WARNING: replacing URL of id '%s' to '%s' (was '%s')" % (id, url, self.ids[id].url)
                self.ids[id] = resource

class JOParser(LegalSource.Parser):

    def __init__(self,id,file,baseDir):
        self.id = id
        self.dir = baseDir + "/jo/parsed"
        if not os.path.exists(self.dir):
            Util.mkdir(self.dir)
        self.file = file
        print "Loading file %s" % file

    def Parse(self):
        import codecs
        soup = BeautifulSoup.BeautifulSoup(codecs.open(self.file,encoding="iso-8859-1",errors='replace').read())
        
        root = ET.Element("Beslut")
        meta = ET.SubElement(root,"Metadata")
        arendenummer = ET.SubElement(meta,u"Ärendenummer")
        arendenummer.text = soup.first('h2').b.i.string.strip()
        titel = ET.SubElement(meta,"Titel")
        titel.text = soup.first('h3').string.strip()
        arendemening = ET.SubElement(meta,u"Ärendemening")
        arendemening.text = soup.firstText(u"Ärendemening: ").parent.parent.parent.parent.contents[1].string.strip()
        avdelning = ET.SubElement(meta,"Avdelning")
        avdelning.text = soup.firstText('Avdelning: ').parent.parent.parent.parent.contents[1].string.strip()
        beslutsdatum = ET.SubElement(meta, "Beslutsdatum")
        beslutsdatum.text = soup.firstText('Beslutsdatum: ').parent.parent.parent.parent.contents[1].string.strip()
        beslut = ET.SubElement(meta, "Beslut")
        beslut.text = soup.firstText('Beslut: ').parent.parent.parent.parent.contents[1].string.strip()
        
        referat = ET.SubElement(root,"Referat")
        
        node = soup.firstText('Referat:').parent.parent.parent.nextSibling

        while node.name == 'p':
            stycke = ET.SubElement(referat, "Stycke")
            stycke.text = node.string
            node = node.nextSibling

        tree = ET.ElementTree(root)
        tree.write(self.dir + "/" + self.id + ".xml", encoding="iso-8859-1")


class JOManager(LegalSource.Manager):
    def _getModuleDir(self):
        return __moduledir__
    
    def ParseAll(self):
        print "JO: ParseAll not implemented"
        return

    def IndexAll(self):
        print "JO: IndexAll not implemented"
        return
    
    def GenerateAll(self):
        print "JO: GenerateAll not implemented"
        return

    def RelateAll(self):
        print "JO: ParseAll not implemented"
        return

    
    

class TestJOCollection(unittest.TestCase):
    baseDir = "testdata"
    def testDownloadAll(self):
        c = JODownloader(self.baseDir)
        c.DownloadAll()
        # FIXME: come up with some actual tests

    def testParse(self):
        p = JOParser("1997-2944", "testdata/jo/downloaded/1997-2944.html", self.baseDir)
        p.parse()
        # FIXME: come up with actual test (like comparing the
        # resulting XML file to a known good file)
        
if __name__ == "__main__":
    # unittest.main()
    suite = unittest.defaultTestLoader.loadTestsFromName("JO.TestJOCollection.testDownloadAll")
    unittest.TextTestRunner(verbosity=2).run(suite)
