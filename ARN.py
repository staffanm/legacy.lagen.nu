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
import Robot

sys.path.append('3rdparty')
import BeautifulSoup


__version__ = (0,1)
__author__ = "Staffan Malmgren <staffan@tomtebo.org>"

class LegalSourceCollection:
    """Abstract base class for a collection of related legal source documents (statues, cases, etc)."""
    
    def GetIDs():
        """Should return a iterable of some kind that produces string IDs in no particular order"""
        raise NotImplementedError

    def Update():
        raise NotImplementedError 

    def Get(self,id):
        raise NotImplementedError

    def ConvertAll(self):
        for id in self.GetIDs():
            obj = self.Get(id)
            obj.Convert()

class LegalSource:
    """Abstract base class for a legal source document"""
    def __init__(self,baseDir):
        pass
    
    
class ARNCollection(LegalSourceCollection):
    
    def __init__(self,baseDir="data/arn"):
        self.baseDir = baseDir
        self.ids = {}
    
    def GetIDs(self):
        """Returnerar en osorterad lista av avgörande-IDs (diarienummer)"""
        # we should think about clearing (part of) the cache here, or make noncached requests 
        # --  a stale index page would not be good. Alternatively just request descisions for the
        # current year or similar.
        
        # this idiom of getting a first page of results, then iterating until there is no more 
        # "next" links, is common - think about refactoring it to a superclass method
        html = Robot.Get("http://www.arn.se/netacgi/brs.pl?d=REFE&l=20&p=1&u=%2Freferat.htm&r=0&f=S&Sect8=PLSCRIPT&s1=%40DOCN&s2=&s3=&s4=&s5=&s6=")
        soup = BeautifulSoup.BeautifulSoup(html)
        self._extractIDs(soup)
        nexttags = soup.first('img', {'src' : '/netaicon/nxtlspg.gif'})
        
        while nexttags:
            nexturl = "http://www.arn.se" + nexttags.parent['href']
            html = Robot.Get(nexturl)
            soup = BeautifulSoup.BeautifulSoup(html)
            self._extractIDs(soup)
            nexttags = soup.first('img', {'src' : '/netaicon/nxtlspg.gif'})
        
        return self.ids.keys()

    def _extractIDs(self,soup):
        for tag in soup('a', {'href': re.compile(r'/netacgi/brs.pl.*f=G')}):
            id = tag.string
            url = tag['href']
            if id != "Ärendenummer saknas":
                if id in self.ids:
                    print "WARNING: replacing URL of id '%s' to '%s' (was '%s')" % (id, url, self.ids[id])
                self.ids[id] = url
      
    def Update(self):
        """Hämtar eventuellt nytillkommna avgöranden"""
        
    def Get(self,id):
        return ARNDescision(id, baseDir=self.baseDir)
        

class TestARNCollection(unittest.TestCase):
    def testGetIDs(self):
        c = ARNCollection(baseDir="testdata/arn")
        import pprint
        pprint.pprint(c.GetIDs())
        
    
if __name__ == "__main__":
    unittest.main()

    
    