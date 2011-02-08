#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# A number of different classes each fetching the same data from
# different sources
import sys,os,re,datetime
import urllib
import urlparse
import logging

from mechanize import LinkNotFoundError
import BeautifulSoup
from rdflib import Literal, Namespace, URIRef, RDF, RDFS

from DocumentRepository import DocumentRepository
import Util

class DirTrips(DocumentRepository):
    module_dir = "dir-trips"

    # It's possible to alter the ${MAXPAGE} parameter to get a page
    # with all 3000+ documents. We don't do that, though. It's mean.
    start_url = "http://62.95.69.15/cgi-bin/thw?${HTML}=dir_lst&${OOHTML}=dir_dok&${SNHTML}=dir_err&${MAXPAGE}=26&${TRIPSHOW}=format=THW&${BASE}=DIR"

    # %s can be either on the form "Dir. 2010:51" or just
    # "2010:52". We calculate the URL based on what is listed in the
    # search result, using the optional url parameter to
    # download_single
    document_url = "http://62.95.69.15/cgi-bin/thw?${APPL}=DIR&${BASE}=DIR&${HTML}=dir_dok&${TRIPSHOW}=format=THW&BET=%s"

    source_encoding = "iso-8859-1"

    def download_everything(self,usecache=False):
        self.log.info("Starting at %s" % self.start_url)
        self.browser.open(self.start_url)
        done = False
        pagecnt = 1
        while not done:
            self.log.info(u'Result page #%s' % pagecnt)
            for link in self.browser.links(text_regex=r'(\d{4}:\d+)'):
                basefile = re.search('(\d{4}:\d+)',link.text).group(1)
                url = self.document_url % urllib.quote(link.text)
                self.download_single(basefile,usecache=usecache,url=url)
            try:
                self.browser.follow_link(text='Fler poster')
                pagecnt += 1
            except LinkNotFoundError:
                self.log.info(u'No next page link found, this was the last page')
                done = True
    
class DirAsp(DocumentRepository):
    module_dir = "dir-asp"

    start_url = "http://62.95.69.24/search.asp"

    # eg http://62.95.69.24/KOMdoc/06/060128.PDF
    document_url = "http://62.95.69.24/KOMdoc/%s.PDF"

    source_encoding = "iso-8859-1"

    browser_use_robustfactory = True
    
    def download_everything(self,usecache=False,startyear=2006):
        self.log.info("Starting at %s" % self.start_url)
        self.browser.open(self.start_url)
        done = False
        pagecnt = 1
        for y in range(startyear,datetime.datetime.today().year+1):
            self.browser.select_form(nr=0)
            self.browser["kom_nr"] = "%d:*" % y
            self.browser["title"] = ""
            self.browser.submit()
            for link in self.browser.links(text_regex=r'(\d{4}:\d+)'):
                # convert 2006:02 to 2006:2 for consistency
                segments = re.search("(\d+):(\d+)",link.text).groups()
                basefile = ":".join([str(int(x)) for x in segments])
                # we use link.absolute_url rather than relying on our
                # own basefile -> url code in remote_url. It seems
                # that in least one case the URL formatting rule is
                # not followed by the system...
                self.download_single(basefile,usecache=usecache,url=link.absolute_url)
            self.browser.back()

    def remote_url(self,basefile):
        yy = int(basefile[2:4])
        num = int(basefile[5:])
        segment = "%02d/%02d%04d" % (yy,yy,num)
        return self.document_url % segment

    def downloaded_path(self,basefile):
        return self.generic_path(basefile,u'downloaded','.pdf')

class DirSou(DocumentRepository):
    module_dir= "dir-sou"
    start_url="http://www.sou.gov.se/direktiv.htm"
    document_url="http://www.sou.gov.se/kommittedirektiv/%s.pdf"
    basefile_template="\d{4}:\d+"
    
    # this is a common case -- can we generalize? By looking at self.document_url?
    def downloaded_path(self,basefile):
        return self.generic_path(basefile,u'downloaded','.pdf')

    # just to make download_single works in standalone mode (where a
    # URL is not provided)
    def remote_url(self,basefile):
        (year,num) = basefile.split(":")
        segment = "%s/dir%s_%s" % (year,year,num)
        return self.document_url % segment

from Regeringen import Regeringen
class DirPolopoly(Regeringen):
    module_dir = "dir-polo"
    re_basefile_strict = re.compile(r'Dir\. (\d{4}:\d+)')
    re_basefile_lax = re.compile(r'(?:[Dd]ir\.?|) ?(\d{4}:\d+)')

    def __init__(self,options):
        super(DirPolopoly,self).__init__(options) 
        self.document_type = self.KOMMITTEDIREKTIV
    
if __name__ == "__main__":
    if sys.argv[1] == "trips":
        DirTrips.run(sys.argv[2:])
    elif sys.argv[1] == "asp":
        DirAsp.run(sys.argv[2:])
    elif sys.argv[1] == "sou":
        DirSou.run(sys.argv[2:])
    elif sys.argv[1] == "polo":
        DirPolopoly.run(sys.argv[2:])
    else:
        DirTrips.run()
        

