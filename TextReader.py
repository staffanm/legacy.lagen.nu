#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

"""Fancy file-like-class for reading (not writing) text files by line,
paragraph, page or any other user-defined unit of text, with support
for peeking ahead and looking backwards. It can read files in
different encodings, but converts/handles everything using unicode.
Alternatively, it can be initialized from an existing (unicode) buffer""" 

import os, sys, codecs, copy, unittest


class TextReader:
    UNIX = '\n'
    DOS = '\r\n'
    MAC = '\r'

    #----------------------------------------------------------------
    # Internal helper methods etc
    
    def __init__(self, filename=None, ustring=None, encoding=None, linesep=None):
        if not filename and not ustring:
            raise TypeError("Must specify either filename or ustring")

        # implementation of file attributes
        self.closed = False
        self.mode = "r+"
        self.name = filename
        self.newlines = None
        self.softspace = 0

        if encoding:
            self.encoding = encoding
        else:
            self.encoding = 'ascii'

        # Other initialization
        if linesep:
            self.linesep = linesep
        else:
            self.linesep = os.linesep

        # can be changed through getiterator, if we want to iterate over anything else but lines
        self.iterfunc = self.readline
        self.iterargs = []
        self.iterkwargs = {}
        self.autostrip = False
        self.autodewrap = False
        self.autodehyphenate = False

        if filename:
            self.f = codecs.open(self.name,"rb",encoding)
            chunks = []
            chunk = self.f.read(1024*1024)
            while (chunk):
                chunks.append(chunk) 
                chunk = self.f.read(1024*1024)
                # FIXME: check to see if this speeds things up
                # s = struct.pack("%dB" % (len(a),), *a)
                self.data = "".join(chunks)
            self.f.close()
        else:
            assert(isinstance(ustring,unicode))
            self.data = ustring
        
        self.currpos = 0
        self.maxpos = len(self.data)
        self.lastread = u''

    def __iter__(self):
        # self.iterfunc = self.readline
        return self

    def __find(self,delimiter,startpos):
        idx = self.data.find(delimiter, startpos)
        if idx == -1: # not found, read until eof
            res = self.data[startpos:]
            newpos = startpos + len(res)
        else: 
            res = self.data[startpos:idx]
            newpos = idx + len(delimiter)
        return (res,newpos)

    def __rfind(self,delimiter,startpos):
        idx = self.data.rfind(delimiter, 0, startpos)
        if idx == -1: # not found, read until bof
            res = self.data[:startpos]
            newpos = 0
        else:
            res = self.data[idx+len(delimiter):startpos]
            newpos = idx
        return (res,newpos)

    def __process(self,s):
        if self.autostrip:
            s = self.__strip(s)
        if self.autodewrap:
            s = self.__dewrap(s)
        if self.autodehyphenate:
            s = self.__dehyphenate(s)
        return s

    def __strip(self,s):
        return s.strip()

    def __dewrap(self,s):
        return s.replace(self.linesep, " ")

    def __dehyphenate(self,s):
        return s # FIXME: implement


    #----------------------------------------------------------------
    # Implementation of a file-like interface

    def fflush(self): pass

    def next(self):
        oldpos = self.currpos
        # res = self.__process(self.readline())
        # print "self.iterfunc is %r" % self.iterfunc
        res = self.__process(self.iterfunc(*self.iterargs,**self.iterkwargs))
        if self.currpos == oldpos:
            raise StopIteration
        else:
            return res

    def read(self, size=0):
        self.lastread = self.data[self.currpos:self.currpos+size]
        self.currpos += len(self.lastread)
        return self.__process(self.lastread)

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
        self.currpos = offset

    def tell(self):
        return self.currpos

    def truncate(self):
        return IOError("TextReaders are read-only")

    def write(str):
        return IOError("TextReaders are read-only")

    def writelines(sequence):
        return IOError("TextReaders are read-only")

    #----------------------------------------------------------------
    # Added convenience methods

    def eof(self):
        return (self.currpos == self.maxpos)

    def bof(self):
        return (self.currpos == 0)

    def cue(self,string):
        idx = self.data.find(string,self.currpos)
        if idx == -1:
            raise IOError("Could not find %r in file" % string)
        self.currpos = idx

    def cuepast(self,string):
        self.cue(string)
        self.currpos += len(string)

    def readto(self,string):
        idx = self.data.find(string,self.currpos)
        if idx == -1:
            raise IOError("Could not find %r in file" % string)
        res = self.data[self.currpos:idx]
        self.currpos = idx
        return self.__process(res)

    def readparagraph(self):
        return self.readchunk(self.linesep*2)

    def readpage(self):
        return self.readchunk('\f') # form feed - pdftotext generates
                                    # these to indicate page breaks
                                    # (other ascii oriented formats,
                                    # like the GPL, RFCs and even some
                                    # python source code, uses it as
                                    # well)

    def readchunk(self,delimiter):
        (self.lastread,self.currpos) = self.__find(delimiter,self.currpos)
        return self.__process(self.lastread)
        
    def lastread(self):
        """returns the last chunk of data that was actually read
        (i.e. the peek* and prev* methods do not affect this"""
        return self.__process(self.lastread)

    def peek(self, size=0):
        res = self.data[self.currpos:self.currpos+size]
        return self.__process(res)

    def peekline(self,times=1):
        return self.peekchunk(self.linesep,times)

    def peekparagraph(self,times=1):
        return self.peekchunk(self.linesep*2,times)

    def peekchunk(self,delimiter,times=1):
        oldpos = self.currpos
        for i in range(times):
            (res,newpos) = self.__find(delimiter,oldpos)
            # print "peekchunk: newpos: %s, oldpos: %s" % (newpos,oldpos)
            if newpos == oldpos:
                raise IOError("Peek past end of file")
            else:
                oldpos = newpos
        return self.__process(res)

    def prev(self,size=0):
        res = self.data[self.currpos-size:self.currpos]
        return self.__process(res)

    def prevline(self,times=1):
        return self.prevchunk(self.linesep,times)

    def prevparagraph(self,times=1):
        return self.prevchunk(self.linesep*2,times)

    def prevchunk(self,delimiter, times=1):
        oldpos = self.currpos
        for i in range(times):
            (res,newpos) = self.__rfind(delimiter,oldpos)
            if newpos == oldpos:
                raise IOError("Prev (backwards peek) past end of file")
            else:
                oldpos = newpos
        return self.__process(res)
    

    def getreader(self,callableObj,*args,**kwargs):
        """Enables you to treat the result of any single read*, peek*
        or prev* methods as a new TextReader. Particularly useful to
        process individual pages in page-oriented documents"""
        res = callableObj(*args,**kwargs)
        clone = copy.copy(self)
        clone.data = res
        clone.currpos = 0
        clone.maxpos = len(clone.data)
        return clone

    def getiterator(self,callableObj,*args,**kwargs):
        self.iterfunc = callableObj
        self.iterargs = args
        self.iterkwargs = kwargs
        return self

