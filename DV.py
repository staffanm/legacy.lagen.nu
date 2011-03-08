#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Hanterar domslut (detaljer och referat) från Domstolsverket. Data
hämtas från DV:s (ickepublika) FTP-server, eller från lagen.nu."""

# system libraries
import sys, os, re
import shutil
import pprint
import types
import codecs
from time import time, mktime, sleep
from tempfile import mktemp
from datetime import datetime
import xml.etree.cElementTree as ET # Python 2.5 spoken here
import xml.etree.ElementTree as PET
import logging
import zipfile
import traceback
from collections import defaultdict
from operator import itemgetter
import cgi
import textwrap

# 3rdparty libs
from genshi.template import TemplateLoader
from configobj import ConfigObj
from mechanize import Browser, LinkNotFoundError
try: 
    from rdflib.Graph import Graph
except ImportError:
    from rdflib import Graph
    
from rdflib import Literal, Namespace, URIRef, RDF, RDFS

# my libs
import LegalSource
import Util
from LegalRef import LegalRef,ParseError,Link,LinkSubject
from DispatchMixin import DispatchMixin
from DataObjects import UnicodeStructure, CompoundStructure, \
     MapStructure, IntStructure, DateStructure, PredicateType, \
     serialize

__version__   = (1,6)
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
        if 'ftp_user' in self.config[__moduledir__]:
            try:
                self.download_ftp(dirname, recurse, self.config[__moduledir__]['ftp_user'], self.config[__moduledir__]['ftp_pass'])
            except Util.ExternalCommandError:
                log.warning("download_ftp failed, not downloading anything")
        else:
            self.download_www(dirname, recurse)

    def download_ftp(self,dirname,recurse,user,password,ftp=None):
        #url = 'ftp://ftp.dom.se/%s' % dirname
        log.info(u'Listar innehåll i %s' % dirname)
        lines = []
        if not ftp:
            from ftplib import FTP
            ftp = FTP('ftp.dom.se')
            ftp.login(user,password)

        ftp.cwd(dirname)
        ftp.retrlines('LIST',lines.append)
        
        #cmd = "ncftpls -m -u %s -p %s %s" % (user, password, url)
        #(ret, stdout, stderr) = Util.runcmd(cmd)
        #if ret != 0:
        #    raise Util.ExternalCommandError(stderr)

        for line in lines:
            parts = line.split()
            filename = parts[-1].strip()
            if line.startswith('d') and recurse:
                self.download(filename,recurse)
            elif line.startswith('-'):
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
                    #os.system("ncftpget -u %s -p %s ftp.dom.se %s %s" %
                    #          (user, password, localdir, fullname))
                    ftp.retrbinary('RETR %s' % filename, open(localdir+os.path.sep+filename,'wb').write)
                    self.process_zipfile(localdir + os.path.sep + filename)
        ftp.cwd('/')

    def download_www(self,dirname,recurse):
        url = 'https://lagen.nu/dv/downloaded/%s' % dirname
        log.info(u'Listar innehåll i %s' % url)
        self.browser.open(url)
        links = list(self.browser.links())
        for l in links:
            if l.url.startswith("/"):
                continue
            elif l.url.endswith("/") and recurse:
                self.download_www(l.url,recurse)
            elif l.url.endswith(".zip"):
                if dirname:
                    fullname = dirname + l.url
                    localdir = self.download_dir + os.path.sep + dirname
                    Util.mkdir(localdir)
                else:
                    fullname = l.url
                    localdir = self.download_dir

                localfile = "%s/%s" % (self.download_dir, fullname)
                if not os.path.exists(localfile):
                    log.info("Downloading %s" % (l.absolute_url))
                    self.browser.retrieve(l.absolute_url, localfile)
                    self.process_zipfile(localfile)

    # eg. HDO_T3467-96.doc or HDO_T3467-96_1.doc
    re_malnr = re.compile(r'([^_]*)_([^_\.]*)_?(\d*)\.(docx?)')
    # eg. HDO_T3467-96_BYTUT_2010-03-17.doc or HDO_T3467-96_BYTUT_2010-03-17_1.doc
    re_bytut_malnr = re.compile(r'([^_]*)_([^_\.]*)_BYTUT_\d+-\d+-\d+_?(\d*)\.(docx?)')
    re_tabort_malnr = re.compile(r'([^_]*)_([^_\.]*)_TABORT_\d+-\d+-\d+_?(\d*)\.(docx?)')

    def process_zipfile(self, zipfilename):
        removed = replaced = created = untouched = 0
        zipf = zipfile.ZipFile(zipfilename, "r")
        for name in zipf.namelist():
            if "_notis_" in name:
                continue
            # Namnen i zipfilen använder codepage 437 - retro!
            uname = name.decode('cp437')
            uname = os.path.split(uname)[1]
            log.debug("In: %s" % uname)
            if 'BYTUT' in name:
                m = self.re_bytut_malnr.match(uname)
            elif 'TABORT' in name:
                m = self.re_tabort_malnr.match(uname)
                # log.info(u'Ska radera!')
            else:
                m = self.re_malnr.match(uname)
            if m:
                (court, malnr, referatnr, suffix) = (m.group(1), m.group(2), m.group(3), m.group(4))
                # log.debug("court %s, malnr %s, referatnr %s, suffix %s" % (court,malnr, referatnr, suffix))
                assert ((suffix == "doc") or (suffix == "docx")), "Unknown suffix %s in %r" % (suffix, uname)
                if referatnr:
                    outfilename = os.path.sep.join([self.intermediate_dir, court, "%s_%s.%s" % (malnr,referatnr,suffix)])
                else:
                    outfilename = os.path.sep.join([self.intermediate_dir, court, "%s.%s" % (malnr,suffix)])

                if "TABORT" in name:
                    log.info(u'Raderar befintligt referat %s %s' % (court,malnr))
                    if not os.path.exists(outfilename):
                        log.warning(u'Filen %s som ska tas bort fanns inte' % outfilename)
                    else:
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
                log.warning(u'Kunde inte tolka filnamnet %r i %s' % (name, Util.relpath(zipfilename)))
        log.info(u'Processade %s, skapade %s,  bytte ut %s, tog bort %s, lät bli %s filer' % (Util.relpath(zipfilename),created,replaced,removed,untouched))


DCT = Namespace(Util.ns['dct'])
XSD = Namespace(Util.ns['xsd'])
RINFO = Namespace(Util.ns['rinfo'])
RINFOEX = Namespace(Util.ns['rinfoex'])
class DVParser(LegalSource.Parser):
    re_NJAref = re.compile(r'(NJA \d{4} s\. \d+) \(alt. (NJA \d{4}:\d+)\)')
    # I wonder if we really should have : in this. Let's try without!
    re_delimSplit = re.compile("[;,] ?").split


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
                       u'RK': u'http://rinfo.lagrummet.se/ref/rff/rk',
                       u'MIG': u'http://rinfo.lagrummet.se/ref/rff/mig',
                       u'AD': u'http://rinfo.lagrummet.se/ref/rff/ad',
                       u'MD': u'http://rinfo.lagrummet.se/ref/rff/md',
                       u'FÖD': u'http://rinfo.lagrummet.se/ref/rff/fod'}

    domstolsforkortningar = {u'ADO': 'http://lagen.nu/org/2008/arbetsdomstolen',
                             u'HDO': 'http://lagen.nu/org/2008/hogsta-domstolen',
                             u'HGO': 'http://lagen.nu/org/2008/gota-hovratt',
                             u'HNN': 'http://lagen.nu/org/2008/hovratten-for-nedre-norrland',
                             u'HON': 'http://lagen.nu/org/2008/hovratten-for-ovre-norrland',
                             u'HSB': 'http://lagen.nu/org/2008/hovratten-over-skane-och-blekinge',
                             u'HSV': 'http://lagen.nu/org/2008/svea-hovratt',
                             u'HVS': 'http://lagen.nu/org/2008/hovratten-for-vastra-sverige',
                             u'MDO': 'http://lagen.nu/org/2008/marknadsdomstolen',
                             u'MIG': 'http://lagen.nu/org/2008/migrationsoverdomstolen',
                             u'MÖD': 'http://lagen.nu/org/2008/miljooverdomstolen',
                             u'REG': 'http://lagen.nu/org/2008/regeringsratten',
                             u'KST': 'http://lagen.nu/org/2008/kammarratten-i-stockholm'}


    wrapper = textwrap.TextWrapper(break_long_words=False,
                                   width=72)
    
    def Parse(self,id,docfile,config=None):
        import codecs
        self.id = id
        self.config = config
        self.lagrum_parser = LegalRef(LegalRef.LAGRUM)
        self.rattsfall_parser = LegalRef(LegalRef.RATTSFALL)

        filetype = "docx" if docfile.endswith("docx") else "doc"

        # Parsing is a two step process: First extract some version of
        # the text from the binary blob (either through running
        # antiword for old-style doc documents, or by unzipping
        # document.xml, for new-style docx documents)
        if filetype == "docx":
            parsablefile = docfile.replace('word','ooxml').replace('.docx','.xml')
            self.word_to_ooxml(docfile,parsablefile)
        else:
            parsablefile = docfile.replace('word','docbook').replace('.doc','.xml')
            try:
                self.word_to_docbook(docfile,parsablefile)
            except Util.ExternalCommandError:
                # Some .doc files are .docx with wrong suffix
                parsablefile = docfile.replace('word','ooxml').replace('.doc','.xml')
                self.word_to_ooxml(docfile,parsablefile)
                filetype = "docx"
                
                
        # FIXME: This is almost identical to the code in
        # SFSManager.Parse - should be refactored somehow
        #
        # Patches produced for the MS Word HTML export will need to be
        # modified for the new antiword docbook output...
        patchfile = 'patches/dv/%s.patch' % id
        descfile = 'patches/dv/%s.desc' % id
        patchdesc = None
        if os.path.exists(patchfile):
            patchedfile = mktemp()
            # we don't want to sweep the fact that we're patching under the carpet
            log.warning(u'%s: Applying patch %s' % (id, patchfile))
            cmd = 'patch -s %s %s -o %s' % (parsablefile, patchfile, patchedfile)
            log.debug(u'%s: running %s' % (id, cmd))
            (ret, stdout, stderr) = Util.runcmd(cmd)
            if ret == 0: # successful patch
                parsablefile = patchedfile
                assert os.path.exists(descfile), "No description of patch %s found" % patchfile
                patchdesc = codecs.open(descfile,encoding='utf-8').read().strip()

            else:
                # If patching fails, do not continue (patching
                # generally done for privacy reasons -- if it fails
                # and we go on, we could expose sensitive information)
                raise Util.ExternalCommandError(u"%s: Could not apply patch %s: %s" % (id, patchfile, stdout.strip()))
                # log.warning(u"%s: Could not apply patch %s: %s" % (id, patchfile, stdout.strip()))
            

        # The second step is to mangle the crappy XML produced by
        # antiword (docbook) or Word 2007 (OOXML) into a nice XHTML2
        # structure.
        if filetype == "docx":
            return self.parse_ooxml(parsablefile, patchdesc)
        else:
            return self.parse_antiword_docbook(parsablefile, patchdesc)


    def word_to_ooxml(self,indoc, outdoc):
        name = "word/document.xml"
        zipf = zipfile.ZipFile(indoc,"r")
        assert name in zipf.namelist(), "No %s in zipfile %s" % (name,indoc)
        data = zipf.read(name)
        Util.ensureDir(outdoc)
        outfile = open(outdoc,"wb")
        outfile.write(data)
        outfile.close()
        Util.indent_xml_file(outdoc)
        zi = zipf.getinfo(name)
        dt = datetime(*zi.date_time)
        ts = mktime(dt.timetuple())
        os.utime(outdoc, (ts,ts))

    def word_to_docbook(self,indoc,outdoc):
        from string import Template
        # assert 'wordconverter' in self.config, "No wordconverter defined in conf.ini"
        # s = Template(self.config['wordconverter'])
        # cmd = s.substitute(indoc=indoc, outdoc=outdoc)
        tmpfile = mktemp()
        cmd = "antiword -x db %s > %s" % (indoc, tmpfile)

        Util.ensureDir(outdoc)
        if (os.path.exists(outdoc) and
            os.path.getsize(outdoc) > 0 and
            os.stat(outdoc).st_mtime > os.stat(indoc).st_mtime):
            log.debug("outdoc %s exists, not converting" % outdoc)
            return
        if not os.path.exists(indoc):
            log.warning("indoc %s does not exist" % indoc)
            return
        log.debug("Executing %s" % cmd)
        (ret,stdout,stderr) = Util.runcmd(cmd)

        if ret != 0:
            log.error("Docbook conversion failed: %s" % stderr)
            raise Util.ExternalCommandError("Docbook conversion failed: %s" % stderr.strip())
            
        if not os.path.exists(tmpfile):
            log.warning("tmp file %s wasn't created, that can't be good?" % tmpfile)

        tree = ET.parse(tmpfile)
        for element in tree.getiterator():
            if element.text and element.text.strip() != "":
                replacement = ""
                for p in element.text.split("\n"):
                    if p:
                        replacement += self.wrapper.fill(p) + "\n\n";
                
                element.text = replacement.strip()

        tree.write(outdoc,encoding="utf-8")
        os.unlink(tmpfile)


    def _sokord_to_subject(self, sokord):
        return u'http://lagen.nu/concept/%s' % sokord.capitalize().replace(' ','_')
    
    def parse_ooxml(self,ooxmlfile,patchdescription=None):
        # FIXME: Change this code bit by bit to handle OOXML instead
        # of docbook (generalizing where possible)
        soup = Util.loadSoup(ooxmlfile,encoding='utf-8')
        head = Metadata()


        # Högst uppe på varje domslut står domstolsnamnet ("Högsta
        # domstolen") följt av referatnumret ("NJA 1987
        # s. 113"). 
        firstfield = soup.find("w:t")
        domstol = Util.elementText(firstfield)
        nextfield = firstfield.findParent("w:tc").findNext("w:tc")
        referat = u''
        for e in nextfield.findAll("w:t"):
            referat += e.string
        referat = Util.normalizeSpace(referat)

        # log.info(u"Domstol: %r, referat: %r" % (domstol,referat))
        #firstfields = soup.findAll("w:t",limit=4)
        #if not re.search('\d{4}', referat):
        #    referat += " " + Util.elementText(firstfields[2])
        #    
        #tmp = Util.elementText(firstfields[3])
        #if tmp.startswith("NJA "):
        #    referat += " (" + tmp + ")"

        # FIXME: Could be generalized
        domstolsuri = self.domstolsforkortningar[self.id.split("/")[0]]
        head[u'Domstol'] = LinkSubject(domstol,
                                       uri=domstolsuri,
                                       predicate=self.labels[u'Domstol'])

        head[u'Referat'] = UnicodeSubject(referat,
                                          predicate=self.labels[u'Referat'])

        # Hitta övriga enkla metadatafält i sidhuvudet
        for key in self.labels.keys():
            node = soup.find(text=re.compile(key+u':'))
            if node:
                # can't just use the next w:t element, sometimes the
                # text field is broken up (so that "20" is in one
                # cell, "10" in another, and "-06-09" in a third...)
                next_text = node.findNext("w:t")
                text_root = next_text.findParent("w:p")
                txt = ""
                for text_el in text_root.findAll("w:t"):
                    txt += Util.elementText(text_el)
                
                if txt: # skippa fält med tomma strängen-värden
                    head[key] = UnicodeSubject(txt, predicate=self.labels[key])
            else:
                # Sometimes these text fields are broken up
                # (eg "<w:t>Avgörand</w:t>...<w:t>a</w:t>...<w:t>tum</w:t>")
                # Use (ridiculous) fallback method
                nodes = soup.findAll('w:statustext',attrs={'w:val':key})
                if nodes:
                    node = nodes[-1]
                    txt = Util.elementText(node.findNext("w:t"))
                    if txt: # skippa fält med tomma strängen-värden
                        # log.info("Fallback %r=%r" % (key,txt))
                        head[key] = UnicodeSubject(txt, predicate=self.labels[key])
                #else:
                #    log.warning("%s: Couldn't find field %r" % (self.id,key))
                
        # Hitta sammansatta metadata i sidhuvudet
        for key in [u"Lagrum", u"Rättsfall"]:
            node = soup.find(text=re.compile(key+u':'))
            if node:
                items = []
                textnodes = node.findParent('w:tc').findNextSibling('w:tc')
                for textnode in textnodes.findAll('w:t'):
                    items.append(Util.elementText(textnode))

                if items and items != ['']:
                    if key == u'Lagrum':
                        containercls = Lagrum
                        parsefunc = self.lagrum_parser.parse
                    elif key == u'Rättsfall':
                        containercls = Rattsfall
                        parsefunc = self.rattsfall_parser.parse

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

        if not head[u'Referat']:
            # För specialdomstolarna kan man lista ut referatnumret
            # från målnumret
            if head[u'Domstol'] == u'Marknadsdomstolen':
                head[u'Referat'] = u'MD %s' % head[u'Domsnummer'].replace('-',':')
            else:
                raise AssertionError(u"Kunde inte hitta referatbeteckningen i %s" % docbookfile)

        # Hitta själva referatstexten... här kan man göra betydligt
        # mer, exv hitta avsnitten för de olika instanserna, hitta
        # dissenternas domskäl, ledamöternas namn, hänvisning till
        # rättsfall och lagrum i löpande text...
        body = Referatstext()
        for p in soup.find(text=re.compile('EFERAT')).findParent('w:tr').findNextSibling('w:tr').findAll('w:p'):
            body.append(Stycke([Util.elementText(p)]))

        # Hitta sammansatta metadata i sidfoten
        txt = Util.elementText(soup.find(text=re.compile(u'Sökord:')).findNext('w:t'))
        sokord = []
        for s in self.re_delimSplit(txt):
            s = Util.normalizeSpace(s)
            if not s:
                continue
            # terms longer than 72 chars are not legitimate
            # terms. more likely descriptions. If a term has a - in
            # it, it's probably a separator between a term and a
            # description
            while len(s) >= 72 and " - " in s:
                h, s = s.split(" - ",1)
                sokord.append(h)
            if len(s) < 72:
                sokord.append(s)

        # Using LinkSubjects (below) is more correct, but we need some
        # way of expressing the relation:
        # <http://lagen.nu/concept/Förhandsbesked> rdfs:label "Förhandsbesked"@sv
        head[u'Sökord'] = [UnicodeSubject(x,
                                          predicate=self.multilabels[u'Sökord'])
                           for x in sokord]
        #head[u'Sökord'] = [LinkSubject(x,
        #                               uri=self._sokord_to_subject(x),
        #                               predicate=self.multilabels[u'Sökord'])
        #                   for x in sokord]

        if soup.find(text=re.compile(u'^\s*Litteratur:\s*$')):
            n = soup.find(text=re.compile(u'^\s*Litteratur:\s*$')).findNext('w:t')
            txt = Util.elementText(n)
            head[u'Litteratur'] = [UnicodeSubject(Util.normalizeSpace(x),predicate=self.multilabels[u'Litteratur'])
                                   for x in txt.split(";")]

        # pprint.pprint(head)
        self.polish_metadata(head)
        if patchdescription:
            head[u'Textändring'] = UnicodeSubject(patchdescription,
                                                  predicate=RINFOEX['patchdescription'])
        
        xhtml = self.generate_xhtml(head,body,None,__moduledir__,globals())
        return xhtml


    def parse_antiword_docbook(self,docbookfile,patchdescription=None):
        soup = Util.loadSoup(docbookfile,encoding='utf-8')
        head = Metadata()
        header_elements = soup.first("para")
        header_text = u''
        for el in header_elements.contents:
            if hasattr(el, 'name') and el.name == "informaltable":
                break
            else:
                header_text += el.string

        # Högst uppe på varje domslut står domstolsnamnet ("Högsta
        # domstolen") följt av referatnumret ("NJA 1987
        # s. 113"). Beroende på worddokumentet ser dock XML-strukturen
        # olika ut. Det vanliga är att informationen finns i en
        # pipeseparerad paragraf:

        parts = [x.strip() for x in header_text.split("|")]
        if len(parts) > 1:
            domstol = parts[0]
            referat = parts[1]
        else:
            # alternativ står de på första raden i en informaltable
            domstol = soup.first("informaltable").tgroup.tbody.row.findAll('entry')[0].string
            referat = soup.first("informaltable").tgroup.tbody.row.findAll('entry')[1].string
        
        domstolsuri = self.domstolsforkortningar[self.id.split("/")[0]]
        
        head[u'Domstol'] = LinkSubject(domstol,
                                       uri=domstolsuri,
                                       predicate=self.labels[u'Domstol'])

        head[u'Referat'] = UnicodeSubject(referat,
                                          predicate=self.labels[u'Referat'])

        # Hitta övriga enkla metadatafält i sidhuvudet
        for key in self.labels.keys():
            node = soup.find(text=re.compile(key+u':'))
            if node:
                txt = Util.elementText(node.findParent('entry').findNextSibling('entry'))
                if txt: # skippa fält med tomma strängen-värden
                    head[key] = UnicodeSubject(txt, predicate=self.labels[key])

        # Hitta sammansatta metadata i sidhuvudet
        for key in [u"Lagrum", u"Rättsfall"]:
            node = soup.find(text=re.compile(key+u':'))
            if node:
                items = []
                textchunk = node.findParent('entry').findNextSibling('entry').string
                #for line in [x.strip() for x in self.re_delimSplit(textchunk)]:
                for line in [x.strip() for x in textchunk.split("\n\n")]:
                    if line: 
                        items.append(Util.normalizeSpace(line))
                if items and items != ['']:
                    if key == u'Lagrum':
                        containercls = Lagrum
                        parsefunc = self.lagrum_parser.parse
                    elif key == u'Rättsfall':
                        containercls = Rattsfall
                        parsefunc = self.rattsfall_parser.parse

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

        if not head[u'Referat']:
            # För specialdomstolarna kan man lista ut referatnumret
            # från målnumret
            if head[u'Domstol'] == u'Marknadsdomstolen':
                head[u'Referat'] = u'MD %s' % head[u'Domsnummer'].replace('-',':')
            else:
                raise AssertionError(u"Kunde inte hitta referatbeteckningen i %s" % docbookfile)

        # Hitta själva referatstexten... här kan man göra betydligt
        # mer, exv hitta avsnitten för de olika instanserna, hitta
        # dissenternas domskäl, ledamöternas namn, hänvisning till
        # rättsfall och lagrum i löpande text...
        body = Referatstext()
        for p in soup.find(text=re.compile('REFERAT')).findParent('tgroup').findNextSibling('tgroup').find('entry').string.strip().split("\n\n"):
            body.append(Stycke([p]))

        # Hitta sammansatta metadata i sidfoten

        txt = Util.elementText(soup.find(text=re.compile(u'Sökord:')).findParent('entry').nextSibling.nextSibling)
        sokord = []
        for s in self.re_delimSplit(txt):
            s = Util.normalizeSpace(s)
            if not s:
                continue
            # terms longer than 72 chars are not legitimate
            # terms. more likely descriptions. If a term has a - in
            # it, it's probably a separator between a term and a
            # description
            while len(s) >= 72 and " - " in s:
                h, s = s.split(" - ",1)
                sokord.append(h)
            if len(s) < 72:
                sokord.append(s)

        # Using LinkSubjects (below) is more correct, but we need some
        # way of expressing the relation:
        # <http://lagen.nu/concept/Förhandsbesked> rdfs:label "Förhandsbesked"@sv
        head[u'Sökord'] = [UnicodeSubject(x,
                                          predicate=self.multilabels[u'Sökord'])
                           for x in sokord]
        #head[u'Sökord'] = [LinkSubject(x,
        #                               uri=self._sokord_to_subject(x),
        #                               predicate=self.multilabels[u'Sökord'])
        #                   for x in sokord]

        if soup.find(text=re.compile(u'^\s*Litteratur:\s*$')):
            n = soup.find(text=re.compile(u'^\s*Litteratur:\s*$')).findParent('entry').nextSibling.nextSibling
            txt = Util.elementText(n)
            head[u'Litteratur'] = [UnicodeSubject(Util.normalizeSpace(x),predicate=self.multilabels[u'Litteratur'])
                                   for x in txt.split(";")]

        self.polish_metadata(head)
        if patchdescription:
            head[u'Textändring'] = UnicodeSubject(patchdescription,
                                                  predicate=RINFOEX['patchdescription'])
        
        xhtml = self.generate_xhtml(head,body,None,__moduledir__,globals())
        return xhtml


    def polish_metadata(self,head):
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
                        head[u'[%s]'%pred] = LinkSubject(m.group(1),
                                                         uri=self.publikationsuri[m.group(1)],
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
            res = self.rattsfall_parser.parse(head[u'Referat'])
            if hasattr(res[0], 'uri'):
                head['xml:base'] = res[0].uri

        if not head['xml:base']:
            log.error(u'%s: Could not find out URI for this doc automatically (%s)' % (self.id, head[u'Referat']))

        # Putsa till avgörandedatum - det är ett date, inte en string
        # pprint.pprint(head)
        
        head[u'Avgörandedatum'] = DateSubject(datetime.strptime(unicode(head[u'Avgörandedatum'].replace(" ","")),
                                                                '%Y-%m-%d'),
                                              predicate=self.labels[u'Avgörandedatum'])

        
        # OK, färdigputsat!


class DVManager(LegalSource.Manager):
    __parserClass = DVParser
    re_xmlbase = re.compile('xml:base="http://rinfo.lagrummet.se/publ/rattsfall/([^"]+)"').search
    # Converts a NT file to RDF/XML -- needed for uri.xsl to work for legal cases
    def NTriplesToXML(self):
        ntfile = Util.relpath(os.path.sep.join([self.baseDir, self.moduleDir, u'parsed', u'rdf.nt']))
        xmlfile = os.path.sep.join([self.baseDir, self.moduleDir, u'parsed', u'rdf.xml']) 
        minixmlfile = os.path.sep.join([self.baseDir, self.moduleDir, u'parsed', u'rdf-mini.xml'])
        if self._outfile_is_newer([ntfile],xmlfile) and self._outfile_is_newer([ntfile],minixmlfile):
            log.info(u"Not regenerating RDF/XML files")
            return
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
        """'basefile' here is a alphanumeric string representing the
        filename on disc, which may or may not correspond with any ID
        found in the case itself """

        if verbose: print"Setting verbosity"
        log.setLevel(logging.DEBUG)
        start = time()

        if '~$' in basefile: # word autosave file
            log.debug(u"%s: Överhoppad", basefile)
            return

        suffix = ".doc"
        infile = os.path.sep.join([self.baseDir, __moduledir__, 'intermediate', 'word', basefile]) + suffix
        if not os.path.exists(infile):
            suffix = ".docx"
            infile = os.path.sep.join([self.baseDir, __moduledir__, 'intermediate', 'word', basefile]) + suffix
            
        outfile = os.path.sep.join([self.baseDir, __moduledir__, 'parsed', basefile]) + ".xht2"

        # check to see if the outfile is newer than all ingoing files and don't parse if so
        force = (self.config[__moduledir__]['parse_force'] == 'True')
        if not force and self._outfile_is_newer([infile],outfile):
            log.debug(u"%s: Överhoppad", basefile)
            return

        # print "Force: %s, infile: %s, outfile: %s" % (force,infile,outfile)

        p = self.__parserClass()
        p.verbose = verbose
        parsed = p.Parse(basefile,infile,self.config)
        Util.ensureDir(outfile)

        tmpfile = mktemp()
        out = file(tmpfile, "w")
        out.write(parsed)
        out.close()
        # Util.indentXmlFile(tmpfile)
        Util.replace_if_different(tmpfile,outfile)
        log.info(u'%s: OK (%.3f sec, %s)', basefile,time()-start, suffix)

    def ParseAll(self):
        intermediate_dir = os.path.sep.join([self.baseDir, u'dv', 'intermediate','word'])
        self._do_for_all(intermediate_dir, '.doc',self.Parse)
        self._do_for_all(intermediate_dir, '.docx',self.Parse)

    def Generate(self,basefile):
        infile = Util.relpath(self._xmlFileName(basefile))
        outfile = Util.relpath(self._htmlFileName(basefile))

        # get URI from basefile as fast as possible
        head = codecs.open(infile,encoding='utf-8').read(1024)
        m = self.re_xmlbase(head)
        if m:
            uri = "http://rinfo.lagrummet.se/publ/rattsfall/%s" % m.group(1)
            mapfile = os.path.sep.join([self.baseDir, self.moduleDir, u'generated', u'uri.map.new'])
            Util.ensureDir(mapfile)
            f = codecs.open(mapfile,'a',encoding='iso-8859-1')
            f.write(u"%s\t%s\n" % (m.group(1),basefile))
        else:
            log.warning("could not find xml:base in %s" % infile)

        sq = """
