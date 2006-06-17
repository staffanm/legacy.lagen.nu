#!/sw/bin/python
# -*- coding: iso-8859-1 -*-
"""Hanterar författningar i SFS från Regeringskansliet rättsdatabaser.
"""
import sys, os, re
import shutil
import unittest
import pprint
import types
import datetime
import LegalSource
import Util
from DispatchMixin import DispatchMixin

sys.path.append('3rdparty')
import BeautifulSoup
import elementtree.ElementTree as ET

__version__ = (0,1)
__author__  = "Staffan Malmgren <staffan@tomtebo.org>"
__shortdesc__ = "Författningar i SFS"
__moduledir__ = "sfs"

class SFSDownloader(LegalSource.Downloader):
    def __init__(self,baseDir="data"):
        self.dir = baseDir + "/%s/downloaded" % __moduledir__
        if not os.path.exists(self.dir):
            Util.mkdir(self.dir)
        self.ids = {}
    
    def DownloadAll(self):
        pass

    def DownloadNew(self):
        pass


class SFSParser(LegalSource.Parser):
    def parse(self):
        pass

class SFSManager(LegalSource.Manager):
    def _SFSidToFilename(self,sfsid):
        """converts a SFS id to a filename, sans suffix, eg: '1909:bih. 29
        s.1' => '1909/bih._29_s.1'. Returns None if passed an invalid SFS
        id."""
        if sfsid.find(":") < 0: return None
        return re.sub(r'([A-Z]*)(\d{4}):',r'\2/\1',sfsid.replace(' ', '_'))

    def _filenameToSFSid(self,filename):
        """converts a filename, sans suffix, to a sfsid, eg:
        '1909/bih._29_s.1' => '1909:bih. 29 s.1'"""
        (dir,file)=filename.split("/")
        if file.startswith('RFS'):
            return re.sub(r'(\d{4})/([A-Z]*)(\d*)',r'\2\1:\3', filename.replace('_',' '))
        else:
            return re.sub(r'(\d{4})/(\d*)',r'\1:\2', filename.replace('_',' '))

    def generate(self,id):
        indir = "%s/%s/parsed" % (self.baseDir, __moduledir__)
        outdir = "%s/%s/generated" % (self.baseDir, __moduledir__)
        infile = "%s/%s.xml" % (indir,self._SFSidToFilename(id))
        outfile = "%s/%s.html" % (outdir,self._SFSidToFilename(id))
        sanitized_sfsid = id.replace(' ','.')
        Util.transform("xsl/sfs.xsl",
                       infile,
                       outfile,
                       {'lawid': sanitized_sfsid,
                        'today':datetime.date.today().strftime("%Y-%m-%d")},
                       validate=False)
        
if __name__ == "__main__":
    SFSManager.__bases__ += (DispatchMixin,)
    mgr = SFSManager("testdata")
    mgr.dispatch()