#----------------------------------------------------------------
# Unit tests

import unittest
if sys.platform == 'win32':
    PREFIX = sys.prefix
    LIBPREFIX = PREFIX + "/Lib"
else:
    PREFIX = sys.prefix +  "/lib/python2.5"
    LIBPREFIX = PREFIX

class Basic(unittest.TestCase):
    def setUp(self):
        self.f = TextReader(PREFIX + "/LICENSE.txt")

    def testReadline(self):
        self.assertEqual(self.f.readline(),
                         u'A. HISTORY OF THE SOFTWARE')

        self.assertEqual(self.f.readline(),
                         u'==========================')
        self.f.seek(0)

    def testIterateFile(self):
        self.assertEqual(self.f.bof(), True)
        self.assertEqual(self.f.eof(), False)
        for line in self.f:
            pass
        self.assertEqual(self.f.bof(), False)
        self.assertEqual(self.f.eof(), True)
        self.f.seek(0)
        
    def testReadparagraph(self):
        l = self.f.readparagraph()
        self.assertEqual(l, u'A. HISTORY OF THE SOFTWARE'+self.f.linesep+'==========================')
        l = self.f.readparagraph()
        self.assertEqual(l, u'Python was created in the early 1990s by Guido van Rossum at Stichting'+self.f.linesep+
                         'Mathematisch Centrum (CWI, see http://www.cwi.nl) in the Netherlands'+self.f.linesep+
                         'as a successor of a language called ABC.  Guido remains Python\'s'+self.f.linesep+
                         'principal author, although it includes many contributions from others.')
        self.f.seek(0)

    def testReadChunk(self):
        l = self.f.readchunk('(')
        l = self.f.readchunk(')')
        self.assertEqual(l,u'CWI, see http://www.cwi.nl')
        self.f.seek(0)

    def testPeekLine(self):
        l = self.f.peekline()
        self.assertEqual(l, u'A. HISTORY OF THE SOFTWARE')
        l = self.f.peekline(4)
        self.assertEqual(l, u'Python was created in the early 1990s by Guido van Rossum at Stichting')
        self.f.seek(0)
        
    def testPeekParagraph(self):
        l = self.f.peekparagraph()
        self.assertEqual(l, u'A. HISTORY OF THE SOFTWARE'+self.f.linesep+'==========================')
        l = self.f.peekparagraph(2)
        self.assertEqual(l, u'Python was created in the early 1990s by Guido van Rossum at Stichting'+self.f.linesep+
                         'Mathematisch Centrum (CWI, see http://www.cwi.nl) in the Netherlands'+self.f.linesep+
                         'as a successor of a language called ABC.  Guido remains Python\'s'+self.f.linesep+
                         'principal author, although it includes many contributions from others.')
        self.f.seek(0)

    

    def testPrevLine(self):
        self.f.readparagraph()
        self.f.readparagraph()
        self.assertEqual(self.f.prevline(3), # first two newlines, then the actual previous line (does this make sense?)
                         u'principal author, although it includes many contributions from others.')
        self.assertEqual(self.f.prevline(6),
                         u'Python was created in the early 1990s by Guido van Rossum at Stichting')
        self.f.seek(0)

    def testCue(self):
        self.f.cue("Guido")
        self.assertEquals(self.f.readline(),
                          u'Guido van Rossum at Stichting')
        self.f.seek(0)

    def testCuePast(self):
        self.f.cuepast("Guido")
        self.assertEquals(self.f.readline(),
                          u' van Rossum at Stichting')
        self.f.seek(0)

    def testReadTo(self):
        self.assertEquals(self.f.readto("SOFTWARE"),
                          u'A. HISTORY OF THE ')