PREFIX dct:<http://purl.org/dc/terms/>
PREFIX rinfo:<http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#>

SELECT ?uri ?id ?desc
WHERE {
      ?uri dct:description ?desc .
      ?uri dct:identifier ?id .
      ?uri rinfo:rattsfallshanvisning <%s>
}
""" % uri

        rattsfall = self._store_select(sq)

        root_node = PET.Element("rdf:RDF")
        for prefix in Util.ns:
            PET._namespace_map[Util.ns[prefix]] = prefix
            root_node.set("xmlns:" + prefix, Util.ns[prefix])

        main_node = PET.SubElement(root_node, "rdf:Description")
        main_node.set("rdf:about", uri)

        for r in rattsfall:
            subject_node = PET.SubElement(main_node, "dct:subject")
            rattsfall_node = PET.SubElement(subject_node, "rdf:Description")
            rattsfall_node.set("rdf:about",r['uri'])
            id_node = PET.SubElement(rattsfall_node, "dct:identifier")
            id_node.text = r['id']
            desc_node = PET.SubElement(rattsfall_node, "dct:description")
            desc_node.text = r['desc']

        Util.indent_et(root_node)
        tree = PET.ElementTree(root_node)
        tmpfile = mktemp()
        tree.write(tmpfile, encoding="utf-8")

        annotations = "%s/%s/intermediate/annotations/%s.ann.xml" % (self.baseDir, self.moduleDir, basefile)

        Util.replace_if_different(tmpfile,annotations)

        force = (self.config[__moduledir__]['generate_force'] == 'True')
        if not force and self._outfile_is_newer([infile,annotations], outfile):
            log.debug(u"%s: Överhoppad", basefile)
            return

        Util.mkdir(os.path.dirname(outfile))
        log.info(u'Transformerar %s > %s' % (infile,outfile))
        # xsltproc silently fails to open files through the document()
        # functions if the filename has non-ascii
        # characters. Therefore, we copy the annnotation file to a
        # separate temp copy first.
        tmpfile = mktemp()
        shutil.copy2(annotations,tmpfile)
        params = {'annotationfile':tmpfile.replace("\\","/")}
        Util.transform("xsl/dv.xsl",
                       infile,
                       outfile,
                       parameters = params,
                       validate=False)
        sleep(1) # let sesame catch it's breath
        

    def GenerateAll(self):
        mapfile = os.path.sep.join([self.baseDir, u'dv', 'generated', 'uri.map'])
        Util.robust_remove(mapfile+".new")

        parsed_dir = os.path.sep.join([self.baseDir, u'dv', 'parsed'])
        self._do_for_all(parsed_dir, '.xht2',self.Generate)
        Util.robustRename(mapfile+".new", mapfile)
        
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
                     u'http://rinfo.lagrummet.se/ref/rff/rk':  u'Kammarrätterna',
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
            for subject in list(set(by_pred_obj[publ_pred][obj])):
                if not desc_pred in by_subj_pred[subject]:
                    log.warning("No description for %s, skipping" % subject)
                    continue
                if not id_pred in by_subj_pred[subject]:
                    log.warning("No identifier for %s, skipping" % subject)
                    continue
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
            f = message.replace('\\','/').replace('intermediate/word','parsed').replace('.doc','.xht2')
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
                        elif e.text in ('http://rinfo.lagrummet.se/ref/rff/ra',
                                        'http://rinfo.lagrummet.se/ref/rff/rk'):
                            slot = u'förvaltningsdomstolarna'
                        else:
                            slot = self.publikationer[e.text]
                elif ('rel' in e.attrib):
                    if e.attrib['rel'] == "rinfo:rattsfallspublikation":
                        if e.attrib['href'] in ('http://rinfo.lagrummet.se/ref/rff/nja',
                                             'http://rinfo.lagrummet.se/ref/rff/rh'):
                            slot = u'de allmänna domstolarna'
                        elif e.attrib['href'] in ('http://rinfo.lagrummet.se/ref/rff/ra',
                                                  'http://rinfo.lagrummet.se/ref/rff/rk'):
                            slot = u'förvaltningsdomstolarna'
                        else:
                            slot = None
                    elif e.attrib['rel'] == "dct:creator":
                        domstol = e.text
                    
                if e.text and e.text.startswith(u'http://rinfo.lagrummet.se/publ/rattsfall'):
                    uri = e.text.replace('http://rinfo.lagrummet.se/publ/rattsfall','/dom')

            if not slot:
                slot = domstol
                
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
            htmlfile = Util.relpath("%s/%s/generated/news/%s.html" % (self.baseDir, self.moduleDir, base))
            atomfile = Util.relpath("%s/%s/generated/news/%s.atom" % (self.baseDir, self.moduleDir, base))
            self._render_newspage(htmlfile, atomfile, u'Nya r\xe4ttsfall fr\xe5n %s'%slot, 'De senaste 30 dagarna', slotentries)


    ####################################################################
    # CLASS-SPECIFIC HELPER FUNCTIONS
    ####################################################################

    # none for now...

if __name__ == "__main__":
    import logging.config
    logging.config.fileConfig('etc/log.conf')
    DVManager.__bases__ += (DispatchMixin,)
    mgr = DVManager()
    mgr.Dispatch(sys.argv)
