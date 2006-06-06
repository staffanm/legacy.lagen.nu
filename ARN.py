#!/usr/local/bin/python
# -*- coding: iso-8859-1 -*-
"""Hanterar referat från Allmäna Reklamationsnämnden, www.arn.se.

Modulen hanterar hämtande av referat från ARNs webbplats samt omvandlande av dessa till XML.

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


sys.path.append('3rdparty')
import BeautifulSoup
import elementtree.ElementTree as ET

__version__ = (0,1)
__author__ = "Staffan Malmgren <staffan@tomtebo.org>"
__shortdesc__ = "Referat från ARN"

class ARNDownloader(LegalSource.Downloader):
    
    def __init__(self,baseDir="data"):
        self.dir = baseDir + "/arn/downloaded"
        if not os.path.exists(self.dir):
            Util.mkdir(self.dir)
        self.ids = {}
    
    def DownloadAll(self):
        """Hämtar alla avgöranden"""
        # we should think about clearing (part of) the cache here, or
        # make noncached requests -- a stale index page would not be
        # good. Alternatively just request descisions for the current
        # year or similar.
        
        # this idiom of getting a first page of results, then
        # iterating until there is no more "next" links, is common -
        # think about refactoring it to a superclass method
        html = Robot.Get("http://www.arn.se/netacgi/brs.pl?d=REFE&l=20&p=1&u=%2Freferat.htm&r=0&f=S&Sect8=PLSCRIPT&s1=%40DOCN&s2=&s3=&s4=&s5=&s6=")
        soup = BeautifulSoup.BeautifulSoup(html)
        self._downloadDecisions(soup)
        nexttags = soup.first('img', {'src' : '/netaicon/nxtlspg.gif'})
        
        while nexttags:
            nexturl = urllib.basejoin("http://www.arn.se/",nexttags.parent['href'])
            html = Robot.Get(nexturl)
            soup = BeautifulSoup.BeautifulSoup(html)
            self._downloadDecisions(soup)
            nexttags = soup.first('img', {'src' : '/netaicon/nxtlspg.gif'})
            
        self._saveIndex()
        
    def DownloadNew(self):
        pass
        
    def _downloadDecisions(self,soup):
        for tag in soup('a', {'href': re.compile(r'/netacgi/brs.pl.*f=G')}):
            id = tag.string
            if id != "Ärendenummer saknas":
                url = "http://www.arn.se" + tag['href']
                filename = id + ".html"

                resource = DownloadedResource(id)
                resource.url = url
                resource.localFile = filename
                Robot.Store(url, None, self.dir + "/" + id + ".html")
                resource.fetched = time.localtime()
                if id in self.ids:
                    print "WARNING: replacing URL of id '%s' to '%s' (was '%s')" % (id, url, self.ids[id].url)
                self.ids[id] = resource

class ARNParser(LegalSource.Parser):

    def __init__(self,id,file,baseDir):
        self.id = id
        self.dir = baseDir + "/arn/parsed"
        if not os.path.exists(self.dir):
            Util.mkdir(self.dir)
        self.file = file
        print "Loading file %s" % file

    def parse(self):
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

class ARNManager(LegalSource.Manager):
    def __init__(self,baseDir):
        self.baseDir = baseDir

class TestARNCollection(unittest.TestCase):
    baseDir = "testdata"
    def testDownloadAll(self):
        c = ARNDownloader(self.baseDir)
        c.DownloadAll()
        # FIXME: come up with some actual tests

    def testParse(self):
        p = ARNParser("1997-2944", "testdata/arn/downloaded/1997-2944.html", self.baseDir)
        p.parse()
        # FIXME: come up with actual test (like comparing the
        # resulting XML file to a known good file)
        
if __name__ == "__main__":
    # unittest.main()
    suite = unittest.defaultTestLoader.loadTestsFromName("ARN.TestARNCollection.testParse")
    unittest.TextTestRunner(verbosity=2).run(suite)
    
    
    