# run all basic tests again, but this time initialised from a unicode buffer
class Ustring(Basic):
    def setUp(self):
        data = codecs.open(PREFIX + "/LICENSE.txt",encoding='ascii').read()
        self.f = TextReader(ustring=data)


class Codecs:
    def testUTF(self):
        f = TextReader(LIBPREFIX + "/test/test_doctest4.txt", "utf-8")
        f.cue(u"u'f")
        self.assertEquals(f.read(5),
                          u"u'f\u00f6\u00f6") 
        f.cue(u"u'b")
        self.assertEquals(f.read(5),
                          u"u'b\u0105r")

    def testISO(self):
        f = TextReader(LIBPREFIX + "/test/test_shlex.py", "iso-8859-1")
        f.cue(';|-|)|')
        f.readline()
        self.assertEquals(f.read(5),
                          u"\u00e1\u00e9\u00ed\u00f3\u00fa")

    def testKOI8(self):
        f = TextReader(LIBPREFIX + "/test/test_pep263.py", "koi8-r")
        f.cue(u'u"')
        self.assertEquals(f.read(7),
                          u'u"\u041f\u0438\u0442\u043e\u043d')

class Processing(unittest.TestCase):
    def setUp(self):
        self.f = TextReader(PREFIX + "/LICENSE.txt")

    def testStrip(self):
        self.f.autostrip = True
        self.assertEquals(self.f.peekline(28),
                          u'Release         Derived     Year        Owner       GPL-')
        self.f.autostrip = False
        self.assertEquals(self.f.peekline(28),
                          u'    Release         Derived     Year        Owner       GPL-')
        self.f.seek(0)

    def testDewrap(self):
        self.f.autodewrap = True
        self.assertEquals(self.f.readparagraph(),
                          u'A. HISTORY OF THE SOFTWARE ==========================')
        self.f.seek(0)
        self.f.autodewrap = False
        self.assertEquals(self.f.readparagraph(),
                          u'A. HISTORY OF THE SOFTWARE'+self.f.linesep+'==========================')
        self.f.seek(0)
        

    def testDehyphenate(self):
        pass

    def testReadTable(self):
        # Should this even be in the Processing test suite?
        pass
    

