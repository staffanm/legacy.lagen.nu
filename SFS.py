#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Hanterar författningar i SFS från Regeringskansliet rättsdatabaser.
"""
# system libraries
import sys, os, re
import shutil
import unittest
import pprint
import types
import datetime
from cStringIO import StringIO

# 3rdparty libs
sys.path.append('3rdparty')
import BeautifulSoup
import elementtree.ElementTree as ET

# my own libraries
import LegalSource
import Util
from DispatchMixin import DispatchMixin
from DocComments import AnnotatedDoc

__version__ = (0,1)
__author__  = "Staffan Malmgren <staffan@tomtebo.org>"
__shortdesc__ = "Författningar i SFS"
__moduledir__ = "sfs"

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
    attributemapping = {
        "Rubrik"                           : "title",
        "SFS nr"                           : "sfsid",
        "Departement/ myndighet"           : "dept",
        "Utfärdad"                         : "issued",
        "Ändring införd"                   : "containedchanges",
        "Författningen har upphävts genom" : "revokedby",
        "Upphävd"                          : "revoked",
        "Övrigt"                           : "other",
        "Omtryck"                          : "reprint",
        "Tidsbegränsad"                    : "timelimited"
    }    
    re_SimpleSfsId     = re.compile(r'^\d{4}:\d+\s*$').match
    re_ChapterId       = re.compile(r'^(\d+( \w|)) [Kk]ap.').match
    re_DivisionId      = re.compile(r'^AVD. ([IVX]*)').match
    re_SectionId       = re.compile(r'^(\d+ ?\w?) §[ \.]') # used for both match+sub
    re_SectionIdOld    = re.compile(r'^§ (\d+ ?\w?).')     # as used in eg 1810:0926
    re_DottedNumber    = re.compile(r'^(\d+)\. ').match
    re_NumberRightPara = re.compile(r'^(\d+)\) ').match
    re_ElementId       = re.compile(r'^(\d+) mom\.')        # used for both match+sub
    re_ChapterRevoked  = re.compile(r'^(\d+( \w|)) [Kk]ap. (upphävd|har upphävts) genom (förordning|lag) \([\d\:\. s]+\)\.$').match
    
    
    
    def Parse(self,id,files,baseDir):
        self.id = id
        self.baseDir = baseDir
        self.verbose = True

        # extract lawtext (handle twoparter mode here)
        txtfilename = files[0].replace("downloaded","generated-text").replace(".html", ".txt")
        lawtext = file(txtfilename).read()

        # extract and parse bibliography (AKA changelog)
        self.bibliography = self.__parseBiography()
        
        # parse lawtext
        self.lawtext = self.__parseLawtext(lawtext)
        
        # write it to XML
        
    
    def __extractLawtext(self, files = []):
        parse
    
    def __parseLawtext(self, lawtext):
        # adapted from _init() in extract.py
        
        paras = lawtext.split("\n\n")
        index = 0
        self.preamble = []
        self.lawtext = []
        self.transitional = []
        self.appendix = []
        self.headlineid = 0
        self.current_section = '0'
        current_part = self.preamble
        for p in paras:
            sp = p.strip()
            if (sp == " -----------" or sp == ""):
                if (not self.lawtext):
                    self.lawtext = []
                    current_part = self.lawtext
            elif sp == "Övergångsbestämmelser":
                self.transitional = []
                current_part = self.transitional
            elif sp == "Bilaga" or sp == "Bilaga 1":
                self.appendix = []
                current_part = self.appendix
                current_part.append(p)
            else:
                current_part.append(p)
            

        #self.log.info("_init (%s): preamble: %d, lawtext: %d, transitional: %d, appendix: %d" % (
        #    self.sfsid,
        #    len(self.preamble),
        #    len(self.lawtext),
        #    len(self.transitional),
        #    len(self.appendix)))
        

        # first do the preamble
        self.attributes = Util.OrderedDict()
        for p in self.preamble:
            if p.strip() == '': continue
            possible_continuation = True
            # this is more complicated than it should have to be, but look at 1998:778 for a good reason
            for l in p.splitlines():
                if (l.find(":") != -1 and l.index(":") <= 18):
                    possible_continuation = 0
                else:
                    pass
                
            if possible_continuation:
                # maybe it's a continuation from last line?
                self.attributes.append_to_value(self.attributemapping[key]," " + p)
                continue
            # print "doing preamble '%s'" % p[0:30]
            (key,value) = (p.split(":", 1))
            key = key.strip()
            value = value.strip() # i think I could do this in a oneliner with list comprehensions

            if key == "Rubrik":
                value = re.sub(r'\(\d{4}:\d+(| \d)\)','',value)
            if key == "SFS nr":
                if self.id != value:
                    print "VARNING: SFS-numret i lagtexten (%s) skiljer sig från det givna (%s)" % (value,self.id)
                    value = self.sfsid
                
            # normalize spacing
            # key = re.sub(r'\s+', ' ', key)
            key = Util.normalizeSpace(key)

            try:
                self.attributes.append(self.attributemapping[key],value)
            except KeyError:
                print "Unknown preamble key '%s', skipping" % key

        self.paras = paras[index+1:]

        # Now parse. adapted from _txt_to_xml() in extract.py
        
        self.f = StringIO()
        self.f.write("<?xml version=\"1.0\" encoding=\"iso-8859-1\" ?>")
        self.f.write("<law>")
        # create some metadata
        self.f.write("<meta>")

        # FIXME: rewrite timestamp handling (not sure who should be responsible
        # for keeping track of last-downloaded, but probably not the parser
        # itself)
        #timestamp = None
        #if os.path.exists("downloaded/lawtext/%s.html"%self.basefile):
        #    timestamp = os.path.getmtime("downloaded/lawtext/%s.html"%self.basefile)
        #elif os.path.exists("downloaded/lawtext/%s_A.html"%self.basefile):
        #    timestamp = os.path.getmtime("downloaded/lawtext/%s_A.html"%self.basefile)
        #if timestamp:
        #    self.f.write('<fetched>%s</fetched>' % datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M"))
        self.f.write("</meta>")
        # write the data from the preamble
        self.f.write("<preamble>")
        for tuple in self.attributes.list:
            self.f.write("<%s>%s</%s>" % (tuple[0],self.fixup(tuple[1]),tuple[0]))
        self.f.write("</preamble>")

        self.namedlaws = {}
        self.in_chapter = False
        self.in_section = False
        self.in_introduction = False
        self.in_ordered_list = False
        self.in_table = False
        # self.in_para = False
        self.possibleheadlines = []

        self.current_section = '0' # these must be strings, not numbers, otherwise Utilnumsort croaks
        self.current_chapter = '0'

        # this loops through all non-empty paragraphs. 
        for p in [p for p in self.lawtext if p.strip() != '']:
            p = self.xmlescape(p)
            # raw_p is the paragraph with leading (and trailing)
            # whitespace; it's needed for the table recognition
            # algorithm to work. Ideally, we'd like to use raw_p all
            # over, but it breaks other stuff (TODO: write test cases
            # for this 'other stuff')
            raw_p = p 
            p = p.strip()
            # print "Doing '%s'" % p[0:40].replace("\n", " ")
            # self.verbose = True
            if self.is_chapter(p):
                print "CHA: %s" % p[0:30]
                self.close_ordered_list()
                self.close_table()
                # self.close_para()
                self.close_introduction()
                self.close_section()
                self.close_chapter()
                self.open_chapter(p)
            
            elif self.is_ordered_list(p):
                if self.verbose: print "ORD: %s" % p[0:30]
                self.close_headlines(True)
                self.close_table()
                
                self.open_ordered_list()
                self.do_ordered_list(p)

            elif self.is_tablerow(raw_p):
                if self.verbose:
                    print "TAB: %s" % p[0:30]
                self.close_headlines(True)
                self.close_ordered_list()
                
                # self.open_table()
                # self.do_tablerow(raw_p)
                self.do_preformatted(raw_p)
                
            elif self.is_preformatted(raw_p):
                # if self.verbose:
                print "PRE: %s" % p[0:30]
                self.close_ordered_list()
                self.close_table()
                
                self.do_preformatted(raw_p)

                
            elif self.is_section(p):
                print "SEC: %s" % p[0:30]
                self.close_ordered_list()
                self.close_table()
                # self.close_para()
                self.close_introduction()
                self.close_section()
                self.open_section(p)

            elif self.is_headline(p):
                if self.verbose: print "HEA: %s" % p[0:30]
                self.possibleheadlines.append(p)
            else: # ok, not the start of a new section. This means
                # that if we had some possibleheadlines, we can now
                # be sure that they were, in fact, only ordinary
                # p's
                self.close_headlines(True)
                self.close_ordered_list()
                self.close_table()
                if not self.in_introduction and not self.in_section:
                    self.open_introduction()
                if self.verbose: print "NOR: %s" % p[0:30]
                # self.close_para()
                # note that the string has already been XML-escaped!
                self.f.write("<p>%s</p>" % self.find_references(Util.normalizeSpace(p)))
                # self.in_para = True
        
        # ok, all sections are done, close up shop.
        # self.close_para()
        self.close_ordered_list()
        self.close_table()
        self.close_introduction()
        self.close_section()
        self.close_chapter()

        if self.transitional:
            in_transitional = 0
            # in some cases (like 1902:71 s.1), the transitional law
            # section do not start with a law id.  we'll just to the
            # best we can in that case
            #if not re.match(r'^\d{4}:\d+\s*$', self.transitional[0]):
            if not self.re_SimpleSfsId(self.transitional[0]):
                current_changelog = OrderedDict()
                current_changelog.append('Övergångsbestämmelser','')
                current_changelog.append('SFS-nummer','okänt')
                self.changelog.append(current_changelog)
            for p in self.transitional:
                # print 'doing transitional para %s' % p
                #if re.match(r'^\d{4}:\d+\s*$', p):
                if self.re_SimpleSfsId(p):
                    current_transitional_id = p
                    in_transitional = 1
                    current_changelog = None
                    for c in self.bibliography:
                        if c.item('SFS-nummer') == current_transitional_id:
                            current_changelog = c
                            current_changelog.append('Övergångsbestämmelser', '')
                    if current_changelog == None:
                        print "Warning: couldn't find the correct changelog entry for %s, faking it" % current_transitional_id
                        current_changelog = Util.OrderedDict()
                        current_changelog.append('Övergångsbestämmelser', '')
                        current_changelog.append('SFS-nummer',current_transitional_id)
                else:
                    current_changelog.append_to_value('Övergångsbestämmelser', '<p>%s</p>'% self.xmlescape(p))

        if self.appendix:
            self.create_headline("Bilagor", "1")
            self.f.write("<appendix>")
            for p in self.appendix:
                if self.is_preformatted(p):
                    # we use self.xmlescape, because self.fixup calls
                    # normalize_space, which is exactly what we DON'T
                    # want
                    self.f.write('<pre>%s</pre>' % self.xmlescape(p))
                else:
                    self.f.write('<p>%s</p>' % self.fixup(p))

            self.f.write("</appendix>")

        if self.bibliography:
            self.f.write("<changes>")
            for  c in self.changelog:
                # print "changelog entry:"
                # print c.dict.keys()
                self.f.write('<change id="%s">' % c.item('SFS-nummer'))
                if Utilpdf_url(c.item('SFS-nummer')):
                    self.f.write('<link href="%s">Officiell PDF-version</link>' % Utilpdf_url(c.item('SFS-nummer')))
                for tuple in c.list:
                    if tuple[0] == "Omfattning":
                        self.f.write('<prop key="%s">%s</prop>' % (tuple[0],self.find_change_references(self.fixup(tuple[1]))))
                    elif tuple[0] == "Övergångsbestämmelser":
                        self.f.write('<prop key="%s">%s</prop>' % (tuple[0],self.find_references(self.normalize_space(tuple[1]))))
                    elif tuple[0] == "Förarbeten" or tuple[0] == "CELEX-nr":
                        self.f.write('<prop key="%s">%s</prop>'  % (tuple[0],self.find_prep_references(self.fixup(tuple[1]))))
                    else:
                        self.f.write('<prop key="%s">%s</prop>' % (tuple[0],tuple[1]))
                self.f.write('</change>')
            self.f.write("</changes>")
        self.f.write("</law>")
        return self.f.getvalue()

    ################################################################
    # CHAPTER HANDLING
    ################################################################
    def is_chapter(self,p):
        return self.chapter_id(p) != None
    
    def chapter_id(self,p):
        # '1 a kap.' -- almost always a headline, regardless if it
        # streches several lines but there are always special cases
        # (1982:713 1 a kap. 7 §)
        #m = re.match(r'^(\d+( \w|)) [Kk]ap.',p)
        m = self.re_ChapterId(p)
        if m:
            if (p.endswith(",") or
                p.endswith(";") or
                p.endswith(")") or
                p.endswith("och") or
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

                # print "chapter_id: '%s' failed second check" % p
                return None
            else:
                return m.group(1).replace(" ","")
        else:
            # print "chapter_id: '%s' failed first check" % p[:40]
            return None

    def close_chapter(self):
        if self.in_chapter:
            self.f.write('</chapter>')
            self.in_chapter = False

    def open_chapter(self,p):
        self.current_chapter = self.chapter_id(p)
        self.f.write('<chapter id="%s">' % self.current_chapter)
        self.possibleheadlines.append(p)
        self.in_chapter = True
        # self.in_para = False
            
    ################################################################
    # HEADLINE HANDLING
    ################################################################
    def is_headline(self,p):
        """returns wheter a para might be a headline. since this only
        looks at the line itself, it cannot determine for sure, as
        that requires knowledge of context, but this at least sifts
        away the easy cases"""
        #print "is_headline: %s" % p
        # the rules for something being a headline:
        if (p.find("\n") != -1): # it must be a single line (Exception: headline just before 25 § 1960:729)

            #print "_is_headline: fail 1"
            return False
        if (p.find("§") != -1): # if it contains a §, it's probably
                                 # just a short section
            #print "_is_headline: fail 2"
            return False
        if (p.endswith(".") and not (p.endswith("m.m.") or p.endswith("m. m."))):
            #print "_is_headline: fail 3"
            return False # a headline never ends with a period,
                                # unless it ends with the string
                                # "m.m."
        if (p.endswith(",") or p.endswith("samt") or p.endswith("eller")):
            return False
        # ok, all tests passed, this might be a headline!
        #print "_is_headline: succeed"
        return True

    def close_headlines(self,NotHeadlines=False):
        if (NotHeadlines or
            len(self.possibleheadlines) > 3 or # this treshold used to be 2, but it caused problems w 2003:389 3 kap.
            len(self.possibleheadlines) == 0):

            if len(self.possibleheadlines) > 0:
                self.close_ordered_list() # this used to be a problem
                                          # eg between the two OL
                                          # lists in 1960:729 26 h §
                                          # (and other places). One
                                          # more step for XHTML
                                          # compliance!
            for h in self.possibleheadlines:
                self.f.write("<p>%s</p>" %
                             self.find_references(h))
        else:
            if len(self.possibleheadlines) == 1:
                #if re.match(r'^(\d+( \w|)) [Kk]ap.',
                #            self.possibleheadlines[0]):
                if (self.re_ChapterId(self.possibleheadlines[0]) or
                    self.re_DivisionId(self.possibleheadlines[0])):
                    self.create_headline(self.possibleheadlines[0], "1")
                else:
                    self.create_headline(self.possibleheadlines[0], "2")

            else:
                self.create_headline(self.possibleheadlines[0], "1")
                self.create_headline(self.possibleheadlines[1], "2")

        self.possibleheadlines=[]

    def create_headline(self,text,level):
        self.headlineid = self.headlineid + 1
        self.f.write('<headline level="%s" id="%s">%s</headline>' %
                     (level,self.headlineid,text))
    
    ################################################################
    # SECTION HANDLING
    ################################################################
    def is_section(self,p):
        section_id = self.section_id(p)
        if section_id == None:
            return False
        if section_id == '1':
            if self.verbose: print "is_section: The section numbering's restarting"
            return True
        # now, if this sectionid is less than last section id, the
        # section is probably just a reference and not really the
        # start of a new section. One example of that is
        # /1991:1469#K1P7S1. We use util.numsort to get section id's
        # like "26 g" correct.
        a = [self.current_section,section_id]
        
        if a == Util.numsort(a):
            # ok, the sort order's still the same, which means the potential new section has a larger ID
            #if self.verbose: print "is_section: '%s' looks like the start of the section, and it probably is (%s < %s)" % (
            #    p[:30], self.current_section, section_id)
            return True
        else:
            #if self.verbose: print "is_section: Even though '%s' looks like the start of the section, the numbering's wrong (%s > %s)" % (
            #    p[:30], self.current_section, section_id)
            return False

    def close_section(self):
        if self.in_section:
            self.f.write('</section>')
            self.in_section = False
        self.close_headlines()

    def open_section(self,p=""):
        self.in_section = True
        assert(p != "")
        section_id = self.section_id(p)
        self.current_section = section_id
        #p = re.sub("^(\d+ ?\w?) § ","",p)
        if self.re_SectionIdOld.match(p):
            p = self.re_SectionIdOld.sub('',p)
        else:
            p = self.re_SectionId.sub('',p)


        # some old laws have sections split up in "elements" (moment),
        # eg '1 § 1 mom.', '1 § 2 mom.' etc
        match = self.re_ElementId.match(p)
        if self.re_ElementId.match(p):
            element_id = match.group(1)
            p = self.re_ElementId.sub('',p)
        else:
            element_id = None
            
        if element_id:
            self.f.write('<section id="%s" element="%s">' % (section_id,element_id))
        else:
            self.f.write('<section id="%s">' % section_id)
        self.f.write('<p>%s</p>' % self.find_references(self.fixup(p)))
        # self.in_para = True

    def section_id(self,p):
        #match = re.match("^(\d+ ?\w?) §[ \.]", p)
        match = self.re_SectionId.match(p)
        if match:
            return match.group(1).replace(" ","")
        else:
            match = self.re_SectionIdOld.match(p)
            if match:
                return match.group(1).replace(" ","")
            else:
                return None

    ################################################################
    # INTRODUCTION HANDLING
    ################################################################
    # A introduction is like a section, but without section ID (it
    # appears before the actual sections in a law, like the beginning
    # of 1810:0903). Some laws have no sections, so they get all
    #introductions.
    def close_introduction(self):
        if self.in_introduction:
            self.f.write('</introduction>')
            self.in_introduction = False
        # self.close_headlines() # not really needed, at least not
        # yet. and it messes up headline placement (they appear before
        # </section>, which is not good). 

    def open_introduction(self):
        self.f.write('<introduction>')
        self.in_introduction = True
        
    ################################################################
    # ORDERED LIST HANDLING
    ################################################################
    def open_ordered_list(self):
        if not self.in_ordered_list:
            self.f.write('<ol>')
            self.in_ordered_list = True

    def close_ordered_list(self):
        if self.in_ordered_list:
            self.f.write('</ol>')
            self.in_ordered_list = False
        
    def do_ordered_list(self,p):
        self.f.write('  <li>%s</li>' %
                     self.find_references(p))

    def is_ordered_list(self,p):
        return self.ordered_list_id(p) != None

    def ordered_list_id(self,p):
        #match = re.match(r'^(\d+)\. ',p)
        match = self.re_DottedNumber(p)
        
        if match != None:
            return match.group(1).replace(" ","")
        else:
            match = self.re_NumberRightPara(p)
            if match != None:
                return match.group(1).replace(" ","")
        return None
        
    ################################################################
    # TABLE HANDLING
    ################################################################
    # tables are handled much like ordered lists, in that they are
    # in-section structures.
    def open_table(self):
        if not self.in_table:
            self.f.write('<table>')
            self.in_table = True

    def close_table(self):
        if self.in_table:
            self.f.write('</table>')
            self.in_table = False

    def do_tablerow(self,p):
        tabstops = self.find_tabstops(p)
        self.is_tablerow(p,tabstops) # this does some fixing up of 'tight' (single space) tabstops

        cells = []
        lineidx = 0
        element = 'td' # If we determine that this tablerow contains 'header'-like stuff, we will change this to 'th'

        lines = p.split('\n')
        for lineidx in range(len(lines)):
            line = lines[lineidx]
            lasttab = 0
            tabcnt = len(tabstops[lineidx])+1
            # print range(tabcnt)
            for tabidx in range(tabcnt):    # normally [0,1]
                if tabidx == tabcnt - 1:    # last field, no tabstop for this one
                    tabpos = len(line)
                else:
                    tabpos = tabstops[lineidx][tabidx]
                if len(cells) <= tabidx:
                    cells.append('')

                cell_line = line[lasttab:tabpos].strip()
                if re.match(r'^\-+$',cell_line):
                    # print "this is a table header, not a regular table row"
                    if lineidx == 0:
                        element = 'th'
                    cell_line = "" # we don't need the actual dashes, they look like crap
                    
                # bring together words that have been hyphenated due
                # to line breaks
                if cell_line.endswith("-"):
                    cell_line = cell_line[:-1]
                else:
                    cell_line += " "

                # try to guess if there should be an explicit
                # linebreak before next line (only works on first cell
                # for now). If the next line starts with a capital
                # letter, there probably should be a linebreak
                if (tabidx == 0) and (lineidx < len(lines)-1):
                    
                    if lines[lineidx+1][:1].isupper() and cell_line != " ":
                        cell_line += "<br></br>"

                cells[tabidx] += cell_line
                lasttab = tabpos
                
        
        self.f.write('<tr>')
        for cell in cells:
            cell = self.normalize_space(cell)
            self.f.write('<%s>%s</%s>' % (element,self.find_references(cell),element))
        self.f.write('</tr>')

    def is_tablerow(self,p,init_tabstops=[]):
        # print "is_tablerow: '%s'" % p[:50]
        # print p
        tabstops = self.find_tabstops(p)
        if init_tabstops:
            tabstops = init_tabstops

        # print "is_tablerow result"
        # print tabstops
        if tabstops == []: # means there were no lines, ie p was empty string. shouldn't happen.
            # print "Returning False"
            return False

        lines = p.split("\n")
        lineidx = 0
        tabstop_lineidx = 0
        last_initial_tabstop = 0
        lines_with_tabstop = 0
        lines_without_tabstop = 0
        for tabstops_line in tabstops:
            if len(tabstops_line) > 1:
                # print "the line is too complex (more than a single
                # tabstop)" in this case, is_preformatted() will
                # return True, so it's no use for this check to go on.
                return False
            if tabstops_line == []:
                if re.match(r'^\-+$',lines[lineidx]):
                    #print "dashed line, that's ok!"
                    pass
                elif lines[lineidx][last_initial_tabstop:] == "":
                    # print "only leftmost column, that's ok!"
                    pass
                elif (len(tabstops) > tabstop_lineidx+1) and (tabstops[tabstop_lineidx+1] != []):
                    # peek at next line, if that one has a tab. If it
                    # does, and the current line has a space on that
                    # tabpos, maybe it's just a really tightly packed
                    # table
                    nextline_tab = tabstops[tabstop_lineidx+1][0]
                    if lines[lineidx][nextline_tab-1:nextline_tab] != ' ':
                        # return False
                        lines_without_tabstop += 1
                    else:
                        # modify tabstobs table, so that do_tablerow
                        # can re-use this function
                        lines_with_tabstop += 1
                        tabstops[tabstop_lineidx] = [nextline_tab]
                else:
                    # print "no, not ok!"
                    # return False
                    lines_without_tabstop += 1
            else:
                lines_with_tabstop += 1
                last_initial_tabstop = tabstops_line[0]

            lineidx += 1
            tabstop_lineidx += 1

        if lines_with_tabstop > 0:
            if self.verbose: print "is_tabstop: %s with, %s without" % (lines_with_tabstop, lines_without_tabstop)

        if lines_without_tabstop > lines_with_tabstop:
            return False
        else:
            return True
        

    def find_tabstops(self,p):
        tabstops = []
        linecount = 0
        for line in p.split('\n'):
            tabstops.append([])
            linecount += 1
            charidx = 0
            spacecount = 0
            for char in line:
                charidx += 1
                if char == ' ':
                    spacecount += 1
                else:
                    if spacecount > 2:  # we found a tabstop,maybe
                        tabstops[linecount-1].append(charidx-1)
                    else:
                        pass
                    spacecount = 0
        return tabstops


    ################################################################
    # PREFORMATTED HANDLING
    ################################################################
    # Preformatted sections are usually tables, but so complex that
    # it's too hard to convert them to proper tables, therefore we
    # punt and just preformat the section. How to determine that a
    # section is "too complex" is a difficult problem in itself, but
    # for now we have the strategy that anything with more than two
    # columns is too complex.
    
    def is_preformatted(self,p):
        # print "is_preformatted: test on this"
        # print p
        tabstops = self.find_tabstops(p)
        # print "is_preformatted result"
        # print tabstops
        if tabstops == []: # means there were no lines, ie p was empty string. shouldn't happen.
            # print "Returning False"
            return False
        for tabstops_line in tabstops:
            if len(tabstops_line) > 1:
                # print "is_preformatted: this is a complex line"
                return True

        return False

    def do_preformatted(self,p):
        # print "preformatting: '%s'" % p
        self.f.write("<pre>%s</pre>" % p)
    

    # FIXME: we should never have to do this -- we should be storing our data in
    # an ElementTree structure
    def xmlescape(self,str):
        """Does proper XML escaping for &, < and >"""
        return str.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    
    def fixup(self, str):
        """Makes sure the passed-in string works good in a XML
        document by removing leading and trailing whitespace,
        normalizes other spacing, and xmlescapes what needs to be
        XML-escaped"""
        return self.xmlescape(Util.normalizeSpace(str))
    
    # FIXME: tie in the old LawParser object here somehow
    def find_references(self,str):
        return str

    def __parseBiography(self, files = [], forceregen=True,workaround=False):
        """Extracts all biography (changelog) information for a constitution from
        it's registry page (the SFSR info, as opposed to SFST, which
        is the lawtext). The information is stored as XML, similar to
        the <changes> section that will end up in the complete XML
        file, but without the transitional rules (since those are in
        the lawtext itself, not the registry page) and w/o link tags
        and other advanced stuff."""

        # FIXME: replace most of the stuff below with some lean BeutifulSoup code
        return []

        filename = "downloaded/lawinfo/%s.html" % self.basefile
        changelog_html = open(filename).read()
        cl = SFSChangelogExtractor()
        try:
            cl.feed(changelog_html)
        except LawNotFoundError:
            self.log.error("extract_changelog: Changelog for %s (%s) doesn't contain anything (trying to go on anyway...)" % (self.sfsid, filename))


        if (len(cl.changelog) == 0 or
            len(cl.changelog) == 1 and cl.changelog[0].list == []):
            # if there is a file, but no changes included in it, it
            # might be a two-parter (maybe this should be signalled
            # with an Exception from SFSChangelogExtractor()?)
            if (os.path.exists("downloaded/lawinfo/%s_A.html" % self.basefile) and
                os.path.exists("downloaded/lawinfo/%s_B.html" % self.basefile)):
                cl = SFSChangelogExtractor()
                cl.feed(open("downloaded/lawinfo/%s_A.html" % self.basefile).read())
                cl_b = SFSChangelogExtractor()
                cl_b.feed(open("downloaded/lawinfo/%s_B.html" % self.basefile).read())
                cl.changelog.extend(cl_b.changelog)
            

        if not os.path.exists("generated/lawinfo/%s" % self.year):
            os.mkdir("generated/lawinfo/%s" % self.year)
        filename = "generated/lawinfo/%s.xml" % self.basefile
        f = open(filename, "w")
        f.write('<?xml version="1.0" encoding="iso-8859-1"?>')
        f.write("<changes>")
        changecount = 0
        for  c in cl.changelog:
            if c.list != []:
                f.write("<change>")
                changecount += 1
                for tuple in c.list:
                    f.write('<prop key="%s">%s</prop>' % (tuple[0],tuple[1]))
                f.write('</change>')
        f.write("</changes>")
        f.close()
        Util.indentXmlFile(filename)

        # this can be removed later
        if changecount == 0 and workaround:
            print "No changes, re-getting changelog"
            try:
                self.get_changelog(force=True)
            except IOError:
                pass
            self.extract_changelog(workaround=False)
    
    
class SFSManager(LegalSource.Manager):
    def _SFSidToFilename(self,sfsid):
        """converts a SFS id to a filename, sans suffix, eg: '1909:bih. 29
        s.1' => '1909/bih._29_s.1'. Returns None if passed an invalid SFS
        id."""
        if sfsid.find(":") < 0: return None
        return re.sub(r'([A-Z]*)(\d{4}):',r'\2/\1',sfsid.replace(' ', '_'))

    def _filenameToSFSid(self,filename):
        """converts a filename, sans suffix, to a sfsid, eg:
        '1909/bih._29_s.1' => '1909:bih. 29 s.1'"""
        (dir,file)=filename.split("/")
        if file.startswith('RFS'):
            return re.sub(r'(\d{4})/([A-Z]*)(\d*)',r'\2\1:\3', filename.replace('_',' '))
        else:
            return re.sub(r'(\d{4})/(\d*)',r'\1:\2', filename.replace('_',' '))

    def Parse(self, id):
        files = ["%s/sfs/downloaded/%s.html" % (self.baseDir, self._SFSidToFilename(id))]
        print("Files: %r" % files)
        p = SFSParser(self.baseDir)
        p.Parse(id, files, self.baseDir)

    def Generate(self,id):
        indir = "%s/%s/parsed" % (self.baseDir, __moduledir__)
        outdir = "%s/%s/generated" % (self.baseDir, __moduledir__)
        infile = "%s/%s.xml" % (indir,self._SFSidToFilename(id))
        outfile = "%s/%s.html" % (outdir,self._SFSidToFilename(id))
        sanitized_sfsid = id.replace(' ','.')
        print "Transforming %s > %s" % (infile,outfile)
        Util.transform("xsl/sfs.xsl",
                       infile,
                       outfile,
                       {'lawid': sanitized_sfsid,
                        'today':datetime.date.today().strftime("%Y-%m-%d")},
                       validate=False)
        print "Generating index for %s" % outfile
        ad = AnnotatedDoc(outfile)
        ad.Prepare()
        print "done"
        
        
if __name__ == "__main__":
    SFSManager.__bases__ += (DispatchMixin,)
    mgr = SFSManager("testdata")
    print "argv: %r" % sys.argv
    mgr.Dispatch(sys.argv)
