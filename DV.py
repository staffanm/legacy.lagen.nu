#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Hanterar domslut (detaljer och referat) från Domstolsverket. Data
hämtas från DV:s (ickepublika) FTP-server"""

# system libraries
import sys, os, re
import pprint
import types
import codecs
from time import time, mktime
from tempfile import mktemp
from datetime import datetime
import xml.etree.cElementTree as ET # Python 2.5 spoken here
import logging
import zipfile
import traceback
from collections import defaultdict
from operator import itemgetter
import cgi

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

# Objektmodellen för rättsfall:
# 
# Referat(list)
#   Metadata(map)
#       'Domstol':                 LinkSubject(u'Högsta Domstolen',predicate='dc:creator',uri='http://[AP-uri]')
#       'Referatnummer':           UnicodeSubject(u'NJA 1987 s 187', predicate='dc:identifier')
#       '[rattsfallspublikation]': UnicodeSubject(u'NJA,predicate='rinfo:rattsfallspublikation')
#       '[publikationsordinal]':   UnicodeSubject(u'1987:39',predicate='rinfo:publikationsordinal')
#       '[arsutgava]':             DateSubject(1987,predicate='rinfo:arsutgava')
#       '[sidnummer]':             IntSubject(187, predicate='rinfo:sidnummer')
#       'Målnummer':               UnicodeSubject(u'B 123-86',predicate='rinfo:malnummer')
#       'Domsnummer'               UnicodeSubject(u'',predicate='rinfo:domsnummer')
#       'Diarienummer':            UnicodeSubject(u'',predicate='rinfo:diarienummer')
#       'Avgörandedatum'           DateSubject(date(1987,3,14),predicate='rinfo:avgorandedatum')
#       'Rubrik'                   UnicodeSubject(u'',predicate='dc:description')
#       'Lagrum': list
#           Lagrum(list)
#              unicode/LinkSubject(u'4 kap. 13 § rättegångsbalken',uri='http://...',predicate='rinfo:lagrum')
#       'Rättsfall': list
#           Rattsfall(list)
#               unicode/LinkSubject(u'RÅ 1980 2:68',
#                                   uri='http://...',
#                                   predicate='rinfo:rattsfallshanvisning')
#       'Sökord': list
#           UnicodeSubject(u'Förhandsbesked',predicate='dc:subject')
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
    def __init__(self,config):
        super(DVDownloader,self).__init__(config) # sets config, logging initializes browser
        self.intermediate_dir = os.path.sep.join([config['datadir'], __moduledir__, 'intermediate','word'])

    def _get_module_dir(self):
        return __moduledir__

    def DownloadAll(self):
        unpack_all = False
        if unpack_all:
            zipfiles = []
            for d in os.listdir(self.download_dir):
                if os.path.isdir("%s/%s" % (self.download_dir,d)):
                    for f in os.listdir("%s/%s" % (self.download_dir,d)):
                        if os.path.isfile("%s/%s/%s" % (self.download_dir,d,f)):
                            zipfiles.append("%s/%s/%s" % (self.download_dir,d,f))
            for f in os.listdir("%s" % (self.download_dir)):
                if os.path.isfile("%s/%s" % (self.download_dir,f)) and f.endswith(".zip"):
                   zipfiles.append("%s/%s" % (self.download_dir,f))

            for f in zipfiles:
                self.process_zipfile(f)
        else:
            self.download(recurse=True)


    def DownloadNew(self):
        self.download(recurse=False)
        
    def download(self,dirname='',recurse=False):
        # Download using ncftpls/ncftpget, since we can't get python:s
        # ftplib to play nice w/ domstolsverkets ftp server
        url = 'ftp://ftp.dom.se/%s' % dirname
        log.info(u'Listar innehåll i %s' % url)
        cmd = "ncftpls -m -u %s -p %s %s" % (self.config[__moduledir__]['ftp_user'], self.config[__moduledir__]['ftp_pass'], url)
        (ret, stdout, stderr) = Util.runcmd(cmd)
        if ret != 0:
            raise Util.ExternalCommandError(stderr)

        for line in stdout.split("\n"):
            parts = line.split(";")
            filename = parts[-1].strip()
            if line.startswith('type=dir') and recurse:
                self.download(filename,recurse)
            elif line.startswith('type=file'):
                if os.path.exists(os.path.sep.join([self.download_dir,dirname,filename])):
                    pass
                    # localdir = self.download_dir + os.path.sep + dirname
                    # self.process_zipfile(localdir + os.path.sep + filename)
                else:
                    if dirname:
                        fullname = '%s/%s' % (dirname,filename)
                        localdir = self.download_dir + os.path.sep + dirname
                        Util.mkdir(localdir)
                    else:
                        fullname = filename
                        localdir = self.download_dir
                        
                    log.info(u'Hämtar %s till %s' % (filename, localdir))
                    os.system("ncftpget -E -u %s -p %s ftp.dom.se %s %s" %
                              (self.config[__moduledir__]['ftp_user'], self.config[__moduledir__]['ftp_pass'], localdir, fullname))
                    self.process_zipfile(localdir + os.path.sep + filename)

    re_malnr = re.compile(r'([^_]*)_([^_\.]*)_?(\d*)')
    re_bytut_malnr = re.compile(r'([^_]*)_([^_\.]*)_BYTUT_\d+-\d+-\d+_?(\d*)')
    def process_zipfile(self, zipfilename):
        removed = replaced = created = untouched = 0
        zipf = zipfile.ZipFile(zipfilename, "r")
        for name in zipf.namelist():
            # Namnen i zipfilen använder codepage 437 - retro!
            uname = name.decode('cp437')
            uname = os.path.split(uname)[1]
            #log.debug("In: %s" % uname)
            if 'BYTUT' in name:
                m = self.re_bytut_malnr.match(uname)
            else:
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
                    # log.debug(u'%s: Packar upp %s' % (zipfilename, outfilename))
                    if "BYTUT" in name:
                        log.info(u'Byter ut befintligt referat %s %s' % (court,malnr))
                        if not os.path.exists(outfilename):
                            log.warning(u'Filen %s som ska bytas ut fanns inte' % outfilename)
                        self.download_log.info(outfilename)
                        replaced += 1
                    else:
                        if os.path.exists(outfilename):
                            untouched += 1
                            continue
                        else:
                            self.download_log.info(outfilename)
                            created += 1
                    data = zipf.read(name)
                    
                    Util.ensureDir(outfilename)
                    # sys.stdout.write(".")
                    outfile = open(outfilename,"wb")
                    outfile.write(data)
                    outfile.close()
                    # Make the unzipped files have correct timestamp
                    zi = zipf.getinfo(name)
                    dt = datetime(*zi.date_time)
                    ts = mktime(dt.timetuple())
                    os.utime(outfilename, (ts,ts))
                    #log.debug("Out: %s" % outfilename)
            else:
                log.warning(u'Kunde inte tolka filnamnet %s i %s' % (name, zipfilename))
        log.info(u'Processade %s, skapade %s,  bytte ut %s, tog bort %s, lät bli %s files' % (zipfilename,created,replaced,removed,untouched))


DCT = Namespace(Util.ns['dct'])
XSD = Namespace(Util.ns['xsd'])
RINFO = Namespace(Util.ns['rinfo'])
RINFOEX = Namespace(Util.ns['rinfoex'])
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
    labels = {u'Rubrik'        :DCT['description'],
              u'Domstol'       :DCT['creator'], # konvertera till auktoritetspost
              u'Målnummer'     :RINFO['malnummer'], 
              u'Domsnummer'    :RINFO['domsnummer'],
              u'Diarienummer'  :RINFO['diarienummer'],
              u'Avdelning'     :RINFO['domstolsavdelning'],
              u'Referat'       :DCT['identifier'], 
              u'Avgörandedatum':RINFO['avgorandedatum'], # konvertera till xsd:date
              }

    # Metadata som kan innehålla noll eller flera poster.
    # Litteratur/sökord har ingen motsvarighet i RINFO-vokabulären
    multilabels = {u'Lagrum'    :RINFO['lagrum'],
                   u'Rättsfall' :RINFO['rattsfallshanvisning'],
                   u'Litteratur':DCT['relation'], # dct:references vore bättre, men sådana ska inte ha literalvärden
                   u'Sökord'    :DCT['subject']
                   }

    # Listan härledd från containers.n3/rattsfallsforteckningar.n3 i
    # rinfoprojektets källkod - en ambitiösare lösning vore att läsa
    # in de faktiska N3-filerna i en rdflib-graf.
    publikationsuri = {u'NJA': u'http://rinfo.lagrummet.se/ref/rff/nja',
                       u'RH': u'http://rinfo.lagrummet.se/ref/rff/rh',
                       u'MÖD': u'http://rinfo.lagrummet.se/ref/rff/mod',
                       u'RÅ': u'http://rinfo.lagrummet.se/ref/rff/ra',
                       u'MIG': u'http://rinfo.lagrummet.se/ref/rff/mig',
                       u'AD': u'http://rinfo.lagrummet.se/ref/rff/ad',
                       u'MD': u'http://rinfo.lagrummet.se/ref/rff/md',
                       u'FÖD': u'http://rinfo.lagrummet.se/ref/rff/fod'}
                       
    def Parse(self,id,docfile):
        import codecs
        self.id = id
        htmlfile = docfile.replace('word','html').replace('.doc','.html')
        Util.word_to_html(docfile,htmlfile)

        # FIXME: This is almost identical to the code in
        # SFSManager.Parse - should be refactored somehow
        patchfile = 'patches/dv/%s.patch' % id
        if os.path.exists(patchfile):
            patchedfile = mktemp()
            # we don't want to sweep the fact that we're patching under the carpet
            log.warning(u'%s: Applying patch %s' % (id, patchfile))
            cmd = 'patch -s %s %s -o %s' % (htmlfile, patchfile, patchedfile)
            log.debug(u'%s: running %s' % (id, cmd))
            (ret, stdout, stderr) = Util.runcmd(cmd)
            if ret == 0: # successful patch
                # patch from cygwin always seem to produce unix lineendings
                cmd = 'unix2dos %s' % patchedfile
                log.debug(u'%s: running %s' % (id, cmd))
                (ret, stdout, stderr) = Util.runcmd(cmd)
                if ret == 0: 
                    htmlfile = patchedfile
                else:
                    log.warning(u"%s: Failed lineending conversion: %s" % (id, stderr))
            else:
                log.warning(u"%s: Could not apply patch %s: %s" % (id, patchfile, stdout.strip()))
            

        lagrum_parser = LegalRef(LegalRef.LAGRUM)
        rattsfall_parser = LegalRef(LegalRef.RATTSFALL)

        # Basic parsing
        soup = Util.loadSoup(htmlfile)
        head = Metadata()
        # Worddokumenten är bara mestadels standardiserade...  En
        # alternativ fallbackmetod vore att söka efter tabellceller
        # vars enda text är något av de kända domstolsnamnen
        #
        # Ibland saknas domstolsnamnet helt eller är felskrivet
        # (".Högsta Domstolen"). Det löses genom att
        # find_authority_rec fuzzymatchar.
        if soup.first('span', 'riDomstolsRubrik'):
            node = soup.first('span', 'riDomstolsRubrik').findParent('td')
        elif soup.first('td', 'ritop1'):
            node = soup.first('td', 'ritop1')
        elif soup.first('span', style="letter-spacing:2.0pt"):
            node = soup.first('span', style="letter-spacing:2.0pt").findParent('td')
        elif soup.first('span', style="letter-spacing:1.3pt"):
            node = soup.first('span', style="letter-spacing:1.3pt").findParent('td')
        elif soup.first('span', style="font-family:Verdana;letter-spacing:2.0pt"):
            node = soup.first('span', style="font-family:Verdana;letter-spacing:2.0pt").findParent('td')
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
        
            
        

        # Det som står till höger om domstolsnamnet är referatnumret
        # (exv "NJA 1987 s. 113")
        node = node.findNextSibling('td')
        head[u'Referat'] = UnicodeSubject(Util.elementText(node),
                                          predicate=self.labels[u'Referat'])
        if not head[u'Referat']:
            # För specialdomstolarna kan man lista ut referatnumret
            # från målnumret - det borde vi försöka göra här
            raise AssertionError(u"Kunde inte hitta referatbeteckningen i %s" % htmlfile)

        # Hitta övriga enkla metadatafält i sidhuvudet
        for key in self.labels.keys():
            node = soup.firstText(key+u':')
            if node:
                txt = Util.elementText(node.findParent('td').findNextSibling('td'))
                if txt: # skippa fält med tomma strängen-värden
                    head[key] = UnicodeSubject(txt, predicate=self.labels[key])

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
                        containercls = Lagrum
                        parsefunc = lagrum_parser.parse
                    elif key == u'Rättsfall':
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

        # Hitta själva referatstexten... här kan man göra betydligt
        # mer, exv hitta avsnitten för de olika instanserna, hitta
        # dissenternas domskäl, ledamöternas namn, hänvisning till
        # rättsfall och lagrum i löpande text...
        body = Referatstext()
        for p in soup.firstText(u'REFERAT').findParent('tr').findNextSibling('tr').fetch('p'):
            body.append(Stycke([Util.elementText(p)]))

        # Hitta sammansatta metadata i sidfoten
        txt = Util.elementText(soup.firstText(u'Sökord:').findParent('td').nextSibling.nextSibling)
        head[u'Sökord'] = [UnicodeSubject(Util.normalizeSpace(x),predicate=self.multilabels[u'Sökord'])
                           for x in self.re_delimSplit(txt)]
        
        if soup.firstText(u'Litteratur:'):
            txt = Util.elementText(soup.firstText(u'Litteratur:').findParent('td').nextSibling.nextSibling)
            head[u'Litteratur'] = [UnicodeSubject(Util.normalizeSpace(x),predicate=self.multilabels[u'Litteratur'])
                                   for x in txt.split(";")]

        # Putsa upp metadatan på olika sätt
        #
        # Lägg till utgivare
        authrec = self.find_authority_rec(u'Domstolsverket'),
        head[u'Utgivare'] = LinkSubject(u'Domstolsverket',
                                       uri=unicode(authrec[0]),
                                       predicate=DCT['publisher'])

        # I RINFO-vokabulären motsvaras en referatsbeteckning (exv
        # "NJA 1987 s 187 (NJA 1987:39)") av upp till fyra separata
        # properties
        if u'Referat' in head:
            # print "finding out stuff from %s" % head['Referat']
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
                        tmp_publikationsid = m.group(1)
                        # head[u'[%s]'%pred] = self.publikationsuri[m.group(1)]
                        head[u'[%s]'%pred] = UnicodeSubject(self.publikationsuri[m.group(1)],
                                                            predicate=RINFO[pred])
                    else:
                        head[u'[%s]'%pred] = UnicodeSubject(m.group(1),predicate=RINFO[pred])
            if not '[publikationsordinal]' in head: # Workaround för AD-domar
                m = re.search(r'(\d{4}) nr (\d+)', txt)
                if m:
                    head['[publikationsordinal]'] = m.group(1) + ":" + m.group(2)
                else: # workaround för RegR-domar
                    m = re.search(r'(\d{4}) ref. (\d+)', txt)
                    if m:
                        head['[publikationsordinal]'] = m.group(1) + ":" + m.group(2)

            m = re.search(r'(NJA \d{4} s.? \d+)', head['Referat'])
            if m:
                head['[referatkortform]'] = UnicodeSubject(m.group(1),
                                                           predicate=self.labels[u'Referat'])
                head['Referat'] = unicode(head['Referat'])
            

        # Find out correct URI for this case, preferably by leveraging
        # the URI formatting code in LegalRef
        if u'Referat' in head:
            assert '[rattsfallspublikation]' in head, "missing rinfo:rattsfallspublikation for %s" % head['Referat']
            assert '[publikationsordinal]' in head, "missing rinfo:publikationsordinal for %s" % head['Referat']
        else:
            assert '[rattsfallspublikation]' in head, "missing rinfo:rattsfallspublikation"
            assert '[publikationsordinal]' in head, "missing rinfo:publikationsordinal"
            
        head['xml:base'] = None
        if u'Referat' in head:
            res = rattsfall_parser.parse(head[u'Referat'])
            if hasattr(res[0], 'uri'):
                head['xml:base'] = res[0].uri

        if not head['xml:base']:
            log.error(u'%s: Could not find out URI for this doc automatically (%s)' % (self.id, head[u'Referat']))
            #print head.keys()
            #attrs = {'domstol':tmp_publikationsid,
            #         'lopnr':head['[publikationsordinal]']}
            #head['xml:base'] = rattsfall_parser.make_uri(attrs)
        
        # head['xml:base'] = "http://rinfo.lagrummet.se%s%s" % (self.containerid[head['[rattsfallspublikation]']], head['[publikationsordinal]'])

        # Putsa till avgörandedatum - det är ett date, inte en string
        head[u'Avgörandedatum'] = DateSubject(datetime.strptime(unicode(head[u'Avgörandedatum']),'%Y-%m-%d'),
                                              predicate=self.labels[u'Avgörandedatum'])

        
        # OK, färdigputsat!

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

class DVManager(LegalSource.Manager):
    __parserClass = DVParser
    re_xmlbase = re.compile('xml:base="http://rinfo.lagrummet.se/publ/rattsfall/([^"]+)"').search
    # Converts a NT file to RDF/XML -- needed for uri.xsl to work for legal cases
    def NTriplesToXML(self):
        ntfile = os.path.sep.join([self.baseDir, self.moduleDir, u'parsed', u'rdf.nt'])
        xmlfile = os.path.sep.join([self.baseDir, self.moduleDir, u'parsed', u'rdf.xml']) 
        minixmlfile = os.path.sep.join([self.baseDir, self.moduleDir, u'parsed', u'rdf-mini.xml']) 
        log.info("Loading NT file %s" % ntfile)
        g = Graph()
        for key, value in Util.ns.items():
            g.bind(key,  Namespace(value));
        g.parse(ntfile,format="nt")

        log.info("Making a minimal graph")
        mg = Graph()
        for key, value in Util.ns.items():
            mg.bind(key,  Namespace(value));
        for triple in g:
            if triple[1] == RDF.type:
                mg.add(triple)

        log.info("Serializing the minimal graph")
        f = open(minixmlfile, 'w')
        f.write(mg.serialize(format="pretty-xml"))
        f.close()
        
        log.info("Serializing to file %s" % xmlfile)
        f = open(xmlfile, 'w')
        f.write(g.serialize(format="pretty-xml"))
        f.close()
    

    ####################################################################
    # IMPLEMENTATION OF Manager INTERFACE  
    ####################################################################
    
    def Parse(self,basefile,verbose=False):
        """'basefile' here is a single digit representing the filename on disc, not
        any sort of inherit case id or similarly"""
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
        force = (self.config[__moduledir__]['parse_force'] == 'True')
        if not force and self._outfile_is_newer([infile],outfile):
            log.debug(u"%s: Överhoppad", basefile)
            return
        # print "Force: %s, infile: %s, outfile: %s" % (force,infile,outfile)

        p = self.__parserClass()
        p.verbose = verbose
        parsed = p.Parse(basefile,infile)
        Util.ensureDir(outfile)

        tmpfile = mktemp()
        out = file(tmpfile, "w")
        out.write(parsed)
        out.close()
        Util.indentXmlFile(tmpfile)
        Util.replace_if_different(tmpfile,outfile)
        log.info(u'%s: OK (%.3f sec)', basefile,time()-start)

    def ParseAll(self):
        intermediate_dir = os.path.sep.join([self.baseDir, u'dv', 'intermediate','word'])
        self._do_for_all(intermediate_dir, '.doc',self.Parse)

    def Generate(self,basefile):
        infile = self._xmlFileName(basefile)
        outfile = self._htmlFileName(basefile)

        # get URI from basefile as fast as possible
        head = codecs.open(infile,encoding='utf-8').read(1024)
        m = self.re_xmlbase(head)
        if m:
            mapfile = os.path.sep.join([self.baseDir, self.moduleDir, u'generated', u'uri.map'])
            Util.ensureDir(mapfile)
            f = codecs.open(mapfile,'a',encoding='iso-8859-1')
            f.write(u"%s\t%s\n" % (m.group(1),basefile))
        else:
            log.warning("could not find xml:base in %s" % infile)

        force = (self.config[__moduledir__]['generate_force'] == 'True')
        if not force and self._outfile_is_newer([infile], outfile):
            log.debug(u"%s: Överhoppad", basefile)
            return
        Util.mkdir(os.path.dirname(outfile))
        log.info(u'Transformerar %s > %s' % (infile,outfile))
        Util.transform("xsl/dv.xsl",
                       infile,
                       outfile,
                       {},
                       validate=False)
        

    def GenerateAll(self):
        Util.robust_remove(os.path.sep.join([self.baseDir, u'dv', 'generated', 'uri.map']))
        parsed_dir = os.path.sep.join([self.baseDir, u'dv', 'parsed'])
        self._do_for_all(parsed_dir, '.xht2',self.Generate)
        
    def ParseGen(self,basefile):
        self.Parse(basefile)
        self.Generate(basefile)

    def DownloadAll(self):
        sd = DVDownloader(self.config)
        sd.DownloadAll()

    def DownloadNew(self):
        sd = DVDownloader(self.config)
        sd.DownloadNew()

    def RelateAll(self):
        super(DVManager,self).RelateAll()
        self.NTriplesToXML()

    ####################################################################
    # OVERRIDES OF Manager METHODS
    ####################################################################
    
    def _get_module_dir(self):
        return __moduledir__

    publikationer = {u'http://rinfo.lagrummet.se/ref/rff/nja': u'Högsta domstolen',
                     u'http://rinfo.lagrummet.se/ref/rff/rh':  u'Hovrätterna',
                     u'http://rinfo.lagrummet.se/ref/rff/ra':  u'Regeringsrätten',
                     u'http://rinfo.lagrummet.se/ref/rff/ad':  u'Arbetsdomstolen',
                     u'http://rinfo.lagrummet.se/ref/rff/fod': u'Försäkringsöverdomstolen',
                     u'http://rinfo.lagrummet.se/ref/rff/md':  u'Marknadsdomstolen',
                     u'http://rinfo.lagrummet.se/ref/rff/mig': u'Migrationsöverdomstolen',
                     u'http://rinfo.lagrummet.se/ref/rff/mod': u'Miljööverdomstolen'
                     }
    def _build_indexpages(self, by_pred_obj, by_subj_pred):
        documents = defaultdict(lambda:defaultdict(list))
        pagetitles = {}
        pagelabels = {}
        publ_pred = Util.ns['rinfo']+'rattsfallspublikation'
        year_pred = Util.ns['rinfo']+'arsutgava'
        id_pred =   Util.ns['dct']+'identifier'
        desc_pred = Util.ns['dct']+'description'
        subj_pred = Util.ns['dct']+'subject'
        for obj in by_pred_obj[publ_pred]:
            label = self.publikationer[obj]
            for subject in by_pred_obj[publ_pred][obj]:
                year = by_subj_pred[subject][year_pred]
                identifier = by_subj_pred[subject][id_pred]
                
                desc = by_subj_pred[subject][desc_pred]
                if len(desc) > 80:
                    desc = desc[:80].rsplit(' ',1)[0]+'...'
                pageid = '%s-%s' % (obj.split('/')[-1], year)
                pagetitles[pageid] = u'Rättsfall från %s under %s' % (label, year)
                pagelabels[pageid] = year
                documents[label][pageid].append({'uri':subject,
                                               'sortkey':identifier,
                                               'title':identifier,
                                               'trailer':' '+desc[:80]})

        # FIXME: build a fancy three level hierarchy ('Efter sökord' /
        # 'A' / 'Anställningsförhållande' / [list...])


        # build index.html - same as Högsta domstolens verdicts for current year 
        outfile = "%s/%s/generated/index/index.html" % (self.baseDir, self.moduleDir)
        category = u'Högsta domstolen'
        if 'nja-%d' % (datetime.today().year) in pagetitles:
            pageid = 'nja-%d' % (datetime.today().year)
        else:
            # handles the situation in january, before any verdicts
            # for the new year is available
            pageid = 'nja-%d' % (datetime.today().year-1) 

        title = pagetitles[pageid]
        self._render_indexpage(outfile,title,documents,pagelabels,category,pageid,docsorter=Util.numcmp)

        for category in documents.keys():
            for pageid in documents[category].keys():
                outfile = "%s/%s/generated/index/%s.html" % (self.baseDir, self.moduleDir, pageid)
                title = pagetitles[pageid]
                self._render_indexpage(outfile,title,documents,pagelabels,category,pageid,docsorter=Util.numcmp)


    def _build_newspages(self,messages):
        basefile = {u'de allmänna domstolarna': 'allmanna',
                    u'förvaltningsdomstolarna': 'forvaltning',
                    u'Arbetsdomstolen': 'ad',
                    u'Marknadsdomstolen': 'md',
                    u'Migrationsöverdomstolen': 'mig',
                    u'Miljööverdomstolen': 'mod'}

        #entries = defaultdict(list)
        entries = {}
        for base in basefile.keys():
            entries[base] = []
        for (timestamp,message) in messages:
            f = message.replace('intermediate\word','parsed').replace('.doc','.xht2')
            if not os.path.exists(f):
                # kan hända om parsandet gick snett
                log.warning("File %s not found" % f)
                continue

            tree,ids = ET.XMLID(open(f).read())
            metadata = tree.find(".//{http://www.w3.org/2002/06/xhtml2/}dl")
            sokord = []
            for e in metadata:
                if 'property' in e.attrib:
                    if e.attrib['property'] == "dct:description":
                        content = '<p>%s</p>' % cgi.escape(e.text)
                    elif e.attrib['property'] == "dct:identifier":
                        title = e.text
                    elif e.attrib['property'] == "rinfo:avgorandedatum":
                        timestamp = datetime.strptime(e.text, "%Y-%m-%d")
                    elif e.attrib['property'] == "dct:subject" and e.text:
                        sokord.append(e.text)
                    elif e.attrib['property'] == "rinfo:rattsfallspublikation":
                        if e.text in ('http://rinfo.lagrummet.se/ref/rff/nja',
                                      'http://rinfo.lagrummet.se/ref/rff/rh'):
                            slot = u'de allmänna domstolarna'
                        elif e.text == 'http://rinfo.lagrummet.se/ref/rff/ra':
                            slot = u'förvaltningsdomstolarna'
                        else:
                            slot = self.publikationer[e.text]
                if e.text and e.text.startswith(u'http://rinfo.lagrummet.se/publ/rattsfall'):
                    uri = e.text.replace('http://rinfo.lagrummet.se/publ/rattsfall','/dom')
                    
            if sokord:
                title += " (%s)" % ", ".join(sokord)

            entry = {'title':title,
                     'timestamp':timestamp,
                     'id':uri,
                     'uri':uri,
                     'content':u'%s<p><a href="%s">Referat i fulltext</a></p>' % (content,uri)}
            entries[slot].append(entry)

        for slot in entries.keys():
            slotentries = sorted(entries[slot],key=itemgetter('timestamp'),reverse=True)
            base = basefile[slot]
            htmlfile = "%s/%s/generated/news/%s.html" % (self.baseDir, self.moduleDir, base)
            atomfile = "%s/%s/generated/news/%s.atom" % (self.baseDir, self.moduleDir, base)
            self._render_newspage(htmlfile, atomfile, u'Nya r\xe4ttsfall fr\xe5n %s'%slot, 'De senaste 30 dagarna', slotentries)


    ####################################################################
    # CLASS-SPECIFIC HELPER FUNCTIONS
    ####################################################################

    # none for now...

if __name__ == "__main__":
    #if not '__file__' in dir():
    #    print "probably running from within emacs"
    #    sys.argv = ['DV.py','Parse', '42']
    import logging.config
    logging.config.fileConfig('etc/log.conf')
    DVManager.__bases__ += (DispatchMixin,)
    mgr = DVManager()
    mgr.Dispatch(sys.argv)