class Customiterator(unittest.TestCase):
    def setUp(self):
        self.f = TextReader(PREFIX + "/LICENSE.txt")

    def testIterateParagraph(self):
        cnt = 0
        for p in self.f.getiterator(self.f.readchunk,self.f.linesep*2):
            cnt += 1

        self.assertEquals(cnt, 44) 
        

class Subreaders(unittest.TestCase):
    def setUp(self):
        self.f = TextReader(LIBPREFIX + "/test/test_base64.py")

    def testPage1(self):
        p = self.f.getreader(self.f.readpage)
        # print "p.maxpos: %s" % p.maxpos
        self.assertEqual(p.readline(),
                         u'import unittest')
        self.assertRaises(IOError, p.peekline, 32) # we shouldn't be able to read ahead to page 2
        self.assertRaises(IOError, p.cue, u'LegacyBase64TestCase') # not by this method either
        self.f.seek(0)


    def testPage2(self):
        self.f.readpage() 
        p = self.f.getreader(self.f.readpage)
        p.readline()
        self.assertEqual(p.readline(),
                         u'class LegacyBase64TestCase(unittest.TestCase):')

        self.assertRaises(IOError,p.prevline, 4) # we shouldn't be able to read backwards to page 1

        self.f.seek(0)
    


class Edgecases(unittest.TestCase):
    def setUp(self):
        self.f = TextReader(PREFIX + "/LICENSE.txt")

    def testPeekPastEOF(self):
        self.assertRaises(IOError,
                          self.f.peekline, 4711)

    def testPrevPastBOF(self):
        self.assertRaises(IOError,
                          self.f.prevline, 4711)

    def testReadPastEOF(self):
        self.assertEqual(len(self.f.read(1)), 1)
        self.f.read(sys.maxint) # read past end of file - no license text is THAT big
        self.assertNotEqual(self.f.currpos, sys.maxint+1)
        self.assertEqual(len(self.f.read(1)), 0) # no more to read
        self.assertEqual(len(self.f.readline()), 0)
        self.f.seek(0)
        
    def testReadlineUntilEOF(self):
        for line in self.f:
            prev = line
            pass
        self.assertEqual(prev,
                         u'OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.')
        self.assertEqual(self.f.readline(), u'')

    def testSearchInVain(self):
        self.assertRaises(IOError,
                          self.f.cue, u'I am a little teapot')
        self.f.seek(0)

class Fileops(unittest.TestCase):

    def testClose(self):
        f = open("textreader.tmp","w")
        f.write("foo")
        f.close()
        r = TextReader("textreader.tmp")
        # make sure TextReader isn't keeping the file open
        os.rename("textreader.tmp", "textreader2.tmp")
        os.unlink("textreader2.tmp")
        self.assertEqual("foo",r.readline())
                       
if __name__ == '__main__':
    unittest.main()

        
        
