#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Hanterar lagförarbeten från Regeringskansliet (SOU/Ds och propositioner)

Modulen laddar ner publikationer och konverterar till XML
"""
# From python stdlib
import sys
import os
import re
import shutil
import urllib
import unittest
import pprint
import types
import xml.etree.cElementTree as ET # Python 2.5 spoken here

# 3rd party modules
import BeautifulSoup
from genshi.template import TemplateLoader

# My own stuff
import LegalSource
import Util
import Robot
from DispatchMixin import DispatchMixin


__version__ = (0,1)
__author__  = "Staffan Malmgren <staffan@tomtebo.org>"
__shortdesc__ = "Förarbeten (SOU/Ds/Prop)"
__moduledir__ = "regpubl"

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
        node = soup.find("div", id="content")
        
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
    #def __init__(self,baseDir):
    #    self.id = id
    #    self.dir = baseDir + "/regpubl/parsed"
    #    if not os.path.exists(self.dir):
    #        Util.mkdir(self.dir)
    #    self.files = files

    def Parse(self, id, files):
        # FIXME: extract relevant data from the HTML page
        # soup = self.LoadDoc(files['html'][0])

        text = ""
        for f in files['pdf']:
            # create a tmp textfile 
            outfile = f.replace(".pdf",".txt").replace("downloaded","intermediate")
            Util.ensureDir(outfile)
            cmd = "pdftotext -layout %s %s" % (f, outfile)
            print "Running %s" % cmd
            (ret,stdout,stderr) = Util.runcmd(cmd)
            if (ret != 0):
                print "ERROR"
                print stderr
            text += open(outfile).read()
        lines = text.split("\n")

        body = makeProp(lines)

    def makeRapport(lines):
        pass

    def makeAvdelning(lines):
        pass

    # En propositions struktur (jfr även PDF-bookmarkshiearkin
    #
    # Rubrik / Överlämnande / Propositionens huvudsakliga innnehåll
    # Innehållsförteckning
    # Avdelningar
    #   Underavdelning
    #     Underunderavdelning
    # Bilagor
    # Utdrag ur protokoll vid regeringssammanträde
    # Rättsdatablad


class RegPublManager(LegalSource.Manager):

    def _getModuleDir(self):
        return __moduledir__

    def Download(self,id):
        rd = RegPublDownloader(self.baseDir)
        rd._downloadSingle("http://www.regeringen.se/sb/d/108/a/%s" % id)

    def DownloadAll(self):
        print "RegPubl: DownloadAll not implemented"

    def __listfiles(self,basefile,suffix):
        d = "%s/%s/downloaded/%s" % (self.baseDir,__moduledir__,basefile)
        return Util.listDirs(d, suffix)
        
    def Parse(self, basefile):
        # create something like
        # {'html':['testdata/regpubl/downloaded/60809/index.html'],
        #  'pdf': ['testdata/regpubl/downloaded/60809/2c0a24ce.pdf']}
        files = {'html':list(self.__listfiles(basefile,'.html')),
                 'pdf':list(self.__listfiles(basefile,'.pdf'))}
        print files
        rp = RegPublParser()
        rp.Parse(basefile,files)
    
    def ParseAll(self):
        print "RegPubl: ParseAll not implemented"
        return

    def IndexAll(self):
        print "RegPubl: IndexAll not implemented"
        return
    
    def GenerateAll(self):
        print "RegPubl: GenerateAll not implemented"
        return

    def RelateAll(self):
        print "RegPubl: ParseAll not implemented"
        return
        

class TestRegPublCollection(unittest.TestCase):
    baseDir = "testdata"
    def testParse(self):
        pass

                
if __name__ == "__main__":
    # unittest.main()
    RegPublManager.__bases__ += (DispatchMixin,)
    mgr = RegPublManager("testdata",__moduledir__)
    mgr.Dispatch(sys.argv)
