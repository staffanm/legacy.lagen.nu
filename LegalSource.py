#!/sw/bin/python
# -*- coding: iso-8859-1 -*-
"""Base classes for Downloaders and Parsers. Also utility classes (should be moved?)"""
import sys, os, re, codecs, types, htmlentitydefs
sys.path.append("3rdparty")
import BeautifulSoup
class Downloader:
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

    def _saveIndex(self):
        indexroot = ET.Element("index")
        for k in self.ids.keys():
            resource = ET.SubElement(indexroot, "resource")
            resource.set("id", k)
            resource.set("url", self.ids[k].url)
            resource.set("localFile", self.ids[k].localFile)
            resource.set("fetched", time.strftime(self.TIME_FORMAT,self.ids[k].fetched))
        tree = ET.ElementTree(indexroot)
        tree.write(self.dir + "/index.xml")

    def _loadIndex(self):
        self.ids.clear()
        tree = ET.ElementTree(file=self.dir + "/index.xml")
        for node in tree.getroot():
            id = node.get("id")
            resource = LegalSource.DownloadedResource(id)
            resource.url = node.get("url")
            resource.localFile = node.get("localFile")
            resource.fetched = time.strptime(node.get("fetched"), self.TIME_FORMAT)
            self.ids[id] = resource
    def loadDoc(self,filename,encoding='iso-8859-1'):
        return BeautifulSoup.BeautifulSoup(codecs.open(filename,encoding=encoding,errors='replace').read())



class Parser:
    """Abstract base class for a legal source document"""
    re_NormalizeSpace  = re.compile(r'\s+',).sub

    def __init__(self,baseDir):
        pass
    def normalizeSpace(self,string):
        return self.re_NormalizeSpace(' ',string).strip()
    def loadDoc(self,filename,encoding='iso-8859-1'):
        return BeautifulSoup.BeautifulSoup(codecs.open(filename,encoding=encoding,errors='replace').read())
    def elementText(self,element):
        """finds the plaintext contained in a BeautifulSoup element"""
        return self.normalizeSpace(''.join([e for e in element.recursiveChildGenerator() if isinstance(e,unicode)]))

class Manager:
    def __init__(self,baseDir):
        self.baseDir = baseDir
        print "LegalSource.py: self.baseDir set to " + self.baseDir

    def print_usage(self,argv):
        print "Syntax: %s [action] [id]" % argv[0]
        
    def run(self,argv):
        if len(sys.argv) < 3:
            self.print_usage(argv)
        else:
            action = argv[1]
            id = argv[2]
            if id == 'all':
                action += "All"
            m = getattr(self,action)
            if m:
                m(id)
            else:
                print "Unknown action %s" % action
                
    def parse(self,id):
        raise NotImplementedError
    
    def download(self,id):
        raise NotImplementedError
    
    def parseAll(self):
        raise NotImplementedError

    def generate(self):
        """generate does the basic XML-to-HTML-ahead-of-time conversion"""
        raise NotImplementedError


class ParseError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)


class DownloadedResource:
    """Data object for containing information about a downloaded resource.

    A downloaded resource is typically a HTML or PDF document. There
    is usually, but not always, a 1:1 mapping between a resource and a
    legalsource."""
    def __init__(self,id,url=None,localFile=None,fetched=None):
        self.id, self.url, self.localFile, self.fetched = id,url,localFile,fetched

class HtmlParser(BeautifulSoup.BeautifulSoup):
    """Subclass of the regular BeautifulSoup parser that removes
    comments and handles entitys"""
    # seems both these extensions will be handled by the upcoming
    # BeautifulSoup 3.0
    # kill all the comments
    def handle_comment(self, text):
        print "handling comment"
        pass
    # and resolve entities
    def handle_entityref(self, text):
        print "handling entity %s" % text
        try:
            if (type(text) == types.UnicodeType):
                self.handle_data(unichr(htmlentitydefs.name2codepoint[text]))
            else:
                self.handle_data(chr(htmlentitydefs.name2codepoint[text]))
        except KeyError:
            self.handle_data("&%s;" % text)
