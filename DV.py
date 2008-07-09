#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Hanterar domslut (detaljer och referat) fr�n Domstolsverket. Data
h�mtas fr�n DV:s (ickepublika) FTP-server"""

# system libraries
import sys, os, re
import pprint
import types
import codecs
from time import time
from datetime import datetime
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
import Util
from LegalRef import LegalRef,ParseError,Link,LinkSubject
from DispatchMixin import DispatchMixin
from DataObjects import UnicodeStructure, CompoundStructure, \
     MapStructure, IntStructure, DateStructure, PredicateType, \
     serialize

__version__   = (0,1)
__author__    = u"Staffan Malmgren <staffan@tomtebo.org>"
__shortdesc__ = u"Domslut (referat)"
__moduledir__ = "dv"
log = logging.getLogger(__moduledir__)

# Objektmodellen f�r r�ttsfall:
# 
# Referat(list)
#   Metadata(map)
#       'Domstol':                 LinkSubject(u'H�gsta Domstolen',predicate='dc:creator',uri='http://[AP-uri]')
#       'Referatnummer':           UnicodeSubject(u'NJA 1987 s 187', predicate='dc:identifier')
#       '[rattsfallspublikation]': UnicodeSubject(u'NJA,predicate='rinfo:rattsfallspublikation')
#       '[publikationsordinal]':   UnicodeSubject(u'1987:39',predicate='rinfo:publikationsordinal')
#       '[arsutgava]':             DateSubject(1987,predicate='rinfo:arsutgava')
#       '[sidnummer]':             IntSubject(187, predicate='rinfo:sidnummer')
#       'M�lnummer':               UnicodeSubject(u'B 123-86',predicate='rinfo:malnummer')
#       'Domsnummer'               UnicodeSubject(u'',predicate='rinfo:domsnummer')
#       'Diarienummer':            UnicodeSubject(u'',predicate='rinfo:diarienummer')
#       'Avg�randedatum'           DateSubject(date(1987,3,14),predicate='rinfo:avgorandedatum')
#       'Rubrik'                   UnicodeSubject(u'',predicate='dc:description')
#       'Lagrum': list
#           Lagrum(list)
#              unicode/LinkSubject(u'4 kap. 13 � r�tteg�ngsbalken',uri='http://...',predicate='rinfo:lagrum')
#       'R�ttsfall': list
#           Rattsfall(list)
#               unicode/LinkSubject(u'R� 1980 2:68',
#                                   uri='http://...',
#                                   predicate='rinfo:rattsfallshanvisning')
#       'S�kord': list
#           UnicodeSubject(u'F�rhandsbesked',predicate='dc:subject')
#       'Litteratur': list
#           UnicodeSubject(u'Grosskopf, Skattenytt 1988, s. 182-183.', predicate='dct:relation') 
#   Referatstext(list)
#       Stycke(list)
#           unicode/Link

class Referat(CompoundStructure): pass

class Metadata(MapStructure): pass

class UnicodeSubject(PredicateType,UnicodeStructure): pass

class IntSubject(PredicateType,IntStructure): pass

class DateSubject(PredicateType, DateStructure): pass

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
        self.intermediate_dir = baseDir + os.path.sep + __moduledir__ + os.path.sep + 'word'
        if not os.path.exists(self.dir): 
            Util.mkdir(self.dir)
        inifile = self.dir + os.path.sep + __moduledir__ + ".ini"
        log.info(u'Laddar inst�llningar fr�n %s' % inifile)
        self.config = ConfigObj(inifile)
        # Why does this say "super() argument 1 must be type, not
        # classobj"? Because LegalSource.Downloader is an oldstyle
        # class. Change it to inherit from object, or replace the
        # super call with LegalSource.Downloader.__init__(self)
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
        log.info(u'Listar inneh�ll i %s' % url)
        cmd = "ncftpls -m -u %s -p %s %s" % (self.config['ftp_user'], self.config['ftp_pass'], url)
        (ret, stdout, stderr) = Util.runcmd(cmd)
        if ret != 0:
            raise Util.ExternalCommandError(stderr)

        for line in stdout.split("\n"):
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
                        
                    log.info(u'H�mtar %s till %s' % (filename, localdir))
                    os.system("ncftpget -E -u %s -p %s ftp.dom.se %s %s" %
                              (self.config['ftp_user'], self.config['ftp_pass'], localdir, fullname))
                    self.process_zipfile(localdir + os.path.sep + filename)

    re_malnr = re.compile(r'([^_]*)_([^_\.]*)_?(\d*)')
    def process_zipfile(self, zipfilename):
        removed = replaced = created = untouched = 0
        file = zipfile.ZipFile(zipfilename, "r")
        for name in file.namelist():
            # Namnen i zipfilen anv�nder codepage 437 - retro!
            uname = name.decode('cp437')
            m = self.re_malnr.match(uname)
            if m:
                (court, malnr, referatnr) = (m.group(1), m.group(2), m.group(3))
                if referatnr:
                    outfilename = os.path.sep.join([self.intermediate_dir, court, "%s_%s.doc" % (malnr,referatnr)])
                else:
                    outfilename = os.path.sep.join([self.intermediate_dir, court, "%s.doc" % (malnr)])

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
        log.info(u'Processade %s, skapade %s,  bytte ut %s, tog bort %s, l�t bli %s files' % (zipfilename,created,replaced,removed,untouched))


DCT = Namespace(Util.ns['dct'])
XSD = Namespace(Util.ns['xsd'])
RINFO = Namespace(Util.ns['rinfo'])
RINFOEX = Namespace(Util.ns['rinfoex'])
class DVParser(LegalSource.Parser):
    re_NJAref = re.compile(r'(NJA \d{4} s\. \d+) \(alt. (NJA \d{4}:\d+)\)')
    re_delimSplit = re.compile("[:;,] ?").split


    # Mappar termer f�r enkel metadata (enstaka
    # str�ngliteraler/datum/URI:er) fr�n de str�ngar som anv�nds i
    # worddokumenten ('M�lnummer') till de URI:er som anv�nds i
    # rinfo-vokabul�ren
    # ("http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#avgorandedatum").

    # FIXME: f�r allm�nna och f�rvaltningsdomstolar ska kanske hellre
    # referatAvDomstolsavgorande anv�ndas �n malnummer - det �r
    # skillnad p� ett domstolsavg�rande och referatet av detsamma
    #
    # 'Referat' delas upp i rattsfallspublikation ('NJA'),
    # publikationsordinal ('1987:39'), arsutgava (1987) och sidnummer
    # (187). Alternativt kan publikationsordinal/arsutgava/sidnummer
    # ers�ttas med publikationsplatsangivelse.
    labels = {u'Rubrik'        :DCT['description'],
              u'Domstol'       :DCT['creator'], # konvertera till auktoritetspost
              u'M�lnummer'     :RINFO['malnummer'], 
              u'Domsnummer'    :RINFO['domsnummer'],
              u'Diarienummer'  :RINFO['diarienummer'],
              u'Avdelning'     :RINFO['domstolsavdelning'],
              u'Referat'       :DCT['identifier'], 
              u'Avg�randedatum':RINFO['avgorandedatum'], # konvertera till xsd:date
              }

    # Metadata som kan inneh�lla noll eller flera poster.
    # Litteratur/s�kord har ingen motsvarighet i RINFO-vokabul�ren
    multilabels = {u'Lagrum'    :RINFO['lagrum'],
                   u'R�ttsfall' :RINFO['rattsfallshanvisning'],
                   u'Litteratur':DCT['relation'], # dct:references vore b�ttre, men s�dana ska inte ha literalv�rden
                   u'S�kord'    :DCT['subject']
                   }

    # Listan h�rledd fr�n containers.n3/rattsfallsforteckningar.n3 i
    # rinfoprojektets k�llkod - en ambiti�sare l�sning vore att l�sa
    # in de faktiska N3-filerna i en rdflib-graf.
    publikationsuri = {u'NJA': 'http://rinfo.lagrummet.se/ref/rff/nja',
                       u'RH': 'http://rinfo.lagrummet.se/ref/rff/rh',
                       u'M�D': 'http://rinfo.lagrummet.se/ref/rff/mod',
                       u'R�': 'http://rinfo.lagrummet.se/ref/rff/ra',
                       u'MIG': 'http://rinfo.lagrummet.se/ref/rff/mig',
                       u'AD': 'http://rinfo.lagrummet.se/ref/rff/ad',
                       u'MD': 'http://rinfo.lagrummet.se/ref/rff/md',
                       u'F�D': 'http://rinfo.lagrummet.se/ref/rff/fod'}
                       
    containerid = {'http://rinfo.lagrummet.se/ref/rff/nja': '/publ/rattsfall/nja/',
                   'http://rinfo.lagrummet.se/ref/rff/rh': '/publ/rattsfall/rh/',
                   'http://rinfo.lagrummet.se/ref/rff/mod': '/publ/rattsfall/mod/',
                   'http://rinfo.lagrummet.se/ref/rff/ra': '/publ/rattsfall/ra/',
                   'http://rinfo.lagrummet.se/ref/rff/mig': '/publ/rattsfall/mig/',
                   'http://rinfo.lagrummet.se/ref/rff/ad': '/publ/rattsfall/ad/',
                   'http://rinfo.lagrummet.se/ref/rff/md': '/publ/rattsfall/md/',
                   'http://rinfo.lagrummet.se/ref/rff/fod': '/publ/rattsfall/fod/'}

                   
        
    def Parse(self,id,docfile):
        import codecs
        self.id = id
        htmlfile = docfile.replace('word','html').replace('.doc','.html')
        Util.word_to_html(docfile,htmlfile)

        lagrum_parser = LegalRef(LegalRef.LAGRUM)
        rattsfall_parser = LegalRef(LegalRef.RATTSFALL)

        # Basic parsing
        soup = Util.loadSoup(htmlfile)
        head = Metadata()
        # Worddokumenten �r bara mestadels standardiserade...  En
        # alternativ fallbackmetod vore att s�ka efter tabellceller
        # vars enda text �r n�got av de k�nda domstolsnamnen
        #
        # Ibland saknas domstolsnamnet helt eller �r felskrivet
        # (".H�gsta Domstolen"). D�r borde vi kunna falla tillbaks p�
        # f�rsta delen av basename/id
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
        txt = Util.elementText(node)
        authrec = self.find_authority_rec(txt),
        head[u'Domstol'] = LinkSubject(txt,
                                       uri=unicode(authrec[0]),
                                       predicate=self.labels[u'Domstol'])
        
            
        

        # Det som st�r till h�ger om domstolsnamnet �r referatnumret
        # (exv "NJA 1987 s. 113")
        node = node.findNextSibling('td')
        head[u'Referat'] = UnicodeSubject(Util.elementText(node),
                                          predicate=self.labels[u'Referat'])
        if not head[u'Referat']:
            # F�r specialdomstolarna kan man lista ut referatnumret
            # fr�n m�lnumret - det borde vi f�rs�ka g�ra h�r
            raise AssertionError(u"Kunde inte hitta referatbeteckningen i %s" % htmlfile)

        # Hitta �vriga enkla metadataf�lt i sidhuvudet
        for key in self.labels.keys():
            node = soup.firstText(key+u':')
            if node:
                txt = Util.elementText(node.findParent('td').findNextSibling('td'))
                if txt: # skippa f�lt med tomma str�ngen-v�rden
                    head[key] = UnicodeSubject(txt, predicate=self.labels[key])

        # Hitta sammansatta metadata i sidhuvudet
        for key in [u"Lagrum", u"R�ttsfall"]:
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
                        containercls = Lagrum
                        parsefunc = lagrum_parser.parse
                    elif key == u'R�ttsfall':
                        containercls = Rattsfall
                        parsefunc = rattsfall_parser.parse

                    head[key] = []
                    for i in items:
                        l = containercls()
                        # Modify the result of parsing for references
                        # and change all Link objects to LinkSubject
                        # objects with an extra RDF predicate
                        # property. Maybe the link class should be
                        # changed to do this instead?
                        for node in parsefunc(i):
                            if isinstance(node,Link):
                                l.append(LinkSubject(unicode(node),
                                                     uri=unicode(node.uri),
                                                     predicate=self.multilabels[key]))
                            else:
                                l.append(node)

                        head[key].append(l)

        # Hitta sj�lva referatstexten... h�r kan man g�ra betydligt
        # mer, exv hitta avsnitten f�r de olika instanserna, hitta
        # dissenternas domsk�l, ledam�ternas namn, h�nvisning till
        # r�ttsfall och lagrum i l�pande text...
        body = Referatstext()
        for p in soup.firstText(u'REFERAT').findParent('tr').findNextSibling('tr').fetch('p'):
            body.append(Stycke([Util.elementText(p)]))

        # Hitta sammansatta metadata i sidfoten
        txt = Util.elementText(soup.firstText(u'S�kord:').findParent('td').nextSibling.nextSibling)
        head[u'S�kord'] = [UnicodeSubject(Util.normalizeSpace(x),predicate=self.multilabels[u'S�kord'])
                           for x in self.re_delimSplit(txt)]
        
        if soup.firstText(u'Litteratur:'):
            txt = Util.elementText(soup.firstText(u'Litteratur:').findParent('td').nextSibling.nextSibling)
            head[u'Litteratur'] = [UnicodeSubject(Util.normalizeSpace(x),predicate=self.multilabels[u'Litteratur'])
                                   for x in txt.split(";")]

        # Putsa upp metadatan p� olika s�tt
        #
        # L�gg till utgivare
        authrec = self.find_authority_rec(u'Domstolsverket'),
        head[u'Utgivare'] = LinkSubject(u'Domstolsverket',
                                       uri=unicode(authrec[0]),
                                       predicate=DCT['publisher'])

        # I RINFO-vokabul�ren motsvaras en referatsbeteckning (exv
        # "NJA 1987 s 187 (NJA 1987:39)") av upp till fyra separata
        # properties
        if u'Referat' in head:
            txt = unicode(head[u'Referat'])
            for (pred,regex) in {u'rattsfallspublikation':r'([^ ]+)',
                                 u'publikationsordinal'  :r'(\d{4}:\d+)',
                                 u'arsutgava'            :r'(\d{4})',
                                 u'sidnummer'            :r's.? ?(\d+)'}.items():
                m = re.search(regex,txt)
                # print "Trying to match %s with %s" % (regex, txt)
                if m:
                    # print "success"
                    # FIXME: arsutgava should be typed as DateSubject
                    if pred == 'rattsfallspublikation':
                        head[u'[%s]'%pred] = self.publikationsuri[m.group(1)]
                    else:
                        head[u'[%s]'%pred] = UnicodeSubject(m.group(1),predicate=RINFO[pred])
            if not '[publikationsordinal]' in head: # Workaround f�r AD-domar
                m = re.search(r'(\d{4}) nr (\d+)', txt)
                if m:
                    head['[publikationsordinal]'] = m.group(1) + ":" + m.group(2)
                

        # Hitta r�tt URI till det h�r referatet.
        #if u'Referat' in head:
        #    res = rattsfall_parser.parse(head[u'Referat'])
        #    if hasattr(res[0], 'uri'):
        #        docuri = res[0].uri
        #    else:
        #        docuri = URIRef(u'http://lagen.nu/%s' % self.id)
        #else:
        #    docuri = URIRef(u'http://lagen.nu/%s' % self.id)
        #pprint.pprint(head)
        assert '[rattsfallspublikation]' in head, "missing rinfo:rattsfallspublikation"
        assert '[publikationsordinal]' in head, "missing rinfo:publikationsordinal"
        
        head['xml:base'] = "http://rinfo.lagrummet.se%s%s" % (self.containerid[head['[rattsfallspublikation]']], head['[publikationsordinal]'])

        # Putsa till avg�randedatum - det �r ett date, inte en string
        head[u'Avg�randedatum'] = DateSubject(datetime.strptime(unicode(head[u'Avg�randedatum']),'%Y-%m-%d'),
                                              predicate=self.labels[u'Avg�randedatum'])

        
        # OK, f�rdigputsat!

        # print serialize(head)
        xhtml = self.generate_xhtml(head,body,None,__moduledir__,globals())
        return xhtml

    
    def add_to_graph(self,objecturi,graph,nodes):
        for item in nodes:
            if isinstance(item,list):
                self.add_to_graph(objecturi,graph,item)
            elif isinstance(item,PredicateType):
                if isinstance(item,Link):
                    # print "adding %s as %s (URIRef)" % (item.uri,item.predicate)
                    graph.add((objecturi,item.predicate,URIRef(item.uri)))
                else:
                    # print "adding %s as %s (Literal)" % (item,item.predicate)
                    graph.add((objecturi,item.predicate,Literal(item)))
            else:
                # probably just a unicode object used for presentation
                pass

    def __createUrn(self,data):
        domstolar = {
            u'Marknadsdomstolen':                 u'md',
            u'Hovr�tten f�r �vre Norrland':       u'hovr:�vrenorrland',
            u'Hovr�tten f�r Nedre Norrland':      u'hovr:nedrenorrland',
            u'Hovr�tten �ver Sk�ne och Blekinge': u'hovr:sk�ne',
            u'Svea hovr�tt':                      u'hovr:svea',
            u'Hovr�tten f�r V�stra Sverige':      u'hovr:v�stra',
            u'G\xf6ta hovr\xe4tt':                u'hovr:g�ta',
            u'Kammarr\xe4tten i G\xf6teborg':     u'kamr:g�teborg',
            u'Kammarr\xe4tten i J\xf6nk\xf6ping': u'kamr:j�nkoping',
            u'Kammarr\xe4tten i Stockholm':       u'kamr:stockholm',
            u'Kammarr\xe4tten i Sundsvall':       u'kamr:sundsvall',
            u'Arbetsdomstolen':                   u'ad',
            u'H�gsta domstolen':                  u'hd',
            u'Regeringsr�tten':                   u'regr',
            u'Patentbesv�rsr�tten':               u'pbr',
            u'R�ttshj�lpsn�mnden':                u'rhn',
            u'Milj��verdomstolen':                u'm�d',
             }
        idfield = {
            u'Marknadsdomstolen':                 u'Domsnummer',
            u'Hovr�tten f�r �vre Norrland':       u'M�lnummer',
            u'Hovr�tten f�r Nedre Norrland':      u'M�lnummer',
            u'Hovr�tten �ver Sk�ne och Blekinge': u'M�lnummer',
            u'Svea hovr�tt':                      u'M�lnummer',
            u'Hovr�tten f�r V�stra Sverige':      u'M�lnummer',
            u'G\xf6ta hovr\xe4tt':                u'M�lnummer',
            u'Kammarr\xe4tten i G\xf6teborg':     u'M�lnummer',
            u'Kammarr\xe4tten i J\xf6nk\xf6ping': u'M�lnummer',
            u'Kammarr\xe4tten i Stockholm':       u'M�lnummer',
            u'Kammarr\xe4tten i Sundsvall':       u'M�lnummer',
            u'Arbetsdomstolen':                   u'Domsnummer',
            u'H�gsta domstolen':                  u'M�lnummer',
            u'Regeringsr�tten':                   u'M�lnummer',
            u'Patentbesv�rsr�tten':               u'M�lnummer',
            u'R�ttshj�lpsn�mnden':                u'Diarienummer',
            u'Milj��verdomstolen':                u'M�lnummer',
            }
        domstol = data['Domstol']
        urn = "urn:x-dv:%s:%s" % (domstolar[domstol], data[idfield[domstol]])
        return urn


class DVManager(LegalSource.Manager):
    __parserClass = DVParser
    

    ####################################################################
    # CLASS-SPECIFIC HELPER FUNCTIONS
    ####################################################################
    
    # FIXME: This could and should be done in LegalSource
    def __doAll(self,dir,suffix,method):
        from sets import Set
        basefiles = Set()
        # find all IDs based on existing files
        for f in Util.listDirs(dir, suffix):
            # this transforms 'foo/bar/baz/HDO/1-01.doc' to 'HDO/1-01'
            basefile = "/".join(os.path.split(os.path.splitext(os.sep.join(os.path.normpath(f).split(os.sep)[-2:]))[0]))
            basefiles.add(basefile)
        for basefile in sorted(basefiles,Util.numcmp):
            method(basefile)

    def __doAllParsed(self,method,max=None):
        cnt = 0
        for f in Util.listDirs(self.baseDir+u'/dv/parsed',u'xht2'):
            if max and (max <= cnt):
                return cnt
            cnt += 1
            basefile = "/".join(os.path.split(os.path.splitext(os.sep.join(os.path.normpath(f).split(os.sep)[-2:]))[0]))
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
        if displayid.endswith(u', Referat �nnu ej publicerat'): # 29 chars of trailing data, chop them off
           displayid = displayid[:-29]
        if (displayid == u'Referat �nnu ej publicerat' or 
            displayid == u'Referat finns ej'):
            displayid = None
        
        if not displayid:
            displayid = root.findtext(u'Metadata/M�lnummer')
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
            # print "Basefile: %s" % basefile
            infile = os.path.sep.join([self.baseDir, __moduledir__, 'intermediate', 'word', basefile]) + ".doc"
            outfile = os.path.sep.join([self.baseDir, __moduledir__, 'parsed', basefile]) + ".xht2"
            # print "infile: %s" % infile
            # check to see if the outfile is newer than all ingoing
            # files. If it is, don't parse
            force = True
            if not force and self._outfileIsNewer([infile],outfile):
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
            # Vi hanterar traceback-loggning sj�lva eftersom
            # loggging-modulen inte klarar av n�r k�llkoden
            # (iso-8859-1-kodad) inneh�ller svenska tecken
            formatted_tb = [x.decode('iso-8859-1') for x in traceback.format_tb(sys.exc_info()[2])]
            log.error(u'%r: %s:\nMyTraceback (most recent call last):\n%s%s %s' %
                      (basefile,
                       sys.exc_info()[0].__name__, 
                       u''.join(formatted_tb),
                       sys.exc_info()[0].__name__,
                       unicode(str(sys.exc_info()[1]), 'iso-8859-1')))
            # raise


    def ParseAll(self):
        #log.info("ParseAll temporarily disabled")
        #return
        self.__doAll(os.path.sep.join([self.baseDir, u'dv', 'intermediate','word']), '.doc',self.Parse)

    def Generate(self,basefile):
        infile = self._xmlFileName(basefile)
        outfile = self._htmlFileName(basefile)
        Util.mkdir(os.path.dirname(outfile))
        log.info(u'Transformerar %s > %s' % (infile,outfile))
        Util.transform("xsl/dv.xsl",
                       infile,
                       outfile,
                       {},
                       validate=False)

    def GenerateAll(self):
        self.__doAllParsed(self.Generate)
        
    def DownloadAll(self):
        sd = DVDownloader(self.baseDir)
        sd.DownloadAll()

    def DownloadNew(self):
        sd = DVDownloader(self.baseDir)
        sd.DownloadNew()

    def IndexAll(self):
        self.indexroot = ET.Element("documents")
        self.__doAllParsed(self.Index)
        tree = ET.ElementTree(self.indexroot)
        tree.write("%s/%s/index.xml" % (self.baseDir,__moduledir__))


if __name__ == "__main__":
    #if not '__file__' in dir():
    #    print "probably running from within emacs"
    #    sys.argv = ['DV.py','Parse', '42']
    import logging.config
    logging.config.fileConfig('etc/log.conf')
    DVManager.__bases__ += (DispatchMixin,)
    mgr = DVManager(u'testdata', __moduledir__)
    mgr.Dispatch(sys.argv)
