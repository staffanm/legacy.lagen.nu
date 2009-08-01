#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Hanterar referat från Allmäna Reklamationsnämnden, www.arn.se.

Modulen hanterar hämtande av referat från ARNs webbplats, omvandlande
av dessa till XHTML2/RDFa, samt transformering till browserfärdig
XHTML1.
"""
import unittest
import sys
import time
import re
import os
import urllib
import xml.etree.cElementTree as ET # Python 2.5 spoken here
import logging
from datetime import datetime
from time import time
from tempfile import mktemp
from pprint import pprint
from collections import defaultdict

# 3rd party
import BeautifulSoup
from mechanize import Browser, LinkNotFoundError, urlopen
from rdflib import Namespace

# My own stuff
import LegalSource
import Util
from LegalRef import LegalRef,ParseError,Link,LinkSubject
from DispatchMixin import DispatchMixin
from DataObjects import UnicodeStructure, CompoundStructure, \
     MapStructure, IntStructure, DateStructure, PredicateType, \
     serialize

__version__   = (0,1)
__author__    = u"Staffan Malmgren <staffan@tomtebo.org>"
__shortdesc__ = u"Referat från ARN"
__moduledir__ = "arn"
log = logging.getLogger(__moduledir__)
if not os.path.sep in __file__:
    __scriptdir__ = os.getcwd()
else:
    __scriptdir__ = os.path.dirname(__file__)


class UnicodeSubject(PredicateType,UnicodeStructure): pass
class Stycke(CompoundStructure): pass

class ARNDownloader(LegalSource.Downloader):
    
    def __init__(self,config):
        super(ARNDownloader,self).__init__(config)

    def _get_module_dir(self):
        return __moduledir__
    
    def DownloadAll(self):
        self.__download("http://www.arn.se/netacgi/brs.pl?d=REFE&l=20&p=1&u=%2Freferat.htm&r=0&f=S&Sect8=PLSCRIPT&s1=%40DOCN&s2=&s3=&s4=&s5=&s6=")
        
    def DownloadNew(self):
        self.__download("http://www.arn.se/netacgi/brs.pl?d=REFE&l=20&p=1&u=%2Freferat.htm&r=0&f=S&Sect8=PLSCRIPT&s1=&s2=&s3=&s4=&s5=" + str(datetime.now().year) +"*&s6=")

    def __download(self,url):
        log.debug("Opening %s" % url)
        self.browser.open(url)
        done = False
        pagecnt = 1
        while not done:
            log.info("Result page #%s" % pagecnt)
            for l in (self.browser.links(text_regex=r'\d+-\d+')):
                basefile = l.text.replace("-", "/")
                filename = "%s/%s.html" % (self.download_dir, basefile)
                if not os.path.exists(filename):
                    log.info("    Fetching %s" % basefile)
                    Util.ensureDir(filename)
                    self.browser.retrieve(l.absolute_url,filename)
                    self.download_log.info(basefile)
                    self.browser.retrieve(l.absolute_url,filename)
            try:
                self.browser.follow_link(predicate=lambda x: x.text == '[NEXT_LIST][IMG]')
                pagecnt += 1
            except LinkNotFoundError:
                log.info(u'No next page link found, we must be done')
                done = True

class ARNParser(LegalSource.Parser):

    def Parse(self,basefile,files):
        parser = LegalRef(LegalRef.LAGRUM, LegalRef.EGLAGSTIFTNING, LegalRef.FORARBETEN)
        DCT = Namespace(Util.ns['dct'])
        RINFO = Namespace(Util.ns['rinfo'])
        RINFOEX = Namespace(Util.ns['rinfoex'])
        self.id = basefile
        import codecs
        soup = Util.loadSoup(files['main'][0])

        # FIXME: Create a better URI pattern
        meta = {'xml:base': "http://rinfo.lagrummet.se/publ/arn/%s" % basefile.replace("/","-")}
        meta[u'Ärendenummer'] = UnicodeSubject(soup.first('h2').b.i.string.strip(),
                                               predicate=RINFOEX['arendenummer'])
        meta['dct:identifier'] = "ARN %s" % meta[u'Ärendenummer']
        # maybe this should be a dct:description?
        meta[u'Rubrik'] = UnicodeSubject(soup.first('h3').string.strip(),
                                         predicate=DCT['description'])
        meta[u'Ärendemening'] = UnicodeSubject(soup.firstText(u"Ärendemening: ").parent.parent.parent.parent.contents[1].string.strip(),
                                               predicate=DCT['subject'])
        meta[u'Avdelning'] = UnicodeSubject(Util.elementText(soup.firstText('Avdelning: ').parent.parent.parent.parent.contents[1]).strip(),
                                            predicate=RINFOEX['avdelning'])
        meta[u'Beslutsdatum'] = UnicodeSubject(Util.elementText(soup.firstText('Beslutsdatum: ').parent.parent.parent.parent.contents[1]).strip(),
                                              predicate=RINFO['beslutsdatum'])
                                            
        meta[u'Beslut'] = UnicodeSubject(soup.firstText('Beslut: ').parent.parent.parent.parent.contents[1].string.strip(),
                                        predicate=RINFOEX['beslutsutfall'])
                                         
        node = soup.firstText('Referat:').parent.parent.parent.nextSibling.nextSibling

        body = []
        while node and node.name == 'p':
            #if node.string:
            body.append(Stycke(parser.parse(Util.elementText(node), predicate="rinfo:lagrum")))
            node = node.nextSibling

        xhtml = self.generate_xhtml(meta, body, None, __moduledir__, globals())
        return xhtml

class ARNManager(LegalSource.Manager):
    __parserClass = ARNParser
    def DownloadAll(self):
        ad = ARNDownloader(self.config)
        ad.DownloadAll()
        pass
       
    def DownloadNew(self):
        ad = ARNDownloader(self.config)
        ad.DownloadNew()
        pass

    def Parse(self,basefile):
        # almost generic code - could be moved to LegalSource
        start = time()
        infile  = os.path.sep.join([self.baseDir, __moduledir__, 'downloaded', basefile]) + ".html"
        outfile = os.path.sep.join([self.baseDir, __moduledir__, 'parsed',     basefile]) + ".xht2"
        
        force = (self.config[__moduledir__]['parse_force'] == 'True')
        if not force and self._outfile_is_newer([infile],outfile):
            log.debug(u"%s: Skipping", basefile)
            return

        p = self.__parserClass()
        parsed = p.Parse(basefile,{'main':[infile]})
        Util.ensureDir(outfile)
        tmpfile = mktemp()
        out = file(tmpfile, "w")
        out.write(parsed)
        out.close()
        Util.indentXmlFile(tmpfile)
        Util.replace_if_different(tmpfile,outfile)
        log.info(u'%s: OK (%.3f sec)', basefile,time()-start)
        
    def _file_to_basefile(self,f):
        """Given a full physical filename, transform it into the
        logical id-like base of that filename, or None if the filename
        shouldn't be processed."""
    
        return "/".join(os.path.split(os.path.splitext(os.sep.join(os.path.normpath(f).split(os.sep)[-2:]))[0]))


    def Generate(self,basefile):
        # Generic code (except "xsl/arn.xsl" - could be moved to LegalSource)
        infile = self._xmlFileName(basefile)
        outfile = self._htmlFileName(basefile)

        force = (self.config[__moduledir__]['generate_force'] == 'True')
        if not force and self._outfile_is_newer([infile], outfile):
            log.debug(u"%s: Överhoppad", basefile)
            return
        Util.mkdir(os.path.dirname(outfile))
        log.info(u'Transformerar %s > %s' % (infile,outfile))
        Util.transform("xsl/arn.xsl",
                       infile,
                       outfile,
                       {},
                       validate=False)

    def _get_module_dir(self):
        return __moduledir__
    
    def _build_indexpages(self, by_pred_obj, by_subj_pred):
        documents = defaultdict(lambda:defaultdict(list))
        pagetitles = {}
        pagelabels = {}

        date_pred = Util.ns['rinfo']+'beslutsdatum'
        id_pred =   Util.ns['dct']+'identifier'
        desc_pred = Util.ns['dct']+'description'
        category = u'Efter år' # just one categeory for now

        # ['beslutsdatum']['2008-302-32'] = [sub1 sub2]

        for obj in by_pred_obj[date_pred]:
            label = category
            year = obj.split("-")[0]
            for subj in by_pred_obj[date_pred][obj]:
                identifier = by_subj_pred[subj][id_pred]
                desc = by_subj_pred[subj][desc_pred]
                if len(desc) > 80:
                    desc = desc[:80].rsplit(' ',1)[0]+'...'
                pageid = '%s' % year
                pagetitles[pageid] = u'Beslut från Allmänna Reklamationsnämnden under %s' % year
                pagelabels[pageid] = year
                documents[label][pageid].append({'uri':subj,
                                                 'sortkey':identifier,
                                                 'title':identifier,
                                                 'trailer':' '+desc[:80]})

        outfile = "%s/%s/generated/index/index.html" % (self.baseDir, self.moduleDir)
        if '%d' % (datetime.today().year) in pagetitles:
            pageid = '%d' % (datetime.today().year)
        else:
            # handles the situation in january, before any verdicts
            # for the new year is available
            pageid = '%d' % (datetime.today().year-1) 
        title = pagetitles[pageid]
        self._render_indexpage(outfile,title,documents,pagelabels,category,pageid,docsorter=Util.numcmp)


        for category in documents.keys():
            for pageid in documents[category].keys():
                outfile = "%s/%s/generated/index/%s.html" % (self.baseDir, self.moduleDir, pageid)
                title = pagetitles[pageid]
                self._render_indexpage(outfile,title,documents,pagelabels,category,pageid,docsorter=Util.numcmp)


if __name__ == "__main__":
    import logging.config
    logging.config.fileConfig(__scriptdir__ + '/etc/log.conf')
    ARNManager.__bases__ += (DispatchMixin,)
    mgr = ARNManager()
    mgr.Dispatch(sys.argv)
    
    
    
