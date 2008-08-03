#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Hanterar (konsoliderade) författningar i SFS från Regeringskansliet
rättsdatabaser.
"""
from __future__ import with_statement
# system libraries
# import shutil
# import types
# from cStringIO import StringIO
# import pickle
import sys
import os
import re
import codecs
import htmlentitydefs
import logging
import difflib
from tempfile import mktemp
from pprint import pprint
from time import time
from datetime import date, datetime
# python 2.5 required
from collections import defaultdict
import xml.etree.cElementTree as ET
import xml.etree.ElementTree as PET

    
# 3rdparty libs
from configobj import ConfigObj
from mechanize import Browser, LinkNotFoundError
from rdflib.Graph import Graph
from rdflib import Literal, Namespace, URIRef, RDF, RDFS

# my own libraries
import LegalSource
from LegalRef import LegalRef, ParseError, Link, LinkSubject
import Util
from DispatchMixin import DispatchMixin
from TextReader import TextReader
import FilebasedTester
from DataObjects import UnicodeStructure, CompoundStructure, \
     MapStructure, TemporalStructure, OrdinalStructure, \
     PredicateType, DateStructure, serialize, deserialize


__version__ = (0, 1)
__author__ = u"Staffan Malmgren <staffan@tomtebo.org>"
__shortdesc__ = u"Författningar i SFS"
__moduledir__ = "sfs"
log = logging.getLogger(__moduledir__)

# Objektmodellen för en författning är uppbyggd av massa byggstenar
# (kapitel, paragrafen, stycken m.m.) där de allra flesta är någon
# form av lista. Även stycken är listor, dels då de kan innehålla
# lagrumshänvisningar i den löpande texten, som uttrycks som
# Link-objekt mellan de vanliga unicodetextobjekten, dels då de kan
# innehålla en punkt- eller nummerlista.
#
# Alla klasser ärver från antingen CompoundStructure (som är en list
# med lite extraegenskaper), UnicodeStructure (som är en unicode med
# lite extraegenskaper) eller MapStructure (som är ett dict med lite
# extraegenskaper).
#
# De kan även ärva från TemporalStructure om det är ett objekt som kan
# upphävas eller träda ikraft (exv paragrafer och rubriker, men inte
# enskilda stycken) och/eller OrdinalStructure om det är ett objekt
# som har nån sorts löpnummer, dvs kan sorteras på ett meningsfullt
# sätt (exv kapitel och paragrafer, men inte rubriker).


class Forfattning(CompoundStructure, TemporalStructure):
    """Grundklass för en konsoliderad författningstext. Metadatan
    (SFS-numret, ansvarigt departement, 'uppdaterat t.o.m.' m.fl. fält
    lagras inte här, utan i en separat Forfattningsinfo-instans"""
    pass

# Rubrike är en av de få byggstenarna som faktiskt inte kan innehålla
# något annat (det förekommer "aldrig" en hänvisning i en
# rubriktext). Den ärver alltså från UnicodeStructure, inte
# CompoundStructure.


class Rubrik(UnicodeStructure,TemporalStructure):
    """En rubrik av något slag - kan vara en huvud- eller underrubrik
    i löptexten, en kapitelrubrik, eller något annat"""
    fragment_label = "R"
    def __init__(self, *args, **kwargs):
        self.id = kwargs['id'] if 'id' in kwargs else None
        super(Rubrik,self).__init__(*args, **kwargs)

class Stycke(CompoundStructure):
    fragment_label = "S"
    def __init__(self, *args, **kwargs):
        self.id = kwargs['id'] if 'id' in kwargs else None
        super(Stycke,self).__init__(*args, **kwargs)

class NumreradLista (CompoundStructure): pass

class Strecksatslista (CompoundStructure): pass

class Bokstavslista (CompoundStructure): pass

class Preformatted(UnicodeStructure): pass

class Tabell(CompoundStructure): pass # Varje tabellrad är ett objekt

class Tabellrad(CompoundStructure, TemporalStructure): pass # Varje tabellcell är ett objekt

class Tabellcell(CompoundStructure): pass # ..som kan innehålla text och länkar

class Avdelning(CompoundStructure, OrdinalStructure):
    pass

class UpphavtKapitel(UnicodeStructure, OrdinalStructure):
    """Ett UpphavtKapitel är annorlunda från ett upphävt Kapitel på så
    sätt att inget av den egentliga lagtexten finns kvar, bara en
    platshållare"""
    pass

class Kapitel(CompoundStructure, OrdinalStructure):
    fragment_label = "K"
    def __init__(self, *args, **kwargs):
        self.id = kwargs['id'] if 'id' in kwargs else None
        super(Kapitel,self).__init__(*args, **kwargs)

class UpphavdParagraf(UnicodeStructure, OrdinalStructure):
    pass

# en paragraf har inget "eget" värde, bara ett nummer och ett eller flera stycken
class Paragraf(CompoundStructure, OrdinalStructure): 
    fragment_label = "P"
    def __init__(self, *args, **kwargs):
        self.id = kwargs['id'] if 'id' in kwargs else None
        super(Paragraf,self).__init__(*args,**kwargs)

# kan innehålla nästlade numrerade listor
class Listelement(CompoundStructure, OrdinalStructure): 
    fragment_label = "N"
    def __init__(self, *args, **kwargs):
        self.id = kwargs['id'] if 'id' in kwargs else None
        super(Listelement,self).__init__(*args,**kwargs)


class Overgangsbestammelser(CompoundStructure):
    def __init__(self, *args, **kwargs):
        self.rubrik = kwargs['rubrik'] if 'rubrik' in kwargs else u'Övergångsbestämmelser'
        super(Overgangsbestammelser,self).__init__(*args,**kwargs)
    
class Overgangsbestammelse(CompoundStructure, OrdinalStructure):
    fragment_label = "L"
    def __init__(self, *args, **kwargs):
        self.id = kwargs['id'] if 'id' in kwargs else None
        super(Overgangsbestammelse,self).__init__(*args,**kwargs)

class Bilaga(CompoundStructure): pass


class Register(CompoundStructure):
    """Innehåller lite metadata om en grundförfattning och dess
    efterföljande ändringsförfattningar"""
    def __init__(self, *args, **kwargs):
        self.rubrik = kwargs['rubrik'] if 'rubrik' in kwargs else None
        super(Register,self).__init__(*args, **kwargs)

class Registerpost(MapStructure):
    """Metadata för en viss (ändrings)författning: SFS-nummer,
    omfattning, förarbeten m.m . Vanligt förekommande nycklar och dess värden:

    * 'SFS-nummer': en sträng, exv u'1970:488'
    * 'Ansvarig myndighet': en sträng, exv u'Justitiedepartementet L3'
    * 'Rubrik': en sträng, exv u'Lag (1978:488) om ändring i lagen (1960:729) om upphovsrätt till litterära och konstnärliga verk'
    * 'Ikraft': en date, exv datetime.date(1996, 1, 1)
    * 'Övergångsbestämmelse': True eller False
    * 'Omfattning': en lista av nodeliknande saker i stil med
      [u'ändr.',
       LinkSubject('23',uri='http://rinfo.lagrummet.se/publ/sfs/1960:729#P23', pred='rinfo:andrar'),
       u', ',
       LinkSubject('24',uri='http://rinfo.lagrummet.se/publ/sfs/1960:729#P24', pred='rinfo:andrar'),
       u' §§; ny ',
       LinkSubject('24 a',uri='http://rinfo.lagrummet.se/publ/sfs/1960:729#P24a' pred='rinfo:inforsI'),
       ' §']
    * 'Förarbeten': en lista av nodeliknande saker i stil med
      [Link('Prop. 1981/82:152',uri='http://rinfo.lagrummet.se/publ/prop/1981/82:152'),
       u', ',
       Link('KrU 1977/78:27',uri='http://rinfo.lagrummet.se/extern/bet/KrU/1977/78:27')]
    * 'CELEX-nr': en node,  exv:
      Link('393L0098',uri='http://rinfo.lagrummet.se/extern/celex/393L0098')
    """
    pass

class Forfattningsinfo(MapStructure):
    pass

class UnicodeSubject(PredicateType,UnicodeStructure): pass

class DateSubject(PredicateType,DateStructure): pass

# module global utility functions
def SFSnrToFilename(sfsnr):
    """converts a SFS id to a filename, sans suffix, eg: '1909:bih. 29
    s.1' => '1909/bih._29_s.1'. Returns None if passed an invalid SFS
    id."""
    if sfsnr.find(":") < 0: return None
    return re.sub(r'([A-Z]*)(\d{4}):',r'\2/\1',sfsnr.replace(' ', '_'))

def FilenameToSFSnr(filename):
    """converts a filename, sans suffix, to a sfsnr, eg:
    '1909/bih._29_s.1' => '1909:bih. 29 s.1'"""
    (dir,file)=filename.split("/")
    if file.startswith('RFS'):
        return re.sub(r'(\d{4})/([A-Z]*)(\d*)( [AB]|)(-(\d+-\d+|first-version)|)',r'\2\1:\3', filename.replace('_',' '))
    else:
        return re.sub(r'(\d{4})/(\d*( s[\. ]\d+|))( [AB]|)(-(\d+-\d+|first-version)|)',r'\1:\2', filename.replace('_',' '))


class SFSDownloader(LegalSource.Downloader):
    def __init__(self,config):
        super(SFSDownloader,self).__init__(config) # sets config, initializes browser
        self.download_dir = config['datadir'] + "/%s/downloaded" % __moduledir__

        # self.browser = Browser()

    
    def DownloadAll(self):
        start = 1600
        end = datetime.today().year
        self.browser.open("http://62.95.69.15/cgi-bin/thw?${HTML}=sfsr_lst&${OOHTML}=sfsr_dok&${SNHTML}=sfsr_err&${MAXPAGE}=26&${BASE}=SFSR&${FORD}=FIND&\xC5R=FR\xC5N+%s&\xC5R=TILL+%s" % (start,end))

        pagecnt = 1
        done = False
        while not done:
            log.info(u'Resultatsida nr #%s' % pagecnt)
            for l in (self.browser.links(text_regex=r'\d+:\d+')):
                self._downloadSingle(l.text)
                # self.browser.back()
            try:
                self.browser.find_link(text='Fler poster')
                self.browser.follow_link(text='Fler poster')
                pagecnt += 1
            except LinkNotFoundError:
                log.info(u'Ingen nästa sida-länk, vi är nog klara')
                done = True
        self._setLastSFSnr(self)


    def _setLastSFSnr(self,last_sfsnr=None):
        if not last_sfsnr:
            log.info(u'Letar efter senaste SFS-nr i  %s/sfst"' % self.download_dir)
            last_sfsnr = "1600:1"
            for f in Util.listDirs(u"%s/sfst" % self.download_dir, ".html"):

                tmp = self._findUppdateradTOM(FilenameToSFSnr(f[len(self.download_dir)+6:-5]), f)
                # FIXME: RFS1975:6 > 2008:1
                if tmp > last_sfsnr:
                    log.info(u'%s > %s (%s)' % (tmp, last_sfsnr, f))
                    last_sfsnr = tmp
        self.config[__moduledir__]['next_sfsnr'] = last_sfsnr 
        self.config.write()

    def DownloadNew(self):
        if not 'next_sfsnr' in self.config[__moduledir__]:
            self._setLastSFSnr()
        (year,nr) = [int(x) for x in self.config[__moduledir__]['next_sfsnr'].split(":")]
        done = False
        while not done:
            log.info(u'Söker efter SFS nr %s:%s' % (year,nr))
            base_sfsnr_list = self._checkForSFS(year,nr)
            if base_sfsnr_list:
                for base_sfsnr in base_sfsnr_list: # usually only a 1-elem list
                    self._downloadSingle(base_sfsnr)
                nr = nr + 1
            else:
                if datetime.today().year > year:
                    log.info(u'    Är det dags att byta år?')
                    base_sfsnr_list = self._checkForSFS(datetime.today().year, 1)
                    if base_sfsnr_list:
                        year = datetime.today().year
                        nr = 1 # actual downloading next loop
                    else:
                        log.info(u'    Vi är klara')
                        done = True
                else:
                    log.info(u'    Vi är klara')
                    done = True
        self._setLastSFSnr("%s:%s" % (year,nr))
                
    def _checkForSFS(self,year,nr):
        """Givet ett SFS-nummer, returnera en lista med alla
        SFS-numret för dess grundförfattningar. Normalt sett har en
        ändringsförfattning bara en grundförfattning, men för vissa
        (exv 2008:605) finns flera. Om SFS-numret inte finns alls,
        returnera en tom lista."""
        # Titta först efter grundförfattning
        log.info(u'    Letar efter grundförfattning')
        grundforf = []
        url = "http://62.95.69.15/cgi-bin/thw?${HTML}=sfsr_lst&${OOHTML}=sfsr_dok&${SNHTML}=sfsr_err&${MAXPAGE}=26&${BASE}=SFSR&${FORD}=FIND&${FREETEXT}=&BET=%s:%s&\xC4BET=&ORG=" % (year,nr)
        # FIXME: consider using mechanize
        self.browser.retrieve(url,"sfs.tmp")
        t = TextReader("sfs.tmp",encoding="iso-8859-1")
        try:
            t.cue(u"<p>Sökningen gav ingen träff!</p>")
        except IOError: # hurra!
            grundforf.append("%s:%s" % (year,nr))
            return grundforf

        # Sen efter ändringsförfattning
        log.info(u'    Letar efter ändringsförfattning')
        url = "http://62.95.69.15/cgi-bin/thw?${HTML}=sfsr_lst&${OOHTML}=sfsr_dok&${SNHTML}=sfsr_err&${MAXPAGE}=26&${BASE}=SFSR&${FORD}=FIND&${FREETEXT}=&BET=&\xC4BET=%s:%s&ORG=" % (year,nr)
        self.browser.retrieve(url, "sfs.tmp")
        # maybe this is better done through mechanize?
        t = TextReader("sfs.tmp",encoding="iso-8859-1")
        try:
            t.cue(u"<p>Sökningen gav ingen träff!</p>")
            log.info(u'    Hittade ingen ändringsförfattning')
            return grundforf
        except IOError:
            t.seek(0)
            try:
                t.cuepast(u'<input type="hidden" name="BET" value="')
                grundforf.append(t.readto("$"))
                log.debug(u'    Hittade ändringsförfattning (till %s)' % grundforf[-1])
                return grundforf
            except IOError:
                t.seek(0)
                page = t.read(sys.maxint)
                for m in re.finditer('>(\d+:\d+)</a>',page):
                    grundforf.append(m.group(1))
                    log.debug(u'    Hittade ändringsförfattning (till %s)' % grundforf[-1])
                return grundforf

    def _downloadSingle(self, sfsnr):
        """Laddar ner senaste konsoliderade versionen av
        grundförfattningen med angivet SFS-nr. Om en tidigare version
        finns på disk, arkiveras den."""
        log.info(u'    Laddar ner %s' % sfsnr)
        # enc_sfsnr = sfsnr.replace(" ", "+")
        # Div specialhack för knepiga författningar
        if sfsnr == "1723:1016+1": parts = ["1723:1016"]
        elif sfsnr == "1942:740": parts = ["1942:740 A", "1942:740 B"]
        else: parts = [sfsnr]

        uppdaterad_tom = old_uppdaterad_tom = None
        for part in parts:
            sfst_url = "http://62.95.69.15/cgi-bin/thw?${OOHTML}=sfst_dok&${HTML}=sfst_lst&${SNHTML}=sfst_err&${BASE}=SFST&${TRIPSHOW}=format=THW&BET=%s" % part.replace(" ","+")
            sfst_file = "%s/sfst/%s.html" % (self.download_dir, SFSnrToFilename(part))
            self.browser.retrieve(sfst_url,"sfst.tmp")
            if os.path.exists(sfst_file):
                old_checksum = self._checksum(sfst_file)
                new_checksum = self._checksum("sfst.tmp")
                if (old_checksum != new_checksum):
                    old_uppdaterad_tom = self._findUppdateradTOM(sfsnr, sfst_file)
                    uppdaterad_tom = self._findUppdateradTOM(sfsnr, "sfst.tmp")
                    if uppdaterad_tom != old_uppdaterad_tom:
                        log.info(u'        %s har ändrats (%s -> %s)' % (sfsnr,old_uppdaterad_tom,uppdaterad_tom))
                        self._archive(sfst_file, sfsnr, old_uppdaterad_tom)
                    else:
                        log.info(u'        %s har ändrats (gammal checksum %s)' % (sfsnr,old_checksum))
                        self._archive(sfst_file, sfsnr, old_uppdaterad_tom,old_checksum)

                    # replace the current file, regardless of wheter
                    # we've updated it or not
                    Util.robustRename("sfst.tmp", sfst_file)
                else:
                    pass # leave the current file untouched
            else:
                Util.robustRename("sfst.tmp", sfst_file)

        sfsr_url = "http://62.95.69.15/cgi-bin/thw?${OOHTML}=sfsr_dok&${HTML}=sfst_lst&${SNHTML}=sfsr_err&${BASE}=SFSR&${TRIPSHOW}=format=THW&BET=%s" % sfsnr.replace(" ","+")
        sfsr_file = "%s/sfsr/%s.html" % (self.download_dir, SFSnrToFilename(sfsnr))
        if uppdaterad_tom != old_uppdaterad_tom:
            self._archive(sfsr_file, sfsnr, old_uppdaterad_tom)

        Util.ensureDir(sfsr_file)
        self.browser.retrieve(sfsr_url, sfsr_file)
        
            
    def _archive(self, filename, sfsnr, uppdaterad_tom, checksum=None):
        """Arkivera undan filen filename, som ska vara en
        grundförfattning med angivet sfsnr och vara uppdaterad
        t.o.m. det angivna sfsnumret"""
        archive_filename = "%s/sfst/%s-%s.html" % (self.download_dir, SFSnrToFilename(sfsnr),
                                                   SFSnrToFilename(uppdaterad_tom).replace("/","-"))
        if checksum:
            archive_filename = archive_filename.replace(".html", "-checksum-%s.html"%checksum)
        log.info(u'        Arkiverar %s till %s' % (filename, archive_filename))

        if not os.path.exists(archive_filename):
            os.rename(filename,archive_filename)
        
    def _findUppdateradTOM(self, sfsnr, filename):
        reader = TextReader(filename,encoding='iso-8859-1')
        try:
            reader.cue("&Auml;ndring inf&ouml;rd:<b> t.o.m. SFS")
            l = reader.readline()
            m = re.search('(\d+:\s?\d+)',l)
            if m:
                return m.group(1)
            else:
                # if m is None, the SFS id is using a non-standard
                # formatting (eg 1996/613-first-version) -- interpret
                # it as if it didn't exist
                return sfsnr
        except IOError:
            return sfsnr

    def _checksum(self,filename):
        """MD5-checksumman för den angivna filen"""
        import hashlib
        c = hashlib.md5()
        # fixme: Use SFSParser._extractSFST so that we only compare
        # the plaintext part of the downloaded file
        #f = open(filename)
        #data = f.read()
        #f.close()
        #c.update(data)
        #return c.hexdigest()
        p = SFSParser()
        try:
            plaintext = p._extractSFST([filename])
            # for some insane reason, hashlib:s update method can't seem
            # to handle ordinary unicode strings
            c.update(plaintext.encode('iso-8859-1'))
        except:
            log.warning("Could not extract plaintext from %s" % filename)
        return c.hexdigest()


class UpphavdForfattning(Exception):
    """Slängs när en upphävd författning parseas"""
    pass

class IckeSFS(Exception):
    """Slängs när en författning som inte är en egentlig SFS-författning parseas"""
    pass

DCT = Namespace(Util.ns['dct'])
XSD = Namespace(Util.ns['xsd'])
RINFO = Namespace(Util.ns['rinfo'])
RINFOEX = Namespace(Util.ns['rinfoex'])
class SFSParser(LegalSource.Parser):
    re_SimpleSfsId     = re.compile(r'(\d{4}:\d+)\s*$')
    re_ChapterId       = re.compile(r'^(\d+( \w|)) [Kk]ap.').match
    re_DivisionId      = re.compile(r'^AVD. ([IVX]*)').match
    re_SectionId       = re.compile(r'^(\d+ ?\w?) §[ \.]') # used for both match+sub
    re_SectionIdOld    = re.compile(r'^§ (\d+ ?\w?).')     # as used in eg 1810:0926
    re_DottedNumber    = re.compile(r'^(\d+ ?\w?)\. ').match
    re_NumberRightPara = re.compile(r'^(\d+)\) ').match
    re_Bokstavslista   = re.compile(r'^(\w)\) ').match
    re_ElementId       = re.compile(r'^(\d+) mom\.')        # used for both match+sub
    re_ChapterRevoked  = re.compile(r'^(\d+( \w|)) [Kk]ap. (upphävd|har upphävts) genom (förordning|lag) \([\d\:\. s]+\)\.?$').match
    re_SectionRevoked  = re.compile(r'^(\d+ ?\w?) §[ \.]([Hh]ar upphävts|[Nn]y beteckning (\d+ ?\w?) §) genom ([Ff]örordning|[Ll]ag) \([\d\:\. s]+\)\.$').match
    re_RevokeDate       = re.compile(r'/Upphör att gälla U:(\d+)-(\d+)-(\d+)/')
    re_EntryIntoForceDate = re.compile(r'/Träder i kraft I:(\d+)-(\d+)-(\d+)/')
    # use this custom matcher to ensure any strings you intend to convert
    # are legal roman numerals (simpler than having from_roman throwing
    # an exception)
    re_roman_numeral_matcher = re.compile('^M?M?M?(CM|CD|D?C?C?C?)(XC|XL|L?X?X?X?)(IX|IV|V?I?I?I?)$').match

    swedish_ordinal_list = (u'första', u'andra', u'tredje', u'fjärde', 
                            u'femte', u'sjätte', u'sjunde', u'åttonde', 
                            u'nionde', u'tionde', u'elfte', u'tolfte')
    swedish_ordinal_dict = dict(zip(swedish_ordinal_list, range(1,len(swedish_ordinal_list)+1)))
    roman_numeral_map = (('M',  1000),
                         ('CM', 900),
                         ('D',  500),
                         ('CD', 400),
                         ('C',  100),
                         ('XC', 90),
                         ('L',  50),
                         ('XL', 40),
                         ('X',  10),
                         ('IX', 9),
                         ('V',  5),
                         ('IV', 4),
                         ('I',  1))

    def __init__(self):
        self.trace = {'rubrik': logging.getLogger('sfs.trace.rubrik'),
                      'paragraf': logging.getLogger('sfs.trace.paragraf'),
                      'numlist': logging.getLogger('sfs.trace.numlist'),
                      'tabell': logging.getLogger('sfs.trace.tabell')}

        self.trace['rubrik'].debug(u'Rubriktracern är igång')
        self.trace['paragraf'].debug(u'Paragraftracern är igång')
        self.trace['numlist'].debug(u'Numlisttracern är igång')
        self.trace['tabell'].debug(u'Tabelltracern är igång')
                      
        self.lagrum_parser = LegalRef(LegalRef.LAGRUM,
                                      LegalRef.EGLAGSTIFTNING)
        self.forarbete_parser = LegalRef(LegalRef.FORARBETEN)

        self.current_section = u'0'
        self.current_chapter = u'0'
        self.current_headline_level = 0 # 0 = unknown, 1 = normal, 2 = sub
        LegalSource.Parser.__init__(self)
    
    def Parse(self,basefile,files):
        self.id = basefile
        # find out when data was last fetched (use the oldest file)
        timestamp = sys.maxint
        for filelist in files.values():
            for file in filelist:
                if os.path.getmtime(file) < timestamp:
                    timestamp = os.path.getmtime(file)
        
        registry = self._parseSFSR(files['sfsr'])
        try:
            plaintext = self._extractSFST(files['sfst'])
            # FIXME: Maybe Parser classes should be directly told what the
            # current basedir is, rather than having to do it the ugly way
            # (c.f. RegPubParser.Parse, which does something similar to
            # the below)
            plaintextfile = files['sfst'][0].replace(".html", ".txt").replace("downloaded/sfst", "intermediate")
            Util.ensureDir(plaintextfile)
            f = codecs.open(plaintextfile, "w",'iso-8859-1')
            f.write(plaintext)
            f.close()
            patchfile = 'patches/sfs/%s.patch' % basefile
            if os.path.exists(patchfile):
                patchedfile = mktemp()
                # we don't want to sweep the fact that we're patching under the carpet
                log.warning(u'%s: Applying patch %s' % (basefile, patchfile))
                cmd = 'patch -s %s %s -o %s' % (plaintextfile, patchfile, patchedfile)
                log.debug(u'%s: running %s' % (basefile,cmd))
                (ret, stdout, stderr) = Util.runcmd(cmd)
                if ret == 0: # successful patch
                    # patch from cygwin always seem to produce unix lineendings
                    cmd = 'unix2dos %s' % patchedfile
                    log.debug(u'%s: running %s' % (basefile,cmd))
                    (ret, stdout, stderr) = Util.runcmd(cmd)
                    if ret == 0: 
                        plaintextfile = patchedfile
                    else:
                        log.warning(u"%s: Failed lineending conversion: %s" % (basefile,stderr))
                else:
                    log.warning(u"%s: Could not apply patch %s: %s" % (basefile, patchfile, stdout.strip()))
            (meta, body) = self._parseSFST(plaintextfile, registry)
        except IOError:
            log.warning("%s: Fulltext saknas" % self.id)
            # extractSFST misslyckades, då det fanns någon post i
            # SFST-databasen (det händer alltför ofta att bara
            # SFSR-databasen är uppdaterad). Fejka ihop en meta
            # (Forfattningsinfo) och en body (Forfattning) utifrån
            # SFSR-datat

            # print serialize(registry)
            meta = Forfattningsinfo()
            meta['Rubrik'] = registry.rubrik
            meta[u'Utgivare'] = LinkSubject(u'Regeringskansliet',
                                            uri=self.find_authority_rec("Regeringskansliet"),
                                            predicate=self.labels[u'Utgivare'])
            # dateval = "1970-01-01" 
            # meta[u'Utfärdad'] = DateSubject(datetime.strptime(dateval, '%Y-%m-%d'),
            #                                 predicate=self.labels[u'Utfärdad'])
            fldmap = {u'SFS-nummer' :u'SFS nr', 
                      u'Ansvarig myndighet':u'Departement/ myndighet'}
            for k,v in registry[0].items():
                if k in fldmap:
                    meta[fldmap[k]] = v
            # self.lagrum_parser.verbose = True
            docuri = self.lagrum_parser.parse(meta[u'SFS nr'])[0].uri
            # self.lagrum_parser.verbose = False
            # print "docuri for %s: %s" % (meta[u'SFS nr'], docuri)
            meta[u'xml:base'] = docuri

            body = Forfattning()

            kwargs = {'id':u'S1'}
            s = Stycke([u'(Lagtext saknas)'], **kwargs)
            body.append(s)
            
        # Lägg till information om konsolideringsunderlag och
        # förarbeten från SFSR-datat
        meta[u'Konsolideringsunderlag'] = []
        meta[u'Förarbeten'] = []
        for rp in registry:
            uri = self.lagrum_parser.parse(rp['SFS-nummer'])[0].uri
            
            meta[u'Konsolideringsunderlag'].append(uri)
            if u'Förarbeten' in rp:
                for node in rp[u'Förarbeten']:
                    if isinstance(node,Link):
                        meta[u'Förarbeten'].append(node.uri)

        # Plocka ut övergångsbestämmelserna och stoppa in varje
        # övergångsbestämmelse på rätt plats i registerdatat.
        obs = None
        for p in body:
            if isinstance(p, Overgangsbestammelser):
                obs = p
                break
        if obs:
            for ob in obs:
                found = False
                # Det skulle vara vackrare om Register-objektet hade
                # nycklar eller index eller något, så vi kunde slippa
                # att hitta rätt registerpost genom nedanstående
                # iteration:
                for rp in registry:
                    if rp[u'SFS-nummer'] == ob.sfsnr:
                        rp[u'Övergångsbestämmelse'] = ob
                        found = True
                        break
                if not found:
                    log.warning(u'%s: Övergångsbestämmelse för [%s] saknar motsvarande registerpost' % (self.id, ob.sfsnr))
                    kwargs = {'id':u'L'+ob.sfsnr,
                              'uri':u'http://rinfo.lagrummet.nu/publ/sfs/'+ob.sfsnr}
                    rp = Registerpost(**kwargs)
                    rp[u'SFS-nummer'] = ob.sfsnr
                    rp[u'Övergångsbestämmelse'] = ob
                    
        # print serialize(meta)
        # print 
        # print serialize(body)
        # print
        # print serialize(registry)
        xhtml = self.generate_xhtml(meta,body,registry,__moduledir__,globals())
        return xhtml

    # metadatafält (kan förekomma i både SFST-header och SFSR-datat)
    # som bara har ett enda värde
    labels = {u'SFS-nummer':             RINFO['fsNummer'],
              u'SFS nr':                 RINFO['fsNummer'],
              u'Ansvarig myndighet':     DCT['creator'],
              u'Departement/ myndighet': DCT['creator'],
              u'Utgivare':               DCT['publisher'],
              u'Rubrik':                 DCT['title'],
              u'Utfärdad':               RINFO['utfardandedatum'],
              u'Ikraft':                 RINFO['ikrafttradandedatum'],
              u'Observera':              RDFS.comment, # FIXME: hitta bättre predikat
              u'Övrigt':                 RDFS.comment, # FIXME: hitta bättre predikat
              u'Tidsbegränsad':          RINFOEX['tidsbegransad'],
              u'Omtryck':                RINFOEX['omtryck'], # subtype av RINFO['fsNummer']
              u'Ändring införd':         RINFO['konsolideringsunderlag'],
              u'Författningen har upphävts genom':
                                         RINFOEX['upphavdAv'], # ska vara owl:inverseOf
                                                               # rinfo:upphaver
              u'Upphävd':                RINFOEX['upphavandedatum']
              }

    # metadatafält som kan ha flera värden (kommer representeras som
    # en lista av unicodeobjekt och LinkSubject-objekt)
    multilabels = {u'Förarbeten':        RINFO['forarbete'],
                   u'CELEX-nr':          RINFO['forarbete'],
                   u'Omfattning':        RINFO['andrar'], # också RINFO['ersatter'], RINFO['upphaver'], RINFO['inforsI']
                   }

              
    def _parseSFSR(self,files):
        """Parsear ut det SFSR-registret som innehåller alla ändringar
        i lagtexten från HTML-filer"""
        all_attribs = []
        r = Register()
        for f in files:
            soup = Util.loadSoup(f)
            r.rubrik = Util.elementText(soup.body('table')[2]('tr')[1]('td')[0])
            changes = soup.body('table')[3:-2]
            for table in changes:
                kwargs = {'id': 'undefined',
                          'uri': u'http://rinfo.lagrummet.nu/publ/sfs/undefined'}
                p = Registerpost(**kwargs)
                for row in table('tr'):
                    key = Util.elementText(row('td')[0])
                    if key.endswith(":"):  key= key[:-1] # trim ending ":"
                    if key == '': continue
                    val = Util.elementText(row('td')[1]).replace(u'\xa0',' ') # no nbsp's, please
                    if val != "":
                        if key == u'SFS-nummer':
                            if val.startswith('N'):
                                raise IckeSFS()
                            if len(r) == 0:
                                firstnode = self.lagrum_parser.parse(val)[0]
                                if hasattr(firstnode,'uri'):
                                    docuri = firstnode.uri
                                else:
                                    log.warning(u'Kunde inte tolka [%s] som ett SFS-nummer' % val)
                            p[key] = UnicodeSubject(val,predicate=self.labels[key])
                            # FIXME: Eftersom det här sen går in i ett
                            # id-fält, id-värden måste vara NCNames,
                            # och NCNames inte får innehålla kolon
                            # måste vi hitta på någon annan
                            # delimiterare, typ bindestreck eller punkt
                            # http://www.w3.org/TR/REC-xml-names/#NT-NCName
                            # http://www.w3.org/TR/REC-xml/#NT-Name
                            #
                            # (börjar med 'L' eftersom NCNames måste
                            # börja med ett Letter)
                            p.id = u'L' + val
                            # p.uri = u'http://rinfo.lagrummet.nu/publ/sfs/' + val
                            firstnode = self.lagrum_parser.parse(val)[0]
                            if hasattr(firstnode,'uri'):
                                p.uri = firstnode.uri
                            else:
                                log.warning(u'Kunde inte tolka [%s] som ett SFS-nummer' % val)
                            
                            # self.lagrum_parser.verbose = False
                            # print "docuri for %s: %s" % (val, p.uri)
                            
                        elif key == u'Ansvarig myndighet':
                            try:
                                authrec = self.find_authority_rec(val)
                                p[key] = LinkSubject(val, uri=unicode(authrec[0]),
                                                     predicate=self.labels[key])
                            except Exception, e:
                                p[key] = val
                        elif key == u'Rubrik':
                            p[key] = UnicodeSubject(val,predicate=self.labels[key])
                        elif key == u'Observera':
                            if u'Författningen är upphävd/skall upphävas: ' in val:
                                if datetime.strptime(val[41:51], '%Y-%m-%d') < datetime.today():
                                    raise UpphavdForfattning()
                            p[key] = UnicodeSubject(val,predicate=self.labels[key])
                        elif key == u'Ikraft':
                            p[key] = DateSubject(datetime.strptime(val[:10], '%Y-%m-%d'), predicate=self.labels[key])
                            p[u'Har övergångsbestämmelse'] = (val.find(u'\xf6verg.best.') != -1)
                        elif key == u'Omfattning':
                            p[key] = []
                            for changecat in val.split(u'; '):
                                if (changecat.startswith(u'ändr.') or
                                    changecat.startswith(u'ändr ') or
                                    changecat.startswith(u'ändring ')):
                                    pred = RINFO['ersatter']
                                elif (changecat.startswith(u'upph.') or
                                      changecat.startswith(u'utgår ')):
                                    pred = RINFO['upphaver']
                                elif (changecat.startswith(u'ny') or
                                      changecat.startswith(u'ikrafttr.') or
                                      changecat.startswith(u'ikrafftr.') or
                                      changecat.startswith(u'ikraftr.') or
                                      changecat.startswith(u'ikraftträd.') or
                                      changecat.startswith(u'tillägg')):
                                    pred = RINFO['inforsI']
                                elif (changecat.startswith(u'nuvarande') or
                                      changecat == 'begr. giltighet' or
                                      changecat == 'Omtryck' or
                                      changecat == 'omtryck' or
                                      changecat == 'forts.giltighet' or
                                      changecat == 'forts. giltighet' or
                                      changecat == 'forts. giltighet av vissa best.'):
                                    # FIXME: Is there something smart
                                    # we could do with these?
                                    pred = None
                                else:
                                    log.warning(u"%s: Okänd omfattningstyp  ['%s']" % (self.id, changecat))
                                    pred = None
                                p[key].extend(self.lagrum_parser.parse(val,docuri,pred))
                                p[key].append(u';')
                            p[key] = p[key][:-1] # chop of trailing ';'
                        elif key == u'F\xf6rarbeten':
                            p[key] = self.forarbete_parser.parse(val,docuri,RINFO['forarbete'])
                        elif key == u'CELEX-nr':
                            p[key] = self.forarbete_parser.parse(val,docuri,RINFO['forarbete'])
                        elif key == u'Tidsbegränsad':
                            p[key] = DateSubject(datetime.strptime(val[:10], '%Y-%m-%d'), predicate=self.labels[key])
                        else:
                            log.warning(u'%s: Obekant nyckel [\'%s\']' % self.id, key)
                r.append(p)
        return r


    def _extractSFST(self, files = [], keepHead=True):
        """Plockar fram plaintextversionen av den konsoliderade
        lagtexten från (idag) nedladdade HTML-filer"""
        if not files:
            return ""

        t = TextReader(files[0], encoding="iso-8859-1")
        if keepHead:
            t.cuepast(u'<pre>')
        else:
            t.cuepast(u'<hr>')

        txt = t.readto(u'</pre>')
        re_entities = re.compile("&(\w+?);")
        txt = re_entities.sub(self._descapeEntity,txt)
        if not '\r\n' in txt:
            txt = txt.replace('\n','\r\n')
        re_tags = re.compile("</?\w{1,3}>")
        txt = re_tags.sub(u'',txt)
        return txt + self._extractSFST(files[1:],keepHead=False)

    def _descapeEntity(self,m):
        return unichr(htmlentitydefs.name2codepoint[m.group(1)])

    # rekursera igenom dokumentet på jakt efter adresserbara enheter
    # (kapitel, paragrafer, stycken, punkter) * konstruera xml:id's
    # för dem, (på lagen-nu-formen sålänge, dvs K1P2S3N4 för 1 kap. 2
    # § 3 st. 4 p)
    def _construct_ids(self, element, prefix, baseuri, skipfragments=[]):
        counters = defaultdict(int)
        if isinstance(element, CompoundStructure):
            for p in element:
                #if type(p) in counters:
                counters[type(p)] += 1
                #else:
                #    counters[type(p)] = 1
                if hasattr(p, 'fragment_label'):
                    elementtype = p.fragment_label
                    if hasattr(p, 'ordinal'):
                        elementordinal = p.ordinal.replace(" ","")
                    elif hasattr(p, 'sfsnr'):
                        elementordinal = p.sfsnr
                    else:
                        elementordinal = counters[type(p)]
                    fragment = "%s%s%s" % (prefix, elementtype, elementordinal)
                    p.id = fragment
                else:
                    fragment = prefix
                if ((hasattr(p, 'fragment_label') and
                     p.fragment_label in skipfragments)):
                    self._construct_ids(p,prefix,baseuri, skipfragments)
                else:
                    self._construct_ids(p,fragment,baseuri, skipfragments)
            if (isinstance(element, Stycke)
                or isinstance(element, Listelement)
                or isinstance(element, Tabellcell)):
                nodes = []
                for p in element: # normally only one, but can be more
                                  # if the Stycke has a NumreradLista
                                  # or similar
                    if isinstance(p,unicode): # look for stuff

                        # Make all links have a dct:references
                        # predicate -- not that meaningful for the
                        # XHTML2 code, but needed to make useful RDF
                        # triples in the RDFa output
                        
                        nodes.extend(self.lagrum_parser.parse(" ".join(p.split()),
                                                              baseuri+prefix,
                                                              "dct:references"))
                        # nodes.extend(self.lagrum_parser.parse(p,baseuri+prefix,DCT["references"]))
                        idx = element.index(p)
                element[idx:idx+1] = nodes

    def _count_elements(self, element):
        counters = defaultdict(int)
        if isinstance(element, CompoundStructure):
            for p in element:
                if hasattr(p, 'fragment_label'):
                    counters[p.fragment_label] += 1
                    if hasattr(p, 'ordinal'):
                        counters[p.fragment_label+p.ordinal] += 1
                    subcounters = self._count_elements(p)
                    for k in subcounters:
                        counters[k] += subcounters[k]
        return counters
                

    def _parseSFST(self, lawtextfile, registry):
        # self.reader = TextReader(ustring=lawtext,linesep=TextReader.UNIX)
        self.reader = TextReader(lawtextfile, encoding='iso-8859-1', linesep=TextReader.DOS)
        self.reader.autostrip = True

        meta = self.makeHeader() 
        body = self.makeForfattning()
        elements = self._count_elements(body)
        # print elements
        if 'K' in elements and elements['P1'] < 2:
            # print "Activating special ignore-the-chapters code"
            skipfragments = ['K']
        else:
            skipfragments = []
        self._construct_ids(body, u'', u'http://rinfo.lagrummet.nu/publ/sfs/%s#' % (FilenameToSFSnr(self.id)), skipfragments)
        return meta,body

    def _swedish_ordinal(self,s):
        sl = s.lower()
        if sl in self.swedish_ordinal_dict:
            return self.swedish_ordinal_dict[sl]
        return None

    # Example code from http://www.diveintopython.org/
    def _from_roman(self,s):
        """convert Roman numeral to integer"""
        result = 0
        index = 0
        for numeral, integer in self.roman_numeral_map:
            while s[index:index+len(numeral)] == numeral:
                result += integer
                index += len(numeral)
        return result

    #----------------------------------------------------------------
    #
    # SFST-PARSNING


    def makeHeader(self):
        subreader = self.reader.getreader(self.reader.readchunk, self.reader.linesep * 4)
        meta = Forfattningsinfo()

        for line in subreader.getiterator(subreader.readparagraph):
            if ":" in line:
                (key,val) = [Util.normalizeSpace(x) for x in line.split(":",1)]
            if key == u'Rubrik':
                meta[key] = UnicodeSubject(val,predicate=self.labels[key])
            elif key == u'Övrigt':
                meta[key] = UnicodeSubject(val,predicate=self.labels[key])
            elif key == u'SFS nr':
                meta[key] = UnicodeSubject(val,predicate=self.labels[key])
            elif key == u'Utfärdad':
                meta[key] = DateSubject(datetime.strptime(val[:10], '%Y-%m-%d'), predicate=self.labels[key])
            elif key == u'Upphävd':
                meta[key] = DateSubject(datetime.strptime(val[:10], '%Y-%m-%d'), predicate=self.labels[key])
                if meta[key] < datetime.today():
                    raise UpphavdForfattning()
            elif key == u'Departement/ myndighet':
                authrec = self.find_authority_rec(val)
                meta[key] = LinkSubject(val, uri=unicode(authrec),
                                     predicate=self.labels[key])
            elif key == u'Ändring införd':
                # återanvänd URI-strategin från LegalRef
                m = self.re_SimpleSfsId.search(val)
                if m:
                    uri = self.lagrum_parser.parse(m.group(1))[0].uri
                    # uri = self.lagrum_parser.parse(val)[0].uri
                    meta[key] = LinkSubject(val,uri=uri,predicate=self.labels[key])
                else:
                    log.warning(u"%s: Kunde inte tolka SFS-numret för senaste ändring" % self.id)

            elif key == u'Omtryck':
                val = val.replace(u'SFS ','')
                val = val.replace(u'SFS','')
                uri = self.lagrum_parser.parse(val)[0].uri
                meta[key] = UnicodeSubject(val,predicate=self.labels[key])
            elif key == u'Författningen har upphävts genom':
                val = val.replace(u'SFS ','')
                val = val.replace(u'SFS','')
                firstnode = self.lagrum_parser.parse(val)[0]
                if hasattr(firstnode,'uri'):
                    uri = firstnode.uri
                    meta[key] = LinkSubject(val,uri=uri,predicate=self.labels[key])
                else:
                    log.warning(u'Kunde inte tolka [%s] som ett "upphävd genom"-SFS-nummer' % val)
                    meta[key] = val
                

            elif key == u'Tidsbegränsad':
                meta[key] = DateSubject(datetime.strptime(val[:10], '%Y-%m-%d'), predicate=self.labels[key])
            else:
                log.warning(u'%s: Obekant nyckel [\'%s\']' % (self.id, key))
            
            meta[u'Utgivare'] = LinkSubject(u'Regeringskansliet',
                                            uri=self.find_authority_rec("Regeringskansliet"),
                                            predicate=self.labels[u'Utgivare'])

        # print "parsing %s" % meta[u'SFS nr']
        docuri = self.lagrum_parser.parse(meta[u'SFS nr'])[0].uri
        # print "docuri for %s: %s" % (meta[u'SFS nr'], docuri)
        meta[u'xml:base'] = docuri

        if u'Rubrik' not in meta:
            log.warning("%s: Rubrik saknas" % self.id)
            
        return meta
        
    def makeForfattning(self):
        while self.reader.peekline() == "":
            self.reader.readline()
            
        # log.debug(u'Första raden \'%s\'' % self.reader.peekline())
        (line, upphor, ikrafttrader) = self.andringsDatum(self.reader.peekline())
        if ikrafttrader:
            log.debug(u'Författning med ikraftträdandedatum %s' % ikrafttrader)
            b = Forfattning(ikrafttrader=ikrafttrader)
            self.reader.readline()
        else:
            log.debug(u'Författning utan ikraftträdandedatum')
            b = Forfattning()
            
        while not self.reader.eof():
            state_handler = self.guess_state()
            # special case - if a Overgangsbestammelse is encountered
            # without the preceeding headline (which would normally
            # set state_handler to makeOvergangsbestammelser (notice
            # the plural)
            if state_handler == self.makeOvergangsbestammelse:
                res = self.makeOvergangsbestammelser(rubrik_saknas = True)
            else:
                res = state_handler()
            if res != None:
                b.append(res)
        return b

    def makeAvdelning(self):
        avdelningsnummer = self.idOfAvdelning()
        p = Avdelning(rubrik = self.reader.readline(),
                      ordinal = avdelningsnummer,
                      underrubrik = None)
        if self.reader.peekline(1) == "" and self.reader.peekline(3) == "":
            self.reader.readline()
            p.underrubrik = self.reader.readline()

        log.debug(u"  Ny avdelning: '%s...'" % p.rubrik[:30])

        while not self.reader.eof():
            state_handler = self.guess_state()

            if state_handler in (self.makeAvdelning, # Strukturer som signalerar att denna avdelning är slut
                                 self.makeOvergangsbestammelser,
                                 self.makeBilaga): 
                log.debug(u"  Avdelning %s färdig" % p.ordinal)
                return p
            else:
                res = state_handler()
                if res != None:
                    p.append(res)
        # if eof is reached
        return p
        
    def makeUpphavtKapitel(self):
        kapitelnummer = self.idOfKapitel()
        c = UpphavtKapitel(self.reader.readline(),
                           ordinal = kapitelnummer)
        log.debug(u"  Upphävt kapitel: '%s...'" % c[:30])

        return c
    
    def makeKapitel(self):
        kapitelnummer = self.idOfKapitel()

        para = self.reader.readparagraph()
        (line, upphor, ikrafttrader) = self.andringsDatum(para)
        
        kwargs = {'rubrik':  Util.normalizeSpace(line),
                  'ordinal': kapitelnummer}
        if upphor: kwargs['upphor'] = upphor
        if ikrafttrader: kwargs['ikrafttrader'] = ikrafttrader
        k = Kapitel(**kwargs)
        self.current_headline_level = 0
        
        log.debug(u"    Nytt kapitel: '%s...'" % line[:30])
        
        while not self.reader.eof():
            state_handler = self.guess_state()

            if state_handler in (self.makeKapitel, # Strukturer som signalerar slutet på detta kapitel
                                 self.makeUpphavtKapitel,
                                 self.makeAvdelning,
                                 self.makeOvergangsbestammelser,
                                 self.makeBilaga): 
                log.debug(u"    Kapitel %s färdigt" % k.ordinal)
                return (k)
            else:
                res = state_handler()
                if res != None:
                    k.append(res)
        # if eof is reached
        return k

    def makeRubrik(self):
        para = self.reader.readparagraph()
        (line,upphor,ikrafttrader) = self.andringsDatum(para)
        log.debug(u"      Ny rubrik: '%s...'" % para[:30])

        kwargs = {}
        if upphor:       kwargs['upphor']       = upphor
        if ikrafttrader: kwargs['ikrafttrader'] = ikrafttrader
        if self.current_headline_level == 2:
            kwargs['type'] = u'underrubrik'
        elif self.current_headline_level == 1:
            self.current_headline_level = 2
        
        h = Rubrik(line, **kwargs)
        return h

    def makeUpphavdParagraf(self):
        paragrafnummer = self.idOfParagraf(self.reader.peekline())
        p = UpphavdParagraf(self.reader.readline(),
                            ordinal = paragrafnummer)
        self.current_section = paragrafnummer
        log.debug(u"      Upphävd paragraf: '%s...'" % p[:30])
        return p
    
    def makeParagraf(self):
        paragrafnummer = self.idOfParagraf(self.reader.peekline())
        self.current_section = paragrafnummer
        firstline = self.reader.peekline()
        log.debug(u"      Ny paragraf: '%s...'" % firstline[:30])
        # Läs förbi paragrafnumret:
        self.reader.read(len(paragrafnummer)+ len(u' § '))

        # some really old laws have sections split up in "elements"
        # (moment), eg '1 § 1 mom.', '1 § 2 mom.' etc
        match = self.re_ElementId.match(firstline)
        if self.re_ElementId.match(firstline):
            momentnummer = match.group(1)
            self.reader.read(len(momentnummer) + len(u' mom. '))
        else:
            momentnummer = None

        (fixedline, upphor, ikrafttrader) = self.andringsDatum(firstline)
        # Läs förbi '/Upphör [...]/' och '/Ikraftträder [...]/'-strängarna
        self.reader.read(len(firstline)-len(fixedline))
        kwargs = {'ordinal': paragrafnummer}
        if upphor: kwargs['upphor'] = upphor
        if ikrafttrader: kwargs['ikrafttrader'] = ikrafttrader

        if momentnummer:
            kwargs['moment'] = momentnummer

        p = Paragraf(**kwargs)

        state_handler = self.makeStycke
        res = self.makeStycke()
        p.append(res)

        while not self.reader.eof():
            state_handler = self.guess_state()
            if state_handler in (self.makeParagraf,
                                 self.makeUpphavdParagraf,
                                 self.makeKapitel,
                                 self.makeUpphavtKapitel,
                                 self.makeAvdelning,
                                 self.makeRubrik,
                                 self.makeOvergangsbestammelser,
                                 self.makeBilaga):
                log.debug(u"      Paragraf %s färdig" % paragrafnummer)
                return p
            elif state_handler == self.blankline:
                state_handler() # Bara att slänga bort
            elif state_handler == self.makeOvergangsbestammelse:
                log.debug(u"      Paragraf %s färdig" % paragrafnummer)
                log.warning(u"%s: Avskiljande rubrik saknas mellan författningstext och övergångsbestämmelser" % self.id)
                return p
            else:
                assert state_handler == self.makeStycke, "guess_state returned %s, not makeStycke" % state_handler.__name__
                #if state_handler != self.makeStycke:
                #    log.warning(u"behandlar '%s...' som stycke, inte med %s" % (self.reader.peekline()[:30], state_handler.__name__))
                res = self.makeStycke()
                p.append(res)

        # eof occurred
        return p

    def makeStycke(self):
        log.debug(u"        Nytt stycke: '%s...'" % self.reader.peekline()[:30])
        s = Stycke([self.reader.readparagraph()])
        while not self.reader.eof():
            state_handler = self.guess_state()
            log.debug(u"            guess_state:%s " % state_handler.__name__)
            if state_handler in (self.makeNumreradLista,
                                 self.makeBokstavslista,
                                 self.makeStrecksatslista,
                                 self.makeTabell):
                res = state_handler()
                s.append(res)
            elif state_handler == self.blankline:
                state_handler() # Bara att slänga bort
            else:
                return s
        return s

    def makeNumreradLista(self): 
        n = NumreradLista()
        while not self.reader.eof():
            # Utgå i första hand från att nästa stycke är ytterligare
            # en listpunkt (vissa tänkbara stycken kan även matcha
            # tabell m.fl.)
            if self.isNumreradLista():
                state_handler = self.makeNumreradLista
            else:
                state_handler = self.guess_state()

            if state_handler not in (self.blankline,
                                     self.makeNumreradLista,
                                     self.makeBokstavslista,
                                     self.makeStrecksatslista):
                return n
            elif state_handler == self.blankline:
                state_handler()
            else:
                if state_handler == self.makeNumreradLista:
                    log.debug(u"          Ny punkt: '%s...'" % self.reader.peekline()[:30])
                    listelement_ordinal = self.idOfNumreradLista()
                    li = Listelement(ordinal = listelement_ordinal)
                    p = self.reader.readparagraph()
                    li.append(p)
                    n.append(li)
                else:
                    # this must be a sublist
                    res = state_handler()
                    n[-1].append(res)
                log.debug(u"          Punkt %s avslutad" % listelement_ordinal)
        return n

    def makeBokstavslista(self):
        n = Bokstavslista()
        while not self.reader.eof():
            state_handler = self.guess_state()
            if state_handler not in (self.blankline, self.makeBokstavslista):
                return n
            elif state_handler == self.blankline:
                res = state_handler()
            else:
                log.debug(u"            Ny underpunkt: '%s...'" % self.reader.peekline()[:30])
                listelement_ordinal = self.idOfBokstavslista()
                li = Listelement(ordinal = listelement_ordinal)
                p = self.reader.readparagraph()
                li.append(p)
                n.append(li)
                log.debug(u"            Underpunkt %s avslutad" % listelement_ordinal)
        return n
        

    def makeStrecksatslista(self):
        n = Strecksatslista()
        cnt = 0
        while not self.reader.eof():
            state_handler = self.guess_state()
            if state_handler not in (self.blankline, self.makeStrecksatslista):
                return n
            elif state_handler == self.blankline:
                res = state_handler()
            else:
                log.debug(u"            Ny strecksats: '%s...'" % self.reader.peekline()[:30])
                cnt += 1
                p = self.reader.readparagraph()
                li = Listelement(ordinal = unicode(cnt))
                li.append(p)
                n.append(li)
                log.debug(u"            Strecksats #%s avslutad" % cnt)
        return n


    def blankline(self):
        self.reader.readline()
        return None

    def eof(self):
        return None

    def makeOvergangsbestammelser(self,rubrik_saknas=False): # svenska: övergångsbestämmelser
        # det kan diskuteras om dessa ska ses som en del av den
        # konsoliderade lagtexten öht, men det verkar vara kutym att
        # ha med åtminstone de som kan ha relevans för gällande rätt
        log.debug(u"    Ny Övergångsbestämmelser")

        if rubrik_saknas:
            rubrik = u"[Övergångsbestämmelser]"
        else:
            rubrik = self.reader.readparagraph()
        obs = Overgangsbestammelser(rubrik=rubrik)
        
        while not self.reader.eof():
            state_handler = self.guess_state()
            if state_handler == self.makeBilaga:
                return obs
                
            res = state_handler()
            if res != None:
                if state_handler != self.makeOvergangsbestammelse:
                    if hasattr(self,'id'):
                        log.warning(u"%s: Övergångsbestämmelsen saknar SFS-nummer" % self.id)
                    else:
                        log.warning(u"(unknown): Övergångsbestämmelsen saknar ett SFS-nummer")

                    obs.append(Overgangsbestammelse([res], sfsnr=u'0000:000'))
                else:
                    obs.append(res)
            
        return obs

    def makeOvergangsbestammelse(self):
        p = self.reader.readline()
        log.debug(u"      Ny Övergångsbestämmelse: %s" % p)
        ob = Overgangsbestammelse(sfsnr=p)
        while not self.reader.eof():
            state_handler = self.guess_state()
            if state_handler in (self.makeOvergangsbestammelse,
                                 self.makeBilaga):
                return ob
            res = state_handler()
            if res != None:
                ob.append(res)

        return ob
        

    def makeBilaga(self): # svenska: bilaga
        rubrik = self.reader.readparagraph()
        b = Bilaga(rubrik=rubrik)
        log.debug(u"    Ny bilaga: %s" % rubrik)
        while not self.reader.eof():
            state_handler = self.guess_state()
            if state_handler in (self.makeBilaga,
                                 self.makeOvergangsbestammelser):
                return b
            res = state_handler()
            if res != None:
                b.append(res)
        return b

    def andringsDatum(self,line,match=False):
        # Hittar ändringsdatumdirektiv i line. Om match, matcha från strängens början, annars sök i hela strängen.
        ikrafttrader = None
        upphor = None
        if match:
            m = self.re_RevokeDate.match(line)
        else:
            m = self.re_RevokeDate.search(line)
        if m:
            upphor = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            line = self.re_RevokeDate.sub("", line)
        if match:
            m = self.re_EntryIntoForceDate.match(line)
        else:
            m = self.re_EntryIntoForceDate.search(line)
        if m:
            ikrafttrader = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            line = self.re_EntryIntoForceDate.sub("", line) 
        return (line, upphor, ikrafttrader)

    
    def guess_state(self):
        # sys.stdout.write("        Guessing for '%s...'" % self.reader.peekline()[:30])
        try:
            if self.reader.peekline() == "": handler = self.blankline
            elif self.isAvdelning():             handler = self.makeAvdelning
            elif self.isUpphavtKapitel():        handler = self.makeUpphavtKapitel
            elif self.isUpphavdParagraf():       handler = self.makeUpphavdParagraf
            elif self.isKapitel():               handler = self.makeKapitel
            elif self.isParagraf():              handler = self.makeParagraf
            elif self.isTabell():                handler = self.makeTabell
            elif self.isOvergangsbestammelser(): handler = self.makeOvergangsbestammelser
            elif self.isOvergangsbestammelse():  handler = self.makeOvergangsbestammelse
            elif self.isBilaga():                handler = self.makeBilaga
            elif self.isNumreradLista():         handler = self.makeNumreradLista
            elif self.isStrecksatslista():       handler = self.makeStrecksatslista
            elif self.isBokstavslista():         handler = self.makeBokstavslista
            elif self.isRubrik():                handler = self.makeRubrik
            else:                                handler = self.makeStycke
        except IOError:
            handler=self.eof
        # sys.stdout.write("%r\n" % handler)
        return handler

    def isAvdelning(self):
        # The start of a part ("avdelning") should be a single line
        if '\n' in self.reader.peekparagraph() != "":
            return False
                      
        return self.idOfAvdelning() != None
    
    def idOfAvdelning(self):
        # There are four main styles of parts ("Avdelning") in swedish law
        # 
        # 1998:808: "FÖRSTA AVDELNINGEN\n\nÖVERGRIPANDE BESTÄMMELSER"
        #  (also in 1932:130, 1942:740, 1956:623, 1957:297, 1962:381, 1962:700, 
        #   1970:988, 1970:994, 1971:235 (revoked), 1973:370 (revoked), 
        #   1977:263 (revoked), 1987:230, 1992:300 (revoked), 1994:200, 
        #   1998:674, 2000:192, 2005:104 and 2007:528 -- not always in all 
        #   uppercase. However, the initial line "FÖRSTA AVDELNININGEN" 
        #   (in any casing) is always followed by another line that 
        #   describes/labels the part.)
        #
        # 1979:1152: "Avd. 1. Bestämmelser om taxering av fastighet" 
        #  (also in 1979:1193 (revoked))
        #
        # 1999:1229: "AVD. I INNEHÅLL OCH DEFINITIONER"
        #
        # and also "1 avd." (in 1959:287 (revoked), 1959:420 (revoked)
        #
        #  The below code checks for all these patterns in turn
        # 
        # The variants "Avdelning 1" and "Avdelning I" have also been found, 
        # but only in appendixes
        p = self.reader.peekline()
        if p.lower().endswith(u"avdelningen") and len(p.split()) == 2:
            ordinal = p.split()[0]
            return self._swedish_ordinal(ordinal)
        elif p.startswith(u"AVD. "):
            roman = re.split(r'\W',p)[2]
            if self.re_roman_numeral_matcher(roman):
                return self._from_roman(roman)
        elif p[2:6] == "avd.":
            if p[0].isdigit():
                return p[0]
        elif p.startswith(u"Avd. "):
            idstr = re.split(r'\W',p)[2]
            if idstr.isdigit():
                return idstr
        return None

    def isUpphavtKapitel(self):
        match = self.re_ChapterRevoked(self.reader.peekline())
        return match != None

    def isKapitel(self):
        return self.idOfKapitel() != None

    def idOfKapitel(self):
        p = self.reader.peekparagraph()
        # '1 a kap.' -- almost always a headline, regardless if it
        # streches several lines but there are always special cases
        # (1982:713 1 a kap. 7 §)
        #m = re.match(r'^(\d+( \w|)) [Kk]ap.',p)
        m = self.re_ChapterId(p)
        if m:
            # even though something might look like the start of a chapter, it's often just the
            # start of a paragraph in a section that lists the names of chapters. These following
            # attempts to filter these out by looking for some typical line endings for those cases
            if (p.endswith(",") or
                p.endswith(";") or
                p.endswith(")") or
                p.endswith(" och") or # in unlucky cases, a chapter heading might span two lines in a way that the first line ends with "och" (eg 1998:808 kap. 3)
                p.endswith(" om") or
                p.endswith(" samt") or
                (p.endswith(".") and not
                 (m.span()[1] == len(p) or # if the ENTIRE p is eg "6 kap." (like it is in 1962:700)
                  p.endswith(" m.m.") or
                  p.endswith(" m. m.") or
                  self.re_ChapterRevoked(p)))): # If the entire chapter's
                                           # been revoked, we still
                                           # want to count it as a
                                           # chapter

                # sys.stdout.write(u"chapter_id: '%s' failed second check" % p)
                return None

            # Om det ser ut som en tabell är det nog ingen kapitelrubrik
            if self.isTabell(p, requireColumns=True):
                return None 

            else:
                return m.group(1)
        else:
            # sys.stdout.write(u"chapter_id: '%s' failed first check" % p[:40])
            return None

    def isRubrik(self, p=None):
        if p == None:
            self.trace['rubrik'].debug("isRubrik: direct")
            p = self.reader.peekparagraph()
            indirect = False
        else:
            self.trace['rubrik'].debug("isRubrik: indirect")
            indirect = True

        self.trace['rubrik'].debug("isRubrik: p=%s" % p)
        if len(p) > 100: # it shouldn't be too long
            self.trace['rubrik'].debug("isRubrik: too long")
            return False

        # A headline should not look like the start of a paragraph or a numbered list
        if self.isParagraf(p): 
            self.trace['rubrik'].debug("isRubrik: looks like para")
            return False

        if self.isNumreradLista(p):
            self.trace['rubrik'].debug("isRubrik: looks like numreradlista")
            return False
            

        if (p.endswith(".") and # a headline never ends with a period, unless it ends with "m.m." or similar
            not (p.endswith("m.m.") or 
                 p.endswith("m. m.") or 
                 p.endswith("m.fl.") or 
                 p.endswith("m. fl."))):
            self.trace['rubrik'].debug("isRubrik: ends with period")
            return False 

        if (p.endswith(",") or  # a headline never ends with these characters
            p.endswith(":") or 
            p.endswith("samt") or 
            p.endswith("eller")):
            self.trace['rubrik'].debug("isRubrik: ends with comma/colon etc")
            return False

        try:
            nextp = self.reader.peekparagraph(2) # FIXME: should be 2
        except IOError:
            nextp = u''
        
        # finally, it should be followed by a paragraph - but this
        # test is only done if this check is not indirect (to avoid
        # infinite recursion)
        if not indirect:
            if (not self.isParagraf(nextp)) and (not self.isRubrik(nextp)):
                self.trace['rubrik'].debug("isRubrik: is not followed by a paragraf or rubrik")
                return False

        # if this headline is followed by a second headline, that
        # headline and all subsequent headlines should be regardes as
        # sub-headlines
        if (not indirect) and self.isRubrik(nextp):
            self.current_headline_level = 1
        
        # ok, all tests passed, this might be a headline!
        self.trace['rubrik'].debug("isRubrik: All tests passed for %s" % p)
        return True

    def isUpphavdParagraf(self):
        match = self.re_SectionRevoked(self.reader.peekline())
        return match != None

    def isParagraf(self, p=None):
        if not p:
            p = self.reader.peekparagraph()
        else:
            self.trace['paragraf'].debug("isParagraf: called w/ '%s'" % p[:30])

        paragrafnummer = self.idOfParagraf(p)
        if paragrafnummer == None:
            self.trace['paragraf'].debug("isParagraf: '%s': no paragrafnummer" % p[:30])
            return False
        if paragrafnummer == '1':
            self.trace['paragraf'].debug("isParagraf: paragrafnummer = 1, return true")
            return True
        # now, if this sectionid is less than last section id, the
        # section is probably just a reference and not really the
        # start of a new section. One example of that is
        # /1991:1469#K1P7S1.
        #
        # FIXME: "10" should be larger than "9"
        if Util.numcmp(paragrafnummer, self.current_section) >= 0:
            self.trace['paragraf'].debug("isParagraf: sectionnumberingcompare succeded (%s > %s)" % (paragrafnummer, self.current_section))
            return True
        else:
            self.trace['paragraf'].debug("isParagraf: section numbering compare failed (%s <= %s)" % (paragrafnummer, self.current_section))
            return False

    def idOfParagraf(self, p):
        match = self.re_SectionId.match(p)
        if match:
            return match.group(1)
        else:
            match = self.re_SectionIdOld.match(p)
            if match:
                return match.group(1)
            else:
                return None

    # Om assumeTable är True är testerna något generösare än
    # annars. Den är False för den första raden i en tabell, men True
    # för de efterföljande.
    #
    # Om requireColumns är True krävs att samtliga rader är
    # spaltuppdelade
    
    def isTabell(self, p=None, assumeTable = False, requireColumns = False):
        if not p:
            p = self.reader.peekparagraph()
        # Vissa snedformatterade tabeller kan ha en högercell som går
        # ned en rad för långt gentemot nästa rad, som har en tom
        # högercell:

        # xxx xxx xxxxxx     xxxx xx xxxxxx xx
        # xxxxx xx xx x      xxxxxx xxx xxx x 
        #                    xx xxx xxx xxx 
        # xxx xx xxxxx xx
        # xx xxx xx x xx

        # dvs något som egentligen är två stycken läses in som
        # ett. Försök hitta sådana fall, och titta i så fall endast på
        # första stycket
        lines = []
        emptyleft = False
        for l in p.split(self.reader.linesep):
            if l.startswith(' '):
                emptyleft = True
                lines.append(l)
            else:
                if emptyleft:
                    self.trace['tabell'].debug(u"isTabell('%s'): Snedformatterade tabellrader" % (p[:20]))
                    break
                else:
                    lines.append(l)

        numlines = len(lines)
        # Heuristiken för att gissa om detta stycke är en tabellrad:
        # Om varje rad
        # 1. Är kort (indikerar en tabellrad med en enda vänstercell)
        if (assumeTable or numlines > 1) and not requireColumns:
            matches = [l for l in lines if len(l) < 50]
            if len(matches) == numlines:
                self.trace['tabell'].debug(u"isTabell('%s'): Alla rader korta, undersöker undantag" % (p[:20]))
                
                # generellt undantag: Om en tabells första rad har
                # enbart vänsterkolumn MÅSTE den följas av en
                # spaltindelad rad - annars är det nog bara två korta
                # stycken, ett kort stycke följt av kort rubrik, eller
                # liknande.
                try:
                    p2 = self.reader.peekparagraph(2)
                except IOError:
                    p2 = ''
                if not assumeTable and not self.isTabell(p2,
                                                         assumeTable = True, 
                                                         requireColumns = True):
                    self.trace['tabell'].debug(u"isTabell('%s'): generellt undantag från alla rader korta-regeln" % (p[:20]))
                    return False
                elif numlines == 1:
                    # Om stycket har en enda rad *kan* det vara en kort
                    # rubrik -- kolla om den följs av en paragraf, isåfall
                    # är nog tabellen slut
                    # FIXME: Kolla om inte generella undantaget borde
                    # fånga det här. Testfall
                    # regression-tabell-foljd-av-kort-rubrik.txt och
                    # temporal-paragraf-med-tabell.txt
                    if self.isParagraf(p2):
                        self.trace['tabell'].debug(u"isTabell('%s'): Specialundantag: följs av Paragraf, inte Tabellrad" % (p[:20]))
                        return False
                    # Om stycket är *exakt* detta signalerar det nog
                    # övergången från tabell (kanske i slutet på en
                    # bilaga, som i SekrL) till övergångsbestämmelserna
                    if self.isOvergangsbestammelser():
                        self.trace['tabell'].debug(u"isTabell('%s'): Specialundantag: Övergångsbestämmelser" % (p[:20]))
                        return False
                    if self.isBilaga():
                        self.trace['tabell'].debug(u"isTabell('%s'): Specialundantag: Bilaga" % (p[:20]))
                        return False

                # Detta undantag behöves förmodligen inte när genererella undantaget används
                #elif (numlines == 2 and
                #      self.isNumreradLista() and (
                #    lines[1].startswith(u'Förordning (') or
                #    lines[1].startswith(u'Lag ('))):
                #
                #        self.trace['tabell'].debug(u"isTabell('%s'): Specialundantag: ser ut som nummerpunkt följd av ändringsförfattningshänvisning" % (p[:20]))
                #        return False
                
                # inget av undantagen tillämpliga, huvudregel 1 gäller
                self.trace['tabell'].debug(u"isTabell('%s'): %s rader, alla korta" % (p[:20], numlines))
                return True
                
        # 2. Har mer än ett mellanslag i följd på varje rad (spaltuppdelning)
        matches = [l for l in lines if '  ' in l]
        if len(matches) == numlines:
            self.trace['tabell'].debug("isTabell('%s'): %s rader, alla spaltuppdelade" % (p[:20],numlines))
            return True

        # 3. Är kort ELLER har spaltuppdelning 
        if (assumeTable or numlines > 1) and not requireColumns:
            matches = [l for l in lines if '  ' in l or len(l) < 50]
            if len(matches) == numlines:
                self.trace['tabell'].debug("isTabell('%s'): %s rader, alla korta eller spaltuppdelade" % (p[:20],numlines))
                return True

        self.trace['tabell'].debug("isTabell('%s'): %s rader, inga test matchade" % (p[:20],numlines))
        return False

    def makeTabell(self):
        pcnt = 0
        t = Tabell()
        autostrip = self.reader.autostrip
        self.reader.autostrip = False
        p = self.reader.readparagraph()
        self.trace['tabell'].debug(u"makeTabell: 1st line: '%s'" % p[:30])
        (trs, tabstops) = self.makeTabellrad(p)
        t.extend(trs)
        while (not self.reader.eof()):
            (l,upphor,ikrafttrader) = self.andringsDatum(self.reader.peekline(),match=True)
            if upphor:
                current_upphor = upphor
                self.reader.readline()
                pcnt = 1
            elif ikrafttrader:
                current_ikrafttrader = ikrafttrader
                current_upphor = None
                self.reader.readline()
                pcnt = -pcnt + 1
            elif self.isTabell(assumeTable=True):
                kwargs = {}
                if pcnt > 0:
                    kwargs['upphor'] = current_upphor
                    pcnt += 1
                elif pcnt < 0:
                    kwargs['ikrafttrader'] = current_ikrafttrader
                    pcnt += 1
                elif pcnt == 0:
                    current_ikrafttrader = None
                p = self.reader.readparagraph()
                if p:
                    (trs,tabstops) = self.makeTabellrad(p,tabstops,kwargs=kwargs)
                    t.extend(trs)
            else:
                self.reader.autostrip = autostrip
                return t
                
        self.reader.autostrip = autostrip
        return t

    def makeTabellrad(self,p,tabstops=None,kwargs={}):
        # Algoritmen är anpassad för att hantera tabeller där texten inte
        # alltid är så jämnt ordnat i spalter, som fallet är med
        # SFSR-datat (gissningvis på grund av någon trasig
        # tab-till-space-konvertering nånstans).
        def makeTabellcell(text):
            # Avavstavningsalgoritmen lämnar lite i övrigt att önska
            return Tabellcell([text.replace("- ", "").strip()])
        cols = [u'',u'',u'',u'',u'',u'',u''] # Ingen tabell kommer nånsin ha mer än sju kolumner
        if tabstops:
            statictabstops = True # Använd de tabbstoppositioner vi fick förra raden
        else:
            statictabstops = False # Bygg nya tabbstoppositioner från scratch
            self.trace['tabell'].debug("rebuilding tabstops")
            tabstops = [0,0,0,0,0,0,0]
        lines = p.split(self.reader.linesep)
        numlines = len([x for x in lines if x])
        potentialrows = len([x for x in lines if x and (x[0].isupper() or x[0].isdigit())])
        linecount = 0
        self.trace['tabell'].debug("numlines: %s, potentialrows: %s" % (numlines, potentialrows))
        if (numlines > 1 and numlines == potentialrows):
            self.trace['tabell'].debug(u'makeTabellrad: Detta verkar vara en tabellrad-per-rad')
            singlelinemode = True
        else:
            singlelinemode = False

        rows = []
        emptyleft = False
        for l in lines:
            if l == "":
                continue
            linecount += 1
            charcount = 0
            spacecount = 0
            lasttab = 0
            colcount = 0
            if singlelinemode:
                cols = [u'',u'',u'',u'',u'',u'',u'']
            if l[0] == ' ':
                emptyleft = True
            else:
                if emptyleft:
                    self.trace['tabell'].debug(u'makeTabellrad: skapar ny tabellrad pga snedformatering')
                    rows.append(cols)
                    cols = [u'',u'',u'',u'',u'',u'',u'']
                    emptyleft = False
                    
            for c in l:
                charcount += 1
                if c == u' ':
                    spacecount += 1
                else:
                    if spacecount > 1: # Vi har stött på en ny tabellcell
                                       # - fyll den gamla
                        # Lägg till ett mellanslag istället för den nyrad
                        # vi kapat - överflödiga mellanslag trimmas senare
                        cols[colcount] += u' ' + l[lasttab:charcount-(spacecount+1)]
                        lasttab = charcount - 1

                        # för hantering av tomma vänsterceller
                        if linecount > 1 or statictabstops:
                            if tabstops[colcount+1]+7 < charcount: # tillåt en ojämnhet om max sju tecken

                                self.trace['tabell'].debug(u'colcount is %d, # of tabstops is %d' % (colcount, len(tabstops)))
                                self.trace['tabell'].debug(u'charcount shoud be max %s, is %s - adjusting to next tabstop (%s)' % (tabstops[colcount+1] + 5, charcount,  tabstops[colcount+2]))
                                if tabstops[colcount+2] != 0:
                                    self.trace['tabell'].debug(u'safe to advance colcount')
                                    colcount += 1
                        colcount += 1 
                        tabstops[colcount] = charcount
                        self.trace['tabell'].debug("Tabstops now: %r" % tabstops)
                    spacecount = 0
            cols[colcount] += u' ' + l[lasttab:charcount]
            self.trace['tabell'].debug("Tabstops: %r" % tabstops)
            if singlelinemode:
                self.trace['tabell'].debug(u'makeTabellrad: skapar ny tabellrad')
                rows.append(cols)

        if not singlelinemode:
            rows.append(cols)

        self.trace['tabell'].debug(repr(rows))
        
        res = []
        for r in rows:
            tr = Tabellrad(**kwargs)
            emptyok = True
            for c in r:
                if c or emptyok:
                    tr.append(makeTabellcell(c))
                    if c.strip() != u'':
                        emptyok = False
            res.append(tr)

        return (res, tabstops)


    def isFastbredd(self):
        return False
    
    def makeFastbredd(self):
        return None

    def isNumreradLista(self, p=None):
        return self.idOfNumreradLista(p) != None

    def idOfNumreradLista(self, p=None):
        if not p:
            p = self.reader.peekline()
            self.trace['numlist'].debug("idOfNumreradLista: called directly (%s)" % p[:30])
        else:
            self.trace['numlist'].debug("idOfNumreradLista: called w/ '%s'" % p[:30])
        match = self.re_DottedNumber(p)

        if match != None:
            self.trace['numlist'].debug("idOfNumreradLista: match DottedNumber" )
            return match.group(1).replace(" ", "")
        else:
            match = self.re_NumberRightPara(p)
            if match != None:
                self.trace['numlist'].debug("idOfNumreradLista: match NumberRightPara" )
                return match.group(1).replace(" ", "")

        self.trace['numlist'].debug("idOfNumreradLista: no match")
        return None

    def isStrecksatslista(self):
        p = self.reader.peekline()
        return (p.startswith("- ") or
                p.startswith("--"))

    def isBokstavslista(self):
        return self.idOfBokstavslista() != None

    def idOfBokstavslista(self):
        p = self.reader.peekline()
        match = self.re_Bokstavslista(p)

        if match != None:
            return match.group(1).replace(" ", "")
        return None
        
    def isOvergangsbestammelser(self):
        separators = [u'Övergångsbestämmelser',
                      u'Ikraftträdande- och övergångsbestämmelser',
                      u'Övergångs- och slutbestämmelser',
                      u'Övergångs- och ikraftträdandebestämmelser']
        
        l = self.reader.peekline()
        if l in separators:
            return True
        fuzz = difflib.get_close_matches(l, separators, 1, 0.9)
        if fuzz:
            log.warning(u"%s: Antar att '%s' ska vara '%s'?" % (self.id, l, fuzz[0]))
            return True
        
        return self.reader.peekline() in [u'Övergångsbestämmelser',
                                          u'Ikraftträdande- och övergångsbestämmelser']

    def isOvergangsbestammelse(self):
        return self.re_SimpleSfsId.match(self.reader.peekline())


    def isBilaga(self):
        return (self.reader.peekline() in (u"Bilaga", u"Bilaga 1"))


        
class SFSManager(LegalSource.Manager,FilebasedTester.FilebasedTester):
    __parserClass = SFSParser


    # processes dv/parsed/rdf.nt to get a new xml file suitable for
    # inclusion by sfs.xslt (something we should be able to do using
    # SPARQL, TriX export or maybe XSLT itself, but...)
    def IndexDV(self):
        g = Graph()
        log.info("Start RDF loading")
        start = time()
        rdffile = "%s/dv/parsed/rdf.nt"%self.baseDir
        assert os.path.exists(rdffile), "RDF file %s doesn't exist" % rdffile
        g.load(rdffile,format="nt")
        log.info("RDF loaded (%.3f sec)", time()-start)
        start = time()
        triples = defaultdict(list)
        lagrum  = defaultdict(list)
        cnt = 0
        for triple in g:
            cnt += 1
            if cnt % 100 == 0:
                sys.stdout.write(".")
            (obj, pred, subj) = triple
            triples[obj].append(triple)
            if pred == RINFO['lagrum']:
                lagrum[subj].append(obj)
        sys.stdout.write("\n")

        # Spara ned RDF-datat "för hand" med xml.etree istf rdflib, så
        # att vi kan se till att det serialiserade datat är lätt för
        # en XSLT-transformation att gräva i (varje rättsfalls
        # information dupliceras, en gång för varje lagrum det
        # hänvisas till - detta gör det enkelt att hitta rättsfall
        # utifrån ett visst lagrum).
        
        # create a etree with rdf:RDF as root node (and register
        # namespaces for rdf, dct, possibly rinfo...)
        root_node = PET.Element("rdf:RDF")
        for prefix in Util.ns:
            # PET._namespace_map[Util.ns[prefix]] = prefix
            root_node.set("xmlns:" + prefix, Util.ns[prefix])

        for l in sorted(lagrum, cmp=Util.numcmp):
            # FIXME: Gör sanitychecks så att vi inte får med trasiga
            # lagnummer-URI:er i stil med "1 §", "1949:105" eller
            # "http://rinfo.lagrummet.nu/publ/sfs/9999:999#K1"
            lagrum_node = PET.SubElement(root_node,"rdf:Description")
            lagrum_node.set("rdf:about",l)
            for r in lagrum[l]:
                isref_node = PET.SubElement(lagrum_node, "dct:isReferencedBy")
                rattsfall_node = PET.SubElement(isref_node, "rdf:Description")
                rattsfall_node.set("rdf:about", r)
                for triple in triples[r]:
                    (subj,pred,obj) = triple
                    if pred in (DCT['description'], DCT['identifier']):
                        nodename = pred.replace(Util.ns['dct'],'dct:')
                        triple_node = PET.SubElement(rattsfall_node, nodename)
                        triple_node.text = Util.normalizeSpace(obj)

        log.info("RDF processed (%.3f sec)", time()-start)
        Util.indent_et(root_node)
        tree = PET.ElementTree(root_node)
        outrdffile = "%s/%s/parsed/dv-rdf.xml" % (self.baseDir,__moduledir__) 
        tree.write(outrdffile, encoding="utf-8")
        log.info("New RDF file created")
        

    ####################################################################
    # IMPLEMENTATION OF Manager INTERFACE
    ####################################################################    

    def Parse(self, basefile, verbose=False):
        try:
            if verbose:
                print "Setting verbosity"
                log.setLevel(logging.DEBUG)

            start = time()
            files = {'sfst':self.__listfiles('sfst',basefile),
                     'sfsr':self.__listfiles('sfsr',basefile)}
            # sanity check - if no files are returned
            if (not files['sfst'] and not files['sfsr']):
                raise LegalSource.IdNotFound("No files found for %s" % basefile)
            filename = self._xmlFileName(basefile)

            # three sets of tests before proper parsing begins

            # 1: check to see if this might not be a proper SFS at all
            # (from time to time, other agencies publish their stuff
            # in SFS - this seems to be handled by giving those
            # documents a SFS nummer on the form "N1992:31". Filter
            # these out.
            if '/N' in basefile:
                raise IckeSFS()

            # 2: check to see if the outfile is newer than all ingoing
            # files. If it is (and force is False), don't parse
            force = (self.config[__moduledir__]['parse_force'] == 'True')
            if not force and self._outfile_is_newer(files,filename):
                log.info(u"%s: Överhoppad", basefile)
                return

            # 3: check to see if the Författning has been revoked using
            # plain fast string searching, no fancy HTML parsing and
            # traversing
            t = TextReader(files['sfsr'][0],encoding="iso-8859-1")
            try:
                t.cuepast(u'<i>Författningen är upphävd/skall upphävas: ')
                datestr = t.readto(u'</i></b>')
                if datetime.strptime(datestr, '%Y-%m-%d') < datetime.today():
                    raise UpphavdForfattning()
            except IOError:
                pass

            # OK, all clear, now begin real parsing
            p = SFSParser()
            p.verbose = verbose
            # p.references.verbose = verbose
            if not verbose:
                for k in p.trace.keys():
                    p.trace[k].setLevel(logging.NOTSET)
            parsed = p.Parse(basefile,files)
            Util.ensureDir(filename)
            out = file(filename, "w")
            out.write(parsed)
            out.close()
            # Util.indentXmlFile(filename)
            log.info(u'%s: OK (%.3f sec)', basefile,time()-start)
        except UpphavdForfattning:
            log.info(u'%s: Upphävd', basefile)
            Util.robust_remove(filename)
        except IckeSFS:
            log.info(u'%s: Ingen SFS', basefile)
            Util.robust_remove(filename)
                     
    def ParseAll(self):
        downloaded_dir = os.path.sep.join([self.baseDir, u'sfs', 'downloaded', 'sfst'])
        self._do_for_all(downloaded_dir,'html',self.Parse)

    def Generate(self,basefile):
        infile = self._xmlFileName(basefile)
        outfile = self._htmlFileName(basefile)
        sanitized_sfsnr = basefile.replace(' ','.')
        log.info(u'Transformerar %s > %s' % (infile,outfile))
        Util.mkdir(os.path.dirname(outfile))
        Util.transform("xsl/sfs.xsl",
                       infile,
                       outfile,
                       {'lawid': sanitized_sfsnr,
                        'today':datetime.today().strftime("%Y-%m-%d")},
                       validate=False)

    def GenerateAll(self):
        parsed_dir = os.path.sep.join([self.baseDir, u'sfs', 'parsed'])
        self._do_for_all(parsed_dir,'xht2',self.Generate)

    def ParseGen(self,basefile):
        self.Parse(basefile)
        self.Generate(basefile)

    def ParseGenAll(self):
        self._do_for_all('downloaded/sfst','html',self.ParseGen)
        
    def Download(self,id):
        sd = SFSDownloader(self.config)
        sd._downloadSingle(id)

    def DownloadAll(self):
        sd = SFSDownloader(self.config)
        sd.DownloadAll()

    def DownloadNew(self):
        sd = SFSDownloader(self.config)
        sd.DownloadNew()

    def RelateAll(self):
        super(SFSManager,self).__init__()
        self.IndexDV

        

    ################################################################
    # IMPLEMENTATION OF FilebasedTester interface
    ################################################################
    testparams = {'Parse': {'dir': u'test/SFS',
                            'testext':'.txt',
                            'testencoding':'iso-8859-1',
                            'answerext':'.xml',
                            'answerencoding':'utf-8'},
                  'Serialize': {'dir': u'test/SFS',
                                'testext':'.xml',
                                'testencoding':'utf-8',
                                'answerext':'.xml'},
                  'Render': {'dir': u'test/SFS/Render',
                             'testext':'.xml',
                             'testencoding':'utf-8',
                             'answerext':'.xht2'},
                  }
    def TestParse(self,data,verbose=None,quiet=None):
        # FIXME: Set this from FilebasedTester
        if verbose == None:
            verbose=False
        if quiet == None:
            #pass
            quiet=True
        p = SFSParser()
        p.verbose = verbose
        p.id = '(test)'
        p.lagrum_parser.verbose = verbose
        if quiet:
            log.setLevel(logging.CRITICAL)
            for k in p.trace.keys():
                p.trace[k].setLevel(logging.NOTSET)

        p.reader = TextReader(ustring=data,encoding='iso-8859-1',linesep=TextReader.DOS)
        p.reader.autostrip=True
        b = p.makeForfattning()
        p._construct_ids(b, u'', u'http://rinfo.lagrummet.se/publ/sfs/9999:999')
        return serialize(b)            

    def TestSerialize(self, data):
        # print "Caller globals"
        # print repr(globals().keys())
        # print "Caller locals"
        # print repr(locals().keys())
        return serialize(deserialize(data,globals()))

    def TestRender(self,data):
        meta = Forfattningsinfo()
        #meta[u'Utgivare'] = UnicodeSubject(u'Testutgivare',uri='http://example.org/')
        #meta[u'Utfärdad'] = date(2008,1,1)
        #meta[u'Förarbeten'] = []
        #meta[u'Rubrik'] = u'Lag (2008:1) om adekvata enhetstester' 
        #meta[u'xml:base'] = u'http://example.org/publ/sfs/9999:999' 
        body = deserialize(data,globals())
        registry = Register()
        p = SFSParser()
        p.id = '(test)'
        return unicode(p.generate_xhtml(meta,body,registry,__moduledir__,globals()),'utf-8')

    # Aktuell teststatus:
    # ..........N.................FN..N.F........N..N..N..N...N..N. 50/61
    # Failed tests:
    # test/SFS\Parse\extra-overgangsbestammelse-med-rubriker.txt
    # test/SFS\Parse\regression-rubrik-inte-vanstercell.txt
    # test/SFS\Parse\regression-stycke-inte-rubrik.txt
    # test/SFS\Parse\regression-tabell-tva-korta-vansterceller.txt
    # test/SFS\Parse\regression-tva-tomma-vansterceller.txt
    # test/SFS\Parse\temporal-kapitelrubriker.txt
    # test/SFS\Parse\temporal-rubriker.txt
    # test/SFS\Parse\tricky-lopande-numrering.txt
    # test/SFS\Parse\tricky-okand-aldre-lag.txt
    # test/SFS\Parse\tricky-paragrafupprakning.txt
    # test/SFS\Parse\tricky-tabell-sju-kolumner.txt

    ####################################################################
    # OVERRIDES OF Manager METHODS
    ####################################################################    
        
    def _get_module_dir(self):
        return __moduledir__

    def _file_to_basefile(self,f):
        """Override of LegalSource._file_to_basefile, with special
        handling of archived versions and two-part documents"""
        # this transforms 'foo/bar/baz/HDO/1-01.doc' to 'HDO/1-01'
        if '-' in f:
            return None
        basefile = "/".join(os.path.split(os.path.splitext(os.sep.join(os.path.normpath(f).split(os.sep)[-2:]))[0]))
        if basefile.endswith('_A') or basefile.endswith('_B'): 
            basefile = basefile[:-2] 
        return basefile
    
    def _indexpages_for_predicate(self,predicate,predtriples,subjects):
        if predicate == 'http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#fsNummer':
            log.info("Creating index pages ordered by fsNummer")
            yearintervals = [(1686,1920),
                             (1921,1940),
                             (1941,1960),
                             (1961,1970),
                             (1971,1974),
                             (1974,1977),
                             (1978,1980),
                             (1981,1984),
                             (1985,1987),
                             (1988,1990)]
            for y in range(1991, datetime.today().year+1):
                yearintervals.append((y,y))

            para = ET.Element("p")
            for (startyear,endyear) in yearintervals:
                if startyear == endyear:
                    title = u'Författningar utgivna %s' % startyear
                    outfile = u'%s/%s/generated/index/%s.html' % (self.baseDir,self.moduleDir,startyear)
                    linktext = startyear
                else:
                    title = u'Författningar utgivna mellan %s och %s' % (startyear,endyear)
                    outfile = u'%s/%s/generated/index/%s-%s.html' % (
                        self.baseDir,self.moduleDir,startyear,endyear)
                    linktext = "%s-%s" % (startyear,endyear)

                self._elementtree_to_html(title,
                                          self.__index_by_year(startyear,endyear,predtriples,subjects),
                                          outfile)

        elif predicate == 'http://dublincore.org/documents/dcmi-terms/title':
            log.info("Creating index pages ordered by title")
            letters = [unicode(chr(x)) for x in range(ord('a'),ord('z'))]
            letters.append(u'å')
            letters.append(u'ä')
            letters.append(u'ö')

            for letter in letters:
                outfile = "%s/%s/generated/index/%s.html"%(self.baseDir,self.moduleDir,letter)
                linktext = letter.upper()
                self._elementtree_to_html(u"Författningar som som börjar på '%s'"%letter,
                                          self.__index_by_letter(letter,predtriples),
                                          outfile)

    ################################################################
    # PURELY INTERNAL FUNCTIONS
    ################################################################

    def __index_by_letter(self,letter,titles):
        ulist = ET.Element(self.XHT2NS+"ul")
        for (key,value) in sorted(titles.items()):
            if key and key.lower().startswith(letter):
                item = ET.SubElement(ulist,self.XHT2NS+"li")
                a = ET.SubElement(item,self.XHT2NS+"a")
                a.attrib['href'] = value[0] # shouldn't be more than
                                            # one with this particular
                                            # title
                a.text = key
        return ulist

    def __index_by_year(self,startyear,endyear,fsnummer,subjects):
        ulist = ET.Element(self.XHT2NS+"ul")
        for (key,value) in sorted(fsnummer.items()):
            year = int(key.split(":")[0])
            if startyear <= year <= endyear:
                item = ET.SubElement(ulist,self.XHT2NS+"li")
                a = ET.SubElement(item,self.XHT2NS+"a")
                a.attrib['href'] = value[0] # shouldn't be more than
                                            # one with this particular
                                            # fsnummer
                a.text = subjects[value[0]]['http://dublincore.org/documents/dcmi-terms/title']
        return ulist

    def __listfiles(self,source,basename):
        """Given a SFS id, returns the filenames within source dir that
        corresponds to that id. For laws that are broken up in _A and _B
        parts, returns both files"""
        templ = "%s/sfs/downloaded/%s/%s%%s.html" % (self.baseDir,source,basename)
        return [templ%f for f in ('','_A','_B') if os.path.exists(templ%f)]
        

if __name__ == "__main__":
    import logging.config
    logging.config.fileConfig('etc/log.conf')
    SFSManager.__bases__ += (DispatchMixin,)
    mgr = SFSManager()
    mgr.Dispatch(sys.argv)


