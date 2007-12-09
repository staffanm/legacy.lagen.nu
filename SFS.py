#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Hanterar författningar i SFS från Regeringskansliet rättsdatabaser.
"""
# system libraries
import sys, os, re
import shutil
import pprint
import types
import datetime
import codecs
from cStringIO import StringIO
from time import time
import pickle
# Python 2.5 plz
import xml.etree.cElementTree as ET
# import cElementTree as ET
# import elementtree.ElementTree as ET


# 3rdparty libs
# sys.path.append('3rdparty')
from genshi.template import TemplateLoader
# import gnosis.xml.pickle


# my own libraries
import LegalSource
import Util
from DispatchMixin import DispatchMixin
# from DocComments import AnnotatedDoc
# from LegalRef import SFSRefParser,PreparatoryRefParser,ParseError

# from Verva / rättsinformationsprojektet
sys.path.append('../rinfo-datacore/scripts/converters/sfst')
from create_example_data import SFSParser as VervaSFSParser
from create_example_data import SFSParserRunner as VervaSFSParserRunner


# Django stuff
# os.environ['DJANGO_SETTINGS_MODULE'] = 'ferenda.settings'
# from ferenda.docview.models import *

__version__ = (0,1)
__author__  = "Staffan Malmgren <staffan@tomtebo.org>"
__shortdesc__ = "Författningar i SFS"
__moduledir__ = "sfs"

# module global utility functions
def SFSidToFilename(sfsid):
    """converts a SFS id to a filename, sans suffix, eg: '1909:bih. 29
    s.1' => '1909/bih._29_s.1'. Returns None if passed an invalid SFS
    id."""
    if sfsid.find(":") < 0: return None
    return re.sub(r'([A-Z]*)(\d{4}):',r'\2/\1',sfsid.replace(' ', '_'))

def FilenameToSFSid(filename):
    """converts a filename, sans suffix, to a sfsid, eg:
    '1909/bih._29_s.1' => '1909:bih. 29 s.1'"""
    (dir,file)=filename.split("/")
    if file.startswith('RFS'):
        return re.sub(r'(\d{4})/([A-Z]*)(\d*)( [AB]|)(-(\d+-\d+|first-version)|)',r'\2\1:\3', filename.replace('_',' '))
    else:
        return re.sub(r'(\d{4})/(\d*( s[\. ]\d+|))( [AB]|)(-(\d+-\d+|first-version)|)',r'\1:\2', filename.replace('_',' '))


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
   
    def Parse(self,basefile,files):
        self.verbose = True
        self.id = FilenameToSFSid(basefile)
        # find out when data was last fetched (use the oldest file)
        timestamp = sys.maxint
        for filelist in files.values():
            for file in filelist:
                if os.path.getmtime(file) < timestamp:
                    timestamp = os.path.getmtime(file)
        
        # extract and parse registry (AKA changelog) - VervaSFSParserRunner
        # contains code to do this as well, but we'd rather do it ourselves
        p = VervaSFSParser(None)
        registry = p.parse_sfsr(files['sfsr'])
        lawtext = p.extract_sfst(files['sfst'])
        
        runner = VervaSFSParserRunner("../rinfo-datacore/scripts/converters/sfst/authrec.n3")
        # runner._set_verbosity(False)
        data = runner._parse_sfst(lawtext, registry)
        
        # print pickle.dumps(data)
        # print gnosis.xml.pickle.dumps(data)
        # pprint.pprint(data)
        xhtml = runner._generate_xhtml(data)
        return xhtml
        
    # The following code should be scrapped or moved to create_example_data.py
    #
    #def __createUrn(self,id):
    #    return "urn:x-sfs:%s" % id.replace(' ','_')
    #
    #def __extractLawtext(self, files = [], keepHead=True):
    #    # print "extractLawtext: %r %r" % (files,keepHead)
    #    if not files:
    #        return ""
    #    soup = self.LoadDoc(files[0])
    #    idx = 0
    #    if keepHead == False: # find out where the <hr> that separates the header from the body is
    #        for el in soup.body('pre')[1].contents:
    #            if (hasattr(el,'name') and el.name == 'hr'):
    #                break
    #            idx += 1
    #        # print "idx: %s" % idx
    #        txt = ''.join([e for e in el.nextGenerator() if isinstance(e,unicode)]).replace('\r\n','\n')
    #    else:
    #        if not soup.body('pre'):
    #            txt = ''
    #        else:
    #            txt = ''.join([e for e in soup.body('pre')[1].recursiveChildGenerator() if isinstance(e,unicode)]).replace('\r\n','\n')
    #    
    #    return txt + self.__extractLawtext(files[1:],keepHead=False)
    #
    #
    #def find_change_references(self,p):
    #    typemap = {u'upph.'    : 'removed',
    #               u'ändr.'    : 'modified',
    #               u'nya'      : 'added',
    #               u'ny'       : 'added',
    #               u'ikrafttr.': 'added',
    #               u'tillägg'  : 'added'}
    #    res = ""
    #    p = self.re_NormalizeSpace(' ',p)
    #    changesets = p.split("; ")
    #    for changeset in changesets:
    #        typelabel =  changeset.split(" ")[0].strip()
    #        if typemap.has_key(typelabel):
    #            res += '<sectionchange type="%s">%s</sectionchange>' % (typemap[typelabel], self.find_references(changeset))
    #        else:
    #            print "Warning: unknown type label '%s'" % typelabel.encode('iso-8859-1')
    #    return res
    # 
    #def find_references(self,p):
    #    try:
    #        lp = SFSRefParser(p,namedlaws=self.namedlaws)
    #        return lp.parse()
    #    except ParseError, e:
    #        print "find_references failed on the following:\n"+p
    #        raise e
    #
    #def find_prep_references(self,p):
    #    try:
    #        lp = PreparatoryRefParser(p,namedlaws=self.namedlaws)
    #        return lp.parse()
    #    except ParseError, e:
    #        print "find_prep_references failed on the following:\n"+p
    #        raise e    
        
        
        
class SFSManager(LegalSource.Manager):
    __parserClass = SFSParser

    ####################################################################
    # CLASS-SPECIFIC HELPER FUNCTIONS
    ####################################################################

    def __listfiles(self,source,basename):
        """Given a SFS id, returns the filenames within source dir that
        corresponds to that id. For laws that are broken up in _A and _B
        parts, returns both files"""
        templ = "%s/sfs/downloaded/%s/%s%%s.html" % (self.baseDir,source,basename)
        # print "__listfiles template: %s" % templ
        return [templ%f for f in ('','_A','_B') if os.path.exists(templ%f)]
        
    def __doAll(self,dir,suffix,method):
        from sets import Set
        basefiles = Set()
        # for now, find all IDs based on existing files
        for f in Util.listDirs("%s/%s/%s" % (self.baseDir,__moduledir__,dir), ".%s" % suffix):
            # moahaha!
            # this transforms 'foo/bar/baz/1960/729.html' to '1960/729'
            basefile = "/".join(os.path.split(os.path.splitext(os.sep.join(os.path.normpath(f).split(os.sep)[-2:]))[0]))
            if basefile.endswith('_A') or basefile.endswith('_B'):
                basefile = basefile[:-2]
            basefiles.add(basefile)
        for basefile in sorted(basefiles):
            # print basefile
            method(basefile)
  
    def __resolveFragment(self,
                          element,
                          context,
                          restartingSectionNumbering):
        """Given a link element and the context in which it was found, resolve
        to a full uri including fragment (eg 'urn:x-sfs:1960:729#K1P2S3N4')"""
        
        # fill a copy of the element structure with required context, then 
        # reuse _createSFSUrn
        if element is None:
            e = ET.Element("link")
        else:
            import copy
            e = copy.deepcopy(element)

        if 'law' in e.attrib: # this is an 'absolute' reference, no context needed
            return self._createSFSUrn(e)
        e.attrib['law'] = context['sfsid']
        if restartingSectionNumbering:
            if 'chapter' not in e.attrib:
                if context['chapter']:
                    e.attrib['chapter'] = context['chapter']
                else:
                    # due to incorrect parsing, some link elements have no
                    # chapter data even though they should
                    raise LegalSource.IdNotFound("No chapter found")
        if context['section'] and 'section' not in e.attrib:
            e.attrib['section'] = context['section']
        if context['piece'] and 'piece' not in e.attrib:
            e.attrib['piece'] = str(context['piece'])
        if context['item'] and 'item' not in e.attrib:
            e.attrib['item'] = str(context['item'])
        
        return self._createSFSUrn(e)
        
    ####################################################################
    # OVERRIDES OF Manager METHODS
    ####################################################################    
    
    def _findDisplayId(self,root,basefile):
        # we don't need the (ElementTree) root -- basename is enough
        return FilenameToSFSid(basefile)

    def _basefileToDisplayId(self,basefile, urnprefix):    
        assert(urnprefix == u'urn:x-sfs')
        return FilenameToSFSid(basefile)
        
    def _basefileToUrn(self, basefile, urnprefix):        
        assert(urnprefix == u'urn:x-sfs')
        return u'urn:x-sfs:%s' % FilenameToSFSid(basefile).replace(' ','_')
        
    def _displayIdToBasefile(self,displayid, urnprefix):        
        assert(urnprefix == u'urn:x-sfs')
        return SFSidToFilename(displayid)
        
    def _displayIdToURN(self,displayid, urnprefix):        
        assert(urnprefix == u'urn:x-sfs')
        return u'urn:x-sfs:%s' % displayid.replace(' ','_')
    
    def _UrnToBasefile(self,urn):
        return SFSidToFilename(self._UrnToDisplayId(urn))
        
    def _UrnToDisplayId(self,urn):
        return urn.split(':',2)[-1].replace('_',' ')
        
    def _getModuleDir(self):
        return __moduledir__
    ####################################################################
    # IMPLEMENTATION OF Manager INTERFACE
    ####################################################################    

    def Parse(self, basefile, verbose=False, force=False):
        start = time()

        files = {'sfst':self.__listfiles('sfst',basefile),
                 'sfsr':self.__listfiles('sfsr',basefile)}
        # sanity check - if no files are returned
        if (not files['sfst'] and not files['sfsr']):
            raise LegalSource.IdNotFound("No files found for %s" % basefile)
        filename = self._xmlFileName(basefile)
        # check to see if the outfile is newer than all ingoing files. If it
        # is (and force is False), don't parse
        if not force and self._outfileIsNewer(files,filename):
            return
                    
        
        if not verbose: sys.stdout.write("\tParse %s" % basefile)        
        # print("Files: %r" % files)
        p = SFSParser()
        parsed = p.Parse(basefile,files)
        
        Util.mkdir(os.path.dirname(filename))
        # print "saving as %s" % filename
        out = file(filename, "w")
        out.write(parsed)
        out.close()
        #  Util.indentXmlFile(filename)
        if not verbose: sys.stdout.write("\t%s seconds\n" % (time()-start))

    def ParseAll(self):
        # print "SFS: ParseAll temporarily disabled"
        # return
        self.__doAll('downloaded/sfst','html',self.Parse)

    def IndexAll(self):
        # print "SFS: IndexAll temporarily disabled"
        # return
        self.indexroot = ET.Element("documents")
        self.__doAll('parsed', 'xml',self.Index)
        tree = ET.ElementTree(self.indexroot)
        tree.write("%s/%s/index.xml" % (self.baseDir,__moduledir__))
        
    def Generate(self,basefile):
        infile = self._xmlFileName(basefile)
        outfile = self._htmlFileName(basefile)
        sanitized_sfsid = basefile.replace(' ','.')
        print "Transforming %s > %s" % (infile,outfile)
        Util.mkdir(os.path.dirname(outfile))
        Util.transform("xsl/sfs.xsl",
                       infile,
                       outfile,
                       {'lawid': sanitized_sfsid,
                        'today':datetime.date.today().strftime("%Y-%m-%d")},
                       validate=False)
        #  print "Generating index for %s" % outfile
        ad = AnnotatedDoc(outfile)
        ad.Prepare()
        

    def GenerateAll(self):
        # print "SFS: GenerateAll temporarily disabled"
        # return
        self.__doAll('parsed','xml',self.Generate)

    def Relate(self,basefile):
        start = time()
        sys.stdout.write("Relate %s" % basefile)
        xmlFileName = self._xmlFileName(basefile)
        root = ET.ElementTree(file=xmlFileName).getroot()
        urn = root.get('urn')
        displayid = self._findDisplayId(root,basefile)
        # delete all previous relations where this document is the object --
        # maybe that won't be needed if the typical GenerateAll scenario
        # begins with wiping the Relation table? It still is useful 
        # in the normal development scenario, though
        Relation.objects.filter(object__startswith=urn.encode('utf-8')).delete()

        self._createRelation(urn,Predicate.IDENTIFIER,displayid,allowDuplicates=False)
        title = root.findtext(u'preamble/title') or ''
        self._createRelation(urn,Predicate.TITLE,title)

        # Find out wheter § numbering is continous for the whole law text
        # (like URL) or restarts for each chapter:
        seenSectionOne = False
        restartingSectionNumbering = False 
        for e in root.getiterator():
            if e.tag == u'section' and e.get('id') == '1':
                if seenSectionOne:
                    restartingSectionNumbering = True
                    break
                else:
                    seenSectionOne = True
        # this second call to root.getiterator() could possibly be merged 
        # with the first one, if I understood how it worked...
        parent_map = dict((c, p) for p in root.getiterator() for c in p)
        context = {'sfsid':     displayid,
                   'changeid':  None, # not really sure it belongs
                   'chapter':   None,
                   'section':   None,
                   'piece':     None,
                   'item':      None}
        referenceCount = 0
        inChangesSection = False
        for e in root.getiterator():
            if e.tag == u'chapter':
                # sys.stdout.write("c")
                context['chapter'] = e.get('id')
                context['section'] = None
                context['piece'] = None
                context['item'] = None
            elif e.tag == u'section':
                # sys.stdout.write("s")
                context['section'] = e.get('id')
                context['piece'] = None
                context['item'] = None
            elif e.tag == u'p':
                # sys.stdout.write("p")
                if context['piece']:
                    context['piece'] += 1
                else:
                    context['piece'] = 1
                context['item'] = None
            elif e.tag == u'li':
                # sys.stdout.write("l")
                if context['item']:
                    context['item'] += 1
                else:
                    context['item'] = 1
            elif e.tag == u'changes':
                # sys.stdout.write("|")
                inChangesSection = True
            elif e.tag == u'change':
                # sys.stdout.write("C")
                context['changeid'] = e.get('id')
                context['chapter'] = None                
                context['section'] = None                
                context['piece'] = None                
                context['item'] = None                
            elif e.tag == u'link':
                # sys.stdout.write("L")
                if 'type' in e.attrib and e.get('type') == 'docref':
                    # sys.stdout.write("-")
                    pass
                elif inChangesSection:
                    # sys.stdout.write("!")
                    try:
                        # urn will be on the form "urn:x-sfs:2005:360" -- should
                        # it be "urn:x-sfs:1960:729#2005:360" instead?
                        sourceUrn = "urn:x-sfs:%s" % context['changeid']
                        # the urn to the changed paragraph (or similar)
                        targetUrn = self.__resolveFragment(e, context,restartingSectionNumbering)
                                               
                        # i'd really like a MODIFIES predicate, but no such thing in DCMI
                        self._createRelation(sourceUrn,Predicate.REFERENCES,targetUrn)
                        self._createReference(basefile,targetUrn,sourceUrn,u'Ändringar', context['changeid'])
                        referenceCount += 1
                    except LegalSource.IdNotFound:
                        # sys.stdout.write("?")
                        pass
                else:
                    # this code, which creates reference entries for every
                    # reference in the lawtext, is disabled for now (there are
                    # 100's or 1000's of such references in a typical law)
                    #try:
                    #    sourceUrn = self.__resolveFragment(None,context,restartingSectionNumbering)
                    #    targetUrn = self.__resolveFragment(e,context,restartingSectionNumbering)
                    #    self._createRelation(sourceUrn,Predicate.REFERENCES,targetUrn)
                    #    # we need to use LegalSource.__formatFragmentId to get a good displayid here
                    #    self._createReference(basefile,targetUrn,sourceUrn,u'Hänvisningar', 'source')
                    #    referenceCount += 1
                    #except LegalSource.IdNotFound:
                    #    pass
                    # sys.stdout.write(".")
                    pass
        sys.stdout.write("\tcreated %s references\tin %s seconds\n" % (referenceCount,(time()-start)))
        self._flushReferenceCache()
    
    def RelateAll(self):
        # print "SFS: RelateAll temporarily disabled"
        # return
        self.__doAll('parsed','xml',self.Relate)
        

if __name__ == "__main__":
    if not '__file__' in dir():
        print "probably running from within emacs"
        sys.argv = ['SFS.py','Parse', '1960:729']
    
    SFSManager.__bases__ += (DispatchMixin,)
    mgr = SFSManager("testdata",__moduledir__)
    mgr.Dispatch(sys.argv)


