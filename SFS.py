#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Hanterar (konsoliderade) f�rfattningar i SFS fr�n Regeringskansliet
r�ttsdatabaser.
"""
# system libraries
import sys, os, re
import shutil
from pprint import pprint
import types
import datetime
import codecs
from cStringIO import StringIO
from time import time
import pickle
import htmlentitydefs
import traceback
# Python 2.5 plz
import xml.etree.cElementTree as ET
# import cElementTree as ET
# import elementtree.ElementTree as ET


# 3rdparty libs
from genshi.template import TemplateLoader
from configobj import ConfigObj
from mechanize import Browser, LinkNotFoundError
from rdflib.Graph import Graph
from rdflib import Literal, Namespace, URIRef, RDF, RDFS


# my own libraries
import LegalSource 
import Util
from DispatchMixin import DispatchMixin
from TextReader import TextReader
from DataObjects import UnicodeStructure, CompoundStructure, MapStructure, TemporalStructure, OrdinalStructure, serialize

# from LegalRef import SFSRefParser,PreparatoryRefParser,ParseError

__version__ = (0,1)
__author__  = "Staffan Malmgren <staffan@tomtebo.org>"
__shortdesc__ = "F�rfattningar i SFS"
__moduledir__ = "sfs"



class Forfattning(CompoundStructure,TemporalStructure):
    pass
#     def __init__(self, ikrafttrader = None, upphor = None):
#         # self.parts = []
#         # self.index = 0
#         super(UnicodeStructure,self).__init__(value)
#         self.ikrafttrader = ikrafttrader
#         self.upphor = upphor

class Rubrik(UnicodeStructure,TemporalStructure):
    fragment_label = "R"

class Stycke(CompoundStructure):
    fragment_label = "S"
#    def __init__(self, value):
#        # self.parts = []
#        # self.index = 0
#        super(UnicodeStructure,self).__init__(value)
#        self.value = value


class Punktlista (CompoundStructure): pass

class NumreradLista (CompoundStructure): pass

class OnumreradLista (CompoundStructure): pass

class Preformatted(UnicodeStructure): pass

class Tabell(CompoundStructure): pass # each table row is a part

class TabellRad(CompoundStructure): pass # each table cell is a part

class Avdelning(CompoundStructure, OrdinalStructure):
    pass

class UpphavtKapitel(UnicodeStructure, OrdinalStructure):
    """Ett UpphavtKapitel �r annorlunda fr�n ett Kapitel vars expires
    �r i det f�rflutna p� s� s�tt att inget av den egentliga lagtexten
    finns kvar, bara en platsh�llare"""


class Kapitel(CompoundStructure, OrdinalStructure):
    fragment_label = "K"

class UpphavdParagraf(UnicodeStructure, OrdinalStructure):
    pass

# en paragraf har inget "eget" v�rde, bara ett nummer och ett eller flera stycken
class Paragraf(CompoundStructure, OrdinalStructure): 
    fragment_label = "P"

# kan inneh�lla n�stlade numrerade listor
class Listelement(CompoundStructure, OrdinalStructure): 
    fragment_label = "N"


class Overgangsbestammelser(CompoundStructure):
    def __init__(self, *args, **kwargs):
        self.rubrik = kwargs['rubrik'] if 'rubrik' in kwargs else u'�verg�ngsbest�mmelser'
    
class Overgangsbestammelse(CompoundStructure, OrdinalStructure):
    pass

class Register(CompoundStructure):
    """Inneh�ller lite metadata om en grundf�rfattning och dess
    efterf�ljande �ndringsf�rfattningar"""
    def __init__(self, *args, **kwargs):
        self.rubrik = kwargs['rubrik'] if 'rubrik' in kwargs else None
        super(Register,self).__init__(*args, **kwargs)

    

class Registerpost(MapStructure):
    """Metadata f�r en viss (�ndrings)f�rfattning: SFS-nummer,
    omfattning, f�rarbeten m.m 

    * sfsnr: en str�ng, exv u'1970:488'
    * ansvarigmyndighet: en str�ng, exv u'Justitiedepartementet L3'
    * rubrik: en str�ng, exv u'Lag (1978:488) om �ndring i lagen (1960:729) om upphovsr�tt till litter�ra och konstn�rliga verk'
    * ikraft: en date, exv datetime.date(1996, 1, 1)
    * overgangsbestammelse: True eller False
    * omfattning: en lista av nodeliknande saker i stil med
      [u'�ndr.', link(uri='http://www.lagen.nu/1960:729#P23', text=u'23' rel='modified'),
       u', ', link (uri='http://www.lagen.nu/1960:729#P24', text=u'24' rel='modified'),
       u'; ny ' link(uri='http://www.lagen.nu/1960:729#P24a' text=u'24 a' rel='added')]
    * forarbeten: en lista av nodeliknande saker i stil med
      [link(uri='http://www.lagen.nu/prop_1981/82:152', text=u'Prop. 1981/82:152'),
       u', ', link(uri='http://www.lagen.nu/KrU_1977/78:27', text=u'KrU_1977/78:27')]
    * celexnr: en node,  exv link(uri='http://www.eurlex.eu/393L0098', text=u'393L0098')
    """
    pass

class Forfattningsinfo(MapStructure):
    pass

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
    def __init__(self,baseDir="data"):
        self.dir = baseDir + "/%s/downloaded" % __moduledir__
        if not os.path.exists(self.dir): 
            Util.mkdir(self.dir)
        self.config = ConfigObj("%s/%s.ini" % (self.dir, __moduledir__))

        # Why does this say "super() argument 1 must be type, not classobj"
        # super(SFSDownloader,self).__init__()
        self.browser = Browser()

    
    def DownloadAll(self):
        start = 1600
        end = datetime.date.today().year
        self.browser.open("http://62.95.69.15/cgi-bin/thw?${HTML}=sfsr_lst&${OOHTML}=sfsr_dok&${SNHTML}=sfsr_err&${MAXPAGE}=26&${BASE}=SFSR&${FORD}=FIND&\xC5R=FR\xC5N+%s&\xC5R=TILL+%s" % (start,end))

        pagecnt = 1
        done = False
        while not done:
            print "Result page #%s" % pagecnt
            for l in (self.browser.links(text_regex=r'\d+:\d+')):
                self._downloadSingle(l.text)
                # self.browser.back()
            try:
                self.browser.find_link(text='Fler poster')
                self.browser.follow_link(text='Fler poster')
                pagecnt += 1
            except LinkNotFoundError:
                print "No next page link found, we must be done"
                done = True
        self._setLastSFSnr(self)


    def _setLastSFSnr(self,last_sfsnr=None):
        if not last_sfsnr:
            print "Looking for the most recent SFS nr"
            last_sfsnr = "1600:1"
            for f in Util.listDirs("%s/sfst" % self.dir, ".html"):

                tmp = self._findUppdateradTOM(FilenameToSFSnr(f[len(self.dir)+6:-5]), f)
                # FIXME: RFS1975:6 > 2008:1
                if tmp > last_sfsnr:
                    print "%s > %s (%s)" % (tmp, last_sfsnr, f)
                    last_sfsnr = tmp
        self.config['next_sfsnr'] = last_sfsnr 
        self.config.write()

    def DownloadNew(self):
        (year,nr) = [int(x) for x in self.config['next_sfsnr'].split(":")]
        done = False
        while not done:
            print "Looking for SFS %s:%s" % (year,nr)
            base_sfsnr = self._checkForSFS(year,nr)
            if base_sfsnr:
                self._downloadSingle(base_sfsnr)
                nr = nr + 1
            else:
                if datetime.date.today().year > year:
                    print "    Possible end-of-year condition"
                    base_sfsnr = self._checkForSFS(datetime.date.today().year, 1)
                    if base_sfsnr:
                        year = datetime.date.today().year
                        nr = 1 # actual downloading next loop
                    else:
                        print "    We're done"
                        done = True
                else:
                    print "    We're done"
                    done = True
        self._setLastSFSnr("%s:%s" % (year,nr))
                
    def _checkForSFS(self,year,nr):
        """Givet ett SFS-nummer, returnera SFS-numret f�r dess
        grundf�rfattning, eller None om det inte finns ett s�dant SFS-nummer"""
        # Titta f�rst efter grundf�rfattning
        print "    Checking for base"
        url = "http://62.95.69.15/cgi-bin/thw?${HTML}=sfsr_lst&${OOHTML}=sfsr_dok&${SNHTML}=sfsr_err&${MAXPAGE}=26&${BASE}=SFSR&${FORD}=FIND&${FREETEXT}=&BET=%s:%s&\xC4BET=&ORG=" % (year,nr)
        # FIXME: consider using mechanize
        self.browser.retrieve(url,"sfs.tmp")
        t = TextReader("sfs.tmp",encoding="iso-8859-1")
        try:
            t.cue(u"<p>S�kningen gav ingen tr�ff!</p>")
        except IOError: # hurra!
            return "%s:%s" % (year,nr)             

        # Sen efter �ndringsf�rfattning
        print "    Base not found, checking for amendment"
        url = "http://62.95.69.15/cgi-bin/thw?${HTML}=sfsr_lst&${OOHTML}=sfsr_dok&${SNHTML}=sfsr_err&${MAXPAGE}=26&${BASE}=SFSR&${FORD}=FIND&${FREETEXT}=&BET=&\xC4BET=%s:%s&ORG=" % (year,nr)
        self.browser.retrieve(url, "sfs.tmp")
        # maybe this is better done through mechanize?
        t = TextReader("sfs.tmp",encoding="iso-8859-1")
        try:
            t.cue(u"<p>S�kningen gav ingen tr�ff!</p>")
            print "    Amendment not found"
            return None
        except IOError:
            t.seek(0)
            t.cuepast(u'<input type="hidden" name="BET" value="')
            sfsnr = t.readto("$")
            print "    Amendment found (to %s)" % sfsnr
            return sfsnr

    def _downloadSingle(self, sfsnr):
        """Laddar ner senaste konsoliderade versionen av
        grundf�rfattningen med angivet SFS-nr. Om en tidigare version
        finns p� disk, arkiveras den."""
        print "    Downloading %s" % sfsnr
        # enc_sfsnr = sfsnr.replace(" ", "+")
        # Div specialhack f�r knepiga f�rfattningar
        if sfsnr == "1723:1016+1": parts = ["1723:1016"]
        elif sfsnr == "1942:740": parts = ["1942:740 A", "1942:740 B"]
        else: parts = [sfsnr]

        uppdaterad_tom = old_uppdaterad_tom = None
        for part in parts:
            sfst_url = "http://62.95.69.15/cgi-bin/thw?${OOHTML}=sfst_dok&${HTML}=sfst_lst&${SNHTML}=sfst_err&${BASE}=SFST&${TRIPSHOW}=format=THW&BET=%s" % part.replace(" ","+")
            sfst_file = "%s/sfst/%s.html" % (self.dir, SFSnrToFilename(part))
            # print "        Getting %s" % sfst_url
            self.browser.retrieve(sfst_url,"sfst.tmp")
            if os.path.exists(sfst_file):
                if (self._checksum(sfst_file) != self._checksum("sfst.tmp")):
                    old_uppdaterad_tom = self._findUppdateradTOM(sfsnr, sfst_file)
                    uppdaterad_tom = self._findUppdateradTOM(sfsnr, "sfst.tmp")
                    if uppdaterad_tom != old_uppdaterad_tom:
                        print "        %s has changed (%s -> %s)" % (sfsnr,old_uppdaterad_tom,uppdaterad_tom)
                        self._archive(sfst_file, sfsnr, old_uppdaterad_tom)

                    # replace the current file, regardless of wheter
                    # we've updated it or not
                    Util.robustRename("sfst.tmp", sfst_file)
                else:
                    pass # leave the current file untouched
            else:
                Util.robustRename("sfst.tmp", sfst_file)

        sfsr_url = "http://62.95.69.15/cgi-bin/thw?${OOHTML}=sfsr_dok&${HTML}=sfst_lst&${SNHTML}=sfsr_err&${BASE}=SFSR&${TRIPSHOW}=format=THW&BET=%s" % sfsnr.replace(" ","+")
        sfsr_file = "%s/sfsr/%s.html" % (self.dir, SFSnrToFilename(sfsnr))
        if uppdaterad_tom != old_uppdaterad_tom:
            self._archive(sfsr_file, sfsnr, old_uppdaterad_tom)

        Util.ensureDir(sfsr_file)
        self.browser.retrieve(sfsr_url, sfsr_file)
        
            
        
    def _archive(self, filename, sfsnr, uppdaterad_tom):
        """Arkivera undan filen filename, som ska vara en
        grundf�rfattning med angivet sfsnr och vara uppdaterad
        t.o.m. det angivna sfsnumret"""
        if sfsnr == "1942:740":
            two_parter_mode = True
        archive_filename = "%s/sfst/%s-%s.html" % (self.dir, SFSnrToFilename(sfsnr),
                                         SFSnrToFilename(uppdaterad_tom).replace("/","-"))
        print "        Archiving %s to %s" % (filename, archive_filename)

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
        """Given a SHA-1 checksum for (the plaintext part of) a downloaded file"""
        import sha
        c = sha.new()
        c.update(self._extractSFST([filename]))
        return c.hexdigest()

class SFSParser(LegalSource.Parser):
    re_SimpleSfsId     = re.compile(r'^\d{4}:\d+\s*$').match
    re_ChapterId       = re.compile(r'^(\d+( \w|)) [Kk]ap.').match
    re_DivisionId      = re.compile(r'^AVD. ([IVX]*)').match
    re_SectionId       = re.compile(r'^(\d+ ?\w?) �[ \.]') # used for both match+sub
    re_SectionIdOld    = re.compile(r'^� (\d+ ?\w?).')     # as used in eg 1810:0926
    re_DottedNumber    = re.compile(r'^(\d+)\. ').match
    re_NumberRightPara = re.compile(r'^(\d+)\) ').match
    re_ElementId       = re.compile(r'^(\d+) mom\.')        # used for both match+sub
    re_ChapterRevoked  = re.compile(r'^(\d+( \w|)) [Kk]ap. (upph�vd|har upph�vts) genom (f�rordning|lag) \([\d\:\. s]+\)\.$').match
    re_SectionRevoked  = re.compile(r'^(\d+ ?\w?) �[ \.]([Hh]ar upph�vts|[Nn]y beteckning (\d+ ?\w?) �) genom ([Ff]�rordning|[Ll]ag) \([\d\:\. s]+\)\.$').match
    re_RevokeDate      = re.compile(r'/Upph�r att g�lla U:(\d+)-(\d+)-(\d+)/')
    re_EntryIntoForceDate = re.compile(r'/Tr�der i kraft I:(d\+)-(\d+)-(\d+)/')
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


    
    def __init__(self):
        self.verbose = True
        self.authority_rec = self._load_authority_rec("authrec.n3")
    
    def _load_authority_rec(self, file):
        graph = Graph()
        graph.load(file, format='n3')
        d = {}
        for uri, label in graph.subject_objects(RDFS.label):
            d[unicode(label)] = str(uri)
        return d
    
    def Parse(self,basefile,files):
        self.id = FilenameToSFSnr(basefile)
        # find out when data was last fetched (use the oldest file)
        timestamp = sys.maxint
        for filelist in files.values():
            for file in filelist:
                if os.path.getmtime(file) < timestamp:
                    timestamp = os.path.getmtime(file)
        
        registry = self._parseSFSR(files['sfsr'])
        plaintext = self._extractSFST(files['sfst'])

        # FIXME: Maybe Parser classes should be directly told what the
        # current basedir is, rather than having to do it the ugly way
        # (c.f. RegPubParser.Parse, which does something similar to
        # the below
        plaintextfile = files['sfst'][0].replace(".html", ".txt").replace("downloaded/sfst", "intermediate")
        Util.ensureDir(plaintextfile)
        f = codecs.open(plaintextfile, "w",'iso-8859-1')
        f.write(plaintext)
        f.close()

        data = self._parseSFST(plaintextfile, registry)
        print serialize(data[1])
        xhtml = self._generate_xhtml(data)
        return xhtml

    def _parseSFSR(self,files):
        """Parsear ut det SFSR-registret som inneh�ller alla �ndringar i lagtexten fr�n HTML-filer"""
        all_attribs = []
        r = Register()
        for f in files:
            soup = Util.loadSoup(f)
            r.rubrik = Util.elementText(soup.body('table')[2]('tr')[1]('td')[0])
            changes = soup.body('table')[3:-2]
            for table in changes:
                p = Registerpost()
                for row in table('tr'):
                    key = Util.elementText(row('td')[0])
                    if key.endswith(":"):  key= key[:-1] # trim ending ":"
                    if key == '': continue
                    val = Util.elementText(row('td')[1]).replace(u'\xa0',' ') # no nbsp's, please
                    if val != "":
                        if key == u'SFS-nummer':
                            p['sfsnr'] = val
                        elif key == u'Ansvarig myndighet':
                            p['ansvarigmyndighet'] = val
                        elif key == u'Rubrik':
                            p['rubrik'] = val
                        elif key == u'Ikraft':
                            p['ikraft'] = datetime.datetime.strptime(val[:10], '%Y-%m-%d')
                            p['overgangsbestammelse'] = (val.find(u'\xf6verg.best.') != -1)
                        elif key == u'Omfattning':
                            # FIXME: run this through LegalRef
                            p['omfattning'] = val 
                        elif key == u'F\xf6rarbeten':
                            # FIXME: run this through LegalRef
                            p['forarbeten'] = val
                        elif key == u'CELEX-nr':
                            # FIXME: run this through LegalRef
                            p['celexnr'] = val
                        else:
                            print "    WARNING: Jag vet inte vad jag ska g�ra med raden '%s'" % key
                r.append(p)
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
        re_tags = re.compile("</?\w{1,3}>")
        txt = re_tags.sub(u'',txt)
        return txt + self._extractSFST(files[1:],keepHead=False)

    def _descapeEntity(self,m):
        return unichr(htmlentitydefs.name2codepoint[m.group(1)])

    # rekursera igenom dokumentet p� jakt efter adresserbara enheter
    # (kapitel, paragrafer, stycken, punkter) * konstruera xml:id's
    # f�r dem, (p� lagen-nu-formen s�l�nge, dvs K1P2S3N4 f�r 1 kap. 2
    # � 3 st. 4 p)
    def _construct_ids(self, element, prefix):
        cnt = 0
        if hasattr(element, 'parts'):
            for p in element.parts:
                cnt += 1
                if hasattr(p, 'fragment_label'):
                    elementtype = p.fragment_label
                    if hasattr(p, 'ordinal'):
                        elementordinal = p.ordinal.replace(" ","")
                    else:
                        elementordinal = cnt
                    fragment = "%s%s%s" % (prefix, elementtype, elementordinal)
                    p.id = fragment
                else:
                    fragment = prefix
                self._construct_ids(p,fragment)
            

    def _parseSFST(self, lawtextfile, registry):
        # self.reader = TextReader(ustring=lawtext,linesep=TextReader.UNIX)
        self.reader = TextReader(lawtextfile, encoding='iso-8859-1', linesep=TextReader.DOS)
        self.reader.autostrip = True

        self.current_section = u'0'
        head = self.makeHeader()
        body = self.makeForfattning()

        # FIXME:
        self._construct_ids(body,"")
        # * anv�nd dessa som URI-fragment och konstruera fullst�ndiga URI:er,
        # (* skapa rinfo:firstParagraph och rinfo:nextParagraph-p�st�enden)
    
        # massera metadatat halvv�gs till RDF-p�st�enden (FIXME: g�r en riktig RDF-graf)
        # FIXME: bryt ut till en egen funktion
        meta = {}
        
        
        # from domainutil import compute_canonical_uri
        # 
        # (check test_domainutil.py for info on how the rdf graph should look.
        # The uri should be the same as the main subject in the rdf graph and
        # can be on the form urn:uuid:4711)
        # meta['xml:base'] = compute_canonical_url(some_rdf_graph, some_other_uri)

        # FIXME: Hantera esoteriska headers som Tidsbegr�nsad, Omtryck, m.m.
        for key, predicate in ((u'Rubrik','dc:title'),
                              (u'SFS nr','rinfo:fsNummer'),
                              (u'Utf�rdad','rinfo:utfardandedatum')):

            try:
                meta[predicate] = head[key]
            except KeyError:
                meta[predicate] = u''

        meta['dc:publisher'] = self._find_authority_rec("Regeringskansliet")
        meta['dc:creator'] = self._find_authority_rec(head["Departement/ myndighet"])
        meta['rinfo:konsoliderar'] = self._storage_uri_value(
                "http://rinfo.lagrummet.se/data/sfs/%s" % head['SFS nr'])
        
        return meta, body

    def _generate_xhtml(self,data):
        """Skapa det f�rdiga XHTML2-dokumentet f�r en konsoliderad lagtext"""
        (meta, body) = data
        loader = TemplateLoader(['.' , os.path.dirname(__file__)]) # only look in cwd and this file's directory
        tmpl = loader.load("template.xht2")
        stream = tmpl.generate(meta=meta, body=body, **globals())
        return stream.render()

    def _find_authority_rec(self, label):
        """Givet en textstr�ng som refererar till n�gon typ av
        organisation, person el. dyl (exv 'Justitiedepartementet
        Gransk', returnerar en URI som �r auktoritetspost f�r denna."""
        for (key, value) in self.authority_rec.items():
            if label.startswith(key):
                return self._storage_uri_value(value)
        raise KeyError(label)

    def _storage_uri_value(self, value):
        return value.replace(" ", '_')


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
        for numeral, integer in self.romanNumeralMap:
            while s[index:index+len(numeral)] == numeral:
                result += integer
                index += len(numeral)
        return result


    #----------------------------------------------------------------
    #
    # SFST-PARSNING


    def makeHeader(self):
        subreader = self.reader.getreader(self.reader.readchunk, self.reader.linesep * 3)
        # FIXME: consider using a MapStructure subclass
        i = Forfattningsinfo()

        for line in subreader.getiterator(subreader.readparagraph):
            if ":" in line:
                (key,value) = [Util.normalizeSpace(x) for x in line.split(":",1)]
                i[key] = value
        
        return i


    def makeForfattning(self):
        b = Forfattning()
        while not self.reader.eof():
            state_handler = self.guess_state()
            res = state_handler()
            if res != None:
                b.append(res)
        return b

    def makeAvdelning(self):
        avdelningsnummer = self.idOfAvdelning()
        p = Avdelning(rubrik = self.reader.readline(),
                      ordinal = avdelningsnummer,
                      subheading = None)
        if self.reader.peekline(1) == "" and self.reader.peekline(3) == "":
            self.reader.readline()
            p.subheading = self.reader.readline()

        if self.verbose: sys.stdout.write(u"  Ny avdelning: '%s...'\n" % p.rubrik[:30])

        while not self.reader.eof():
            state_handler = self.guess_state()
            if state_handler == self.makeAvdelning: # Ny avdelning betyder att den f�rra �r avslutad
                if self.verbose: sys.stdout.write(u"  Avdelning %s f�rdig\n" % p.ordinal)
                return p
            else:
                res = state_handler()
                if res != None:
                    p.append(res)
        # if eof is reached
        return p
        
    def makeUpphavtKapitel(self):
        kapitelnummer = self.idOfKapitel()
        c = UpphavtKapitel(value=self.reader.readline(),
                           ordinal = kapitelnummer)
        if self.verbose: sys.stdout.write(u"  Upph�vt kapitel: '%s...'\n" % c[:30])

        return c
    
    def makeKapitel(self):
        kapitelnummer = self.idOfKapitel()

        para = self.reader.readparagraph()
        (line, upphor, ikrafttrader) = self.andringsDatum(para)
        
        today = datetime.date.today()
        kwargs = {'rubrik':  line,
                  'ordinal': kapitelnummer}
        if upphor: kwargs['upphor'] = upphor
        if ikrafttrader: kwargs['ikrafttrader'] = ikrafttrader
        k = Kapitel(**kwargs)

        if upphor and upphor < today:
            k.inaktuell = True
        elif ikrafttrader and ikrafttrader > today():
            k.inaktuell = True
        
        if self.verbose: sys.stdout.write(u"    Nytt kapitel: '%s...'\n" % line[:30])
        
        while not self.reader.eof():
            state_handler = self.guess_state()

            if state_handler in (self.makeKapitel, self.makeAvdelning): # a new chapter (or part) signals the end of this chapter
                if self.verbose: sys.stdout.write(u"    Kapitel %s f�rdigt\n" % k.ordinal)
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
        h = Rubrik(line,
                   upphor = upphor,
                   ikrafttrader = ikrafttrader)
        return h

    def makeUpphavdParagraf(self):
        paragrafnummer = self.idOfParagraf(self.reader.peekline())
        p = UpphavdParagraf(value=self.reader.readline(),
                            ordinal = paragrafnummer)
        if self.verbose: sys.stdout.write(u"      Upph�vd paragraf: '%s...'\n" % p[:30])
        return p
    
    def makeParagraf(self):
        paragrafnummer = self.idOfParagraf(self.reader.peekline())
        self.current_section = paragrafnummer
        firstline = self.reader.peekline()
        if self.verbose: sys.stdout.write(u"      Ny paragraf: '%s...'\n" % firstline[:30])
        # trim of section numbering
        if self.re_SectionIdOld.match(firstline):
            firstline = self.re_SectionIdOld.sub('',firstline)
        else:
            firstline = self.re_SectionId.sub('',firstline)

        # some really old laws have sections split up in "elements"
        # (moment), eg '1 � 1 mom.', '1 � 2 mom.' etc
        match = self.re_ElementId.match(firstline)
        if self.re_ElementId.match(firstline):
            momentnummer = match.group(1)
            firstline = self.re_ElementId.sub('',firstline)
        else:
            momentnummer = None

        (firstline, upphor, ikrafttrader) = self.andringsDatum(firstline)
        today = datetime.date.today()
        kwargs = {'ordinal': paragrafnummer}
        if upphor: kwargs['upphor'] = upphor
        if ikrafttrader: kwargs['ikrafttrader'] = ikrafttrader
        p = Paragraf(**kwargs)

        if upphor and upphor < today:
            p.inaktuell = True
        elif ikrafttrader and ikrafttrader > today:
            p.inaktuell = True
            
        if momentnummer:
            p.moment = momentnummer

        state_handler = self.makeStycke
        res = self.makeStycke()
        p.append(res)

        while not self.reader.eof():
            state_handler = self.guess_state()
            if state_handler in (self.makeParagraf,
                                 self.makeUpphavdParagraf,
                                 self.makeKapitel,
                                 self.makeUpphavdParagraf,
                                 self.makeAvdelning,
                                 self.makeRubrik,
                                 self.makeOvergangsbestammelser):
                if self.verbose: sys.stdout.write(u"      Paragraf %s f�rdig\n" % paragrafnummer)
                return p
            elif state_handler in (self.makeNumreradLista,
                                   self.makePunktlista):
                res = state_handler()
                p[-1].append(res)
            else:
                assert(state_handler == self.makeStycke)
                #if state_handler != self.makeStycke:
                #    sys.stdout.write(u"VARNING: behandlar '%s...' som stycke, inte med %s\n" % (lines[0][:30], state_handler.__name__))
                res = self.makeStycke()
                p.append(res)

        # eof occurred
        return p

    def makeStycke(self):
        if self.verbose: sys.stdout.write(u"        Nytt stycke: '%s...'\n" % self.reader.peekline()[:30])
        s = Stycke([self.reader.readparagraph()])
        return s

    def makeNumreradLista(self): 
        n = NumreradLista()
        while not self.reader.eof():
            state_handler = self.guess_state()
            if state_handler not in (self.blankline, self.makeNumreradLista):
                return n
            elif state_handler == self.blankline:
                res = state_handler()
            else:
                if self.verbose: sys.stdout.write(u"          Ny listpunkt: '%s...'\n" % self.reader.peekline()[:30])
                listelement_ordinal = self.idOfNumreradLista()
                li = Listelement(text=self.reader.readparagraph(), ordinal = listelement_ordinal)
                n.append(li)
                if self.verbose: sys.stdout.write(u"          Listpunkt %s avslutad\n" % listelement_ordinal)
        return n


    def makePunktlista(self):
        n = Punktlista()
        cnt = 0
        while not self.reader.eof():
            state_handler = self.guess_state()
            if state_handler not in (self.blankline, self.makePunktlista):
                return n
            elif state_handler == self.blankline:
                res = state_handler()
            else:
                if self.verbose: sys.stdout.write(u"          Ny listpunkt: '%s...'\n" % self.reader.peekline()[:30])
                cnt += 1
                li = Listelement(self.reader.readparagraph(), ordinal = str(cnt))
                if self.verbose: sys.stdout.write(u"          Listpunkt #%s avslutad\n" % cnt)
        return n


    def blankline(self):
        self.reader.readline()
        return None

    #def eof(self, lines):
    #    return(None, lines)

    def makeOvergangsbestammelser(self): # svenska: �verg�ngsbest�mmelser
        # det kan diskuteras om dessa ska ses som en del av den
        # konsoliderade lagtexten �ht, men det verkar vara kutym att
        # ha med �tminstone de som kan ha relevans f�r g�llande r�tt

        # TODO: hantera detta
        sys.stdout.write(u"    Ny �verg�ngsbest�mmelser\n")

        rubrik = self.reader.readparagraph()
        obs = Overgangsbestammelser(rubrik)
        
        for p in self.reader.getiterator(self.reader.readparagraph):
            pass
        
        return None

    def makeOvergangsbestammelse(self):
        pass
        

    def makeBilaga(self): # svenska: bilaga
        for p in self.reader.getiterator(self.reader.readparagraph):
            pass
        return None

    def andringsDatum(self,line):
        ikrafttrader = None
        upphor = None
        m = self.re_RevokeDate.search(line)
        if m:
            upphor = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            line = self.re_RevokeDate.sub("", line) 
        m = self.re_EntryIntoForceDate.search(line)
        if m:
            ikrafttrader = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            line = self.re_EntryIntoForceDate.sub("", line) 
        return (line, upphor, ikrafttrader)

    
    def guess_state(self):
        # sys.stdout.write("        Guessing for '%s...'" % self.reader.peekline()[:30])
        if self.reader.peekline() == "":     handler = self.blankline
        elif self.isAvdelning():             handler = self.makeAvdelning
        elif self.isUpphavtKapitel():        handler = self.makeUpphavtKapitel
        elif self.isUpphavdParagraf():       handler = self.makeUpphavdParagraf
        elif self.isKapitel():               handler = self.makeKapitel
        elif self.isParagraf():              handler = self.makeParagraf
        elif self.isTabell():                handler = self.makeTabell
        elif self.isOvergangsbestammelser(): handler = self.makeOvergangsbestammelser
        elif self.isNumreradLista():         handler = self.makeNumreradLista
        elif self.isPunktlista():            handler = self.makePunktlista
        elif self.isRubrik():                handler = self.makeRubrik
        else:                                handler = self.makeStycke
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
        # 1999:1229: "AVD. I INNEH�LL OCH DEFINITIONER"
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
        # (1982:713 1 a kap. 7 �)
        #m = re.match(r'^(\d+( \w|)) [Kk]ap.',p)
        m = self.re_ChapterId(p)
        if m:
            # even though something might look like the start of a chapter, it's often just the
            # start of a paragraph in a section that lists the names of chapters. These following
            # attempts to filter these out by looking for some typical line endings for those cases
            if (p.endswith(",") or
                p.endswith(";") or
                p.endswith(")") or
                p.endswith("och") or # in unlucky cases, a chapter heading might span two lines in a way that the first line ends with "och" (eg 1998:808 kap. 3)
                p.endswith("om") or
                p.endswith("samt") or
                (p.endswith(".") and not
                 (m.span()[1] == len(p) or # if the ENTIRE p is eg "6 kap." (like it is in 1962:700)
                  p.endswith("m.m.") or
                  p.endswith("m. m.") or
                  self.re_ChapterRevoked(p)))): # If the entire chapter's
                                           # been revoked, we still
                                           # want to count it as a
                                           # chapter

                # sys.stdout.write(u"chapter_id: '%s' failed second check" % p)
                return None
            else:
                return m.group(1)
        else:
            # sys.stdout.write(u"chapter_id: '%s' failed first check" % p[:40])
            return None

    def isRubrik(self, p=None):
        if not p:
            p = self.reader.peekparagraph()
        
        if len(p) > 100: # it shouldn't be too long
            return False

        if self.isParagraf(): # A headline should not look like the start of a paragraph
            return False

        if (p.endswith(".") and # a headline never ends with a period, unless it ends with "m.m." or similar
            not (p.endswith("m.m.") or 
                 p.endswith("m. m.") or 
                 p.endswith("m.fl.") or 
                 p.endswith("m. fl."))):
            return False 

        if (p.endswith(",") or  # a headline never ends with these characters
            p.endswith(":") or 
            p.endswith("samt") or 
            p.endswith("eller")):
            return False

        if  (not self.isParagraf(self.reader.peekparagraph())): # finally, it should be followed by a paragraph 
            return False
        
        # ok, all tests passed, this might be a headline!
        return True

    def isUpphavdParagraf(self):
        match = self.re_SectionRevoked(self.reader.peekline())
        return match != None

    def isParagraf(self, p=None):
        if not p:
            p = self.reader.peekparagraph()

        paragrafnummer = self.idOfParagraf(p)
        if paragrafnummer == None:
            return False
        if paragrafnummer == '1':
            # if self.verbose: sys.stdout.write(u"is_section: The section numbering's restarting\n")
            return True
        # now, if this sectionid is less than last section id, the
        # section is probably just a reference and not really the
        # start of a new section. One example of that is
        # /1991:1469#K1P7S1.
        #
        # FIXME: "10" should be larger than "9"
        if cmp(self.current_section, paragrafnummer) <= 0:
            # ok, the sort order's still the same, which means the potential new section has a larger ID
            # sys.stdout.write(u"is_section: '%s' looks like the start of the section, and it probably is (%s < %s)" % (lines[0][:30], self.current_section, paragrafnummer))
            return True
        else:
            # sys.stdout.write(u"is_section: Even though '%s' looks like the start of the section, the numbering's wrong (%s > %s)" % (lines[0][:30], self.current_section, paragrafnummer))
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

    def isTabell(self):
        return False

    def makeTabell(self):
        return None

    def isFastbredd(self):
        return False
    
    def makeFastbredd(self):
        return None

    def isNumreradLista(self):
        return self.idOfNumreradLista() != None

    def idOfNumreradLista(self):
        p = self.reader.peekline()
        match = self.re_DottedNumber(p)

        if match != None:
            return match.group(1).replace(" ", "")
        else:
            match = self.re_NumberRightPara(p)
            if match != None:
                return match.group(1).replace(" ", "")
        return None

    def isPunktlista(self):
        p = self.reader.peekline()
        return (p.startswith("- ") or
                p.startswith("--"))


    def isPreformatted(self):
        # Preformatted sections are usually tables, but so complex that
        # it's too hard to convert them to proper tables, therefore we
        # punt and just preformat the section.
        tabstops = self.find_tabstops(self.reader.peekline())
        if tabstops == []: # means there were no lines, ie p was empty string. shouldn't happen.
            # sys.stdout.write(u"Returning False")
            return False
        for tabstops_line in tabstops:
            if len(tabstops_line) > 1:
                # sys.stdout.write(u"is_preformatted: this is a complex line")
                return True

        return False

    def isOvergangsbestammelser(self):
        #p = self.reader.peekline()
        #print "%r == %r: %r" % (u"�verg�ngsbest�mmelser", p[:30], p == u"�verg�ngsbest�mmelser")
        return self.reader.peekline() == u"�verg�ngsbest�mmelser"


    def isBilaga(self):
        return (self.reader.peekline in (u"Bilaga", u"Bilaga 1"))

        
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
        e.attrib['law'] = context['sfsnr']
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
        return FilenameToSFSnr(basefile)

    def _basefileToDisplayId(self,basefile, urnprefix):    
        assert(urnprefix == u'urn:x-sfs')
        return FilenameToSFSnr(basefile)
        
    def _basefileToUrn(self, basefile, urnprefix):        
        assert(urnprefix == u'urn:x-sfs')
        return u'urn:x-sfs:%s' % FilenameToSFSnr(basefile).replace(' ','_')
        
    def _displayIdToBasefile(self,displayid, urnprefix):        
        assert(urnprefix == u'urn:x-sfs')
        return SFSnrToFilename(displayid)
        
    def _displayIdToURN(self,displayid, urnprefix):        
        assert(urnprefix == u'urn:x-sfs')
        return u'urn:x-sfs:%s' % displayid.replace(' ','_')
    
    def _UrnToBasefile(self,urn):
        return SFSnrToFilename(self._UrnToDisplayId(urn))
        
    def _UrnToDisplayId(self,urn):
        return urn.split(':',2)[-1].replace('_',' ')
        
    def _getModuleDir(self):
        return __moduledir__
    ####################################################################
    # IMPLEMENTATION OF Manager INTERFACE
    ####################################################################    

    def Parse(self, basefile, verbose=False, force=False):
        try:
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
        except Exception,e :
            # Log this properly
            print (" Exception:\nType: %s\nValue: %s\nTraceback:\n %s" % (sys.exc_info()[0],
                                                                          sys.exc_info()[1],
                                                                          "".join(traceback.format_tb(sys.exc_info()[2]))))
        finally: 
            if not verbose: sys.stdout.write("\t%s seconds\n" % (time()-start))

    def ParseAll(self):
        # print "SFS: ParseAll temporarily disabled"
        # return
        self.__doAll('downloaded/sfst','html',self.Parse)

    def ParseTest(self,testfile,verbose=False, quiet=False):
        if not quiet:
            print "\n\n\nRunning test %s\n------------------------------" % testfile
        p = SFSParser()
        p.verbose = verbose
        p.reader = TextReader(testfile,encoding='iso-8859-1',linesep=TextReader.DOS)
        p.reader.autostrip=True
        b = p.makeForfattning()
        testlines = serialize(b).split("\n")
        #pprint(testlines)
        keyfile = testfile.replace(".txt",".xml")
        if os.path.exists(keyfile):
            keylines = [x.rstrip('\r\n') for x in codecs.open(keyfile,encoding='utf-8').readlines()]
        else:
            keylines = []
        #pprint(keylines)
        from difflib import Differ
        difflines = list(Differ().compare(testlines,keylines))
        diffedlines = [x for x in difflines if x[0] != ' ']
        if len(diffedlines) > 0:
            if quiet:
                sys.stdout.write("F")
            else:
                print "FAIL %s" % testfile
                sys.stdout.write(u'\n'.join([x.rstrip('\n') for x in difflines]))
            return False
        else:
            if quiet:
                sys.stdout.write(".")
            else:
                print "OK %s" % testfile
            return True
        


    def ParseTestAll(self):
        res = []
        for f in Util.listDirs("test/data/SFS", ".txt"):
            res.append(self.ParseTest(f,verbose=False,quiet=True))

        succeeded = len([r for r in res if r])
        all       = len(res)
        print "\n%s/%s" % (succeeded,all)

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
        sanitized_sfsnr = basefile.replace(' ','.')
        print "Transforming %s > %s" % (infile,outfile)
        Util.mkdir(os.path.dirname(outfile))
        Util.transform("xsl/sfs.xsl",
                       infile,
                       outfile,
                       {'lawid': sanitized_sfsnr,
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

        # Find out wheter � numbering is continous for the whole law text
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
        context = {'sfsnr':     displayid,
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
                        self._createReference(basefile,targetUrn,sourceUrn,u'�ndringar', context['changeid'])
                        referenceCount += 1
                    except IdNotFound:
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
                    #    # we need to use __formatFragmentId to get a good displayid here
                    #    self._createReference(basefile,targetUrn,sourceUrn,u'H�nvisningar', 'source')
                    #    referenceCount += 1
                    #except IdNotFound:
                    #    pass
                    # sys.stdout.write(".")
                    pass
        sys.stdout.write("\tcreated %s references\tin %s seconds\n" % (referenceCount,(time()-start)))
        self._flushReferenceCache()
    
    def RelateAll(self):
        # print "SFS: RelateAll temporarily disabled"
        # return
        self.__doAll('parsed','xml',self.Relate)

    def Download(self,id):
        sd = SFSDownloader(self.baseDir)
        sd._downloadSingle(id)

    def DownloadAll(self):
        sd = SFSDownloader(self.baseDir)
        sd.DownloadAll()

    def DownloadNew(self):
        sd = SFSDownloader(self.baseDir)
        sd.DownloadNew()
    
    


if __name__ == "__main__":
    if not '__file__' in dir():
        print "probably running from within emacs"
        sys.argv = ['SFS.py','Parse', '1960/729']
    
    SFSManager.__bases__ += (DispatchMixin,)
    mgr = SFSManager("tesdtata",__moduledir__)
    mgr.Dispatch(sys.argv)


