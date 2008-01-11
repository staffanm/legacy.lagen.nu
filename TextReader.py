#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

"""Fancy class for reading (not writing) text files. It can read files
in different encodings, but it gives you unicode, dammit"""

import os, mmap

class TextReader:
    UNIX = '\n'
    DOS = '\r\n'
    MAC = '\r'

    #----------------------------------------------------------------
    # Internal helper methods etc
    
    def __init__(self,name,encoding=None,linesep=None):

        # implementation of file attributes
        self.closed = False
        self.encoding = encoding
        self.mode = "r+"
        self.name = filename
        self.newlines = None
        self.softspace = 0


        # Other initialization
        if linesep:
            self.linesep = linesep
        else:
            self.linesep = os.linesep
        
        self.autostrip = False
        self.autodewrap = False
        self.autodehyphenate = False
        self.f = open(self.name,"r+")
        self.mmap = mmap.mmap(self.f.fileno(),0)
        self.current = 0
        self.lastread = u''

    def __find(self,delimiter,startpos):
        idx = self.mmap.find(delimiter, startpos)
        if idx == -1: # not found, read until eof
            res = self.mmap[startpos:]
            newpos = startpos + len(self.lastread)
        else: 
            res = self.mmap[startpos:idx]
            newpos = idx + len(delimiter)
        return (res,newpos)

    def __rfind(self,delimiter,startpos):
        # naive implementation of rfind, since mmap lacks that method...
        idx = startpos - len(delimiter)
        while ((self.mmap[idx:idx+len(delimiter)] != delimiter) and (idx > -1)):
            idx -= 1;

        # idx = self.mmap.rfind(delimiter, startpos)
        if idx == -1: # not found, read until bof
            res = self.mmap[:startpos]
            newpos = 0
        else:
            res = self.mmap[idx+len(delimiter):startpos]
            newpos = idx
        return (res,newpos)


    #----------------------------------------------------------------
    # Implementation of a file-like interface


    def fflush(self): pass

    def next():
        return self.readline

    def read(self, size=0):
        self.lastread = self.mmap[self.current:self.current+size]
        self.current += size
        return self.lastread

    def readline(self, size=None):
        # FIXME: the size arg is required for file-like interfaces,
        # but we don't support it
        return self.readchunk(self.linesep)

    def readlines(self, sizehint=None):
        # FIXME: Implement
        pass

    def xreadlines(self):
        # FIXME: Implement
        pass
    
    def seek(self, offset, whence=0):
        # FIXME: Implement support for whence
        self.current = offset

    def tell(self):
        return self.current

    def truncate(self):
        return IOError("TextReaders are read-only")

    def write(str):
        return IOError("TextReaders are read-only")

    def writelines(sequence):
        return IOError("TextReaders are read-only")


        
    #----------------------------------------------------------------
    # Added convenience methods


    def readparagraph(self):
        return self.readchunk(self.linesep*2)

    def readpage(self):
        return self.readchunk('\f') # form feed - pdftotext generates these to indicate page breaks 

    def readchunk(self,delimiter):
        (self.lastread,self.current) = self.__find(delimiter,self.current)
        return self.lastread
    
        
        
    def lastread(self):
        """returns the last chunk of data that was actually read
        (i.e. the peek* and prev* methods do not affect this"""
        return self.lastread

    def peekline(self,times=1):
        return self.peekchunk(self.linesep,times)

    def peekparagraph(self,times=1):
        return self.peekchunk(self.linesep,times)

    def peekchunk(self,delimiter,times=1):
        newpos = self.current
        for i in range(times):
            (res,newpos) = self.__find(delimiter,newpos)
        return res

    def prevline(self,times=1):
        return self.prevchunk(self.linesep,times)

    def prevparagraph(self,times=1):
        return self.prevchunk(self.linesep*2,times)

    def prevchunk(self,delimiter, times=1):
        newpos = self.current
        for i in range(times):
            (res,newpos) = self.__rfind(delimiter,newpos)
            print 
        return res
    

#----------------------------------------------------------------
# Unit tests

import unittest

class Basic(unittest.TestCase):
    def setUp(self):
        self.f = TextReader(sys.prefix + "/lib/python2.5/LICENSE.txt")

    def testReadline(self):
        self.assertEqual(self.f.readline(),
                         u'A. HISTORY OF THE SOFTWARE')

        self.assertEqual(self.f.readline(),
                         u'==========================')
        self.f.seek(0)

    def testReadparagraph(self):
        l = self.f.readparagraph()
        self.assertEqual(l, u'A. HISTORY OF THE SOFTWARE\n==========================')
        l = self.f.readparagraph()
        self.assertEqual(l, u'Python was created in the early 1990s by Guido van Rossum at Stichting\nMathematisch Centrum (CWI, see http://www.cwi.nl) in the Netherlands\nas a successor of a language called ABC.  Guido remains Python\'s\nprincipal author, although it includes many contributions from others.')
        self.f.seek(0)

    def testReadChunk(self):
        l = self.f.readchunk('(')
        l = self.f.readhunk(')')
        self.assertEqual(l,u'CWI, see http://www.cwi.nl')
        self.f.seek(0)

    def testPeekLine(self):
        l = self.f.peekline()
        self.assertEqual(l, u'A. HISTORY OF THE SOFTWARE')
        l = self.f.peekline(4)
        self.assertEqual(l, u'Python was created in the early 1990s by Guido van Rossum at Stichting')
        self.f.seek(0)
        

    def testPrevLine(self):
        self.f.readparagraph()
        self.f.readparagraph()
        self.assertEqual(self.f.prevline(),
                         u'principal author, although it includes many contributions from others.')
        self.assertEqual(self.f.prevline(4),
                         u'Python was created in the early 1990s by Guido van Rossum at Stichting')
        self.f.seek(0)

    def testReadTo(self):
        self.f.readTo("Guido")
        self.assertEquals(self.f.readline(),
                          u'Guido van Rossum at Stichting')

class Codecs(unittest.TestCase):
    def setUp(self):
        self.utf = TextReader(sys.prefix + "/lib/python2.5/test/test_doctest4.txt", "utf-8")
        self.koi = TextReader(sys.prefix + "/lib/python2.5/test/test_pep263.py", "koi8-r")
        self.iso = TextReader(sys.prefix + "/lib/python2.5/test/test_shlex.py", "iso-8859-1")
        self.f.autostrip = True

class Processing:
    def testStrip(self): pass
    
    def testDewrap(self): pass

    def testDehyphenate(self): pass
