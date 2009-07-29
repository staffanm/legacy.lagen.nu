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
import logging
import datetime

# 3rd party modules
from genshi.template import TemplateLoader
from configobj import ConfigObj
from mechanize import Browser, LinkNotFoundError

# My own stuff
import LegalSource
import Util
from DispatchMixin import DispatchMixin
from TextReader import TextReader
from DataObjects import UnicodeStructure, CompoundStructure, serialize

__version__   = (0,1)
__author__    = u"Staffan Malmgren <staffan@tomtebo.org>"
__shortdesc__ = u"Förarbeten (SOU/Ds/Prop)"
__moduledir__ = "regpubl"
log = logging.getLogger(__moduledir__)

class RegPublDownloader(LegalSource.Downloader):
    
    def __init__(self,baseDir="data"):
        self.dir = baseDir + "/regpubl/downloaded"
        if not os.path.exists(self.dir):
            Util.mkdir(self.dir)
        self.config = ConfigObj("%s/%s.ini" % (self.dir, __moduledir__))

        # Why does this say "super() argument 1 must be type, not classobj"
        # super(RegPublDownloader,self).__init__()
        self.browser = Browser()
    
    def DownloadAll(self):
        # we use mechanize instead of our own Robot class to list
        # available documents since we can't get the POST/cookie based
        # search to work.
        doctype = '160'
        log.info(u'Selecting documents of type %s' % doctype)
        self.browser.open("http://www.regeringen.se/sb/d/108/action/browse/c/%s" % doctype)
        log.info(u'Posting search form')
        self.browser.select_form(nr=1)
        self.browser.submit()

        pagecnt = 1
        done = False
        while not done:
            log.info(u'Result page #%s' % pagecnt)
            for l in self.browser.links(url_regex=r'/sb/d/108/a/\d+'):
                self._downloadSingle(l.absolute_url)
                self.browser.back()
            try:
                self.browser.find_link(text='N\xe4sta sida')
                self.browser.follow_link(text='N\xe4sta sida')
            except LinkNotFoundError:
                log.info(u'No next page link found, this was the last page')
                done = True
            pagecnt += 1
        self.config['last_update'] = datetime.date.today()    
        self.config.write()
        
    def DownloadNew(self):
        if 'last_update' in self.config:
            then = datetime.datetime.strptime(self.config['last_update'], '%Y-%m-%d')
        else:
            # assume last update was more than a year ago
            then = datetime.datetime.now() - datetime.timedelta(-367)
        
        now =  datetime.datetime.now()
        if (now - then).days > 30:
            pass
            # post a "last 30 days" query
        elif (now - then).days > 365:
            pass
            # post a "last 12 months" query
        else:
            # post a full query
            self.DownloadAll()        
        
    def _downloadSingle(self,url):
        docid = re.match(r'http://www.regeringen.se/sb/d/108/a/(\d+)', url).group(1)

        fname = "%s/%s/index.html" % (self.dir, docid)
        log.info(u'    Loading docidx %s' % url)
        self.browser.open(url)
        if not os.path.exists(fname):
            Util.ensureDir(fname)
            self.browser.retrieve(url,fname)
        
        for l in self.browser.links(url_regex=r'/download/(\w+\.pdf).*'):
            filename = re.match(r'http://www.regeringen.se/download/(\w+\.pdf).*',l.absolute_url).group(1)
            # note; the url goes to a redirect script; however that
            # part of the URL tree (/download/*) is off-limits for
            # robots. But we can figure out the actual URL anyway!
            if len(docid) > 4:
                path = "c6/%02d/%s/%s" % (int(docid[:-4]),docid[-4:-2],docid[-2:])
            else:
                path = "c4/%02d/%s" % (int(docid[:-2]),docid[-2:])
            fileurl = "http://regeringen.se/content/1/%s/%s" % (path,filename)
            
            df = "%s/%s/%s" % (self.dir,docid, filename)
            if not os.path.exists(df):
                log.info(u'        Downloading %s' % (fileurl))
                self.browser.retrieve(fileurl, df)
            else:
                log.info(u'        Already downloaded %s' % (fileurl))

            
