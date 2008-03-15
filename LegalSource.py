#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Base classes for Downloaders and Parsers. Also utility classes (should be moved?)"""
import sys, os, re, codecs, types
import pickle
from time import time
import locale
import xml.etree.cElementTree as ET
import logging

# 3rd party modules
import BeautifulSoup
from mechanize import Browser, LinkNotFoundError
from genshi.template import TemplateLoader
from rdflib.Graph import Graph
from rdflib import Literal, Namespace, URIRef, RDF, RDFS

# my own code
import Util


# Do required codec/locale magic right away, since this is included by
# all runnable scripts
locale.setlocale(locale.LC_ALL,'') 

if sys.platform == 'win32':
    if sys.stdout.encoding:
        defaultencoding = sys.stdout.encoding
    else:
        defaultencoding = 'cp850'
else:
    if sys.stdout.encoding:
        defaultencoding = sys.stdout.encoding
    else:
        defaultencoding = locale.getpreferredencoding()
# print "setting sys.stdout to a '%s' writer" % defaultencoding
sys.stdout = codecs.getwriter(defaultencoding)(sys.__stdout__, 'replace')
sys.stderr = codecs.getwriter(defaultencoding)(sys.__stderr__, 'replace')

log = logging.getLogger(u'legalsource')


class ParseError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class IdNotFound(Exception):
    """thrown whenever we try to lookup a URN/displayid/basefile but can't find it"""
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

    def __init__():
        self.browser = Browser()
        # FIXME: Set user-agent header somehow. Also, if we could make
        # it support Robot.ThrottlingProcessor it would be cool
        self.ids = {}
 
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


class Parser:
    """Abstract base class for a legal source document"""
    re_NormalizeSpace  = re.compile(r'\s+',).sub

    def __init__(self):
        self.authority_rec = self.load_authority_rec("etc/authrec.n3")
    
    def Parse(self):
        raise NotImplementedError

    def generate_xhtml(self,meta,body,module,globals):
        """Skapa en XHTML2-representation av ett rättsinformationsdokument"""
        loader = TemplateLoader(['.' , os.path.dirname(__file__)]) # only look in cwd and this file's directory
        tmpl = loader.load("etc/%s.template.xht2"%module)
        stream = tmpl.generate(meta=meta, body=body, **globals)
        try:
            res = stream.render()
        except Exception, e:
            log.error(u'Fel vid templaterendring (%s):%r' % (e.__class__.__name__,sys.exc_info()[1]))
            raise e
        if 'class="warning"' in res:
            start = res.index('class="warning">')
            end = res.index('</',start+16)
            msg = Util.normalizeSpace(res[start+16:end].decode('utf-8'))
            log.warning(u'%s: templatefel \'%s\'' % (self.id, msg[:80]))
        return res

    def load_authority_rec(self, file):
        """Ladda in en RDF-graf som innehåller auktoritetsposter i n3-format"""
        graph = Graph()
        graph.load(file, format='n3')
        d = {}
        for uri, label in graph.subject_objects(RDFS.label):
            d[unicode(label)] = str(uri)
        return d

    def find_authority_rec(self, label):
        """Givet en textsträng som refererar till någon typ av
        organisation, person el. dyl (exv 'Justitiedepartementet
        Gransk', returnerar en URI som är auktoritetspost för denna."""
        for (key, value) in self.authority_rec.items():
            if label.startswith(key):
                return self.storage_uri_value(value)
        raise KeyError(label)

    def storage_uri_value(self, value):
        return value.replace(" ", '_')

