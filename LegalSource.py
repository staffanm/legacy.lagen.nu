#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Base classes for Downloaders and Parsers. Also utility classes (should be moved?)"""
import sys, os, re, codecs, types, htmlentitydefs
sys.path.append("3rdparty")
import BeautifulSoup

os.environ['DJANGO_SETTINGS_MODULE'] = 'ferenda.settings'
from ferenda.docview.models import Relation, Predicate, LegalDocument

class ParseError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class URNNotFound(Exception):
    """thrown whenever we try to lookup a URN for a displayid (or similar) but can't find it"""
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

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
        return BeautifulSoup.BeautifulSoup(codecs.open(filename,encoding=encoding,errors='replace').read(),
                                           convertEntities='html')



class Parser:
    """Abstract base class for a legal source document"""
    re_NormalizeSpace  = re.compile(r'\s+',).sub

    def __init__(self):
        pass
    
    def Parse(self):
        raise NotImplementedError
    
    # Misc useful methods for subclassed classes
    def LoadDoc(self,filename,encoding='iso-8859-1'):
        return BeautifulSoup.BeautifulSoup(codecs.open(filename,encoding=encoding,errors='replace').read(),
                                           convertEntities='html')
    def NormalizeSpace(self,string):
        return self.re_NormalizeSpace(' ',string).strip()
    def ElementText(self,element):
        """finds the plaintext contained in a BeautifulSoup element"""
        return self.NormalizeSpace(
            ''.join(
                [e for e in element.recursiveChildGenerator() 
                 if (isinstance(e,unicode) and 
                     not isinstance(e,BeautifulSoup.Comment))]))

class Manager:
    
    def __init__(self,baseDir):
        self.baseDir = baseDir
        # print "LegalSource.py/Manager: self.baseDir set to " + self.baseDir

    def Download(self,id):
        """Download a specific Legal source document. The id is
        source-dependent and will often be a web service specific id, not the
        most commonly used ID for that legal source document (ie '4674', not
        'NJA 1984 s. 673' or 'SÖ478-84')"""
        raise NotImplementedError

    def DownloadAll(self):
        """Download all documents for this legal source. This is typically a
        very expensive operation that takes hours."""
        raise NotImplementedError
    
    def DownloadNew(self):
        """Download just new documents for this legal source. This is
        typically very tightly coupled to the web service where the documents
        can be found"""
        raise NotImplementedError

    def Parse(self,id):
        """Parse a single legal source document, i.e. convert it from whatever
        downloaded resource(s) we have into a single XML document"""
        raise NotImplementedError
     
    def ParseAll(self):
        """Parse all legal source documents for which we have downloaded
        resource documents on disk"""
        raise NotImplementedError

    def Index(self,id):
        raise NotImplementedError
    
    def IndexAll(self):
        raise NotImplementedError

    def Generate(self):
        """Generate displayable HTML from a legal source document in XML form"""
        raise NotImplementedError
    
    def GenerateAll(self):
        """Generate HTML for all legal source documents"""
        raise NotImplementedError
    
    def Test(self,testname = None):
        """Runs a named test for the Parser of this module. If no testname is
        given, run all available tests"""
        sys.path.append("test")
        from test_Parser import TestParser
        if testname:
            TestParser.Run(testname,self.parserClass,"test/data/sfs")
        else:
            TestParser.RunAll(self.parserClass,"test/data/sfs")
    
    def Profile(self, testname):
        """Run a named test for the Parser and profile it"""
        import hotshot, hotshot.stats
        prof = hotshot.Profile("%s.prof" % testname)
        prof.runcall(self.Test, testname)
        s = hotshot.stats.load("%s.prof" % testname)
        s.strip_dirs().sort_stats("time").print_stats()

    def findURN(self,refid):
        """Given a typical Legal document identifier such as "NJA 1994 s. 33", finds
        out the correct URN ("urn:x-dv:hd:Ö1484-93") -- or raises URNNotFound"""
        # FIXME: we could speed this up by caching relevant parts of the LegalDocument table
        documents = LegalDocument.objects.filter(displayid__exact=refid.encode('utf-8'))
        # d = LegalDocument.objects.get(displayid=refid.encode('utf-8'))
        if len(documents) == 0:
            raise URNNotFound("Can't find URN for '%r'" % refid)
        elif len(documents) == 1:
            return unicode(documents[0].urn,'utf-8')
        else:
            # FIXME: should we return all URNs here?
            print "WARNING: More than one URNs for '%r' (returning first one)" % refid
            return unicode(documents[0].urn,'utf-8')

    def createRelation(self,urn,predicate,subject,intrinsic=True, comment=""):
        """Creates a single relation"""
        
        object, created = LegalDocument.objects.get_or_create(urn = urn.encode('utf-8'))
        if created:
            print u"WARNING: creating a relation for which the object (%r) doesn't exists in the LegalDocument table" % urn
        
        if predicate.startswith('http://'):
            p = Predicate.objects.get(pk=predicate)
        else:
            p = Predicate.objects.get(label=predicate)
        Relation.objects.create(object=urn.encode('utf-8'),
                                         predicate=p,
                                         subject=subject.encode('utf-8'),
                                         intrinsic=intrinsic,
                                         comment=comment
                                     )

class DownloadedResource:
    """Data object for containing information about a downloaded resource.

    A downloaded resource is typically a HTML or PDF document. There
    is usually, but not always, a 1:1 mapping between a resource and a
    legalsource."""
    def __init__(self,id,url=None,localFile=None,fetched=None):
        self.id, self.url, self.localFile, self.fetched = id,url,localFile,fetched

#class HtmlParser(BeautifulSoup.BeautifulSoup):
    #"""Subclass of the regular BeautifulSoup parser that removes
    #comments and handles entitys"""
    ## seems both these extensions will be handled by the upcoming
    ## BeautifulSoup 3.0
    ## kill all the comments
    #def handle_comment(self, text):
        #print "handling comment"
        #pass
    ## and resolve entities
    #def handle_entityref(self, text):
        #print "handling entity %s" % text
        #try:
            #if (type(text) == types.UnicodeType):
                #self.handle_data(unichr(htmlentitydefs.name2codepoint[text]))
            #else:
                #self.handle_data(chr(htmlentitydefs.name2codepoint[text]))
        #except KeyError:
            #self.handle_data("&%s;" % text)

