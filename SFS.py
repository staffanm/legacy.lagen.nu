#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Hanterar (konsoliderade) f�rfattningar i SFS fr�n Regeringskansliet
r�ttsdatabaser.
"""
from __future__ import with_statement
# system libraries
from pprint import pprint
from tempfile import mktemp
from time import time,sleep
import codecs
import difflib
import htmlentitydefs
import logging
import os
import re
import sys
import unicodedata
import shutil
from datetime import date, datetime
import cgi
# python 2.5 required
from collections import defaultdict
import xml.etree.cElementTree as ET
import xml.etree.ElementTree as PET

    
# 3rdparty libs
from configobj import ConfigObj
from mechanize import Browser, LinkNotFoundError, urlopen
try: 
    from rdflib.Graph import Graph
except ImportError:
    from rdflib import Graph

from rdflib import Literal, Namespace, URIRef, RDF, RDFS

# my own libraries
import LegalSource
from LegalRef import LegalRef, ParseError, Link, LinkSubject
import LegalURI
import Util
from DispatchMixin import DispatchMixin
from TextReader import TextReader
import FilebasedTester
from DataObjects import UnicodeStructure, CompoundStructure, \
     MapStructure, TemporalStructure, OrdinalStructure, \
     PredicateType, DateStructure, serialize, deserialize


__version__ = (1,6)
__author__ = u"Staffan Malmgren <staffan@tomtebo.org>"
__shortdesc__ = u"F�rfattningar i SFS"
__moduledir__ = "sfs"
log = logging.getLogger(__moduledir__)
if not os.path.sep in __file__:
    __scriptdir__ = os.getcwd()
else:
    __scriptdir__ = os.path.dirname(__file__)



# Objektmodellen f�r en f�rfattning �r uppbyggd av massa byggstenar
# (kapitel, paragrafen, stycken m.m.) d�r de allra flesta �r n�gon
# form av lista. �ven stycken �r listor, dels d� de kan inneh�lla
# lagrumsh�nvisningar i den l�pande texten, som uttrycks som
# Link-objekt mellan de vanliga unicodetextobjekten, dels d� de kan
# inneh�lla en punkt- eller nummerlista.
#
# Alla klasser �rver fr�n antingen CompoundStructure (som �r en list
# med lite extraegenskaper), UnicodeStructure (som �r en unicode med
# lite extraegenskaper) eller MapStructure (som �r ett dict med lite
# extraegenskaper).
#
# De kan �ven �rva fr�n TemporalStructure om det �r ett objekt som kan
# upph�vas eller tr�da ikraft (exv paragrafer och rubriker, men inte
# enskilda stycken) och/eller OrdinalStructure om det �r ett objekt
# som har n�n sorts l�pnummer, dvs kan sorteras p� ett meningsfullt
# s�tt (exv kapitel och paragrafer, men inte rubriker).


class Forfattning(CompoundStructure, TemporalStructure):
    """Grundklass f�r en konsoliderad f�rfattningstext. Metadatan
    (SFS-numret, ansvarigt departement, 'uppdaterat t.o.m.' m.fl. f�lt
    lagras inte h�r, utan i en separat Forfattningsinfo-instans"""
    pass

# Rubrike �r en av de f� byggstenarna som faktiskt inte kan inneh�lla
# n�got annat (det f�rekommer "aldrig" en h�nvisning i en
# rubriktext). Den �rver allts� fr�n UnicodeStructure, inte
# CompoundStructure.


class Rubrik(UnicodeStructure,TemporalStructure):
    """En rubrik av n�got slag - kan vara en huvud- eller underrubrik
    i l�ptexten, en kapitelrubrik, eller n�got annat"""
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

class Tabell(CompoundStructure): pass # Varje tabellrad �r ett objekt

class Tabellrad(CompoundStructure, TemporalStructure): pass # Varje tabellcell �r ett objekt

class Tabellcell(CompoundStructure): pass # ..som kan inneh�lla text och l�nkar

class Avdelning(CompoundStructure, OrdinalStructure):
    fragment_label = "A"
    def __init__(self, *args, **kwargs):
        self.id = kwargs['id'] if 'id' in kwargs else None
        super(Avdelning,self).__init__(*args, **kwargs)

class UpphavtKapitel(UnicodeStructure, OrdinalStructure):
    """Ett UpphavtKapitel �r annorlunda fr�n ett upph�vt Kapitel p� s�
    s�tt att inget av den egentliga lagtexten finns kvar, bara en
    platsh�llare"""
    pass

class Kapitel(CompoundStructure, OrdinalStructure):
    fragment_label = "K"
    def __init__(self, *args, **kwargs):
        self.id = kwargs['id'] if 'id' in kwargs else None
        super(Kapitel,self).__init__(*args, **kwargs)

class UpphavdParagraf(UnicodeStructure, OrdinalStructure):
    pass

# en paragraf har inget "eget" v�rde, bara ett nummer och ett eller flera stycken
class Paragraf(CompoundStructure, OrdinalStructure): 
    fragment_label = "P"
    def __init__(self, *args, **kwargs):
        self.id = kwargs['id'] if 'id' in kwargs else None
        super(Paragraf,self).__init__(*args,**kwargs)

# kan inneh�lla n�stlade numrerade listor
class Listelement(CompoundStructure, OrdinalStructure): 
    fragment_label = "N"
    def __init__(self, *args, **kwargs):
        self.id = kwargs['id'] if 'id' in kwargs else None
        super(Listelement,self).__init__(*args,**kwargs)


class Overgangsbestammelser(CompoundStructure):
    def __init__(self, *args, **kwargs):
        self.rubrik = kwargs['rubrik'] if 'rubrik' in kwargs else u'�verg�ngsbest�mmelser'
        super(Overgangsbestammelser,self).__init__(*args,**kwargs)
    
class Overgangsbestammelse(CompoundStructure, OrdinalStructure):
    fragment_label = "L"
    def __init__(self, *args, **kwargs):
        self.id = kwargs['id'] if 'id' in kwargs else None
        super(Overgangsbestammelse,self).__init__(*args,**kwargs)

class Bilaga(CompoundStructure):
    fragment_label = "B"
    def __init__(self, *args, **kwargs):
        self.id = kwargs['id'] if 'id' in kwargs else None
        super(Bilaga,self).__init__(*args,**kwargs)

class Register(CompoundStructure):
    """Inneh�ller lite metadata om en grundf�rfattning och dess
    efterf�ljande �ndringsf�rfattningar"""
    def __init__(self, *args, **kwargs):
        self.rubrik = kwargs['rubrik'] if 'rubrik' in kwargs else None
        super(Register,self).__init__(*args, **kwargs)

class Registerpost(MapStructure):
    """Metadata f�r en viss (�ndrings)f�rfattning: SFS-nummer,
    omfattning, f�rarbeten m.m . Vanligt f�rekommande nycklar och dess v�rden:

    * 'SFS-nummer': en str�ng, exv u'1970:488'
    * 'Ansvarig myndighet': en str�ng, exv u'Justitiedepartementet L3'
    * 'Rubrik': en str�ng, exv u'Lag (1978:488) om �ndring i lagen (1960:729) om upphovsr�tt till litter�ra och konstn�rliga verk'
    * 'Ikraft': en date, exv datetime.date(1996, 1, 1)
    * '�verg�ngsbest�mmelse': True eller False
    * 'Omfattning': en lista av nodeliknande saker i stil med
      [u'�ndr.',
       LinkSubject('23',uri='http://rinfo.lagrummet.se/publ/sfs/1960:729#P23', pred='rinfo:andrar'),
       u', ',
       LinkSubject('24',uri='http://rinfo.lagrummet.se/publ/sfs/1960:729#P24', pred='rinfo:andrar'),
       u' ��; ny ',
       LinkSubject('24 a',uri='http://rinfo.lagrummet.se/publ/sfs/1960:729#P24a' pred='rinfo:inforsI'),
       ' �']
    * 'F�rarbeten': en lista av nodeliknande saker i stil med
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
        super(SFSDownloader,self).__init__(config) # sets config, logging, initializes browser
                                     
    def DownloadAll(self):
        # Split search into two (or more) - the result list fails after 440 result pages
        for start, end in ((1600,2008),(2009,datetime.today().year)):
            log.info(u'Downloading %s to %s' % (start,end))

            self.browser.open("http://rkrattsbaser.gov.se/cgi-bin/thw?${HTML}=sfsr_lst&${OOHTML}=sfsr_dok&${SNHTML}=sfsr_err&${MAXPAGE}=26&${BASE}=SFSR&${FORD}=FIND&\xC5R=FR\xC5N+%s&\xC5R=TILL+%s" % (start,end))

            pagecnt = 1
            done = False
            while not done:
                log.info(u'Resultatsida nr #%s' % pagecnt)
                for l in (self.browser.links(text_regex=r'\d+:\d+')):
                    if not l.text.startswith("N"): # Icke-SFS-f�rfattningar
                                                   # som �nd� finns i
                                                   # databasen
                        self._downloadSingle(l.text)
                    # self.browser.back()
                try:
                    self.browser.find_link(text='Fler poster')
                    self.browser.follow_link(text='Fler poster')
                    pagecnt += 1
                except LinkNotFoundError:
                    log.info(u'Ingen n�sta sida-l�nk, vi �r nog klara')
                    done = True
        self._setLastSFSnr()

    def _get_module_dir(self):
        return __moduledir__

    def _setLastSFSnr(self,last_sfsnr=None):
        maxyear = datetime.today().year+1
        if not last_sfsnr:
            log.info(u'Letar efter senaste SFS-nr i  %s/sfst"' % self.download_dir)
            last_sfsnr = "1600:1"
            for f in Util.listDirs(u"%s/sfst" % self.download_dir, ".html"):
                if "RFS" in f or "checksum" in f or "-" in f:
                    continue

                tmp = self._findUppdateradTOM(FilenameToSFSnr(f[len(self.download_dir)+6:-5].replace("\\", "/")), f)
                tmpyear = int(tmp.split(":")[0])
                if tmpyear > maxyear:
                    log.warning('%s is probably not correct, ignoring (%s)' % (tmp,f))
                    continue
                if Util.numcmp(tmp, last_sfsnr) > 0:
                    log.info(u'%s > %s (%s)' % (tmp, last_sfsnr, f))
                    last_sfsnr = tmp
        self.config[__moduledir__]['next_sfsnr'] = last_sfsnr 
        self.config.write()

    def DownloadNew(self):
        if not 'next_sfsnr' in self.config[__moduledir__]:
            self._setLastSFSnr()
        (year,nr) = [int(x) for x in self.config[__moduledir__]['next_sfsnr'].split(":")]
        done = False
        real_last_sfs_nr = False
        while not done:
            wanted_sfs_nr = '%s:%s' % (year,nr)
            log.info(u'S�ker efter SFS nr %s' % wanted_sfs_nr)
            base_sfsnr_list = self._checkForSFS(year,nr)
            if base_sfsnr_list:
                self.download_log.info("%s:%s [%s]" % (year,nr,", ".join(base_sfsnr_list)))
                for base_sfsnr in base_sfsnr_list: # usually only a 1-elem list
                    uppdaterad_tom = self._downloadSingle(base_sfsnr)
                    if base_sfsnr_list[0] == wanted_sfs_nr:
                        # initial grundf�rfattning - varken
                        # "Uppdaterad T.O.M. eller "Upph�vd av" ska
                        # vara satt
                        pass
                    elif Util.numcmp(uppdaterad_tom, wanted_sfs_nr) < 0:
                        log.warning(u"    Texten uppdaterad t.o.m. %s, inte %s" % (uppdaterad_tom, wanted_sfs_nr))
                        if not real_last_sfs_nr:
                            real_last_sfs_nr = wanted_sfs_nr
                nr = nr + 1
            else:
                log.info('tjuvkikar efter SFS nr %s:%s' % (year,nr+1))
                base_sfsnr_list = self._checkForSFS(year,nr+1)
                if base_sfsnr_list:
                    if not real_last_sfs_nr:
                        real_last_sfs_nr = wanted_sfs_nr
                    nr = nr + 1 # actual downloading next loop
                elif datetime.today().year > year:
                    log.info(u'    �r det dags att byta �r?')
                    base_sfsnr_list = self._checkForSFS(datetime.today().year, 1)
                    if base_sfsnr_list:
                        year = datetime.today().year
                        nr = 1 # actual downloading next loop
                    else:
                        log.info(u'    Vi �r klara')
                        done = True
                else:
                    log.info(u'    Vi �r klara')
                    done = True
        if real_last_sfs_nr:
            self._setLastSFSnr(real_last_sfs_nr)
        else:
            self._setLastSFSnr("%s:%s" % (year,nr))
                
    def _checkForSFS(self,year,nr):
        """Givet ett SFS-nummer, returnera en lista med alla
        SFS-numret f�r dess grundf�rfattningar. Normalt sett har en
        �ndringsf�rfattning bara en grundf�rfattning, men f�r vissa
        (exv 2008:605) finns flera. Om SFS-numret inte finns alls,
        returnera en tom lista."""
        # Titta f�rst efter grundf�rfattning
        log.info(u'    Letar efter grundf�rfattning')
        grundforf = []
        url = "http://rkrattsbaser.gov.se/cgi-bin/thw?${HTML}=sfsr_lst&${OOHTML}=sfsr_dok&${SNHTML}=sfsr_err&${MAXPAGE}=26&${BASE}=SFSR&${FORD}=FIND&${FREETEXT}=&BET=%s:%s&\xC4BET=&ORG=" % (year,nr)
        # FIXME: consider using mechanize
        tmpfile = mktemp()
        self.browser.retrieve(url,tmpfile)
        t = TextReader(tmpfile,encoding="iso-8859-1")
        try:
            t.cue(u"<p>S�kningen gav ingen tr�ff!</p>")
        except IOError: # hurra!
            grundforf.append(u"%s:%s" % (year,nr))
            return grundforf

        # Sen efter �ndringsf�rfattning
        log.info(u'    Letar efter �ndringsf�rfattning')
        url = "http://rkrattsbaser.gov.se/cgi-bin/thw?${HTML}=sfsr_lst&${OOHTML}=sfsr_dok&${SNHTML}=sfsr_err&${MAXPAGE}=26&${BASE}=SFSR&${FORD}=FIND&${FREETEXT}=&BET=&\xC4BET=%s:%s&ORG=" % (year,nr)
        self.browser.retrieve(url, tmpfile)
        # maybe this is better done through mechanize?
        t = TextReader(tmpfile,encoding="iso-8859-1")
        try:
            t.cue(u"<p>S�kningen gav ingen tr�ff!</p>")
            log.info(u'    Hittade ingen �ndringsf�rfattning')
            return grundforf
        except IOError:
            t.seek(0)
            try:
                t.cuepast(u'<input type="hidden" name="BET" value="')
                grundforf.append(t.readto("$"))
                log.debug(u'    Hittade �ndringsf�rfattning (till %s)' % grundforf[-1])
                return grundforf
            except IOError:
                t.seek(0)
                page = t.read(sys.maxint)
                for m in re.finditer('>(\d+:\d+)</a>',page):
                    grundforf.append(m.group(1))
                    log.debug(u'    Hittade �ndringsf�rfattning (till %s)' % grundforf[-1])
                return grundforf

    def _downloadSingle(self, sfsnr):
        """Laddar ner senaste konsoliderade versionen av
        grundf�rfattningen med angivet SFS-nr. Om en tidigare version
        finns p� disk, arkiveras den. Returnerar det SFS-nummer till
        vilket f�rfattningen uppdaterats."""
        sfsnr = sfsnr.replace("/", ":")
        log.info(u'    Laddar ner %s' % sfsnr)
        # enc_sfsnr = sfsnr.replace(" ", "+")
        # Div specialhack f�r knepiga f�rfattningar
        if sfsnr == "1723:1016+1": parts = ["1723:1016"]
        # elif sfsnr == "1942:740": parts = ["1942:740 A", "1942:740 B"]
        else: parts = [sfsnr]

        upphavd_genom = uppdaterad_tom = old_uppdaterad_tom = None
        for part in parts:
            sfst_url = "http://rkrattsbaser.gov.se/cgi-bin/thw?${OOHTML}=sfst_dok&${HTML}=sfst_lst&${SNHTML}=sfst_err&${BASE}=SFST&${TRIPSHOW}=format=THW&BET=%s" % part.replace(" ","+")
            sfst_file = "%s/sfst/%s.html" % (self.download_dir, SFSnrToFilename(part))
            sfst_tempfile = mktemp()
            self.browser.retrieve(sfst_url, sfst_tempfile)
            if os.path.exists(sfst_file):
                old_checksum = self._checksum(sfst_file)
                new_checksum = self._checksum(sfst_tempfile)
                upphavd_genom = self._findUpphavtsGenom(sfst_tempfile)
                uppdaterad_tom = self._findUppdateradTOM(sfsnr, sfst_tempfile)
                if (old_checksum != new_checksum):
                    old_uppdaterad_tom = self._findUppdateradTOM(sfsnr, sfst_file)
                    uppdaterad_tom = self._findUppdateradTOM(sfsnr, sfst_tempfile)
                    if uppdaterad_tom != old_uppdaterad_tom:
                        log.info(u'        %s har �ndrats (%s -> %s)' % (sfsnr,old_uppdaterad_tom,uppdaterad_tom))
                        self._archive(sfst_file, sfsnr, old_uppdaterad_tom)
                    else:
                        log.info(u'        %s har �ndrats (gammal checksum %s)' % (sfsnr,old_checksum))
                        self._archive(sfst_file, sfsnr, old_uppdaterad_tom,old_checksum)

                    # replace the current file, regardless of wheter
                    # we've updated it or not
                    Util.robustRename(sfst_tempfile, sfst_file)
                elif upphavd_genom:
                    log.info(u'        %s har upph�vts' % (sfsnr))
                    
                else:
                    log.debug(u'        %s har inte �ndrats (gammal checksum %s)' % (sfsnr,old_checksum))
            else:
                Util.robustRename(sfst_tempfile, sfst_file)

        sfsr_url = "http://rkrattsbaser.gov.se/cgi-bin/thw?${OOHTML}=sfsr_dok&${HTML}=sfst_lst&${SNHTML}=sfsr_err&${BASE}=SFSR&${TRIPSHOW}=format=THW&BET=%s" % sfsnr.replace(" ","+")
        sfsr_file = "%s/sfsr/%s.html" % (self.download_dir, SFSnrToFilename(sfsnr))
        if (old_uppdaterad_tom and
            old_uppdaterad_tom != uppdaterad_tom):
            self._archive(sfsr_file, sfsnr, old_uppdaterad_tom)

        Util.ensureDir(sfsr_file)
        sfsr_tempfile = mktemp()
        self.browser.retrieve(sfsr_url, sfsr_tempfile)
        Util.replace_if_different(sfsr_tempfile,sfsr_file)

        if upphavd_genom:
            log.info(u'        %s �r upph�vd genom %s' % (sfsnr, upphavd_genom))
            return upphavd_genom
        elif uppdaterad_tom:
            log.info(u'        %s �r uppdaterad tom %s' % (sfsnr, uppdaterad_tom))
            return uppdaterad_tom
        else:
            log.info(u'        %s �r varken uppdaterad eller upph�vd' % (sfsnr))
            return None
        
            
    def _archive(self, filename, sfsnr, uppdaterad_tom, checksum=None):
        """Arkivera undan filen filename, som ska vara en
        grundf�rfattning med angivet sfsnr och vara uppdaterad
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
            return sfsnr # the base SFS nr


    def _findUpphavtsGenom(self, filename):
        reader = TextReader(filename,encoding='iso-8859-1')
        try:
            reader.cue("upph&auml;vts genom:<b> SFS")
            l = reader.readline()
            m = re.search('(\d+:\s?\d+)',l)
            if m:
                return m.group(1)
            else:
                return None
        except IOError:
            return None

    def _checksum(self,filename):
        """MD5-checksumman f�r den angivna filen"""
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
    """Sl�ngs n�r en upph�vd f�rfattning parseas"""
    pass

class IckeSFS(Exception):
    """Sl�ngs n�r en f�rfattning som inte �r en egentlig SFS-f�rfattning parseas"""
    pass

DCT = Namespace(Util.ns['dct'])
XSD = Namespace(Util.ns['xsd'])
RINFO = Namespace(Util.ns['rinfo'])
RINFOEX = Namespace(Util.ns['rinfoex'])
class SFSParser(LegalSource.Parser):
    re_SimpleSfsId     = re.compile(r'(\d{4}:\d+)\s*$')
    re_SearchSfsId     = re.compile(r'\((\d{4}:\d+)\)').search
    re_ChangeNote      = re.compile(ur'(Lag|F�rordning) \(\d{4}:\d+\)\.?$')
    re_ChapterId       = re.compile(r'^(\d+( \w|)) [Kk]ap.').match
    re_DivisionId      = re.compile(r'^AVD. ([IVX]*)').match
    re_SectionId       = re.compile(r'^(\d+ ?\w?) �[ \.]') # used for both match+sub
    re_SectionIdOld    = re.compile(r'^� (\d+ ?\w?).')     # as used in eg 1810:0926
    re_DottedNumber    = re.compile(r'^(\d+ ?\w?)\. ')
    re_Bullet          = re.compile(ur'^(\-\-?|\x96) ')
    re_NumberRightPara = re.compile(r'^(\d+)\) ').match
    re_Bokstavslista   = re.compile(r'^(\w)\) ')
    re_ElementId       = re.compile(r'^(\d+) mom\.')        # used for both match+sub
    re_ChapterRevoked  = re.compile(r'^(\d+( \w|)) [Kk]ap. (upph�vd|har upph�vts) genom (f�rordning|lag) \([\d\:\. s]+\)\.?$').match
    re_SectionRevoked  = re.compile(r'^(\d+ ?\w?) �[ \.]([Hh]ar upph�vts|[Nn]y beteckning (\d+ ?\w?) �) genom ([Ff]�rordning|[Ll]ag) \([\d\:\. s]+\)\.$').match
    re_RevokeDate       = re.compile(ur'/(?:Rubriken u|U)pph�r att g�lla U:(\d+)-(\d+)-(\d+)/')
    re_RevokeAuthorization = re.compile(ur'/Upph�r att g�lla U:(den dag regeringen best�mmer)/')
    re_EntryIntoForceDate = re.compile(ur'/(?:Rubriken t|T)r�der i kraft I:(\d+)-(\d+)-(\d+)/')
    re_EntryIntoForceAuthorization = re.compile(ur'/Tr�der i kraft I:(den dag regeringen best�mmer)/')
    re_dehyphenate = re.compile(r'\b- (?!(och|eller))',re.UNICODE).sub
    re_definitions = re.compile(r'^I (lagen|f�rordningen|balken|denna lag|denna f�rordning|denna balk|denna paragraf|detta kapitel) (avses med|betyder|anv�nds f�ljande)').match
    re_brottsdef     = re.compile(ur'\b(d�ms|d�mes)(?: han)?(?:,[\w� ]+,)? f�r ([\w ]{3,50}) till (b�ter|f�ngelse)', re.UNICODE).search
    re_brottsdef_alt = re.compile(ur'[Ff]�r ([\w ]{3,50}) (d�ms|d�mas) till (b�ter|f�ngelse)', re.UNICODE).search
    re_parantesdef   = re.compile(ur'\(([\w ]{3,50})\)\.', re.UNICODE).search
    re_loptextdef    = re.compile(ur'^Med ([\w ]{3,50}) (?:avses|f�rst�s) i denna (f�rordning|lag|balk)', re.UNICODE).search
    
    # use this custom matcher to ensure any strings you intend to convert
    # are legal roman numerals (simpler than having from_roman throwing
    # an exception)
    re_roman_numeral_matcher = re.compile('^M?M?M?(CM|CD|D?C?C?C?)(XC|XL|L?X?X?X?)(IX|IV|V?I?I?I?)$').match
    
    swedish_ordinal_list = (u'f�rsta', u'andra', u'tredje', u'fj�rde', 
                            u'femte', u'sj�tte', u'sjunde', u'�ttonde', 
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

    keep_expired = False

    def __init__(self):
        self.trace = {'rubrik': logging.getLogger('sfs.trace.rubrik'),
                      'paragraf': logging.getLogger('sfs.trace.paragraf'),
                      'numlist': logging.getLogger('sfs.trace.numlist'),
                      'tabell': logging.getLogger('sfs.trace.tabell')}

        self.trace['rubrik'].debug(u'Rubriktracern �r ig�ng')
        self.trace['paragraf'].debug(u'Paragraftracern �r ig�ng')
        self.trace['numlist'].debug(u'Numlisttracern �r ig�ng')
        self.trace['tabell'].debug(u'Tabelltracern �r ig�ng')
                      
        self.lagrum_parser = LegalRef(LegalRef.LAGRUM,
                                      LegalRef.EGLAGSTIFTNING)
        self.forarbete_parser = LegalRef(LegalRef.FORARBETEN)

        self.current_section = u'0'
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
            tmpfile = mktemp()
            f = codecs.open(tmpfile, "w",'iso-8859-1')
            f.write(plaintext+"\r\n")
            f.close()

            Util.replace_if_different(tmpfile,plaintextfile)
            patchfile = 'patches/sfs/%s.patch' % basefile
            descfile = 'patches/sfs/%s.desc' % basefile
            patchdesc = None
            if os.path.exists(patchfile):
                # Prep the files to have unix lineendings
                plaintextfile_u = mktemp()
                shutil.copy2(plaintextfile,plaintextfile_u)
                patchfile_u = mktemp()
                shutil.copy2(patchfile,patchfile_u)
                cmd = 'dos2unix %s' % plaintextfile_u
                Util.runcmd(cmd)
                cmd = 'dos2unix %s' % patchfile_u
                Util.runcmd(cmd)
                
                patchedfile = mktemp()
                # we don't want to sweep the fact that we're patching under the carpet
                log.warning(u'%s: Applying patch %s' % (basefile, patchfile))
                cmd = 'patch -s %s %s -o %s' % (plaintextfile_u, patchfile_u, patchedfile)
                log.debug(u'%s: running %s' % (basefile,cmd))
                (ret, stdout, stderr) = Util.runcmd(cmd)
                if ret == 0: # successful patch
                    # patch from cygwin always seem to produce unix lineendings
                    assert os.path.exists(descfile), "No description of patch %s found" % patchfile
                    patchdesc = codecs.open(descfile,encoding='utf-8').read().strip()
                    cmd = 'unix2dos %s' % patchedfile
                    log.debug(u'%s: running %s' % (basefile,cmd))
                    (ret, stdout, stderr) = Util.runcmd(cmd)
                    if ret == 0: 
                        plaintextfile = patchedfile
                    else:
                        log.warning(u"%s: Failed lineending conversion: %s" % (basefile,stderr))
                else:
                    log.warning(u"%s: Could not apply patch %s: %s" % (basefile, patchfile, stdout.strip()))
            (meta, body) = self._parseSFST(plaintextfile, registry, patchdesc)
        except IOError:
            log.warning("%s: Fulltext saknas" % self.id)
            # extractSFST misslyckades, d� det fanns n�gon post i
            # SFST-databasen (det h�nder alltf�r ofta att bara
            # SFSR-databasen �r uppdaterad). Fejka ihop en meta
            # (Forfattningsinfo) och en body (Forfattning) utifr�n
            # SFSR-datat

            meta = Forfattningsinfo()
            meta['Rubrik'] = registry.rubrik
            meta[u'Utgivare'] = LinkSubject(u'Regeringskansliet',
                                            uri=self.find_authority_rec("Regeringskansliet"),
                                            predicate=self.labels[u'Utgivare'])
            # dateval = "1970-01-01" 
            # meta[u'Utf�rdad'] = DateSubject(datetime.strptime(dateval, '%Y-%m-%d'),
            #                                 predicate=self.labels[u'Utf�rdad'])
            fldmap = {u'SFS-nummer' :u'SFS nr', 
                      u'Ansvarig myndighet':u'Departement/ myndighet'}
            for k,v in registry[0].items():
                if k in fldmap:
                    meta[fldmap[k]] = v
            docuri = self.lagrum_parser.parse(meta[u'SFS nr'])[0].uri
            meta[u'xml:base'] = docuri

            body = Forfattning()

            kwargs = {'id':u'S1'}
            s = Stycke([u'(Lagtext saknas)'], **kwargs)
            body.append(s)
            
        # L�gg till information om konsolideringsunderlag och
        # f�rarbeten fr�n SFSR-datat
        meta[u'Konsolideringsunderlag'] = []
        meta[u'F�rarbeten'] = []
        for rp in registry:
            uri = self.lagrum_parser.parse(rp['SFS-nummer'])[0].uri
            
            meta[u'Konsolideringsunderlag'].append(uri)
            if u'F�rarbeten' in rp:
                for node in rp[u'F�rarbeten']:
                    if isinstance(node,Link):
                        meta[u'F�rarbeten'].append(node.uri)

        # Plocka in lite extra metadata
        meta[u'Senast h�mtad'] = DateSubject(datetime.fromtimestamp(timestamp),
                                             predicate="rinfoex:senastHamtad")

        # hitta eventuella etablerade f�rkortningar
        g = Graph()
        if sys.platform == "win32":
            g.load("file:///"+__scriptdir__+"/etc/sfs-extra.n3", format="n3")
        else:
            g.load(__scriptdir__+"/etc/sfs-extra.n3", format="n3")
            
        for obj in g.objects(URIRef(meta[u'xml:base']), DCT['alternate']):
            meta[u'F�rkortning'] = unicode(obj)

        # Plocka ut �verg�ngsbest�mmelserna och stoppa in varje
        # �verg�ngsbest�mmelse p� r�tt plats i registerdatat.
        obs = None
        for p in body:
            if isinstance(p, Overgangsbestammelser):
                obs = p
                break
        if obs:
            for ob in obs:
                found = False
                # Det skulle vara vackrare om Register-objektet hade
                # nycklar eller index eller n�got, s� vi kunde slippa
                # att hitta r�tt registerpost genom nedanst�ende
                # iteration:
                for rp in registry:
                    if rp[u'SFS-nummer'] == ob.sfsnr:
                        if u'�verg�ngsbest�mmelse' in rp and rp[u'�verg�ngsbest�mmelse'] != None:
                            log.warning(u'%s: Det finns flera �verg�ngsbest�mmelse-objekt f�r SFS-nummer [%s] - endast det f�rsta beh�lls' % (self.id, ob.sfsnr))
                        else:
                            rp[u'�verg�ngsbest�mmelse'] = ob
                        found = True
                        break
                if not found:
                    log.warning(u'%s: �verg�ngsbest�mmelse f�r [%s] saknar motsvarande registerpost' % (self.id, ob.sfsnr))
                    kwargs = {'id':u'L'+ob.sfsnr,
                              'uri':u'http://rinfo.lagrummet.se/publ/sfs/'+ob.sfsnr}
                    rp = Registerpost(**kwargs)
                    rp[u'SFS-nummer'] = ob.sfsnr
                    rp[u'�verg�ngsbest�mmelse'] = ob
                    
        xhtml = self.generate_xhtml(meta,body,registry,__moduledir__,globals())
        return xhtml

    # metadataf�lt (kan f�rekomma i b�de SFST-header och SFSR-datat)
    # som bara har ett enda v�rde
    labels = {u'SFS-nummer':             RINFO['fsNummer'],
              u'SFS nr':                 RINFO['fsNummer'],
              u'Ansvarig myndighet':     DCT['creator'],
              u'Departement/ myndighet': DCT['creator'],
              u'Utgivare':               DCT['publisher'],
              u'Rubrik':                 DCT['title'],
              u'Utf�rdad':               RINFO['utfardandedatum'],
              u'Ikraft':                 RINFO['ikrafttradandedatum'],
              u'Observera':              RDFS.comment, # FIXME: hitta b�ttre predikat
              u'�vrigt':                 RDFS.comment, # FIXME: hitta b�ttre predikat
              u'Tidsbegr�nsad':          RINFOEX['tidsbegransad'],
              u'Omtryck':                RINFOEX['omtryck'], # subtype av RINFO['fsNummer']
              u'�ndring inf�rd':         RINFO['konsolideringsunderlag'],
              u'F�rfattningen har upph�vts genom':
                                         RINFOEX['upphavdAv'], # ska vara owl:inverseOf
                                                               # rinfo:upphaver
              u'Upph�vd':                RINFOEX['upphavandedatum']
              }

    # metadataf�lt som kan ha flera v�rden (kommer representeras som
    # en lista av unicodeobjekt och LinkSubject-objekt)
    multilabels = {u'F�rarbeten':        RINFO['forarbete'],
                   u'CELEX-nr':          RINFO['forarbete'],
                   u'Omfattning':        RINFO['andrar'], # ocks� RINFO['ersatter'], RINFO['upphaver'], RINFO['inforsI']
                   }

              
    def _parseSFSR(self,files):
        """Parsear ut det SFSR-registret som inneh�ller alla �ndringar
        i lagtexten fr�n HTML-filer"""
        all_attribs = []
        r = Register()
        for f in files:
            soup = Util.loadSoup(f)
            r.rubrik = Util.elementText(soup.body('table')[2]('tr')[1]('td')[0])
            changes = soup.body('table')[3:-2]
            for table in changes:
                kwargs = {'id': 'undefined',
                          'uri': u'http://rinfo.lagrummet.se/publ/sfs/undefined'}
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
                            # FIXME: Eftersom det h�r sen g�r in i ett
                            # id-f�lt, id-v�rden m�ste vara NCNames,
                            # och NCNames inte f�r inneh�lla kolon
                            # m�ste vi hitta p� n�gon annan
                            # delimiterare, typ bindestreck eller punkt
                            # http://www.w3.org/TR/REC-xml-names/#NT-NCName
                            # http://www.w3.org/TR/REC-xml/#NT-Name
                            #
                            # (b�rjar med 'L' eftersom NCNames m�ste
                            # b�rja med ett Letter)
                            p.id = u'L' + val
                            # p.uri = u'http://rinfo.lagrummet.se/publ/sfs/' + val
                            firstnode = self.lagrum_parser.parse(val)[0]
                            if hasattr(firstnode,'uri'):
                                p.uri = firstnode.uri
                            else:
                                log.warning(u'Kunde inte tolka [%s] som ett SFS-nummer' % val)
                            
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
                            if not self.keep_expired:
                                if u'F�rfattningen �r upph�vd/skall upph�vas: ' in val:
                                    if datetime.strptime(val[41:51], '%Y-%m-%d') < datetime.today():
                                        raise UpphavdForfattning()
                            p[key] = UnicodeSubject(val,predicate=self.labels[key])
                        elif key == u'Ikraft':
                            p[key] = DateSubject(datetime.strptime(val[:10], '%Y-%m-%d'), predicate=self.labels[key])
                            #if val.find(u'\xf6verg.best.') != -1):
                            #    p[u'Har �verg�ngsbest�mmelse'] = UnicodeSubject(val,predicate
                        elif key == u'Omfattning':
                            p[key] = []
                            for changecat in val.split(u'; '):
                                if (changecat.startswith(u'�ndr.') or
                                    changecat.startswith(u'�ndr ') or
                                    changecat.startswith(u'�ndring ')):
                                    pred = RINFO['ersatter']
                                elif (changecat.startswith(u'upph.') or
                                      changecat.startswith(u'utg�r')):
                                    pred = RINFO['upphaver']
                                elif (changecat.startswith(u'ny') or
                                      changecat.startswith(u'ikrafttr.') or
                                      changecat.startswith(u'ikrafftr.') or
                                      changecat.startswith(u'ikraftr.') or
                                      changecat.startswith(u'ikrafttr�d.') or
                                      changecat.startswith(u'till�gg')):
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
                                    log.warning(u"%s: Ok�nd omfattningstyp  ['%s']" % (self.id, changecat))
                                    pred = None
                                # print self.lagrum_parser.parse(changecat,docuri,pred)
                                p[key].extend(self.lagrum_parser.parse(changecat,docuri,pred))
                                p[key].append(u';')
                            p[key] = p[key][:-1] # chop of trailing ';'
                        elif key == u'F\xf6rarbeten':
                            p[key] = self.forarbete_parser.parse(val,docuri,RINFO['forarbete'])
                        elif key == u'CELEX-nr':
                            p[key] = self.forarbete_parser.parse(val,docuri,RINFO['forarbete'])
                        elif key == u'Tidsbegr�nsad':
                            p[key] = DateSubject(datetime.strptime(val[:10], '%Y-%m-%d'), predicate=self.labels[key])
                            if p[key] < datetime.today():
                                if not self.keep_expired:
                                    raise UpphavdForfattning()
                        else:
                            log.warning(u'%s: Obekant nyckel [\'%s\']' % self.id, key)
                if p:
                    r.append(p)
                # else:
                #     print "discarding empty post"
        return r


    def _extractSFST(self, files = [], keepHead=True):
        """Plockar fram plaintextversionen av den konsoliderade
        lagtexten fr�n (idag) nedladdade HTML-filer"""
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

    def _term_to_subject(self, term):
        capitalized = term[0].upper() + term[1:]
        return u'http://lagen.nu/concept/%s' % capitalized.replace(' ','_')

    # Post-processar dokumenttr�det rekursivt och g�r tre saker:
    # 
    # Hittar begreppsdefinitioner i l�ptexten
    #
    # Hittar adresserbara enheter (delresurser som ska ha unika URI:s,
    # dvs kapitel, paragrafer, stycken, punkter) och konstruerar id's
    # f�r dem, exv K1P2S3N4 f�r 1 kap. 2 � 3 st. 4 p
    #
    # Hittar lagrumsh�nvisningar i l�ptexten
    def _construct_ids(self, element, prefix, baseuri, skip_fragments=[], find_definitions = False):
        find_definitions_recursive = find_definitions
        counters = defaultdict(int)
        if isinstance(element, CompoundStructure):
            # Hitta begreppsdefinitioner
            if isinstance(element, Paragraf):
                # kolla om f�rsta stycket inneh�ller en text som
                # antyder att definitioner f�ljer
                # log.debug("Testing %r against some regexes" % element[0][0])
                if self.re_definitions(element[0][0]):
                    find_definitions = "normal"
                if (self.re_brottsdef(element[0][0]) or
                    self.re_brottsdef_alt(element[0][0])):
                    find_definitions = "brottsrubricering"
                if self.re_parantesdef(element[0][0]):
                    find_definitions = "parantes"
                if self.re_loptextdef(element[0][0]):
                    find_definitions = "loptext"

                find_definitions_recursive = find_definitions

            # Hitta lagrumsh�nvisningar + definitioner
            if (isinstance(element, Stycke)
                or isinstance(element, Listelement)
                or isinstance(element, Tabellcell)):
                nodes = []
                term = None

                # log.debug("handling text %s, find_definitions %s" % (element[0],find_definitions))
                if find_definitions:
                    elementtext = element[0]
                    termdelimiter = ":"

                    if isinstance(element, Tabellcell):
                        if elementtext != "Beteckning":
                            term = elementtext
                            log.debug(u'"%s" �r nog en definition (1)' % term)
                    elif isinstance(element, Stycke):
                        # Case 1: "antisladdsystem: ett tekniskt st�dsystem"
                        # Sometimes, : is not the delimiter between
                        # the term and the definition, but even in
                        # those cases, : might figure in the
                        # definition itself, usually as part of the
                        # SFS number. Do some hairy heuristics to find
                        # out what delimiter to use
                        
                        if find_definitions == "normal":
                            if not self.re_definitions(elementtext):
                                if " - " in elementtext:
                                    if (":" in elementtext and
                                        (elementtext.index(":") < elementtext.index(" - "))):
                                        termdelimiter = ":"
                                    else:
                                        termdelimiter = " - "
                                m = self.re_SearchSfsId(elementtext)

                                if termdelimiter == ":" and m and m.start() < elementtext.index(":"):
                                    termdelimiter = " "

                                if termdelimiter in elementtext:
                                    term = elementtext.split(termdelimiter)[0]
                                    log.debug(u'"%s" �r nog en definition (2.1)' % term)

                        # case 2: "Den som ber�var annan livet, d�ms
                        # f�r mord till f�ngelse"
                        m = self.re_brottsdef(elementtext)
                        if m:
                            term = m.group(2)
                            log.debug(u'"%s" �r nog en definition (2.2)' % term)

                        # case 3: "F�r milj�brott d�ms till b�ter"
                        m = self.re_brottsdef_alt(elementtext)
                        if m:
                            term = m.group(1)
                            log.debug(u'"%s" �r nog en definition (2.3)' % term)

                        # case 4: "Inteckning f�r p� ans�kan av
                        # fastighets�garen d�das (d�dning)."
                        m = self.re_parantesdef(elementtext)
                        if m:
                            term = m.group(1)
                            log.debug(u'"%s" �r nog en definition (2.4)' % term)

                        # case 5: "Med detaljhandel avses i denna lag
                        # f�rs�ljning av l�kemedel"
                        m = self.re_loptextdef(elementtext)
                        if m:
                            term = m.group(1)
                            log.debug(u'"%s" �r nog en definition (2.5)' % term)

                    elif isinstance(element, Listelement):
                        # remove
                        for rx in (self.re_Bullet,
                                   self.re_DottedNumber,
                                   self.re_Bokstavslista):
                            elementtext = rx.sub('',elementtext)
                        term = elementtext.split(termdelimiter)[0]
                        log.debug(u'"%s" �r nog en definition (3)' % term)

                    # Longest legitimate term found "Valutav�xling,
                    # betalnings�verf�ring och annan finansiell
                    # verksamhet"
                    if term and len(term) < 68:
                        # this results in empty/hidden links -- might
                        # be better to hchange sfs.template.xht2 to
                        # change these to <span rel="" href=""/>
                        # instead. Or use another object than LinkSubject.
                        term = Util.normalizeSpace(term)
                        termnode = LinkSubject(term, uri=self._term_to_subject(term),predicate="dct:subject")
                        find_definitions_recursive = False
                    else:
                        term = None

                for p in element: # normally only one, but can be more
                                  # if the Stycke has a NumreradLista
                                  # or similar
                    if isinstance(p,unicode): # look for stuff
                        # normalize and convert some characters
                        s = " ".join(p.split())
                        s = s.replace(u"\x96","-")
                        # Make all links have a dct:references
                        # predicate -- not that meaningful for the
                        # XHTML2 code, but needed to get useful RDF
                        # triples in the RDFa output
                        # print "Parsing %s" % " ".join(p.split())
                        # print "Calling parse w %s" % baseuri+"#"+prefix
                        parsednodes = self.lagrum_parser.parse(s,
                                                               baseuri+prefix,
                                                               "dct:references")
                        for n in parsednodes:
                            if term and isinstance(n,unicode) and term in n:
                                    (head,tail) = n.split(term,1)
                                    nodes.extend((head,termnode,tail))
                            else:
                                nodes.append(n)
                        
                        idx = element.index(p)
                element[idx:idx+1] = nodes

                           
            # Konstruera IDs
            for p in element:
                counters[type(p)] += 1

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

                #print u"rekurserar, element �r %s, p �r %s, find_definitions �r %s" % (element.__class__.__name__,
                #                                                                       p.__class__.__name__,
                #                                                                       find_definitions)
                if ((hasattr(p, 'fragment_label') and
                     p.fragment_label in skip_fragments)):
                    self._construct_ids(p,prefix,baseuri,skip_fragments, find_definitions_recursive)
                else:
                    self._construct_ids(p,fragment,baseuri,skip_fragments, find_definitions_recursive)

                # Efter att f�rsta tabellcellen i en rad hanterats,
                # undvik att leta definitioner i tabellceller 2,3,4...
                if isinstance(element, Tabellrad):
                    #print u"sl�cker definitionsletarflaggan"
                    find_definitions_recursive = False
                    

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
                

    def _parseSFST(self, lawtextfile, registry, patchdescription=None):
        # self.reader = TextReader(ustring=lawtext,linesep=TextReader.UNIX)
        self.reader = TextReader(lawtextfile, encoding='iso-8859-1', linesep=TextReader.DOS)
        self.reader.autostrip = True
        self.registry = registry
        meta = self.makeHeader() 
        body = self.makeForfattning()
        elements = self._count_elements(body)
        if 'K' in elements and elements['P1'] < 2:
            skipfragments = ['A','K']
        else:
            skipfragments = ['A']
        self._construct_ids(body, u'', u'http://rinfo.lagrummet.se/publ/sfs/%s#' % (FilenameToSFSnr(self.id)), skipfragments)

        if patchdescription:
            meta[u'Text�ndring'] = UnicodeSubject(patchdescription,
                                                  predicate=RINFOEX['patchdescription'])
        
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
            elif key == u'�vrigt':
                meta[key] = UnicodeSubject(val,predicate=self.labels[key])
            elif key == u'SFS nr':
                meta[key] = UnicodeSubject(val,predicate=self.labels[key])
            elif key == u'Utf�rdad':
                meta[key] = DateSubject(datetime.strptime(val[:10], '%Y-%m-%d'), predicate=self.labels[key])
            elif key == u'Upph�vd':
                meta[key] = DateSubject(datetime.strptime(val[:10], '%Y-%m-%d'), predicate=self.labels[key])
                if meta[key] < datetime.today():
                    if not self.keep_expired:
                        raise UpphavdForfattning()
            elif key == u'Departement/ myndighet':
                authrec = self.find_authority_rec(val)
                meta[key] = LinkSubject(val, uri=unicode(authrec),
                                     predicate=self.labels[key])
            elif key == u'�ndring inf�rd':
                # �teranv�nd URI-strategin fr�n LegalRef
                m = self.re_SimpleSfsId.search(val)
                if m:
                    uri = self.lagrum_parser.parse(m.group(1))[0].uri
                    # uri = self.lagrum_parser.parse(val)[0].uri
                    meta[key] = LinkSubject(val,uri=uri,predicate=self.labels[key])
                else:
                    log.warning(u"%s: Kunde inte tolka SFS-numret f�r senaste �ndring" % self.id)

            elif key == u'Omtryck':
                val = val.replace(u'SFS ','')
                val = val.replace(u'SFS','')
                try:
                    uri = self.lagrum_parser.parse(val)[0].uri
                    meta[key] = UnicodeSubject(val,predicate=self.labels[key])
                except AttributeError: # 'unicode' object has no attribute 'uri'
                    pass
            elif key == u'F�rfattningen har upph�vts genom':
                val = val.replace(u'SFS ','')
                val = val.replace(u'SFS','')
                firstnode = self.lagrum_parser.parse(val)[0]
                if hasattr(firstnode,'uri'):
                    uri = firstnode.uri
                    meta[key] = LinkSubject(val,uri=uri,predicate=self.labels[key])
                else:
                    log.warning(u'Kunde inte tolka [%s] som ett "upph�vd genom"-SFS-nummer' % val)
                    meta[key] = val
                

            elif key == u'Tidsbegr�nsad':
                meta[key] = DateSubject(datetime.strptime(val[:10], '%Y-%m-%d'), predicate=self.labels[key])
            else:
                log.warning(u'%s: Obekant nyckel [\'%s\']' % (self.id, key))
            
            meta[u'Utgivare'] = LinkSubject(u'Regeringskansliet',
                                            uri=self.find_authority_rec("Regeringskansliet"),
                                            predicate=self.labels[u'Utgivare'])

        docuri = self.lagrum_parser.parse(meta[u'SFS nr'])[0].uri
        meta[u'xml:base'] = docuri

        if u'Rubrik' not in meta:
            log.warning("%s: Rubrik saknas" % self.id)
            
        return meta
        
    def makeForfattning(self):
        while self.reader.peekline() == "":
            self.reader.readline()
            
        log.debug(u'F�rsta raden \'%s\'' % self.reader.peekline())
        (line, upphor, ikrafttrader) = self.andringsDatum(self.reader.peekline())
        if ikrafttrader:
            log.debug(u'F�rfattning med ikrafttr�dandedatum %s' % ikrafttrader)
            b = Forfattning(ikrafttrader=ikrafttrader)
            self.reader.readline()
        else:
            log.debug(u'F�rfattning utan ikrafttr�dandedatum')
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
        if (self.reader.peekline(1) == "" and
            self.reader.peekline(3) == "" and
            not self.isKapitel(self.reader.peekline(2))):
            self.reader.readline()
            p.underrubrik = self.reader.readline()

        log.debug(u"  Ny avdelning: '%s...'" % p.rubrik[:30])

        while not self.reader.eof():
            state_handler = self.guess_state()

            if state_handler in (self.makeAvdelning, # Strukturer som signalerar att denna avdelning �r slut
                                 self.makeOvergangsbestammelser,
                                 self.makeBilaga): 
                log.debug(u"  Avdelning %s f�rdig" % p.ordinal)
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
        log.debug(u"  Upph�vt kapitel: '%s...'" % c[:30])

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
        self.current_section = u'0'
        
        log.debug(u"    Nytt kapitel: '%s...'" % line[:30])
        
        while not self.reader.eof():
            state_handler = self.guess_state()

            if state_handler in (self.makeKapitel, # Strukturer som signalerar slutet p� detta kapitel
                                 self.makeUpphavtKapitel,
                                 self.makeAvdelning,
                                 self.makeOvergangsbestammelser,
                                 self.makeBilaga): 
                log.debug(u"    Kapitel %s f�rdigt" % k.ordinal)
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
        log.debug(u"      Upph�vd paragraf: '%s...'" % p[:30])
        return p
    
    def makeParagraf(self):
        paragrafnummer = self.idOfParagraf(self.reader.peekline())
        self.current_section = paragrafnummer
        firstline = self.reader.peekline()
        log.debug(u"      Ny paragraf: '%s...'" % firstline[:30])
        # L�s f�rbi paragrafnumret:
        self.reader.read(len(paragrafnummer)+ len(u' � '))

        # some really old laws have sections split up in "elements"
        # (moment), eg '1 � 1 mom.', '1 � 2 mom.' etc
        match = self.re_ElementId.match(firstline)
        if self.re_ElementId.match(firstline):
            momentnummer = match.group(1)
            self.reader.read(len(momentnummer) + len(u' mom. '))
        else:
            momentnummer = None

        (fixedline, upphor, ikrafttrader) = self.andringsDatum(firstline)
        # L�s f�rbi '/Upph�r [...]/' och '/Ikrafttr�der [...]/'-str�ngarna
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
                log.debug(u"      Paragraf %s f�rdig" % paragrafnummer)
                return p
            elif state_handler == self.blankline:
                state_handler() # Bara att sl�nga bort
            elif state_handler == self.makeOvergangsbestammelse:
                log.debug(u"      Paragraf %s f�rdig" % paragrafnummer)
                log.warning(u"%s: Avskiljande rubrik saknas mellan f�rfattningstext och �verg�ngsbest�mmelser" % self.id)
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
        s = Stycke([Util.normalizeSpace(self.reader.readparagraph())])
        while not self.reader.eof():
            #log.debug(u"            makeStycke: calling guess_state ")
            state_handler = self.guess_state()
            #log.debug(u"            makeStycke: guess_state returned %s " % state_handler.__name__)
            if state_handler in (self.makeNumreradLista,
                                 self.makeBokstavslista,
                                 self.makeStrecksatslista,
                                 self.makeTabell):
                res = state_handler()
                s.append(res)
            elif state_handler == self.blankline:
                state_handler() # Bara att sl�nga bort
            else:
                #log.debug(u"            makeStycke: ...we're done")
                return s
        return s

    def makeNumreradLista(self): 
        n = NumreradLista()
        while not self.reader.eof():
            # Utg� i f�rsta hand fr�n att n�sta stycke �r ytterligare
            # en listpunkt (vissa t�nkbara stycken kan �ven matcha
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
                log.debug(u"            Ny strecksats: '%s...'" % self.reader.peekline()[:60])
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

    def makeOvergangsbestammelser(self,rubrik_saknas=False): # svenska: �verg�ngsbest�mmelser
        # det kan diskuteras om dessa ska ses som en del av den
        # konsoliderade lagtexten �ht, men det verkar vara kutym att
        # ha med �tminstone de som kan ha relevans f�r g�llande r�tt
        log.debug(u"    Ny �verg�ngsbest�mmelser")

        if rubrik_saknas:
            rubrik = u"[�verg�ngsbest�mmelser]"
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
                    # assume these are the initial �verg�ngsbest�mmelser
                    if hasattr(self,'id') and '/' in self.id:
                        sfsnr = FilenameToSFSnr(self.id)
                        log.warning(u"%s: �verg�ngsbest�mmelsen saknar SFS-nummer - antar [%s]" % (self.id, sfsnr))
                    else:
                        sfsnr = u'0000:000'
                        log.warning(u"(unknown): �verg�ngsbest�mmelsen saknar ett SFS-nummer - antar %s" % (sfsnr))

                    obs.append(Overgangsbestammelse([res], sfsnr=sfsnr))
                else:
                    obs.append(res)
            
        return obs

    def makeOvergangsbestammelse(self):
        p = self.reader.readline()
        log.debug(u"      Ny �verg�ngsbest�mmelse: %s" % p)
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
        (rubrik,upphor,ikrafttrader) = self.andringsDatum(rubrik)

        kwargs = {'rubrik':rubrik}
        if upphor: kwargs['upphor'] = upphor
        if ikrafttrader: kwargs['ikrafttrader'] = ikrafttrader
        b = Bilaga(**kwargs)
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
        # Hittar �ndringsdatumdirektiv i line. Om match, matcha fr�n str�ngens b�rjan, annars s�k i hela str�ngen.
        dates = {'ikrafttrader': None,
                 'upphor': None}

        for (regex,key) in {self.re_RevokeDate:'upphor',
                            self.re_RevokeAuthorization:'upphor',
                            self.re_EntryIntoForceDate:'ikrafttrader',
                            self.re_EntryIntoForceAuthorization:'ikrafttrader'}.items():
            if match:
                m = regex.match(line)
            else:
                m = regex.search(line)
            if m:
                if len(m.groups()) == 3:
                    dates[key] = datetime(int(m.group(1)),
                                          int(m.group(2)),
                                          int(m.group(3)))
                else:
                    dates[key] = m.group(1)
                line = regex.sub(u'',line)

        return (line.strip(), dates['upphor'], dates['ikrafttrader'])

    
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
        # 1998:808: "F�RSTA AVDELNINGEN\n\n�VERGRIPANDE BEST�MMELSER"
        #  (also in 1932:130, 1942:740, 1956:623, 1957:297, 1962:381, 1962:700, 
        #   1970:988, 1970:994, 1971:235 (revoked), 1973:370 (revoked), 
        #   1977:263 (revoked), 1987:230, 1992:300 (revoked), 1994:200, 
        #   1998:674, 2000:192, 2005:104 and 2007:528 -- not always in all 
        #   uppercase. However, the initial line "F�RSTA AVDELNININGEN" 
        #   (in any casing) is always followed by another line that 
        #   describes/labels the part.)
        #
        # 1979:1152: "Avd. 1. Best�mmelser om taxering av fastighet" 
        #  (also in 1979:1193 (revoked))
        #
        # 1994:1009: "Avdelning I Fartyg"
        #
        # 1999:1229: "AVD. I INNEH�LL OCH DEFINITIONER"
        #
        # 2009:400: "AVDELNING I. INLEDANDE BEST�MMELSER"
        #
        # and also "1 avd." (in 1959:287 (revoked), 1959:420 (revoked)
        #
        #  The below code checks for all these patterns in turn
        # 
        # The variant "Avdelning 1" has also been found, but only in
        # appendixes
        p = self.reader.peekline()
        if p.lower().endswith(u"avdelningen") and len(p.split()) == 2:
            ordinal = p.split()[0]
            return unicode(self._swedish_ordinal(ordinal))
        elif p.startswith(u"AVD. ") or p.startswith(u"AVDELNING "):
            roman = re.split(r'\s+',p)[1]
            if roman.endswith("."):
                roman = roman[:-1]
            if self.re_roman_numeral_matcher(roman):
                return unicode(self._from_roman(roman))
        elif p.startswith(u"Avdelning "):
            roman = re.split(r'\s+',p)[1]
            if self.re_roman_numeral_matcher(roman):
                return unicode(self._from_roman(roman))
        elif p[2:6] == "avd.":
            if p[0].isdigit():
                return p[0]
        elif p.startswith(u"Avd. "):
            idstr = re.split(r'\s+',p)[1]
            if idstr.isdigit():
                return idstr
        return None

    def isUpphavtKapitel(self):
        match = self.re_ChapterRevoked(self.reader.peekline())
        return match != None

    def isKapitel(self, p=None):
        return self.idOfKapitel(p) != None

    def idOfKapitel(self, p=None):
        if not p:
            p = self.reader.peekparagraph().replace("\n", " ")

        # '1 a kap.' -- almost always a headline, regardless if it
        # streches several lines but there are always special cases
        # (1982:713 1 a kap. 7 �)
        #m = re.match(r'^(\d+( \w|)) [Kk]ap.',p)
        m = self.re_ChapterId(p)
        if m:
            # even though something might look like the start of a chapter, it's often just the
            # start of a paragraph in a section that lists the names of chapters. These following
            # attempts to filter these out by looking for some typical line endings for those cases
            if (p.endswith(",") or
                p.endswith(";") or
                # p.endswith(")") or  # but in some cases, a chapter actually ends in ), eg 1932:131
                p.endswith(" och") or # in unlucky cases, a chapter heading might span two lines in a way that the first line ends with "och" (eg 1998:808 kap. 3)
                p.endswith(" om") or
                p.endswith(" samt") or
                (p.endswith(".") and not
                 (m.span()[1] == len(p) or # if the ENTIRE p is eg "6 kap." (like it is in 1962:700)
                  p.endswith(" m.m.") or
                  p.endswith(" m. m.") or
                  p.endswith(" m.fl.") or
                  p.endswith(" m. fl.") or
                  self.re_ChapterRevoked(p)))): # If the entire chapter's
                                           # been revoked, we still
                                           # want to count it as a
                                           # chapter

                # sys.stdout.write(u"chapter_id: '%s' failed second check" % p)
                return None

            # sometimes (2005:1207) it's a headline, referencing a
            # specific section somewhere else - if the "1 kap. " is
            # immediately followed by "5 � " then that's probably the
            # case
            if (p.endswith(u" �") or
                p.endswith(u" ��") or
                (p.endswith(u" stycket") and u" � " in p)):
                return None
            

            # Om det ser ut som en tabell �r det nog ingen
            # kapitelrubrik -- borttaget, triggade inget
            # regressionstest och orsakade bug 168
            
            #if self.isTabell(p, requireColumns=True):
            #    return None 

            else:
                return m.group(1)
        else:
            # sys.stdout.write(u"chapter_id: '%s' failed first check" % p[:40])
            return None

    def isRubrik(self, p=None):
        if p == None:
            p = self.reader.peekparagraph()
            indirect = False
        else:
            indirect = True

        self.trace['rubrik'].debug("isRubrik (%s): indirect=%s" % (p[:50], indirect))
        
        if len(p) > 0 and p[0].lower() == p[0] and not p.startswith("/Rubriken"):
           self.trace['rubrik'].debug("isRubrik (%s): starts with lower-case" % (p[:50]))
           return False

        # self.trace['rubrik'].debug("isRubrik: p=%s" % p)
        if len(p) > 110: # it shouldn't be too long, but some headlines are insanely verbose
            self.trace['rubrik'].debug("isRubrik (%s): too long" % (p[:50]))
            return False

        # A headline should not look like the start of a paragraph or a numbered list
        if self.isParagraf(p): 
            self.trace['rubrik'].debug("isRubrik (%s): looks like para" % (p[:50]))
            return False

        if self.isNumreradLista(p):
            self.trace['rubrik'].debug("isRubrik (%s): looks like numreradlista" % (p[:50]))
            return False

        if self.isStrecksatslista(p):
            self.trace['rubrik'].debug("isRubrik (%s): looks like strecksatslista" % (p[:50]))
            return False
            

        if (p.endswith(".") and # a headline never ends with a period, unless it ends with "m.m." or similar
            not (p.endswith("m.m.") or 
                 p.endswith("m. m.") or 
                 p.endswith("m.fl.") or 
                 p.endswith("m. fl."))):
            self.trace['rubrik'].debug("isRubrik (%s): ends with period" % (p[:50]))
            return False 

        if (p.endswith(",") or  # a headline never ends with these characters
            p.endswith(":") or 
            p.endswith("samt") or 
            p.endswith("eller")):
            self.trace['rubrik'].debug("isRubrik (%s): ends with comma/colon etc" % (p[:50]))
            return False

        if self.re_ChangeNote.search(p): # eg 1994:1512 8 �
            return False

        if p.startswith("/") and p.endswith("./"):
            self.trace['rubrik'].debug("isRubrik (%s): Seems like a comment" % (p[:50]))
            return False
            

        try:
            nextp = self.reader.peekparagraph(2)
        except IOError:
            nextp = u''
        
        # finally, it should be followed by a paragraph - but this
        # test is only done if this check is not indirect (to avoid
        # infinite recursion)
        if not indirect:
            if (not self.isParagraf(nextp)) and (not self.isRubrik(nextp)):
                self.trace['rubrik'].debug("isRubrik (%s): is not followed by a paragraf or rubrik" % (p[:50]))
                return False

        # if this headline is followed by a second headline, that
        # headline and all subsequent headlines should be regardes as
        # sub-headlines
        if (not indirect) and self.isRubrik(nextp):
            self.current_headline_level = 1
        
        # ok, all tests passed, this might be a headline!
        self.trace['rubrik'].debug("isRubrik (%s): All tests passed!" % (p[:50]))
                                                                         
        return True

    def isUpphavdParagraf(self):
        match = self.re_SectionRevoked(self.reader.peekline())
        return match != None

    def isParagraf(self, p=None):
        if not p:
            p = self.reader.peekparagraph()
            self.trace['paragraf'].debug("isParagraf: called w/ '%s' (peek)" % p[:30])
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
        if Util.numcmp(paragrafnummer, self.current_section) < 0:
            self.trace['paragraf'].debug("isParagraf: section numbering compare failed (%s <= %s)" % (paragrafnummer, self.current_section))
            return False

        # a similar case exists in 1994:260 and 2007:972, but there
        # the referenced section has a number larger than last section
        # id. Try another way to detect this by looking at the first
        # character in the paragraph - if it's in lower case, it's
        # probably not a paragraph.
        firstcharidx = (len(paragrafnummer) + len(' � '))
        # print "%r: %s" % (p, firstcharidx)
        if ((len(p) > firstcharidx) and
            (p[len(paragrafnummer) + len(' � ')].islower())):
            self.trace['paragraf'].debug("isParagraf: section '%s' did not start with uppercase" % p[len(paragrafnummer) + len(' � '):30])
            return False
        return True
                                         
            

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

    # Om assumeTable �r True �r testerna n�got gener�sare �n
    # annars. Den �r False f�r den f�rsta raden i en tabell, men True
    # f�r de efterf�ljande.
    #
    # Om requireColumns �r True kr�vs att samtliga rader �r
    # spaltuppdelade
    
    def isTabell(self, p=None, assumeTable = False, requireColumns = False):
        shortline = 55
        shorterline = 52
        if not p:
            p = self.reader.peekparagraph()
        # Vissa snedformatterade tabeller kan ha en h�gercell som g�r
        # ned en rad f�r l�ngt gentemot n�sta rad, som har en tom
        # h�gercell:

        # xxx xxx xxxxxx     xxxx xx xxxxxx xx
        # xxxxx xx xx x      xxxxxx xxx xxx x 
        #                    xx xxx xxx xxx 
        # xxx xx xxxxx xx
        # xx xxx xx x xx

        # dvs n�got som egentligen �r tv� stycken l�ses in som
        # ett. F�rs�k hitta s�dana fall, och titta i s� fall endast p�
        # f�rsta stycket
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
        # Heuristiken f�r att gissa om detta stycke �r en tabellrad:
        # Om varje rad
        # 1. �r kort (indikerar en tabellrad med en enda v�nstercell)
        self.trace['tabell'].debug("assumeTable: %s numlines: %s requireColumns: %s " % (assumeTable,numlines,requireColumns))
        if (assumeTable or numlines > 1) and not requireColumns:
            matches = [l for l in lines if len(l) < shortline]
            if numlines == 1 and '  ' in lines[0]:
                self.trace['tabell'].debug(u"isTabell('%s'): Endast en rad, men tydlig kolumnindelning" % (p[:20]))
                return True
            if len(matches) == numlines:
                self.trace['tabell'].debug(u"isTabell('%s'): Alla rader korta, unders�ker undantag" % (p[:20]))
                
                # generellt undantag: Om en tabells f�rsta rad har
                # enbart v�nsterkolumn M�STE den f�ljas av en
                # spaltindelad rad - annars �r det nog bara tv� korta
                # stycken, ett kort stycke f�ljt av kort rubrik, eller
                # liknande.
                try:
                    p2 = self.reader.peekparagraph(2)
                except IOError:
                    p2 = ''
                try:
                    p3 = self.reader.peekparagraph(3)
                except IOError:
                    p3 = ''
                if not assumeTable and not self.isTabell(p2,
                                                         assumeTable = True, 
                                                         requireColumns = True):
                    self.trace['tabell'].debug(u"isTabell('%s'): generellt undantag fr�n alla rader korta-regeln" % (p[:20]))
                    return False
                elif numlines == 1:
                    # Om stycket har en enda rad *kan* det vara en kort
                    # rubrik -- kolla om den f�ljs av en paragraf, is�fall
                    # �r nog tabellen slut
                    # FIXME: Kolla om inte generella undantaget borde
                    # f�nga det h�r. Testfall
                    # regression-tabell-foljd-av-kort-rubrik.txt och
                    # temporal-paragraf-med-tabell.txt
                    if self.isParagraf(p2):
                        self.trace['tabell'].debug(u"isTabell('%s'): Specialundantag: f�ljs av Paragraf, inte Tabellrad" % (p[:20]))
                        return False
                    if self.isRubrik(p2) and self.isParagraf(p3):
                        self.trace['tabell'].debug(u"isTabell('%s'): Specialundantag: f�ljs av Rubrik och sedan Paragraf, inte Tabellrad" % (p[:20]))
                        return False
                    # Om stycket �r *exakt* detta signalerar det nog
                    # �verg�ngen fr�n tabell (kanske i slutet p� en
                    # bilaga, som i SekrL) till �verg�ngsbest�mmelserna
                    if self.isOvergangsbestammelser():
                        self.trace['tabell'].debug(u"isTabell('%s'): Specialundantag: �verg�ngsbest�mmelser" % (p[:20]))
                        return False
                    if self.isBilaga():
                        self.trace['tabell'].debug(u"isTabell('%s'): Specialundantag: Bilaga" % (p[:20]))
                        return False

                # Detta undantag beh�ves f�rmodligen inte n�r genererella undantaget anv�nds
                #elif (numlines == 2 and
                #      self.isNumreradLista() and (
                #    lines[1].startswith(u'F�rordning (') or
                #    lines[1].startswith(u'Lag ('))):
                #
                #        self.trace['tabell'].debug(u"isTabell('%s'): Specialundantag: ser ut som nummerpunkt f�ljd av �ndringsf�rfattningsh�nvisning" % (p[:20]))
                #        return False
                
                # inget av undantagen till�mpliga, huvudregel 1 g�ller
                self.trace['tabell'].debug(u"isTabell('%s'): %s rader, alla korta" % (p[:20], numlines))
                return True
                
        # 2. Har mer �n ett mellanslag i f�ljd p� varje rad (spaltuppdelning)
        matches = [l for l in lines if '  ' in l]
        if numlines > 1 and len(matches) == numlines:
            self.trace['tabell'].debug("isTabell('%s'): %s rader, alla spaltuppdelade" % (p[:20],numlines))
            return True

        # 3. �r kort ELLER har spaltuppdelning
        self.trace['tabell'].debug("test 3")
        if (assumeTable or numlines > 1) and not requireColumns:
            self.trace['tabell'].debug("test 3.1")
            matches = [l for l in lines if '  ' in l or len(l) < shorterline]
            if len(matches) == numlines:
                self.trace['tabell'].debug("isTabell('%s'): %s rader, alla korta eller spaltuppdelade" % (p[:20],numlines))
                return True

        # 3. �r enrading med TYDLIG tabelluppdelning
        if numlines == 1 and '   ' in l:
            self.trace['tabell'].debug("isTabell('%s'): %s rader, alla spaltuppdelade" % (p[:20],numlines))
            return True

        self.trace['tabell'].debug("isTabell('%s'): %s rader, inga test matchade (aT:%r, rC: %r)" % (p[:20],numlines,assumeTable,requireColumns))
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
        # Algoritmen �r anpassad f�r att hantera tabeller d�r texten inte
        # alltid �r s� j�mnt ordnat i spalter, som fallet �r med
        # SFSR-datat (gissningvis p� grund av n�gon trasig
        # tab-till-space-konvertering n�nstans).
        def makeTabellcell(text):
            if len(text) > 1:
                text = self.re_dehyphenate("", text)
            return Tabellcell([Util.normalizeSpace(text)])

        cols = [u'',u'',u'',u'',u'',u'',u'',u''] # Ingen tabell kommer n�nsin ha mer �n �tta kolumner
        if tabstops:
            statictabstops = True # Anv�nd de tabbstoppositioner vi fick f�rra raden
        else:
            statictabstops = False # Bygg nya tabbstoppositioner fr�n scratch
            self.trace['tabell'].debug("rebuilding tabstops")
            tabstops = [0,0,0,0,0,0,0,0]
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
                cols = [u'',u'',u'',u'',u'',u'',u'',u'']
            if l[0] == ' ':
                emptyleft = True
            else:
                if emptyleft:
                    self.trace['tabell'].debug(u'makeTabellrad: skapar ny tabellrad pga snedformatering')
                    rows.append(cols)
                    cols = [u'',u'',u'',u'',u'',u'',u'',u'']
                    emptyleft = False
                    
            for c in l:
                charcount += 1
                if c == u' ':
                    spacecount += 1
                else:
                    if spacecount > 1: # Vi har st�tt p� en ny tabellcell
                                       # - fyll den gamla
                        # L�gg till en nyrad f�r att ers�tta den vi kapat -
                        # �verfl�dig whitespace trimmas senare
                        cols[colcount] += u'\n' + l[lasttab:charcount-(spacecount+1)]
                        lasttab = charcount - 1

                        # f�r hantering av tomma v�nsterceller
                        if linecount > 1 or statictabstops:
                            if tabstops[colcount+1]+7 < charcount: # till�t en oj�mnhet om max sju tecken
                                if len(tabstops) <= colcount + 2:
                                    tabstops.append(0)
                                    cols.append(u'')
                                self.trace['tabell'].debug(u'colcount is %d, # of tabstops is %d' % (colcount, len(tabstops)))
                                self.trace['tabell'].debug(u'charcount shoud be max %s, is %s - adjusting to next tabstop (%s)' % (tabstops[colcount+1] + 5, charcount,  tabstops[colcount+2]))
                                if tabstops[colcount+2] != 0:
                                    self.trace['tabell'].debug(u'safe to advance colcount')
                                    colcount += 1
                        colcount += 1
                        if len(tabstops) <= charcount:
                            tabstops.append(0)
                            cols.append(u'')
                        tabstops[colcount] = charcount
                        self.trace['tabell'].debug("Tabstops now: %r" % tabstops)
                    spacecount = 0
            cols[colcount] += u'\n' + l[lasttab:charcount]
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
                    tr.append(makeTabellcell(c.replace("\n", " ")))
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
        match = self.re_DottedNumber.match(p)

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

    def isStrecksatslista(self,p=None):
        if not p:
            p = self.reader.peekline()

        return (p.startswith("- ") or
                p.startswith(u"\x96 ") or 
                p.startswith("--"))

    def isBokstavslista(self):
        return self.idOfBokstavslista() != None

    def idOfBokstavslista(self):
        p = self.reader.peekline()
        match = self.re_Bokstavslista.match(p)

        if match != None:
            return match.group(1).replace(" ", "")
        return None
        
    def isOvergangsbestammelser(self):
        separators = [u'�verg�ngsbest�mmelser',
                      u'Ikrafttr�dande- och �verg�ngsbest�mmelser',
                      u'�verg�ngs- och ikrafttr�dandebest�mmelser']
        
        l = self.reader.peekline()
        if l not in separators:
            fuzz = difflib.get_close_matches(l, separators, 1, 0.9)
            if fuzz:
                log.warning(u"%s: Antar att '%s' ska vara '%s'?" % (self.id, l, fuzz[0]))
            else:
                return False
        try:
            # if the separator "�verg�ngsbest�mmelser" (or similar) is
            # followed by a regular paragraph, it was probably not a
            # separator but an ordinary headline (occurs in a few law
            # texts)
            np = self.reader.peekparagraph(2)
            if self.isParagraf(np):
                return False
            
        except IOError:
            pass

        return True


    def isOvergangsbestammelse(self):
        return self.re_SimpleSfsId.match(self.reader.peekline())


    def isBilaga(self):
        (line,upphor,ikrafttrader) = self.andringsDatum(self.reader.peekline())
        return (line in (u"Bilaga", u"Bilaga*", u"Bilaga *",
                                                   u"Bilaga 1", u"Bilaga 2", u"Bilaga 3",
                                                   u"Bilaga 4", u"Bilaga 5", u"Bilaga 6"));
    
class SFSManager(LegalSource.Manager,FilebasedTester.FilebasedTester):
    __parserClass = SFSParser
    _document_name_cache = {}

    ####################################################################
    # IMPLEMENTATION OF Manager INTERFACE
    ####################################################################    

    def Parse(self, basefile, verbose=False):
        try:
            if verbose:
                print "Setting verbosity"
                log.setLevel(logging.DEBUG)

            start = time()
            basefile = basefile.replace(":","/")
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
            filelist = []
            [filelist.extend(files[x]) for x in files.keys()]
            if not force and self._outfile_is_newer(filelist,filename):
                log.debug(u'%s: Skipping' % basefile)
                return

            # 3: check to see if the F�rfattning has been revoked using
            # plain fast string searching, no fancy HTML parsing and
            # traversing
            t = TextReader(files['sfsr'][0],encoding="iso-8859-1")
            if self.config[__moduledir__]['keep_expired'] != 'True':
                try:
                    t.cuepast(u'<i>F�rfattningen �r upph�vd/skall upph�vas: ')
                    datestr = t.readto(u'</i></b>')
                    if datetime.strptime(datestr, '%Y-%m-%d') < datetime.today():
                        log.debug(u'%s: Expired' % basefile)
                        raise UpphavdForfattning()
                except IOError:
                    pass

            # OK, all clear, now begin real parsing
            p = SFSParser()
            p.verbose = verbose
            if self.config[__moduledir__]['keep_expired'] == 'True':
                p.keep_expired = True
            # p.references.verbose = verbose
            if not verbose:
                for k in p.trace.keys():
                    p.trace[k].setLevel(logging.NOTSET)
            #parsed = "dummy text"
            parsed = p.Parse(basefile,files)
            tmpfile = mktemp()
            out = file(tmpfile, "w")
            out.write(parsed)
            out.close()
            if force:
                Util.replace_if_different(tmpfile,filename)
            else:
                Util.robustRename(tmpfile,filename)
            # Util.indentXmlFile(filename)
            log.info(u'%s: OK (%.3f sec)', basefile,time()-start)
            return '(%.3f sec)' % (time()-start)
        except UpphavdForfattning:
            log.debug(u'%s: Upph�vd', basefile)
            Util.robust_remove(filename)
            Util.robust_remove(Util.relpath(self._htmlFileName(basefile)))
        except IckeSFS:
            log.debug(u'%s: Ingen SFS', basefile)
            Util.robust_remove(filename)
            Util.robust_remove(Util.relpath(self._htmlFileName(basefile)))
                     
    def ParseAll(self):
        downloaded_dir = os.path.sep.join([self.baseDir, u'sfs', 'downloaded', 'sfst'])
        #self._do_for_all(downloaded_dir,'html',StaticParse)
        self._do_for_all(downloaded_dir,'html',self.Parse)

    def _generateAnnotations(self,annotationfile,basefile):
        p = LegalRef(LegalRef.LAGRUM)
        sfsnr = FilenameToSFSnr(basefile)
        baseuri = p.parse(sfsnr)[0].uri
        start = time()
        # Putting togeher a (non-normalized) RDF/XML file, suitable
        # for XSLT inclusion in six easy steps
        stuff = {}
        #
        # 1. all rinfo:Rattsfallsreferat that has baseuri as a
        # rinfo:lagrum, either directly or through a chain of
        # dct:isPartOf statements
        start = time()
        rattsfall = self._store_run_query("sparql/sfs_rattsfallsref.sq", uri=baseuri)
        log.debug(u'%s: Orig: Selected %d legal cases (%.3f sec)', basefile, len(rattsfall), time()-start)
        stuff[baseuri] = {}
        stuff[baseuri]['rattsfall'] = []

        specifics = {}
        for row in rattsfall:
            if 'lagrum' not in row:
                lagrum = baseuri
            else:
                # truncate 1998:204#P7S2 to just 1998:204#P7
                if "S" in row['lagrum']:
                    lagrum = row['lagrum'][:row['lagrum'].index("S")]
                else:
                    lagrum = row['lagrum']
                specifics[row['id']] = True
            # we COULD use a tricky defaultdict for stuff instead of
            # this initializing code, but defauldicts don't pprint
            # so pretty...
            if not lagrum in stuff:
                stuff[lagrum] = {}
            if not 'rattsfall' in stuff[lagrum]:
                stuff[lagrum]['rattsfall'] = []

            record = {'id':row['id'],
                      'desc':row['desc'],
                      'uri':row['uri']}

            # if one case references two or more paragraphs in a
            # particular section (ie "6 kap 1 � 1 st. och 6 kap 1 � 2
            # st.") we will get duplicates that we can't (easily)
            # filter out in the SPARQL query. Filter them out here
            # instead.
            if not record in stuff[lagrum]['rattsfall']:
                stuff[lagrum]['rattsfall'].append(record)

        # remove cases that refer to the law itself and a specific
        # paragraph (ie only keep cases that only refer to the law
        # itself)
        filtered = []
        for r in stuff[baseuri]['rattsfall']:
            if r['id'] not in specifics:
                filtered.append(r)
        stuff[baseuri]['rattsfall'] = filtered


        # 2. all law sections that has a dct:references that matches this (using dct:isPartOf).
        start = time()
        #inboundlinks = self._store_run_query("sparql/sfs_inboundlinks_orig.sq",uri=baseuri)
        #log.debug(u'%s: Orig: Selected %d inbound links (%.3f sec)', basefile, len(inboundlinks), time()-start)
        start = time()
        inboundlinks = self._store_run_query("sparql/sfs_inboundlinks.sq",uri=baseuri)
        log.debug(u'%s:  New: Selected %d inbound links (%.3f sec)', basefile, len(inboundlinks), time()-start)
        # inboundlinks = []
        stuff[baseuri]['inboundlinks'] = []

        # mapping <http://rinfo.lagrummet.se/publ/sfs/1999:175> =>
        # "R�ttsinformationsf�rordning (1999:175)"
        doctitles = {} 
        specifics = {}
        for row in inboundlinks:
            if 'lagrum' not in row:
                lagrum = baseuri
            else:
                # truncate 1998:204#P7S2 to just 1998:204#P7
                if "S" in row['lagrum']:
                    lagrum = row['lagrum'][:row['lagrum'].index("S")]
                else:
                    lagrum = row['lagrum']
                lagrum = row['lagrum'] 
                specifics[row['uri']] = True
            # we COULD use a tricky defaultdict for stuff instead of
            # this initializing code, but defauldicts don't pprint
            # so pretty...
            if not lagrum in stuff:
                stuff[lagrum] = {}
            if not 'inboundlinks' in stuff[lagrum]:
                stuff[lagrum]['inboundlinks'] = []
            #print "adding %s under %s" % (row['id'],lagrum)
            stuff[lagrum]['inboundlinks'].append({'uri':row['uri']})

        # remove inbound links that refer to the law itself plus at
        # least one specific paragraph (ie only keep cases that only
        # refer to the law itself)
        filtered = []
        for r in stuff[baseuri]['inboundlinks']:
            if r['uri'] not in specifics:
                filtered.append(r)
        stuff[baseuri]['inboundlinks'] = filtered

        # pprint (stuff)
        # 3. all wikientries that dct:description this
        start = time()
        #wikidesc = self._store_run_query("sparql/sfs_wikientries_orig.sq",uri=baseuri)
        #log.debug(u'%s: Orig: Selected %d wiki comments (%.3f sec)', basefile, len(wikidesc), time()-start)
        start = time()
        wikidesc = self._store_run_query("sparql/sfs_wikientries.sq",uri=baseuri)
        log.debug(u'%s:  New: Selected %d wiki comments (%.3f sec)', basefile, len(wikidesc), time()-start)
        # wikidesc = []
        for row in wikidesc:
            if not 'lagrum' in row:
                lagrum = baseuri
            else:
                lagrum = row['lagrum']

            if not lagrum in stuff:
                stuff[lagrum] = {}
            stuff[lagrum]['desc'] = row['desc']



        # pprint(wikidesc)
        # (4. eurlex.nu data (mapping CELEX ids to titles))
        # (5. Propositionstitlar)
        # 6. change entries for each section
        # FIXME: we need to differentiate between additions, changes
        # and deletions

        start = time()
        #changes = self._store_run_query("sparql/sfs_changes_orig.sq",uri=baseuri)
        #log.debug(u'%s: Orig: Selected %d change annotations (%.3f sec)', basefile, len(changes), time()-start)
        start = time()
        changes = self._store_run_query("sparql/sfs_changes.sq",uri=baseuri)
        log.debug(u'%s:  New: Selected %d change annotations (%.3f sec)', basefile, len(changes), time()-start)
        # changes = []

        for row in changes:
            lagrum = row['lagrum']
            if not lagrum in stuff:
                stuff[lagrum] = {}
            if not 'changes' in stuff[lagrum]:
                stuff[lagrum]['changes'] = []
            stuff[lagrum]['changes'].append({'uri':row['change'],
                                          'id':row['id']})

        # then, construct a single de-normalized rdf/xml dump, sorted
        # by root/chapter/section/paragraph URI:s. We do this using
        # raw XML, not RDFlib, to avoid normalizing the graph -- we
        # need repetition in order to make the XSLT processing simple.
        #
        # The RDF dump looks something like:
        #
        # <rdf:RDF>
        #   <rdf:Description about="http://rinfo.lagrummet.se/publ/sfs/1998:204#P1">
        #     <rinfo:isLagrumFor>
        #       <rdf:Description about="http://rinfo.lagrummet.se/publ/dom/rh/2004:51">
        #           <dct:identifier>RH 2004:51</dct:identifier>
        #           <dct:description>Hemsida p� Internet. Fr�ga om...</dct:description>
        #       </rdf:Description>
        #     </rinfo:isLagrumFor>
        #     <dct:description>Personuppgiftslagens syfte �r att skydda...</dct:description>
        #     <rinfo:isChangedBy>
        #        <rdf:Description about="http://rinfo.lagrummet.se/publ/sfs/2003:104">
        #           <dct:identifier>SFS 2003:104</dct:identifier>
        #           <rinfo:proposition>
        #             <rdf:Description about="http://rinfo.lagrummet.se/publ/prop/2002/03:123">
        #               <dct:title>�versyn av personuppgiftslagen</dct:title>
        #               <dct:identifier>Prop. 2002/03:123</dct:identifier>
        #             </rdf:Description>
        #           </rinfo:proposition>
        #        </rdf:Description>
        #     </rinfo:isChangedBy>
        #   </rdf:Description>
        # </rdf:RDF>

        start = time()
        root_node = PET.Element("rdf:RDF")
        for prefix in Util.ns:
            # we need this in order to make elementtree not produce
            # stupid namespaces like "xmlns:ns0" when parsing an external
            # string like we do below (the PET.fromstring call)
            PET._namespace_map[Util.ns[prefix]] = prefix
            root_node.set("xmlns:" + prefix, Util.ns[prefix])

        for l in sorted(stuff.keys(),cmp=Util.numcmp):
            lagrum_node = PET.SubElement(root_node, "rdf:Description")
            lagrum_node.set("rdf:about",l)
            if 'rattsfall' in stuff[l]:
                for r in stuff[l]['rattsfall']:
                    islagrumfor_node = PET.SubElement(lagrum_node, "rinfo:isLagrumFor")
                    rattsfall_node = PET.SubElement(islagrumfor_node, "rdf:Description")
                    rattsfall_node.set("rdf:about",r['uri'])
                    id_node = PET.SubElement(rattsfall_node, "dct:identifier")
                    id_node.text = r['id']
                    desc_node = PET.SubElement(rattsfall_node, "dct:description")
                    desc_node.text = r['desc']
            if 'inboundlinks' in stuff[l]:
                inbound = stuff[l]['inboundlinks']
                inboundlen = len(inbound)
                prev_uri = None
                for i in range(inboundlen):
                    if "#" in inbound[i]['uri']:
                        (uri,fragment) = inbound[i]['uri'].split("#")
                    else:
                        (uri,fragment) = (inbound[i]['uri'], None)

                    # 1) if the baseuri differs from the previous one,
                    # create a new dct:references node
                    if uri != prev_uri:
                        references_node = PET.Element("dct:references")
                        # 1.1) if the baseuri is the same as the uri
                        # for the law we're generating, place it first
                        if uri == baseuri:
                            # If the uri is the same as baseuri (the law
                            # we're generating), place it first.
                            lagrum_node.insert(0,references_node)
                        else:
                            lagrum_node.append(references_node)
                    # Find out the next uri safely
                    if (i+1 < inboundlen):
                        next_uri = inbound[i+1]['uri'].split("#")[0]
                    else:
                        next_uri = None

                    # If uri is the same as the next one OR uri is the
                    # same as baseuri, use relative form for creating
                    # dct:identifer
                    # print "uri: %s, next_uri: %s, baseuri: %s" % (uri[35:],next_uri[35:],baseuri[35:])
                    if (uri == next_uri) or (uri == baseuri):
                        form = "relative"
                    else:
                        form = "absolute"

                    inbound_node = PET.SubElement(references_node, "rdf:Description")
                    inbound_node.set("rdf:about",inbound[i]['uri'])
                    id_node = PET.SubElement(inbound_node, "dct:identifier")
                    id_node.text = self.display_title(inbound[i]['uri'],form)

                    prev_uri = uri

            if 'changes' in stuff[l]:
                for r in stuff[l]['changes']:
                    ischanged_node = PET.SubElement(lagrum_node, "rinfo:isChangedBy")
                    #rattsfall_node = PET.SubElement(islagrumfor_node, "rdf:Description")
                    #rattsfall_node.set("rdf:about",r['uri'])
                    id_node = PET.SubElement(ischanged_node, "rinfo:fsNummer")
                    id_node.text = r['id']
            if 'desc' in stuff[l]:
                desc_node = PET.SubElement(lagrum_node, "dct:description")
                # xhtmlstr = "<xht2:div>%s</xht2:div>" % (stuff[l]['desc'])
                xhtmlstr = "<xht2:div xmlns:xht2='%s'>%s</xht2:div>" % (Util.ns['xht2'], stuff[l]['desc'])
                xhtmlstr = xhtmlstr.replace(' xmlns="http://www.w3.org/2002/06/xhtml2/"','')
                desc_node.append(PET.fromstring(xhtmlstr.encode('utf-8')))

        Util.indent_et(root_node)
        tree = PET.ElementTree(root_node)
        tmpfile = mktemp()
        treestring = PET.tostring(root_node,encoding="utf-8").replace(' xmlns:xht2="http://www.w3.org/2002/06/xhtml2/"','',1)
        fp = open(tmpfile,"w")
        fp.write(treestring)
        fp.close()
        #tree.write(tmpfile, encoding="utf-8")
        Util.replace_if_different(tmpfile,annotationfile)
        os.utime(annotationfile,None)
        log.debug(u'%s: Serialized annotation (%.3f sec)', basefile, time()-start)
        

    def Generate(self,basefile):
        start = time()
        basefile = basefile.replace(":","/")
        infile = Util.relpath(self._xmlFileName(basefile))
        outfile = Util.relpath(self._htmlFileName(basefile))

        annotations = "%s/%s/intermediate/%s.ann.xml" % (self.baseDir, self.moduleDir, basefile)

        force = (self.config[__moduledir__]['generate_force'] == 'True')
        

        dependencies = self._load_deps(basefile)
        wiki_comments = "data/wiki/parsed/SFS/%s.xht2" % basefile
        if os.path.exists(wiki_comments):
            dependencies.append(wiki_comments)

        if not force and self._outfile_is_newer(dependencies,annotations):
            if os.path.exists(self._depsFileName(basefile)):
                log.debug(u"%s: All %s dependencies untouched in rel to %s" %
                          (basefile, len(dependencies), Util.relpath(annotations)))
            else:
                log.debug(u"%s: Has no dependencies" % basefile)
                
        else:
            log.info(u"%s: Generating annotation file", basefile)
            start = time()
            self._generateAnnotations(annotations,basefile)
            if time()-start > 5:
                log.info("openrdf-sesame is getting slow, reloading")
                cmd = "curl -u %s:%s http://localhost:8080/manager/reload?path=/openrdf-sesame" % (self.config['tomcatuser'], self.config['tomcatpassword'])
                Util.runcmd(cmd)
            else:
                sleep(0.5) # let sesame catch it's breath

        if not force and self._outfile_is_newer([infile,annotations],outfile):
            log.debug(u"%s: �verhoppad", basefile)
            return

        Util.mkdir(os.path.dirname(outfile))
        #params = {'annotationfile':annotations}
        # FIXME: create a relative version of annotations, instead of
        # hardcoding self.baseDir like below
        params = {'annotationfile':'../data/sfs/intermediate/%s.ann.xml' % basefile}
        Util.transform(__scriptdir__ + "/xsl/sfs.xsl",
                       infile,
                       outfile,
                       parameters = params,
                       validate=False)
        log.info(u'%s: OK (%s, %.3f sec)', basefile,outfile, time()-start)
        return

    def display_title(self,uri,form="absolute"):
        parts = LegalURI.parse(uri)
        res = ""
        for (field,label) in (('chapter',u'kap.'),
                              ('section',u'�'),
                              ('piece',  u'st'),
                              ('item',   u'p')):
            if field in parts and not (field == 'piece' and
                                       parts[field] == u'1' and
                                       'item' not in parts):
                res += "%s %s " % (parts[field], label)

        if form == "absolute":
            if parts['law'] not in self._document_name_cache:
                baseuri = LegalURI.construct({'type':LegalRef.LAGRUM,
                                              'law':parts['law']})
                sq = """PREFIX dct:<http://purl.org/dc/terms/>
                        SELECT ?title WHERE {<%s> dct:title ?title }""" % baseuri
                changes = self._store_select(sq)
                if changes:
                    self._document_name_cache[parts['law']] = changes[0]['title']
                else:
                    self._document_name_cache[parts['law']] = "SFS %s" % parts['law']
                    #print "Cache miss for %s (%s)" % (parts['law'],
                    #                              self._document_name_cache[parts['law']])

            res += self._document_name_cache[parts['law']]
            return res
        elif form == "relative":
            return res.strip()
        else:
            raise ValueError('unknown form %s' % form)

    def CleanupAnnulled(self,basefile):
        infile = self._xmlFileName(basefile)
        outfile = self._htmlFileName(basefile)
        if not os.path.exists(infile):
            Util.robust_remove(outfile)

    def GenerateAll(self):
        parsed_dir = os.path.sep.join([self.baseDir, u'sfs', 'parsed'])
        self._do_for_all(parsed_dir,'xht2',self.Generate)
        #self._do_for_all(parsed_dir,'xht2',StaticGenerate)

        # generated_dir = os.path.sep.join([self.baseDir, u'sfs', 'generated'])
        # self._do_for_all(generated_dir,'html',self.CleanupAnnulled)

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
        self._build_mini_rdf()
        super(SFSManager,self).RelateAll()

    def _build_mini_rdf(self):
        # the resulting file contains one triple for each law text
        # that has comments (should this be in Wiki.py instead?
        termdir = os.path.sep.join([self.baseDir, u'wiki', u'parsed', u'SFS'])
        minixmlfile = os.path.sep.join([self.baseDir, self.moduleDir, u'parsed', u'rdf-mini.xml'])
        files = list(Util.listDirs(termdir, ".xht2"))
        parser = LegalRef(LegalRef.LAGRUM)

        log.info("Making a mini graph")
        RINFO = Namespace(Util.ns['skos'])
        DCT = Namespace(Util.ns['dct'])
        mg = Graph()
        for key, value in Util.ns.items():
            mg.bind(key,  Namespace(value));
        
        for f in files:
            basefile = ":".join(os.path.split(os.path.splitext(os.sep.join(os.path.normpath(f).split(os.sep)[-2:]))[0]))
            # print "Finding out URI for %s" % basefile
            try:
                uri = parser.parse(basefile)[0].uri
            except AttributeError: # basefile is not interpretable as a SFS no
                continue
            mg.add((URIRef(uri), RDF.type, RINFO['KonsolideradGrundforfattning']))

        log.info("Serializing the minimal graph")
        f = open(minixmlfile, 'w')
        f.write(mg.serialize(format="pretty-xml"))
        f.close()

        

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

    # Status just nu (090820, markerade med * borde kunna fixas n�gorlunda enkelt)
    #
    # ..................NF........N.............................................N.....N..F..N.........NN..
    #  91/100
    # Failed tests:
    # test/SFS\Parse\definition-paranthesis-multiple.txt *
    # test/SFS\Parse\definition-paranthesis-twoparas.txt *
    # test/SFS\Parse\extra-overgangsbestammelse-med-rubriker.txt
    # test/SFS\Parse\tricky-felformatterad-tabell.txt
    # test/SFS\Parse\tricky-lista-not-rubriker-2.txt
    # test/SFS\Parse\tricky-lopande-rubriknumrering.txt *
    # test/SFS\Parse\tricky-okand-aldre-lag.txt
    # test/SFS\Parse\tricky-tabell-overgangsbest.txt *
    # test/SFS\Parse\tricky-tabell-sju-kolumner.txt
    def TestParse(self,data,verbose=None,quiet=None):
        # FIXME: Set this from FilebasedTester
        if verbose == None:
            verbose=False
        if quiet == None:
            #quiet=True
            pass

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
        elements = p._count_elements(b)
        if 'K' in elements and elements['K'] > 1 and  elements['P1'] < 2:
            # should be "skipfragments = ['A','K']", but this breaks test cases
            skipfragments = ['A','K']
        else:
            skipfragments = ['A']
        p._construct_ids(b, u'', u'http://rinfo.lagrummet.se/publ/sfs/9999:999', skipfragments)
        #import simplejson as json
        #return json.dumps(b)
        return serialize(b)            

    def TestSerialize(self, data):
        return serialize(deserialize(data,globals()))

    def TestRender(self,data):
        meta = Forfattningsinfo()
        #meta[u'Utgivare'] = UnicodeSubject(u'Testutgivare',uri='http://example.org/')
        #meta[u'Utf�rdad'] = date(2008,1,1)
        #meta[u'F�rarbeten'] = []
        #meta[u'Rubrik'] = u'Lag (2008:1) om adekvata enhetstester' 
        #meta[u'xml:base'] = u'http://example.org/publ/sfs/9999:999' 
        body = deserialize(data,globals())
        registry = Register()
        p = SFSParser()
        p.id = '(test)'
        return unicode(p.generate_xhtml(meta,body,registry,__moduledir__,globals()),'utf-8')

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

    def _indexpages_predicates(self):
        return [Util.ns['dct']+"title",
                Util.ns['rinfo']+'fsNummer',
                Util.ns['rdf']+'type',
                Util.ns['rinfo']+'KonsolideradGrundforfattning']
                
    
    def _build_indexpages(self, by_pred_obj, by_subj_pred):
        documents = defaultdict(lambda:defaultdict(list))
        pagetitles = {}
        pagelabels = {}
        fsnr_pred  = Util.ns['rinfo']+'fsNummer'
        title_pred = Util.ns['dct']+'title'
        type_pred  = Util.ns['rdf']+'type'
        type_obj   = Util.ns['rinfo']+'KonsolideradGrundforfattning'
        year_lbl  = u'Ordnade efter utgivnings�r'
        title_lbl = u'Ordnade efter titel'
        # construct the 404 page - we should really do this in the
        # form of a xht2 page that gets transformed using static.xsl,
        # but it's tricky to get xslt to output a href attribute with
        # an embedded (SSI) comment.
        doc = u'''<?xml version="1.0"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd"><html xmlns="http://www.w3.org/1999/xhtml" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:rinfo="http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#" xmlns:xsd="http://www.w3.org/2001/XMLSchema#" xmlns:rinfoex="http://lagen.nu/terms#" xml:lang="sv" lang="sv"><head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8" /><title>F�rfattningstext saknas | Lagen.nu</title><script type="text/javascript" src="/js/jquery-1.2.6.min.js"></script><script type="text/javascript" src="/js/jquery.treeview.min.js"></script><script type="text/javascript" src="/js/base.js"></script><link rel="shortcut icon" href="/img/favicon.ico" type="image/x-icon" /><link rel="stylesheet" href="/css/screen.css" media="screen" type="text/css" /><link rel="stylesheet" href="/css/print.css" media="print" type="text/css" /></head><body><div id="vinjett"><h1><a href="/">lagen.nu</a></h1><ul id="navigation"><li><a href="/nyheter/">Nyheter</a></li><li><a href="/index/">Lagar</a></li><li><a href="/dom/index/">Domar</a></li><li><a href="/om/">Om</a></li></ul><form method="get" action="http://www.google.com/custom"><p><span class="accelerator">S</span>�k:<input type="text" name="q" id="q" size="40" maxlength="255" value="" accesskey="S" /><input type="hidden" name="cof" value="S:http://blog.tomtebo.org/;AH:center;AWFID:22ac01fa6655f6b6;" /><input type="hidden" name="domains" value="lagen.nu" /><input type="hidden" name="sitesearch" value="lagen.nu" checked="checked" /></p></form></div><div id="colmask" class="threecol"><div id="colmid"><div id="colleft"><div id="dokument">
    
    <h1>F�rfattningstext saknas</h1>
    <p>Det verkar inte finnas n�gon f�rfattning med SFS-nummer
    <!--#echo var="REDIRECT_SFS" -->. Om den har funnits tidigare s�
    kanske den har blivit upph�vd?</p>
    <p>Om den har blivit upph�vd kan den finnas i sin sista lydelse p�
    Regeringskansliets r�ttsdatabaser:
    <a href="http://rkrattsbaser.gov.se/cgi-bin/thw?${HTML}=sfst_lst&amp;${OOHTML}=sfst_dok&amp;${SNHTML}=sfst_err&amp;${BASE}=SFST&amp;${TRIPSHOW}=format%3DTHW&amp;BET=<!--#echo var="REDIRECT_SFS" -->">S�k efter SFS <!--#echo var="REDIRECT_SFS" --></a>.</p>
    
  </div><div id="kommentarer"></div><div id="referenser"></div></div></div></div><div id="sidfot"><b>Lagen.nu</b> �r en privat webbplats. Informationen h�r �r	inte officiell och kan vara felaktig | <a href="/om/ansvarsfriskrivning.html">Ansvarsfriskrivning</a> | <a href="/om/kontakt.html">Kontaktinformation</a></div><script type="text/javascript">var gaJsHost = (("https:" == document.location.protocol) ? "https://ssl." : "http://www."); document.write(unescape("%3Cscript src='" + gaJsHost + "google-analytics.com/ga.js' type='text/javascript'%3E%3C/script%3E"));</script><script type="text/javascript">var pageTracker = _gat._getTracker("UA-172287-1"); pageTracker._trackPageview();</script></body></html>'''

        outfile = "%s/%s/generated/notfound.shtml" % (self.baseDir, self.moduleDir)
        fp = codecs.open(outfile,"w",encoding='utf-8')
        fp.write(doc)
        fp.close()
        log.info("wrote %s" % outfile)


        # list all subjects that are of rdf:type rinfo:KonsolideradGrundforfattning
        for subj in by_pred_obj[type_pred][type_obj]:
            fsnr  = by_subj_pred[subj][fsnr_pred]
            title = by_subj_pred[subj][title_pred]

            sorttitle = re.sub(ur'Kungl\. Maj:ts ','',title)
            sorttitle = re.sub(ur'^(Lag|F�rordning|Tillk�nnagivande|[kK]ung�relse) ?\([^\)]+\) ?(av|om|med|ang�ende) ','',sorttitle)
            year = fsnr.split(':')[0]
            letter = sorttitle[0].lower()

            pagetitles[year] = u'F�rfattningar utgivna %s' % year
            pagelabels[year] = year
            documents[year_lbl][year].append({'uri':subj,
                                              'sortkey':fsnr,
                                              'title':title})

            if letter.isalpha():
                pagetitles[letter] = u'F�rfattningar som b�rjar p� "%s"' % letter.upper()
                pagelabels[letter] = letter.upper()
                documents[title_lbl][letter].append({'uri':subj,
                                                     'sortkey':sorttitle.lower(),
                                                     'title':sorttitle,
                                                     'leader':title.replace(sorttitle,'')})

        # FIXME: port the 'Nyckelbegrepp' code from 1.0
        #        import the old etiketter data and make a tag cloud or something 
        
        for category in documents.keys():
            for pageid in documents[category].keys():
                outfile = "%s/%s/generated/index/%s.html" % (self.baseDir, self.moduleDir, pageid)
                title = pagetitles[pageid]
                if category == year_lbl:
                    self._render_indexpage(outfile,title,documents,pagelabels,category,pageid,docsorter=Util.numcmp)
                else:
                    self._render_indexpage(outfile,title,documents,pagelabels,category,pageid)
                    if pageid == 'a': # make index.html
                        outfile = "%s/%s/generated/index/index.html" % (self.baseDir, self.moduleDir)
                        self._render_indexpage(outfile,title,documents,pagelabels,category,pageid)

    re_message = re.compile(r'(\d+:\d+) \[([^\]]*)\]')
    re_qname = re.compile(r'(\{.*\})(\w+)')
    re_sfsnr = re.compile(r'\s*(\(\d+:\d+\))')

    def _build_newspages(self,messages):
        changes = {}
        all_entries = []
        lag_entries = []
        ovr_entries = []
        for (timestamp,message) in messages:
            m = self.re_message.match(message)
            change = m.group(1)
            if change in changes:
                continue
            changes[change] = True
            bases = m.group(2).split(", ")
            basefile = "%s/%s/parsed/%s.xht2" % (self.baseDir, self.moduleDir, SFSnrToFilename(bases[0]))
            # print "opening %s" % basefile
            if not os.path.exists(basefile):
                # om inte den parseade filen finns kan det bero p� att
                # f�rfattningen �r upph�vd _eller_ att det blev n�got
                # fel vid parseandet.
                log.warning("File %s not found" % basefile)
                continue
            tree,ids = ET.XMLID(open(basefile).read())

            if (change != bases[0]) and (not 'L'+change in ids):
                log.warning("ID %s not found in %s" % ('L'+change,basefile))
                continue

            if change != bases[0]:
                for e in ids['L'+change].findall(".//{http://www.w3.org/2002/06/xhtml2/}dd"):
                    if 'property' in e.attrib and e.attrib['property'] == 'dct:title':
                        title = e.text
            else:
                title = tree.find(".//{http://www.w3.org/2002/06/xhtml2/}title").text

            # use relative, non-rinfo uri:s here - since the atom
            # transform wont go through xslt and use uri.xslt
            uri = u'/%s' % bases[0]
            
            for node in ids['L'+change]:
                m = self.re_qname.match(node.tag)
                if m.group(2) == 'dl':
                    content = self._element_to_string(node)

            entry = {'title':title,
                     'timestamp':timestamp,
                     'id':change,
                     'uri':uri,
                     'content':u'<p><a href="%s">F�rfattningstext</a></p>%s' % (uri, content)}
            all_entries.append(entry)

            basetitle = self.re_sfsnr.sub('',title)
            # print "%s: %s" % (change, basetitle)
            if (basetitle.startswith('Lag ') or
                (basetitle.endswith('lag') and not basetitle.startswith(u'F�rordning')) or
                basetitle.endswith('balk')):
                lag_entries.append(entry)
            else:
                ovr_entries.append(entry)

        htmlfile = "%s/%s/generated/news/all.html" % (self.baseDir, self.moduleDir)
        atomfile = "%s/%s/generated/news/all.atom" % (self.baseDir, self.moduleDir)
        self._render_newspage(htmlfile, atomfile, u'Nya och andrade forfattningar', 'De senaste 90 dagarna', all_entries)

        htmlfile = "%s/%s/generated/news/lagar.html" % (self.baseDir, self.moduleDir)
        atomfile = "%s/%s/generated/news/lagar.atom" % (self.baseDir, self.moduleDir)
        self._render_newspage(htmlfile, atomfile, u'Nya och �ndrade lagar', 'De senaste 90 dagarna', lag_entries)

        htmlfile = "%s/%s/generated/news/forordningar.html" % (self.baseDir, self.moduleDir)
        atomfile = "%s/%s/generated/news/forordningar.atom" % (self.baseDir, self.moduleDir)
        self._render_newspage(htmlfile, atomfile, u'Nya och �ndrade f�rordningar och �vriga f�rfattningar', 'De senaste 90 dagarna', ovr_entries)

    def _element_to_string(self,e):
        """Creates a XHTML1 string from a elementtree.Element,
        removing namespaces and rel/propery attributes"""
        m = self.re_qname.match(e.tag)
        tag = m.group(2)

        if e.attrib.keys():
            attributestr = " " + " ".join([x+'="'+e.attrib[x].replace('"','&quot;')+'"' for x in e.attrib.keys() if x not in ['rel','property']])
        else:
            attributestr = ""

        childstr = u''
        for child in e:
            childstr += self._element_to_string(child)

        text = ''
        tail = ''
        if e.text:
            text = cgi.escape(e.text)
        if e.tail:
            tail = cgi.escape(e.tail)
        return "<%s%s>%s%s%s</%s>" % (tag,attributestr,text,childstr,tail,tag)

    ################################################################
    # PURELY INTERNAL FUNCTIONS
    ################################################################

    def __listfiles(self,source,basename):
        """Given a SFS id, returns the filenames within source dir that
        corresponds to that id. For laws that are broken up in _A and _B
        parts, returns both files"""
        templ = "%s/sfs/downloaded/%s/%s%%s.html" % (self.baseDir,source,basename)
        return [templ%f for f in ('','_A','_B') if os.path.exists(templ%f)]


if __name__ == "__main__":
    import logging.config
    logging.config.fileConfig(__scriptdir__ + '/etc/log.conf')
    SFSManager.__bases__ += (DispatchMixin,)
    mgr = SFSManager()
    mgr.Dispatch(sys.argv)


