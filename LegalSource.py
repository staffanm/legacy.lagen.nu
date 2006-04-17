#!/usr/local/bin/python
# -*- coding: iso-8859-1 -*-
"""Base classes for Downloaders and Parsers."""
import sys, os
class LegalSourceDownloader:
    TIME_FORMAT = "%Y-%m-%d %H:%M:%S %Z"
    """Abstract base class for downloading legal source documents
    (statues, cases, etc).

    Apart from naming the resulting files, and constructing a
    index.xml file, subclasses should do as little modification to the
    data as possible."""

    # http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/82465
    def _mkdir(self,newdir):
        """works the way a good mkdir should :)
        - already exists, silently complete
        - regular file in the way, raise an exception
        - parent directory(ies) does not exist, make them as well
        """
        if os.path.isdir(newdir):
            pass
        elif os.path.isfile(newdir):
            raise OSError("a file with the same name as the desired " \
                          "dir, '%s', already exists." % newdir)
        else:
            head, tail = os.path.split(newdir)
            if head and not os.path.isdir(head):
                self._mkdir(head)
            #print "_mkdir %s" % repr(newdir)
            if tail:
                os.mkdir(newdir)

    def DownloadAll():
        raise NotImplementedError
    
    def DownloadNew():
        raise NotImplementedError

class LegalSourceParser:
    """Abstract base class for a legal source document"""
    def __init__(self,baseDir):
        pass
    

class DownloadedResource:
    def __init__(self,id,url=None,localFile=None,fetched=None):
        self.id, self.url, self.localFile, self.fetched = id,url,localFile,fetched