class RegPublParser(LegalSource.Parser):
    # Rättskällespecifika dataobjekt
    class Stycke(UnicodeStructure):
        pass

    class Avsnitt(CompoundStructure):
        pass
    
    class Forfattningskommentar(CompoundStructure):
        pass

    # FIXME: Flytta till LegalSource
    class Rattsinformationsdokument:
        # dessa properties utgår från rinfo:Rattsinformationsdokument i ESFR
        def __init__(self):
            self.title = '' # detta är en dc:title - strängliteral
            self.description = '' # detta är dc:description - strängliteral
            self.references = [] # detta är dct:resource - noll eller flera URI:er
            self.publisher = '' # detta är dc:publisher - en URI
            self.bilaga = []
            self.seeAlso # detta är rdfs:SeeAlso - noll eller flera URI:er
        
    class Proposition(Rattsinformationsdokument):
        # dessa properties utgår rinfo:Proposition i ESFR
        def __init__(self):
            self.propositionsnummer = u'' # Sträng på formen '2004/05:100'
            self.utgarFran = []           # (URI:er till) noll eller flera tidigare förarbeten (typiskt SOU/Ds:ar)
            self.foreslarAndringAv = []   # (URI:er till) noll eller flera lagar i sin grundform (möjligtvis även andra författningar)
            self.beslutsdatum = None

    class Utredningsbetankande(Rattsinformationsdokument):
        # utgår från rinfo:Utredningsbetankande i ESFR
        def __init__(self):
            self.utgarFran = ''         # (URI:er till) ett komittedirektiv
            self.foreslarAndringAv = [] # (URI:er till) noll eller flera lagar i sin grundform (möjligtvis även andra författningar)
            self.utrSerienummer = ''    # exv '2003:12'
            self.utrSerie               # exv 'SOU'
            
            

        
            
            
    
    #def __init__(self,baseDir):
    #    self.id = id
    #    self.dir = baseDir + "/regpubl/parsed"
    #    if not os.path.exists(self.dir):
    #        Util.mkdir(self.dir)
    #    self.files = files

    def Parse(self, id, files):
        # FIXME: Plocka ut relevant information från HTLM-sidan (datum, departement, summering)
        # soup = self.LoadDoc(files['html'][0])

        text = ""
        for f in files['pdf']:
            # create a tmp textfile 
            outfile = f.replace(".pdf",".txt").replace("downloaded","intermediate")
            if not os.path.exists(outfile):
                Util.ensureDir(outfile)
                cmd = "pdftotext -layout %s %s" % (f, outfile)
                log.info(u'Running %s' % cmd)
                (ret,stdout,stderr) = Util.runcmd(cmd)
                if (ret != 0):
                    log.error(stderr)
            text += open(outfile).read()
        if len(files['pdf']) > 1:
            fulltextfile = os.path.dirname(files['pdf'][0]).replace("downloaded","intermediate") + "/fulltext.txt"
            fp = open(fulltextfile, "w")
            fp.write(text)
            fp.close()
        else:
            fulltextfile = files['pdf'][0]

        from time import time
        start = time()
        self.reader = TextReader(fulltextfile)
        log.info(u'Loaded %s in %s seconds\n' % (fulltextfile, time()-start))

        # FIXME: Anropa rätt konstruktor beroende på prop eller sou/ds
        body = makeProp()

    def makeProp(self):
        pass



    # En propositions struktur (jfr även PDF-bookmarkshiearkin)
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

    def _get_module_dir(self):
        return __moduledir__

    def Download(self,id):
        rd = RegPublDownloader(self.baseDir)
        rd._downloadSingle("http://www.regeringen.se/sb/d/108/a/%s" % id)

    def DownloadAll(self):
        rd = RegPublDownloader(self.baseDir)
        rd.DownloadAll()

    def DownloadNew(self):
        rd = RegPublDownloader(self.baseDir)
        rd.DownloadNew()


    def __listfiles(self,basefile,suffix):
        d = "%s/%s/downloaded/%s" % (self.baseDir,__moduledir__,basefile)
        return Util.listDirs(d, suffix)
        
    def Parse(self, basefile):
        # create something like
        # {'html':['testdata/regpubl/downloaded/60809/index.html'],
        #  'pdf': ['testdata/regpubl/downloaded/60809/2c0a24ce.pdf']}
        d = "%s/%s/downloaded/%s" % (self.baseDir,__moduledir__,basefile)
        indexfiles = list(self.__listfiles(basefile,'.html')) # can only be one

        # There can be multiple PDFs, so make sure they're in the right order
        soup = Util.loadSoup(indexfiles[0])
        pdfs = []
        for l in soup.findAll('a', href=re.compile(r'/download/(\w+\.pdf).*')):
            pdfname = re.match(r'/download/(\w+\.pdf).*',l['href']).group(1)
            pdfs.append(d + "/"+ pdfname)
                          
        log.info(u'pdfs: %r' % pdfs)
        files = {'html':indexfiles,
                 'pdf':pdfs}
        rp = RegPublParser()
        rp.Parse(basefile,files)
    
    def ParseAll(self):
        log.info(u'RegPubl: ParseAll not implemented')
        return

    def IndexAll(self):
        log.info(u'RegPubl: IndexAll not implemented')
        return
    
    def GenerateAll(self):
        log.info(u'RegPubl: GenerateAll not implemented')
        return

    def RelateAll(self):
        log.info(u'RegPubl: ParseAll not implemented')
        return
        

class TestRegPublCollection(unittest.TestCase):
    baseDir = "testdata"
    def testParse(self):
        pass

                
if __name__ == "__main__":
    # unittest.main()
    import logging.config
    logging.config.fileConfig('etc/log.conf')
    RegPublManager.__bases__ += (DispatchMixin,)
    mgr = RegPublManager()
    mgr.Dispatch(sys.argv)
