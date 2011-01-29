#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

import sys,os,re,datetime

from DocumentRepository import DocumentRepository
import Util

from mechanize import LinkNotFoundError

class DirTrips(DocumentRepository):
    module_dir = "dir-trips"

    # It's possible to alter the ${MAXPAGE} parameter to get a page
    # with all 3000+ documents. We don't do that, though. It's mean.
    start_url = "http://62.95.69.15/cgi-bin/thw?${HTML}=dir_lst&${OOHTML}=dir_dok&${SNHTML}=dir_err&${MAXPAGE}=26&${TRIPSHOW}=format=THW&${BASE}=DIR"

    # %s can be either on the form "Dir. 2010:51" or just
    # %"2010:52". remote_url is adapted to this.
    document_url = "http://62.95.69.15/cgi-bin/thw?${APPL}=DIR&${BASE}=DIR&${HTML}=dir_dok&${TRIPSHOW}=format=THW&BET=%s"

    source_encoding = "iso-8859-1"

    def download_everything(self,usecache=False):
        self.log.info("Starting at %s" % self.start_url)
        self.browser.open(self.start_url)
        done = False
        pagecnt = 1
        while not done:
            self.log.info(u'Result page #%s' % pagecnt)
            for link in self.browser.links(text_regex=r'(\d{4}:\d+)$'):
                basefile = link.text
                if basefile.startswith("Dir. "):
                    basefile = basefile[5:]
                url = self.document_url % link.text
                self.download_single(basefile,usecache=usecache)
            try:
                self.browser.follow_link(text='Fler poster')
                pagecnt += 1
            except LinkNotFoundError:
                log.info(u'No next page link found, this was the last page')
                done = True

    def remote_url(self,basefile):
        (year,number) = [int(x) for x in basefile.split(":")]
        if (year > 2010 or (year == 2010 and number >= 52)):
            basefile = "Dir.%20" + basefile
        return self.document_url % basefile

    
    
if __name__ == "__main__":
    DirTrips.run()
        

