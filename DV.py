#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Hanterar domslut (detaljer och referat) från Domstolsverket, www.rattsinfosok.dom.se

Modulen hanterar omvandlande av domslutsdetaljer och -referat till XML
"""
# system libraries
import sys, os, re
import pprint
import types
import codecs
from time import time
import xml.etree.cElementTree as ET # Python 2.5 spoken here
import logging
import zipfile
import traceback

# 3rdparty libs
from genshi.template import TemplateLoader
from configobj import ConfigObj
from mechanize import Browser, LinkNotFoundError
from rdflib.Graph import Graph
from rdflib import Literal, Namespace, URIRef, RDF, RDFS

# my libs
import LegalSource
from LegalRef import SFSRefParser,PreparatoryRefParser,DVRefParser,ParseError,Link
import Util
from DispatchMixin import DispatchMixin
from DataObjects import UnicodeStructure, CompoundStructure, \
     MapStructure, TemporalStructure, OrdinalStructure, serialize

__version__   = (0,1)
__author__    = u"Staffan Malmgren <staffan@tomtebo.org>"
__shortdesc__ = u"Domslut (referat)"
__moduledir__ = "dv"
log = logging.getLogger(__moduledir__)

# Objektmodellen för rättsfall:
# 
# Referat (list)
#   Metadata (map)
#       'Domstol': Link (AP-uri)
#       'Referatnummer': unicode
#       'Målnummer': unicode
#       'Domsnummer': unicode
#       'Avgörandedatum': date
#       'Rubrik': unicode
#       'Lagrum': list
#           Lagrum(list)
#              unicode/Link
#       'Rättsfall': list
#           Rattsfall(list)
#               unicode/Link
#       'Sökord': list
#           unicode
#       'Litteratur': list
#           unicode (på sikt även Link)
#   Referatstext (list)
#       Stycke (list)
#           unicode/Link

class Referat(CompoundStructure): pass

class Metadata(MapStructure): pass

class Lagrum(CompoundStructure): pass

class Rattsfall(CompoundStructure): pass

class Referatstext(CompoundStructure): pass

class Stycke(CompoundStructure): pass

    

# NB: You can't use this class unless you have an account on
# domstolsverkets FTP-server, and unfortunately I'm not at liberty to
# give mine out in the source code...
class DVDownloader(LegalSource.Downloader):
    def __init__(self,baseDir="data"):
        self.dir = baseDir + os.path.sep + __moduledir__ + os.path.sep + 'downloaded'
        self.intermediate_dir = baseDir + os.path.sep + __moduledir__ + 'word'
        if not os.path.exists(self.dir): 
            Util.mkdir(self.dir)
        inifile = self.dir + os.path.sep + __moduledir__ + ".ini"
        log.info(u'Laddar inställningar från %s' % inifile)
        self.config = ConfigObj(inifile)
        # Why does this say "super() argument 1 must be type, not classobj"?
        # super(DVDownloader,self).__init__()
        self.browser = Browser()

    def DownloadAll(self):
        self.download(recurse=True)

    def DownloadNew(self):
        self.download(recurse=False)
        
    def download(self,dirname='',recurse=False):
        # Download using ncftpls/ncftpget, since we can't get python:s
        # ftplib to play nice w/ domstolsverkets ftp server
        url = 'ftp://ftp.dom.se/%s' % dirname
        log.info(u'Listar innehåll i %s' % url)
        out = os.popen("ncftpls -m -u %s -p %s %s" % (self.config['ftp_user'], self.config['ftp_pass'], url))
        lines = out.readlines()
        for line in lines:
            parts = line.split(";")
            filename = parts[-1].strip()
            if line.startswith('type=dir') and recurse:
                self.download(filename,recurse)
            elif line.startswith('type=file'):
                if os.path.exists(os.path.sep.join([self.dir,dirname,filename])):
                    pass 
                else:
                    if dirname:
                        fullname = '%s/%s' % (dirname,filename)
                        localdir = self.dir + os.path.sep + dirname
                        Util.mkdir(localdir)
                    else:
                        fullname = filename
                        localdir = self.dir
                        
                    log.info(u'Hämtar %s till %s' % (filename, localdir))
                    os.system("ncftpget -E -u %s -p %s ftp.dom.se %s %s" %
                              (self.config['ftp_user'], self.config['ftp_pass'], localdir, fullname))
                    self.process_zipfile(localdir + os.path.sep + filename)

    re_malnr = re.compile(r'([^_]*)_([^_\.]*)_?(\d*)')
    def process_zipfile(self, zipfilename):
        removed = replaced = created = untouched = 0
        file = zipfile.ZipFile(zipfilename, "r")
        for name in file.namelist():
            # Namnen i zipfilen använder codepage 437 - retro!
            uname = name.decode('cp437')
            m = self.re_malnr.match(uname)
            if m:
                (court, malnr, referatnr) = (m.group(1), m.group(2), m.group(3))
                if referatnr:
                    outfilename = os.path.sep.join([self.dir, 'unzipped', court, "%s_%s.doc" % (malnr,referatnr)])
                else:
                    outfilename = os.path.sep.join([self.dir, 'unzipped', court, "%s.doc" % (malnr)])

                if "_notis_" in name:
                    continue
                elif "BORT" in name:
                    log.info(u'Raderar befintligt referat %s %s' % (court,malnr))
                    os.unlink(outfilename)
                    removed += 1
                else:
                    if "BYTUT" in name:
                        replaced += 1
                    else:
                        if os.path.exists(outfilename):
                            untouched += 1
                            continue
                        else:
                            created += 1
                    data = file.read(name)
                    Util.ensureDir(outfilename)
                    # sys.stdout.write(".")
                    outfile = open(outfilename,"wb")
                    outfile.write(data)
                    outfile.close()
            else:
                log.warning(u'Kunde inte tolka filnamnet %s i %s' % (name, zipfilename))
        log.info(u'Processade %s, skapade %s,  bytte ut %s, tog bort %s, lät bli %s files' % (zipfilename,created,replaced,removed,untouched))


DC = Namespace("http://purl.org/dc/elements/1.1/")
XSD = Namespace("http://www.w3.org/2001/XMLSchema#")
RINFO = Namespace("http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#")
class DVParser(LegalSource.Parser):
    re_NJAref = re.compile(r'(NJA \d{4} s\. \d+) \(alt. (NJA \d{4}:\d+)\)')
    re_delimSplit = re.compile("[:;,] ?").split


    # Mappar termer för enkel metadata (enstaka
    # strängliteraler/datum/URI:er) från de strängar som används i
    # worddokumenten ('Målnummer') till de URI:er som används i
    # rinfo-vokabulären
    # ("http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#avgorandedatum").

    # FIXME: för allmänna och förvaltningsdomstolar ska kanske hellre
    # referatAvDomstolsavgorande användas än malnummer - det är
    # skillnad på ett domstolsavgörande och referatet av detsamma
    #
    # 'Referat' delas upp i rattsfallspublikation ('NJA'),
    # publikationsordinal ('1987:39'), arsutgava (1987) och sidnummer
    # (187). Alternativt kan publikationsordinal/arsutgava/sidnummer
    # ersättas med publikationsplatsangivelse.
    labels = {u'Rubrik':DC['title'],
              u'Domstol':DC['creator'], # konvertera till auktoritetspost
              u'Målnummer':RINFO['malnummer'], 
              u'Domsnummer':RINFO['domsnummer'],
              u'Diarienummer':RINFO['diarienummer'],
              u'Avdelning':RINFO['domstolsavdelning'],
              u'Referat':None, 
              u'Avgörandedatum':RINFO['avgorandedatum'], # konvertera till xsd:date
              }

    # Metadata som kan innehålla noll eller flera poster.
    # Litteratur/sökord har ingen motsvarighet i RINFO-vokabulären
    multilabels = {u'Lagrum':RINFO['lagrum'],
                   u'Rättsfall':RINFO['rattsfallshanvisning'],
                   u'Litteratur':None,
                   u'Sökord':None}

    #def __init__(self,id,files,baseDir):
        #self.id = id
        #self.dir = baseDir + "/dv/parsed"
        #if not os.path.exists(self.dir):
            #Util.mkdir(self.dir)
        #self.files = files

    def Parse(self,id,docfile):
        import codecs
        self.id = id
        htmlfile = docfile.replace('word','html').replace('.doc','.html')
        Util.word_to_html(docfile,htmlfile)

        lagrum_parser = SFSRefParser()
        rattsfall_parser = DVRefParser()

        # Basic parsing
        soup = Util.loadSoup(htmlfile)
        head = Metadata()
        # Worddokumenten är bara mestadels standardiserade...  En
        # alternativ fallbackmetod vore att söka efter tabellceller
        # vars enda text är något av de kända domstolsnamnen
        if soup.first('span', 'riDomstolsRubrik'):
            node = soup.first('span', 'riDomstolsRubrik').findParent('td')
        elif soup.first('td', 'ritop1'):
            node = soup.first('td', 'ritop1')
        elif soup.first('span', style="letter-spacing:2.0pt"):
            node = soup.first('span', style="letter-spacing:2.0pt").findParent('td')
        elif soup.first('span', style="letter-spacing:1.3pt"):
            node = soup.first('span', style="letter-spacing:1.3pt").findParent('td')
        elif soup.first('span', style="font-size:10.0pt;letter-spacing:\r\n  2.0pt"):
            node = soup.first('span', style="font-size:10.0pt;letter-spacing:\r\n  2.0pt").findParent('td')
        elif soup.first('span', style="font-family:Verdana;letter-spacing:\r\n  2.0pt"):
            node = soup.first('span', style="font-family:Verdana;letter-spacing:\r\n  2.0pt").findParent('td')
        else:
            raise AssertionError(u"Kunde inte hitta domstolsnamnet i %s" % htmlfile)
        head[u'Domstol'] = Util.elementText(node)

        # Det som står till höger om domstolsnamnet är referatnumret
        # (exv "NJA 1987 s. 113")
        node = node.findNextSibling('td')
        head[u'Referatnummer'] = Util.elementText(node)
        if not head[u'Referatnummer']:
            # För specialdomstolarna kan man lista ut referatnumret
            # från målnumret - det borde vi försöka göra här
            raise AssertionError(u"Kunde inte hitta referatnumret i %s" % htmlfile)

        # Hitta övriga enkla metadatafält i sidhuvudet
        for key in self.labels.keys():
            node = soup.firstText(key+u':')
            if node:
                head[key] = Util.elementText(node.findParent('td').findNextSibling('td'))

        # Hitta sammansatta metadata i sidhuvudet
        for key in [u"Lagrum", u"Rättsfall"]:
            node = soup.firstText(key+u':')
            if node:
                items = []
                for p in node.findParent('td').findNextSibling('td').findAll('p'):
                    txt = Util.elementText(p)
                    if txt.startswith(u'\xb7'):
                        txt = txt[1:]
                        items.append(Util.normalizeSpace(txt))
                    else:
                        items = [Util.normalizeSpace(x) for x in self.re_delimSplit(txt)]
                if items != ['']:
                    if key == u'Lagrum':
                        head[key] = [Lagrum([lagrum_parser.parse(i)]) for i in items]
                    elif key == u'Rättsfall':
                        head[key] = [Rattsfall([rattsfall_parser.parse(i)]) for i in items]

        # Hitta själva referatstexten... här kan man göra betydligt
        # mer, exv hitta avsnitten för de olika instanserna, hitta
        # dissenternas domskäl, ledamöternas namn, hänvisning till
        # rättsfall och lagrum i löpande text...
        body = Referatstext()
        for p in soup.firstText(u'REFERAT').findParent('tr').findNextSibling('tr').fetch('p'):
            body.append(Stycke([Util.elementText(p)]))

        # Hitta sammansatta metadata i sidfoten
        txt = Util.elementText(soup.firstText(u'Sökord:').findParent('td').nextSibling.nextSibling)
        head[u'Sökord'] = [Util.normalizeSpace(x) for x in self.re_delimSplit(txt)]
            
        if soup.firstText(u'Litteratur:'):
            txt = Util.elementText(soup.firstText(u'Litteratur:').findParent('td').nextSibling.nextSibling)
            head[u'Litteratur'] = [Util.normalizeSpace(x) for x in txt.split(";")]


        # Formulera om delar av metadatan till en RDF-graf
        docuri = URIRef(u'http://lagen.nu/%s' % self.id)
        graph = Graph()
        graph.bind("dc", "http://purl.org/dc/elements/1.1/")
        graph.bind("xsd", "http://www.w3.org/2001/XMLSchema#")
        graph.bind("rinfo", "http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#")
        graph.add((docuri, RDF.type, RINFO['VagledandeDomstolsavgorande']))

        for (key,val) in self.labels.items():
            if key in head and val:
                graph.add((docuri, val, Literal(head[key].encode('utf-8'))))
                #graph.add((docuri, val, Literal(u'blahonga')))

        for (key,val) in self.multilabels.items():
            if key in head and val:
                # bara sådana lagrums/rättsfallshänvisningar vi
                # faktiskt lyckats uttyda är intressanta att ha med
                for item in val:
                    if isinstance(item,Link):
                        #pass
                        graph.add((docuri, RINFO['lagrum'],URIRef(item.uri)))

        # tyvärr funkar inte graph.query på windows, så vi kan inte
        # göra så mycket mer med grafen än att serialisera den...
        #
        # print graph.serialize(format="n3").decode('utf-8')
        # 
        # nsmap = {u'rdf':RDF.RDFNS,
        #          u'rinfo':RINFO,
        #          u'dc':DC}
        # print graph.query(u'SELECT ?subj WHERE { ?obj dc:subject ?subj }', nsmap)

        xhtml = self.generate_xhtml(head,body,__moduledir__,globals())
        return xhtml
    

    def __createUrn(self,data):
        domstolar = {
            u'Marknadsdomstolen':                 u'md',
            u'Hovrätten för Övre Norrland':       u'hovr:övrenorrland',
            u'Hovrätten för Nedre Norrland':      u'hovr:nedrenorrland',
            u'Hovrätten över Skåne och Blekinge': u'hovr:skåne',
            u'Svea hovrätt':                      u'hovr:svea',
            u'Hovrätten för Västra Sverige':      u'hovr:västra',
            u'G\xf6ta hovr\xe4tt':                u'hovr:göta',
            u'Kammarr\xe4tten i G\xf6teborg':     u'kamr:göteborg',
            u'Kammarr\xe4tten i J\xf6nk\xf6ping': u'kamr:jönkoping',
            u'Kammarr\xe4tten i Stockholm':       u'kamr:stockholm',
            u'Kammarr\xe4tten i Sundsvall':       u'kamr:sundsvall',
            u'Arbetsdomstolen':                   u'ad',
            u'Högsta domstolen':                  u'hd',
            u'Regeringsrätten':                   u'regr',
            u'Patentbesvärsrätten':               u'pbr',
            u'Rättshjälpsnämnden':                u'rhn',
            u'Miljööverdomstolen':                u'möd',
             }
        idfield = {
            u'Marknadsdomstolen':                 u'Domsnummer',
            u'Hovrätten för Övre Norrland':       u'Målnummer',
            u'Hovrätten för Nedre Norrland':      u'Målnummer',
            u'Hovrätten över Skåne och Blekinge': u'Målnummer',
            u'Svea hovrätt':                      u'Målnummer',
            u'Hovrätten för Västra Sverige':      u'Målnummer',
            u'G\xf6ta hovr\xe4tt':                u'Målnummer',
            u'Kammarr\xe4tten i G\xf6teborg':     u'Målnummer',
            u'Kammarr\xe4tten i J\xf6nk\xf6ping': u'Målnummer',
            u'Kammarr\xe4tten i Stockholm':       u'Målnummer',
            u'Kammarr\xe4tten i Sundsvall':       u'Målnummer',
            u'Arbetsdomstolen':                   u'Domsnummer',
            u'Högsta domstolen':                  u'Målnummer',
            u'Regeringsrätten':                   u'Målnummer',
            u'Patentbesvärsrätten':               u'Målnummer',
            u'Rättshjälpsnämnden':                u'Diarienummer',
            u'Miljööverdomstolen':                u'Målnummer',
            }
        domstol = data['Domstol']
        urn = "urn:x-dv:%s:%s" % (domstolar[domstol], data[idfield[domstol]])
        return urn


class DVManager(LegalSource.Manager):
    __parserClass = DVParser
    

    ####################################################################
    # CLASS-SPECIFIC HELPER FUNCTIONS
    ####################################################################
    
    
    def __doAllParsed(self,method,max=None):
        cnt = 0
        for f in Util.listDirs(self.baseDir+"/dv/parsed",'xml'):
            if max and (max <= cnt):
                return cnt
            cnt += 1
            basefile = os.path.splitext(os.path.basename(f))[0]
            method(basefile)
        return cnt
    
    def __listfiles(self,suffix,basefile):
        filename = "%s/%s/downloaded/%s.%s.html" % (self.baseDir,__moduledir__,basefile,suffix)
        return [f for f in (filename,) if os.path.exists(f)]


    ####################################################################
    # OVERRIDES OF Manager METHODS
    ####################################################################
    
    def _findDisplayId(self,root,basefile):
        displayid = root.findtext(u'Metadata/Referat')
        # trim or discard displayid if neccesary -- maybe code like this should live in DVParser?
        if displayid.endswith(u', Referat ännu ej publicerat'): # 29 chars of trailing data, chop them off
           displayid = displayid[:-29]
        if (displayid == u'Referat ännu ej publicerat' or 
            displayid == u'Referat finns ej'):
            displayid = None
        
        if not displayid:
            displayid = root.findtext(u'Metadata/Målnummer')
        if not displayid:
            displayid = root.findtext(u'Metadata/Diarienummer')
        if not displayid:
            displayid = root.findtext(u'Metadata/Domsnummer') # this seems to occur only for MD verdicts - maybe we should transform "2002-14" into "MD 2002:14"
        if not displayid:
            raise LegalSource.ParseError("Couldn't find suitable displayid") # a filename or URN would be useful here...

        return displayid
    
    def _getModuleDir(self):
        return __moduledir__
    ####################################################################
    # IMPLEMENTATION OF Manager INTERFACE  
    ####################################################################
    
    def Parse(self,basefile,verbose=False):
        """'basefile' here is a single digit representing the filename on disc, not
        any sort of inherit case id or similarly"""
        try:
            if verbose:
                print "Setting verbosity"
                log.setLevel(logging.DEBUG)
            start = time()

            infile = os.path.sep.join([self.baseDir, __moduledir__, 'intermediate', 'word', basefile]) + ".doc"
            outfile = os.path.sep.join([self.baseDir, __moduledir__, 'parsed', basefile]) + ".xht2"

            # check to see if the outfile is newer than all ingoing
            # files. If it is, don't parse
            if self._outfileIsNewer([infile],outfile):
                return

            p = self.__parserClass()
            p.verbose = verbose
            parsed = p.Parse(basefile,infile)
            Util.ensureDir(outfile)

            out = file(outfile, "w")
            out.write(parsed)
            out.close()
            Util.indentXmlFile(outfile)
            log.info(u'%s: OK (%.3f sec)', basefile,time()-start)
        except Exception:
            # Vi hanterar traceback-loggning själva eftersom
            # loggging-modulen inte klarar av när källkoden
            # (iso-8859-1-kodad) innehåller svenska tecken
            formatted_tb = [x.decode('iso-8859-1') for x in traceback.format_tb(sys.exc_info()[2])]
            log.error(u'%s: %s:\nMyTraceback (most recent call last):\n%s%s: %s' %
                      (basefile,
                       sys.exc_info()[0].__name__,
                       u''.join(formatted_tb),
                       sys.exc_info()[0].__name__,
                       sys.exc_info()[1]))
            # raise


    def ParseAll(self):
        # print "DV: ParseAll temporarily disabled"
        # return
        downloadDir = self.baseDir + "/dv/downloaded"
        for f in Util.listDirs(downloadDir,"detalj.html"):
            basefile = os.path.basename(f)[:-12]
            self.Parse(basefile)

    def Generate(self,basefile):
        infile = self._xmlFileName(basefile)
        outfile = self._htmlFileName(basefile)
        Util.mkdir(os.path.dirname(outfile))
        print "Generating %s" % outfile
        Util.transform("xsl/dv.xsl",
                       infile,
                       outfile,
                       {},
                       validate=False)
        # print "Generating index for %s" % outfile
        # ad = AnnotatedDoc(outfile)
        # ad.Prepare()

    def GenerateAll(self):
        # print "DV: GenerateAll temporarily disabled"
        # return
        self.__doAllParsed(self.Generate)
        

    def DownloadAll(self):
        sd = DVDownloader(self.baseDir)
        sd.DownloadAll()

    def DownloadNew(self):
        sd = DVDownloader(self.baseDir)
        sd.DownloadNew()

    def IndexAll(self):
        # print "DV: IndexAll temporarily disabled"
        # return
        self.indexroot = ET.Element("documents")
        self.__doAllParsed(self.Index)
        tree = ET.ElementTree(self.indexroot)
        tree.write("%s/%s/index.xml" % (self.baseDir,__moduledir__))
        
        
    def Relate(self,basefile):
        start = time()
        sys.stdout.write("Relate: %s" % basefile)
        xmlFileName = "%s/%s/parsed/%s.xml" % (self.baseDir, __moduledir__,basefile)
        root = ET.ElementTree(file=xmlFileName).getroot()
        urn = root.get('urn') # or root.attribs['urn'] ?
        displayid = self._findDisplayId(root,basefile)
        targetUrns = []  # keeps track of other legal sources that this verdict references, so we can create Reference objects for them

        # delete all previous relations where this document is the object --
        # maybe that won't be needed if the typical GenerateAll scenario
        # begins with wiping the Relation table? It still is useful 
        # in the normal development scenario, though
        Relation.objects.filter(object__exact=urn.encode('utf-8')).delete()

        self._createRelation(urn,Predicate.IDENTIFIER,displayid,allowDuplicates=False)
        
        desc = root.findtext('Metadata/Rubrik')
        self._createRelation(urn,Predicate.DESCRIPTION, desc,allowDuplicates=False)
        
        for e in root.findall(u'Metadata/Sökord'):
            if e.text:
                self._createRelation(urn,Predicate.SUBJECT,e.text)
        for e in root.findall(u'Metadata/Rättsfall'):
            try:
                targetUrn = self._displayIdToURN(e.text,u'urn:x-dv')
                self._createRelation(urn,Predicate.REFERENCES,targetUrn)
                targetUrns.append(targetUrn)
            except LegalSource.IdNotFound:
                pass
        for e in root.findall(u'Metadata/Lagrum/link'):
            if 'law' in e.attrib:
                try:
                    targetUrn = self._createSFSUrn(e)
                    self._createRelation(urn,Predicate.REQUIRES,targetUrn)
                    targetUrns.append(targetUrn)
                except LegalSource.IdNotFound:
                    pass
        
        sys.stdout.write("\tcreating %s references\t" % len(targetUrns))
        for targetUrn in targetUrns:
            self._createReference(basefile = self._UrnToBasefile(targetUrn),
                                  targetUrn = targetUrn, 
                                  sourceUrn = urn,
                                  refLabel = u'Rättsfall',
                                  displayid = displayid,
                                  alternative = None, # this will be filled in later through some other means
                                  desc = desc)
        sys.stdout.write(" %s sec\n" % (time() - start))
        self._flushReferenceCache()
        
    def RelateAll(self):
        # print "DV: RelateAll temporarily disabled"
        # return
        start = time()
        cnt = self.__doAllParsed(self.Relate)
        sys.stdout.write("RelateAll: %s documents handled in %s seconds" % (cnt,(time()-start)))

if __name__ == "__main__":
    #if not '__file__' in dir():
    #    print "probably running from within emacs"
    #    sys.argv = ['DV.py','Parse', '42']
    import logging.config
    logging.config.fileConfig('etc/log.conf')
    DVManager.__bases__ += (DispatchMixin,)
    mgr = DVManager("testdata", __moduledir__)
    mgr.Dispatch(sys.argv)
