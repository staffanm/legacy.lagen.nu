#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

import sys,os,re,datetime

from DocumentRepository import DocumentRepository
import Util

from mechanize import LinkNotFoundError

class DirTrips(DocumentRepository):
    module_dir = "dir-asp"

    start_url = "http://62.95.69.24/search.asp"

    # eg http://62.95.69.24/KOMdoc/06/060128.PDF
    document_url = "http://62.95.69.24/KOMdoc/%s.PDF"

    source_encoding = "iso-8859-1"

    def download_everything(self,usecache=False,startyear=2006):
        self.log.info("Starting at %s" % self.start_url)
        self.browser.open(self.start_url)
        done = False
        pagecnt = 1
        for y in range(startyear,datetime.today().year+1):
            self.browser.select_form(nr=0)
            self.browser["kom_nr"] = "%d:*" % y
            self.browser.submit()
            for link in self.browser.links(text_regex=r'(\d{4}:\d+)'):
                print link.text
                print link.absolute_url
                basefile = re.search("(\d+:\d+)",link.text).group(0)
                self.download_single(basefile,usecache=usecache)

    def remote_url(self,basefile):
        pass

    
    
if __name__ == "__main__":
    DirTrips.run()
        

