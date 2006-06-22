#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Hanterar lagförarbeten från Regeringskansliet (SOU/Ds och propositioner)

Modulen laddar ner publikationer och konverterar till XML
"""
import sys
import os
import re
import shutil
import urllib
import unittest
import pprint
import types
import LegalSource
import Util
import Robot

sys.path.append('3rdparty')
import BeautifulSoup
import elementtree.ElementTree as ET

__version__ = (0,1)
__author__  = "Staffan Malmgren <staffan@tomtebo.org>"
__shortdesc__ = "Förarbeten (SOU/Ds/Prop)"


class RegPublDownloader(LegalSource.Downloader):
    
    def __init__(self,baseDir="data"):
        self.dir = baseDir + "/regpubl/downloaded"
        if not os.path.exists(self.dir):
            Util.mkdir(self.dir)
        self.ids = {}
    
    def DownloadAll(self):
        self._downloadSingle("http://www.regeringen.se/sb/d/108/a/58696")

    def DownloadNew(self):
        pass
        
    def _downloadSingle(self,url):
        id = re.match(r'http://www.regeringen.se/sb/d/108/a/(\d+)', url).group(1)
        print "id is %s " %id
        f = Robot.Store(url,r'http://www.regeringen.se/sb/d/108/a/(\d+)',r'%s/\1/index.html'%self.dir)
        soup = self.loadDoc(f)
        node = soup.find("div", "articleContent")
        
        for n in node.findAll(True,'pdf'):
            tmpurl = urllib.basejoin(url,n.a['href'].replace("&amp;","&"))
            filename = re.match(r'http://www.regeringen.se/download/(\w+\.pdf).*',tmpurl).group(1)
            # note; the url goes to a redirect script; however that
            # part of the URL tree (/download/*) is off-limits for
            # robots. But we can figure out the actual URL anyway!
            if len(id) > 4:
                path = "c6/%02d/%s/%s" % (int(id[:-4]),id[-4:-2],id[-2:])
            else:
                path = "c4/%02d/%s" % (int(id[:-2]),id[-2:])
            fileurl = "http://regeringen.se/content/1/%s/%s" % (path,filename)
            
            print "downloading %s" % fileurl
            df = Robot.Store(fileurl,None,f.replace("index.html",filename))
            # print "stored at %s" % df
            
class RegPublParser(LegalSource.Parser):
    def __init__(self,id,files,baseDir):
        self.id = id
        self.dir = baseDir + "/regpubl/parsed"
        if not os.path.exists(self.dir):
            Util.mkdir(self.dir)
        self.files = files

    def Parse(self):
        soup = self.loadDoc("/regpubl/downloaded/%s/index.html")
        node = soup.find("div", "articleContent")
        # first, create metadata-XML from the HTML index page
        for n in node.findAll(True,'publicationInfoBoxTextLeft'):
            key = self.elementText(n)
            val = self.elementText(n.findNextSibling(True,'publicationInfoBoxTextRight'))
        # secondly, create plaintext-in-a-XML-wrapper for the actual documents
        for f in files.values():
            Util.runcmd("pdftotext -layout %s > %s/%s.txt" % f, self.dir,
                        os.path.splitext(os.path.basename(f))[0])



class RegPublManager(LegalSource.Manager):

    def download(self,id):
        rd = RegPublDownloader(self.baseDir)
        rd._downloadSingle("http://www.regeringen.se/sb/d/108/a/%s" % id)
        
    def parseAll(self):
        downloadDir = self.baseDir + "/regpubl/downloaded"
        for f in Util.numsort(os.listdir(downloadDir)):
            pass

class TestRegPublCollection(unittest.TestCase):
    baseDir = "testdata"
    def testParse(self):
        pass

                
if __name__ == "__main__":
    # unittest.main()
    mgr = RegPublManager("testdata")
    mgr.run(sys.argv)