class Manager:
    def __init__(self,baseDir,moduleDir):
        """basedir is the top-level directory in which all file-based data is
        stored and handled. moduledir is a sublevel directory that is unique
        for each LegalSource.Manager subclass."""
        self.baseDir = baseDir
        self.moduleDir = moduleDir
        self.referenceCache = {}
        
    def __del__(self):
        if hasattr(self,'referenceCache') and self.referenceCache:
            print "__del__: flushing cache(s)"
            self._flushReferenceCache()
        
    ####################################################################
    # MISC HELPER FUNCTIONS (overridable by subclasses)
    # 
    # some of these will never be overridden by subclasses, but
    # needs to be calleable from outside, hence the single _ in the name.
    ####################################################################

    def _flushReferenceCache(self):
        # print "Flushing reference cache: %s items" % len(self.referenceCache)
        if hasattr(self,'referenceCache'):
            for (file,data) in self.referenceCache.items():
                self.__serializeReferences(file,data)
            self.referenceCache = {}

    
    def _htmlFileName(self,basefile):
        # will typically never be overridden
        """Returns the full path of the GENERATED HTML fragment that represents a legal document"""
        return "%s/%s/generated/%s.html" % (self.baseDir, self.moduleDir,basefile)        

    def _xmlFileName(self,basefile):
        # will typically never be overridden
        """Returns the full path of the XHTML2/RDFa doc that represents the parsed legal document"""
        return "%s/%s/parsed/%s.xht2" % (self.baseDir, self.moduleDir,basefile)
    
    def _refFileName(self,basefile,moduleDir=None):
        # will typically never be overridden
        # FIXME: using an optional moduleDir (for allowing eg DV.py
        # to construct file paths to files belonging to SFS.py) is
        # not that clean -- would be better to instansiate a 
        # SFSManager and call its _refFileName
        """Returns the full path to the file containing references to this legal document"""
        if not moduleDir:
            moduleDir = self.moduleDir
        return "%s/%s/references/%s.xml" % (self.baseDir, moduleDir,basefile)

    def _splitUrn(self,urn):
        if "#" in urn:
            base, fragment = urn.split("#",1)
        else:
            base = urn
            fragment = u'' # or should we return None?
        return (base,fragment)

    def _createSFSUrn(self,el):
        """Given a ElementTree element representing a Swedish law reference
        (eg <link law="1960:729" section="49" piece="2">49 § 2 st.
        Upphovsrättslagen</link>), returns a URN representing that location
        (eg urn:x-sfs:1960:729#P49S2)"""
        # This needs to be called from both DV.py and SFS.py (and maybe more?)
        
        # this is slower than just deducing the urn from the sfsid attribute, but 
        # this way we catch invalid references (pointing to SFS ids which doesn't exists) 
        urn  = self._displayIdToURN(el.attrib['law'],u'urn:x-sfs')

        # special case for those links that only inform when a 
        # paragraph was last changed
        if 'lawref' in el.attrib:
            return u'urn:x-sfs:%s' % (el.attrib['lawref'])
        
        frag = u'#'
        if 'chapter' in el.attrib:
            frag += u'K' + el.attrib['chapter']
        if 'section' in el.attrib:
            frag += u'P' + el.attrib['section']
        if 'piece' in el.attrib:
            frag += u'S' + el.attrib['piece']
        if 'item' in el.attrib:
            frag += u'N' + el.attrib['item']
        if frag == u'#':
            return urn
        else:
            return urn + frag

    def _commentsAsArray(self,basefile):
        displayid = self._basefileToDisplayId(basefile,u'urn:x-'+self.moduleDir)
        htmlFileName = self._htmlFileName(basefile)
        order = self._buildIndex(htmlFileName)
        
        try:
            article = Article.objects.get(pk=displayid)
        except Article.DoesNotExist:
            return []
        comments = self.__parseComments(article.body)
        res = []
        for frag in order:
            if frag in comments:
                res.append({'fragmentid':frag,
                            'label':self.__formatFragmentId(frag),
                            'body':comments[frag]})
                del comments[frag]
                
        # leftovers (like when the comment points to a paragraph which has
        # been removed -- hopefully rare
        for frag in comments.keys():
            if frag in comments:
                print "_commentsAsArray: leftover fragment %s" % frag                
                # res.append({'fragmentid':frag,
                #            'label':self.__formatFragmentId(i),
                #            'body':b})
        return res
        

    def _createRelation(self,urn,predicate,subject,intrinsic=True, comment="",allowDuplicates=True):
        """Creates a single relation"""
        (objectUri, objectFragment) = self._splitUrn(urn)
        # maybe we should just pregenerate the whole of self.predicateCache just like 
        # we do for sell.predicateCache[Predicate.IDENTIFIER]
        if predicate in self.predicateCache:
            p = self.predicateCache[predicate]
        else:
            p = Predicate.objects.get(uri=predicate)
            self.predicateCache[predicate] = p
        
        if not allowDuplicates:
            (r, created) = Relation.objects.get_or_create(object    = objectUri.encode('utf-8'), 
                                                          predicate = p,
                                                          intrinsic = intrinsic)
        else:
            
            r = Relation()
            r.object         = objectUri.encode('utf-8')
            r.objectFragment = objectFragment.encode('utf-8')
            r.predicate      = p
        
        r.intrinsic       = intrinsic
        r.comment         = comment.encode('utf-8')

        if subject.startswith('urn:'):
            (subjectUri, subjectFragment) = self._splitUrn(subject)
            if subjectUri in self.relationCache:
                if self.relationCache[subjectUri]:
                    s = self.relationCache[subjectUri]
                else:
                    # print "WARNING: Could not find uri %r as object in (the cache of) the Relation table, not creating %r relation from %r to it" % (subjectUri, predicate, objectUri)
                    return
            else:
                try:
                    s = Relation.objects.get(object=subjectUri.encode('utf-8'),
                                             predicate = self.predicateCache[Predicate.IDENTIFIER])
                    self.relationCache[subjectUri] = s
                except Relation.DoesNotExist:
                    # print "WARNING: Could not find uri %r as object in the Relation table, not creating %r relation from %r to it" % (subjectUri, predicate, objectUri)
                    self.relationCache[subjectUri] = None
                    return
            r.subject = s
            r.subjectFragment = subjectFragment.encode('utf-8')
            # print 'Creating relation <%r> <%r> <%r>.' % (r.object,predicate,s.object)
        else:
            r.subjectLiteral = subject.encode('utf-8')
            # print 'Creating relation <%r> <%r> "%s".' % (r.object,predicate,r.subjectLiteral)
        
        r.save()


    def _referencesAsArray(self,basefile):
        # FIXME: it's all fun and well with lists of dicts of lists of dicts, but
        # somewhere around the third nesting level we really should consider a
        # more robust API
        def __documents(docs):
            res = []
            # print type(docs)
            for d in docs:
                res.append({'displayid':d['displayid'],
                            'desc':d['desc'],
                            'alternative':d['alternative']})
            return res
        
        def __documenttypes(doctypes):
            res = []
            for t in doctypes.keys():
                # print "frag: %s" % t
                res.append({'label':t,
                            'documents':__documents(doctypes[t])})
            return res
                
        refFileName = self._refFileName(basefile)
        htmlFileName = self._htmlFileName(basefile)
        # FIXME: consider caching
        order = self._buildIndex(htmlFileName)
        refs = self._deserializeReferences(refFileName)
        res = []
        #for frag in refs.keys():
        #    res.append({'fragmentid':frag,
        #                'label':self.__formatFragmentId(frag),
        #                'documenttypes':[]})

        for frag in order:
        #    res.append({'fragmentid':frag,
        #                'label':self.__formatFragmentId(frag),
        #                'documenttypes':[]})
            if frag in refs:
                res.append({'fragmentid': frag,
                            'label':self.__formatFragmentId(frag),
                            'documenttypes': __documenttypes(refs[frag])})
                del refs[frag]
        
        # leftovers (like when the reference points to K5P49 when the 'real'
        # fragment is P49) -- hopefully rare
        for frag in refs.keys():
            print "_referencesAsArray: leftover fragment %s" % frag
            # res.append({'fragmentid':frag,
            #            'documenttypes':__documenttypes(refs[frag])})
        return res     
                       
                       
            

    def _createReference(self,basefile,targetUrn, sourceUrn, refLabel, displayid, alternative=None, desc='Beskrivning saknas'):
        """Creates a reference to a (part of a) document in this legal source
        from a (part of a) document in this, or any other, legal source.
        
        basefile: the file for within the reference target is located
        targetUrn: the urn (including fragment) of the reference target
        sourceUrn: the urn (including fragment) of the reference source
        refLabel: label indicating type of reference, eg u'Rättsfall'
        displayid: label for the reference source, suitable for display
        alternative: an alternative label for the reference source
        desc: a description of the reference source
        """
        # print "Creating reference from %s to %s" % (sourceUrn, targetUrn)
        assert(refLabel)
        assert(displayid)
        assert(sourceUrn)
        assert(targetUrn)
        # extract 'sfs' from 'urn:x-sfs:1960:729'
        targetModuleDir = targetUrn.split(":")[1]
        if targetModuleDir.startswith("x-"):
            targetModuleDir = targetModuleDir[2:]
        
        refFile = self._refFileName(basefile,targetModuleDir)
        # assert(os.path.exists(refFile))
        (sourceUrn, sourceFragment) = self._splitUrn(sourceUrn)
        (targetUrn, targetFragment) = self._splitUrn(targetUrn)
        if not targetFragment: targetFragment =  "top"
        if sourceFragment == '': sourceFragment = None
        ref = {'sourceUrn':sourceUrn,
               'sourceFragment':sourceFragment,
               'displayid':displayid,
               'desc':desc}

        if refFile not in self.referenceCache:
            if os.path.exists(refFile):
                refs = self._deserializeReferences(refFile)
            else:
                refs = {}
        else:
            refs = self.referenceCache[refFile]
            
        if targetFragment not in refs:
            refs[targetFragment] = {}
        if refLabel not in refs[targetFragment]:
            refs[targetFragment][refLabel] = []
        # FIXME: it would be good if we find any other ref, with the same
        # sourceUrn/sourceFragment, to replace that ref with this new one
        # (theoretically there can be two references from the same two
        # {target,source}{Urn,Fragment} pairs, but hardly meaningful in
        # practice)
        # if ref not in refs[targetFragment][refLabel]: # avoid pure duplicates

        dupe = False
        for existingRef in refs[targetFragment][refLabel]:
            if (ref['sourceUrn'] == existingRef['sourceUrn'] and
                ref['sourceFragment'] == existingRef['sourceFragment']):
                dupe = True
                break
        if not dupe:
            #print "No dupe, rally creating"
            refs[targetFragment][refLabel].append(ref)    
        #else:
            #print "Dupe, no createing"
        
        self.referenceCache[refFile] = refs

    #def _initReferences(self, basefile):
        #refFile = self._refFileName(basefile)
        #refs = {}
        #self.referenceCache[refFile] = refs

    def _buildIndex(self, htmlFileName):
        """returns an array of adressable positions in this legal document.
        An adressable position is the smallest entity within the legal text to
        which it's meaningful to point, eg a specific item in a section in a
        article in a chapter. Each position has a identifier, eg K1P2S3N4 for
        chapter 1, section 2, paragraph 3, list item 4"""
        # The default implementation relies on the generated XHTML fragment to have 
        # comment markers.
        # htmlFileName = self._htmlFileName(basefile)
        start_or_end_iter = re.compile(r'<!--(start|end):(\w+)-->').finditer
        index = []
        data = codecs.open(htmlFileName, encoding="iso-8859-1").read()
        startmatch = None
        endmatch = None
        for m in start_or_end_iter(data):
            if startmatch:
                endmatch = m
                assert(startmatch.group(1) == 'start')
                assert(endmatch.group(1) == 'end')
                assert(startmatch.group(2) == endmatch.group(2))
                index.append(startmatch.group(2))
                startmatch = None
            else:
                startmatch = m
        return index

    # the following six lookup methods can be overridden (and should, if the
    # inheriting class has a predictable relations between
    # basefile/displayid/urn, like SFSManager has)
    def _basefileToDisplayId(self,basefile, urnprefix):
        return self.__fetchDocumentIDs(basefile=basefile.encode('utf-8'),
                                urnprefix=urnprefix.encode('utf-8')).displayid.decode('utf-8')
    
    
    def _basefileToUrn(self, basefile, urnprefix):
        return self.__fetchDocumentIDs(basefile=basefile.encode('utf-8'),
                               urnprefix=urnprefix.encode('utf-8')).urn.decode('utf-8')
       
    
    def _displayIdToBasefile(self,displayid, urnprefix):
        return self.__fetchDocumentIDs(displayid=displayid.encode('utf-8'),
                                urnprefix=urnprefix.encode('utf-8')).basefile.decode('utf-8')
    
    def _displayIdToURN(self,displayid, urnprefix):
        return self.__fetchDocumentIDs(displayid=displayid.encode('utf-8'),
                                urnprefix=urnprefix.encode('utf-8')).urn.decode('utf-8')
    
    def _UrnToBasefile(self,urn):
        (urn,fragment) = self._splitUrn(urn)
        return self.__fetchDocumentIDs(urn=urn.encode('utf-8')).basefile.decode('utf-8')
        
    def _UrnToDisplayId(self,urn):
        (urn,fragment) = self._splitUrn(urn)
        return self.__fetchDocumentIDs(urn=urn.encode('utf-8')).displayid.decode('utf-8')
    
    def _outfileIsNewer(self,infiles,outfile):
        """check to see if the outfile is newer than all ingoing files"""
        if not os.path.exists(outfile): return False
        outfileMTime = os.stat(outfile).st_mtime
        newer = False
        for f in infiles:
            if os.path.exists(f) and os.stat(f).st_mtime > outfileMTime: newer = True
        return newer
    
    ####################################################################
    # INTERNAL NON-OVERRIDABLE FUNCTIONS
    ####################################################################
    
    def __fetchDocumentIDs(self,urn=None,displayid=None,basefile=None,urnprefix=None):
        """Note: this document expects and returns utf-8 encoded bytestrings, not unicode"""
        kwargs = {}
        if urn:
            if isinstance(urn, unicode):
                raise(TypeError("expected utf-8 bytestring, not unicode"))
            kwargs['urn__exact'] = urn
        elif urnprefix:
            if isinstance(urnprefix, unicode):
                raise(TypeError("expected utf-8 bytestring, not unicode"))
            kwargs['urn__startswith'] = urnprefix
            
        if displayid:
            if isinstance(displayid, unicode):
                raise(TypeError("expected utf-8 bytestring, not unicode"))
            kwargs['displayid__exact'] = displayid
        if basefile:
            if isinstance(basefile, unicode):
                raise(TypeError("expected utf-8 bytestring, not unicode"))
            kwargs['basefile__exact'] = basefile
        
        documents = Document.objects.filter(**kwargs)
        if len(documents) == 0:
            raise IdNotFound("No results for for urn: '%r', displayid: '%r', basefile: '%r'" % (urn,displayid,basefile))
        elif len(documents) == 1:
            return documents[0]
        else:
            # FIXME: should we return all URNs here?
            print "WARNING: __fetchDocumentIDs: More than one results for urn: '%r', displayid: '%r', basefile: '%r' (returning first one)" % (urn,displayid,basefile)
            return documents[0]

    def __serializeReferences(self,filename,data):
        # print "flushing %s" % file
        Util.mkdir(os.path.dirname(filename))            
        # fp = open(filename, mode='w')
        # pickle.dump(data,fp,1)
        # fp.close()            
        rootElem = ET.Element("references")
        for frag in data.keys():
            fragElem = ET.SubElement(rootElem,"fragment")
            fragElem.set("id", frag)
            for reftype in data[frag].keys():
                reftypeElem = ET.SubElement(fragElem,"reftype")
                reftypeElem.set("label", reftype)
                for ref in data[frag][reftype]:
                    refElem = ET.SubElement(reftypeElem,"reference")
                    for k in ref.keys():
                        elem = ET.SubElement(refElem,k)
                        elem.text = ref[k]
        tree = ET.ElementTree(rootElem)
        tree.write(filename)

    def _deserializeReferences(self,filename):
        if os.path.exists(filename):
            data = {}
            # return pickle.load(file(filename))
            tree = ET.parse(filename)
            root = tree.getroot()
            for fragElem in list(root):
                fragId = fragElem.get("id")
                reftypes = {}
                for reftypeElem in list(fragElem):
                    reftypeLabel = reftypeElem.get("label")
                    refs = []
                    for refElem in list(reftypeElem):
                        ref = {}
                        for propElem in list(refElem):
                            ref[propElem.tag] = propElem.text
                        refs.append(ref)
                    reftypes[reftypeLabel] = refs
                data[fragId] = reftypes
            return data
        
        else:
            return {}


    re_ChapterSection = re.compile(r'K(\d+\w?)P(\d+w?)S(\d+)N(\d+)')
    re_Headline = re.compile(r'R(\d+w?)')
    re_Paragraph = re.compile(r'S(\d+)')
    
    re_SFSCommentID = re.compile(r'(K(?P<chapter>\d+[a-z]?)|)(P(?P<section>\d+[a-z]?)|)(S(?P<paragraph>\d+[a-z]?)|)(N(?P<item>\d+[a-z]?)|)')

    def __formatFragmentId(self,fragmentid):
        """Formats a given fragment ID (eg K2P4) to a humanreadable format (2 kap. 4 §)"""
        # this will always match, but possibly with a emptystring
        m = self.re_SFSCommentID.match(fragmentid)
        if m.group(0) != '':
            res = ""
            if m.group('chapter'):
                res = res + u"%s kap. " % m.group('chapter')
            if m.group('section'):
                res = res + u"%s § " % m.group('section')
            if m.group('paragraph'):
                res = res + u"%s st. " % m.group('paragraph')
            if m.group('item'):
                res = res + u"%s p. " % m.group('item')
            return res.strip()
        
        m = self.re_Headline.match(fragmentid)
        if m:
            return u"Rub. %s" % (m.group(1))

        m = self.re_Paragraph.match(fragmentid)
        if m:
            return u"%s st." % (m.group(1))
    
        return fragmentid

    def __parseComments(self, comments):
        # FIXME: the use of Util.normalizeSpace might not be a good idea if
        # we want to do real wiki formatting of text
        inSection = False
        sectionid = None
        sectioncomment = None
        sections = {}
        for line in comments.splitlines():
            if inSection == False and ":" in line:
                if sectionid: # add the previous section
                    sections[sectionid] = sectioncomment
                sectionid, sectioncomment = line.split(":",1)
                # print "%r->%r" % (sectionid,sectioncomment)
            elif line.strip() == "":
                inSection = False
            else:
                inSection = True
                sectioncomment = sectioncomment + "\n"
        if sectioncomment:
            sections[sectionid] = Util.normalizeSpace(sectioncomment)

        # pprint.pprint(sections)    
        return sections

    ####################################################################
    # Manager INTERFACE DEFINITION
    ####################################################################
    
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

    def Parse(self,basefile):
        """Parse a single legal source document, i.e. convert it from whatever
        downloaded resource(s) we have into a single XML document"""
        raise NotImplementedError
     
    def ParseAll(self):
        """Parse all legal source documents for which we have downloaded
        resource documents on disk"""
        raise NotImplementedError

    def IndexAll(self):
        raise NotImplementedError

    def Generate(self):
        """Generate displayable HTML from a legal source document in XML form"""
        raise NotImplementedError
    
    def GenerateAll(self):
        """Generate HTML for all legal source documents"""
        raise NotImplementedError
    
    def Relate(self):
        raise NotImplementedError
    
    def RelateAll(self):
        raise NotImplementedError

    ####################################################################
    # GENERIC DIRECTLY-CALLABLE METHODS
    ####################################################################

    def Index(self,basefile):
        start = time()
        sys.stdout.write("Index: %s" % basefile)
        xmlFileName = self._xmlFileName(basefile)
        root = ET.ElementTree(file=xmlFileName).getroot()

        urn = root.get('urn')
        try:
            displayid = self._findDisplayId(root,basefile)
        except LegalSource.ParseError, e:
            print "error for basefile %s" % basefile
            raise e
        sys.stdout.write("\t%r (displayid: %r)\t" % (urn,displayid))
        (d,created) = Document.objects.get_or_create(urn = urn.encode('utf-8'),
                                                     displayid = displayid.encode('utf-8'),
                                                     basefile = basefile.encode('utf-8'))


        try:
            # build paralell index structure in the form of an xml file
            docElement = ET.SubElement(self.indexroot, "document")
            docElement.set('id', str(d.id))
            docElement.set('urn',urn)
            docElement.set('displayid',displayid)
            docElement.set('basefile',basefile)
        except AttributeError:
            pass # probably b/c self.indexroot doesn't exist
            
        sys.stdout.write(" %s sec\n" % (time() - start))
    
    def Publish(self):
        cmd = "tar czf - %s/%s | ssh staffan@minimac.tomtebo.org \"cd /Library/WebServer/Documents/ferenda.lagen.nu && tar xvzf - && chmod -R go+r %s/%s\"" % (self.baseDir, self._getModuleDir(),self.baseDir, self._getModuleDir())
        print "executing %s" % cmd
        os.system(cmd)

    def Test(self,testname = None):
        """Runs a named test for the Parser of this module. If no testname is
        given, run all available tests"""
        sys.path.append("test")
        from test_Parser import TestParser
        if testname:
            TestParser.Run(testname,self.parserClass,"test/data/sfs")
        else:
            TestParser.RunAll(self.parserClass,"test/data/sfs")
    
class DownloadedResource:
    """Data object for containing information about a downloaded resource.

    A downloaded resource is typically a HTML or PDF document. There
    is usually, but not always, a 1:1 mapping between a resource and a
    legalsource."""
    def __init__(self,id,url=None,localFile=None,fetched=None):
        self.id, self.url, self.localFile, self.fetched = id,url,localFile,fetched
