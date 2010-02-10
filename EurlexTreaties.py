#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
import sys,os
import re
import datetime
from collections import deque, defaultdict

from rdflib import Namespace, URIRef, Literal, RDF
from rdflib.Graph import Graph

from DocumentRepository import DocumentRepository
import Util
import LegalURI
from LegalRef import LegalRef, Link
from DataObjects import UnicodeStructure, CompoundStructure, OrdinalStructure, serialize


__version__ = (1,6)
__author__  = u"Staffan Malmgren <staffan@tomtebo.org>"

# The general outline of a treaty is:
# <Body> C
#   <Paragraph> C (unicode/Link) - starting and ending titles
#   <Preamble> C
#     <Paragraph> - the typographic term, aka "Stycke"
#   <Part> CO - not present for TEU
#     <Title> CO
#       <Chapter> CO
#         <Section> CO
#           <Article> CO
#             <Subarticle> CO
#                <Paragraph> C
#                  <unicode>
#                  <Link>
#                <UnordedList leader="dash"> C
#                  <ListItem> C
#                <OrderedList type="letter"> CO

class IDStructure(object):
    id = None
    attrs = None

class Body(CompoundStructure, IDStructure): pass 
class Paragraph(CompoundStructure, IDStructure): pass
class Preamble(CompoundStructure, IDStructure): pass
class Part(CompoundStructure, IDStructure, OrdinalStructure): pass
class Title(CompoundStructure, IDStructure, OrdinalStructure): pass
class Chapter(CompoundStructure, IDStructure, OrdinalStructure): pass
class Section(CompoundStructure, IDStructure, OrdinalStructure): pass
class Article(CompoundStructure, IDStructure, OrdinalStructure):
    fragment_label = "A"
    rdftype = "eurlex:Article"
class Subarticle(CompoundStructure, IDStructure, OrdinalStructure):
    fragment_label = "P"
    rdftype = "eurlex:Subarticle"
class UnorderedList(CompoundStructure, IDStructure): pass
class OrderedList(CompoundStructure, IDStructure, OrdinalStructure): pass
class ListItem(CompoundStructure, IDStructure): 
    fragment_label = "L"
    rdftype = "eurlex:ListItem"


DCT = Namespace(Util.ns['dct'])
XSD = Namespace(Util.ns['xsd'])
RINFO = Namespace(Util.ns['rinfo'])
RINFOEX = Namespace(Util.ns['rinfoex'])
class EurlexTreaties(DocumentRepository):
    # overrides of superclass variables 
    module_dir = "eut" # European Union Treaties
    start_url = "http://eur-lex.europa.eu/LexUriServ/LexUriServ.do?uri=OJ:C:2008:115:0001:01:EN:HTML"
    document_url = "http://eur-lex.europa.eu/LexUriServ/LexUriServ.do?uri=OJ:C:2008:115:0001:01:EN:HTML#%s"
    source_encoding = "utf-8"
    genshi_tempate = "genshi/supergeneric.xhtml"

    # own class variables
    vocab_url = Util.ns['eurlex']

    def download_everything(self,cache=False):
        self.log.info("Hello")
        self.download_single("teu")
        self.download_single("tfeu")

    re_part = re.compile("PART (ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN)$").match
    re_title = re.compile("TITLE ([IVX]+)$").match
    re_chapter = re.compile("CHAPTER (\d+)$").match
    re_section = re.compile("SECTION (\d+)$").match
    re_article = re.compile("Article (\d+)$").match
    re_subarticle = re.compile("^(\d+)\. ").search
    re_unorderedliststart = re.compile("^- ").search
    re_orderedliststart = re.compile("^\(\w\) ").search
    re_romanliststart = re.compile("^\([ivx]+\) ").search
    ordinal_list = ('ONE', 'TWO', 'THREE', 'FOUR', 'FIVE', 'SIX', 'SEVEN',
                    'EIGHT', 'NINE', 'TEN', 'ELEVEN', 'TWELVE')
    ordinal_dict = dict(zip(ordinal_list, range(1,len(ordinal_list)+1)))

    # Example code from http://www.diveintopython.org/
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

    def _from_roman(self,s):
        """convert Roman numeral to integer"""
        result = 0
        index = 0
        for numeral, integer in self.roman_numeral_map:
            while s[index:index+len(numeral)] == numeral:
                result += integer
                index += len(numeral)
        return result

    def parse_from_soup(self,soup,basefile):
        g = Graph()
        self.log.info("%s: Parsing" % basefile)
        if basefile == "teu":
            # FIXME: Use a better base URI?
            uri = 'http://rinfo.lagrummet.se/extern/celex/12008M'
            startnode = soup.findAll(text="-"*50)[1].parent
            g.add((URIRef(uri),DCT['title'],Literal("Treaty on European Union")))
        elif basefile == "tfeu":
            uri = 'http://rinfo.lagrummet.se/extern/celex/12008E'
            startnode = soup.findAll(text="-"*50)[2].parent
            g.add((URIRef(uri),DCT['title'],Literal("Treaty on the Functioning of the European Union")))

        lines = deque()
        for p in startnode.findNextSiblings("p"):
            if p.string == "-" * 50:
                self.log.info("found the end")
                break
            else:
                if p.string:
                    lines.append(unicode(p.string))

        self.log.info("%s: Found %d lines" % (basefile,len(lines)))
        body = self.make_body(lines)
        self.process_body(body, '', uri)
        print serialize(body)
        return {'meta':g,
                'body':body,
                'lang':'en',
                'uri':uri}

    # To make Paragraph and our other stuff available to Genshi
    def get_globals(self):
        return globals()
    
    def make_body(self,lines):
        b = Body()
        while lines:
            line = lines.popleft()
            if line == "PREAMBLE":
                b.append(self.make_preamble(lines))
            elif self.re_title(line):
                lines.appendleft(line)
                b.append(self.make_title(lines))
            elif self.re_part(line):
                lines.appendleft(line)
                b.append(self.make_part(lines))
            else:
                b.append(Paragraph([line]))
            print type(b[-1])
        return b

    def make_preamble(self,lines):
        p = Preamble(title="PREAMBLE")
        while lines:
            line = lines.popleft()
            if (self.re_part(line) or self.re_title(line)):
                lines.appendleft(line)
                return p
            else:
                p.append(Paragraph([line]))

        self.log.warn("make_preamble ran out of lines!")
        return p # 

    def make_part(self,lines):
        partnumber = lines.popleft()
        ordinal = self.ordinal_dict[self.re_part(partnumber).group(1)]
        parttitle = lines.popleft()
        p = Part(ordinal=ordinal,ordinaltitle=partnumber,title=parttitle)
        while lines:
            line = lines.popleft()
            if (self.re_part(line)):
                lines.appendleft(line)
                return p
            elif (self.re_title(line)):
                lines.appendleft(line)
                p.append(self.make_title(lines))
            elif (self.re_article(line)):
                lines.appendleft(line)
                p.append(self.make_article(lines))
            else:
                p.append(Paragraph([line]))
                self.log.warn("make_part appended naked Paragraph '%s...'" % line[:25])
        return p

    def make_title(self,lines):
        titlenumber = lines.popleft()
        ordinal = self._from_roman(self.re_title(titlenumber).group(1))
        titletitle = lines.popleft()
        t = Title(ordinal=ordinal, ordinaltitle=titlenumber, title=titletitle)
        while lines:
            line = lines.popleft()
            if (self.re_part(line) or self.re_title(line)):
                lines.appendleft(line)
                return t
            elif (self.re_chapter(line)):
                lines.appendleft(line)
                t.append(self.make_chapter(lines))
            elif (self.re_article(line)):
                lines.appendleft(line)
                t.append(self.make_article(lines))
            else:
                t.append(Paragraph([line]))
                self.log.warn("make_title appended naked Paragraph '%s...'" % line[:25])
        return t

    def make_chapter(self,lines):
        chapternumber = lines.popleft()
        ordinal = int(self.re_chapter(chapternumber).group(1))
        chaptertitle = lines.popleft()
        c = Chapter(ordinal=ordinal, ordinaltitle=chapternumber,title=chaptertitle)
        while lines:
            line = lines.popleft()
            if (self.re_part(line) or
                self.re_title(line) or
                self.re_chapter(line)):
                lines.appendleft(line)
                return c
            elif (self.re_section(line)):
                lines.appendleft(line)
                c.append(self.make_section(lines))
            elif (self.re_article(line)):
                lines.appendleft(line)
                c.append(self.make_article(lines))
            else:
                c.append(Paragraph([line]))
                self.log.warn("make_chapter appended naked Paragraph '%s...'" % line[:25])
        return c

    def make_section(self,lines):
        sectionnumber = lines.popleft()
        ordinal = int(self.re_section(sectionnumber).group(1))
        sectiontitle = lines.popleft()
        s = Section(ordinal=ordinal, ordinaltitle=sectionnumber,title=sectiontitle)
        while lines:
            line = lines.popleft()
            if (self.re_part(line) or
                self.re_title(line) or
                self.re_chapter(line) or
                self.re_section(line)):
                lines.appendleft(line)
                return s
            elif (self.re_article(line)):
                lines.appendleft(line)
                s.append(self.make_article(lines))
            else:
                s.append(Paragraph([line]))
                self.log.warn("make_section appended naked Paragraph '%s...'" % line[:25])
        return s

    def make_article(self,lines):
        articlenumber = lines.popleft()
        ordinal = int(self.re_article(articlenumber).group(1))
        self.log.info("Making article: %s" % ordinal)
        exarticlenumber = lines.popleft()
        if not exarticlenumber.startswith("(ex Article"):
            lines.appendleft(exarticlenumber)
            a = Article(ordinal=ordinal, ordinaltitle=articlenumber)
        else:
            a = Article(ordinal=ordinal, ordinaltitle=articlenumber, exarticlenumber=exarticlenumber)

        while lines:
            line = lines.popleft()
            if (self.re_part(line) or
                self.re_title(line) or
                self.re_chapter(line) or
                self.re_section(line) or
                self.re_article(line)):
                lines.appendleft(line)
                return a
            elif (self.re_subarticle(line)):
                lines.appendleft(line)
                a.append(self.make_subarticle(lines))
            elif (self.re_unorderedliststart(line)): 
                lines.appendleft(line)
                a.append(self.make_unordered_list(lines,"dash"))
            elif (self.re_orderedliststart(line)):
                lines.appendleft(line)
                a.append(self.make_ordered_list(lines,"lower-alpha"))
            else:
                # this is OK
                a.append(Paragraph([line]))

        return a
                
    def make_subarticle(self,lines):
        line = lines.popleft()
        subarticlenum = int(self.re_subarticle(line).group(1))
        # self.log.info("Making subarticle %d: %s" % (subarticlenum, line[:30]))
        s = Subarticle(ordinal=subarticlenum)
        lines.appendleft(line)
        while lines:
            line = lines.popleft()
            if (self.re_part(line) or
                self.re_title(line) or
                self.re_chapter(line) or
                self.re_section(line) or
                self.re_article(line)):
                lines.appendleft(line)
                return s
            elif (self.re_subarticle(line) and
                  int(self.re_subarticle(line).group(1)) != subarticlenum):
                lines.appendleft(line)
                return s
            elif (self.re_unorderedliststart(line)): 
                lines.appendleft(line)
                s.append(self.make_unordered_list(lines,"dash"))
            elif (self.re_orderedliststart(line)):
                lines.appendleft(line)
                s.append(self.make_ordered_list(lines,"lower-alpha"))
            else:
                # this is OK
                s.append(Paragraph([line]))
        return s

    def make_unordered_list(self,lines,style):
        ul = UnorderedList(style=style)
        while lines:
            line = lines.popleft()
            if not self.re_unorderedliststart(line):
                lines.appendleft(line)
                return ul
            else:
                ul.append(ListItem([line]))
        return ul
        
    def make_ordered_list(self,lines,style):
        ol = OrderedList(style=style)
        while lines:
            line = lines.popleft()
            # try romanliststart before orderedliststart -- (i) matches
            # both, but is likely the former
            if self.re_romanliststart(line):
                if style=="lower-roman":
                    ol.append(ListItem([line]))
                else:
                    lines.appendleft(line)
                    ol.append(self.make_ordered_list(lines,"lower-roman"))
            elif self.re_orderedliststart(line):
                if style=="lower-alpha":
                    ol.append(ListItem([line]))
                else: # we were in a roman-style sublist, so we should pop up
                    lines.appendleft(line)
                    return ol
            else:
                return ol
        return ol


    # Post-process the document tree in a recursive fashion in order to:
    #
    # Find addressable units (resources that should have unique URI:s,
    # e.g. articles and subarticles) and construct IDs for them, like
    # "A7", "A25(b)(ii)" (or A25S1P2N2 or...?)
    #
    # How should we handle Articles themselves -- they have individual
    # CELEX numbers and therefore URIs (but subarticles don't)?
    

    def process_body(self, element, prefix, baseuri):
        if type(element) == unicode:
            return
        # print "Starting with "  + str(type(element))
        counters = defaultdict(int)
        for p in element:
            counters[type(p)] += 1
            # print "handling " + str(type(p))
            if hasattr(p, 'fragment_label'): # this is an addressable resource
                elementtype = p.fragment_label
                if hasattr(p,'ordinal'):
                    elementordinal = p.ordinal
                else:
                    elementordinal = counters[type(p)]

                fragment = "%s%s%s" % (prefix, elementtype, elementordinal)
                if elementtype == "A":
                    uri = "%s%03d" % (baseuri, elementordinal)
                else:
                    uri = "%s%s%s" % (baseuri, elementtype, elementordinal)

                p.id = fragment
                p.attrs = {'id':p.id,
                           'about':uri,
                           'typeof':p.rdftype}
                if elementtype == "A":
                    uri += "#"
            else:
                fragment = prefix
                uri = baseuri
                
            self.process_body(p,fragment,uri)

    def prep_annotation_file(self,basefile):
        # step 1: Find out all eurlex:Articles that are part of the
        # current treaty (could be done through a simple regex match,
        # if we don't want to mess with dct:isPartOf

        # Step 2: Load all EurlexCaselaw documents into Whoosh (or
        # maybe rather initiate a Whoosh database that was
        # prepopulated by EurlexCaselaw.relate)

        # Step 3: For each article URI, find out the text of it (probably
        # by loading it into ElementTree and finding the node with the
        # right @about attribute)

        # Step 4: Perform a query with the article text against the
        # Whoosh DB (with appropriate stemming and whatnot). Put the
        # top 15 results as being in a ir:BM25NaiveResult with this
        # article as object. This is our baseline.

        # Step 5: Perform a query with the article text against the
        # Whoosh DB, but filter cases so that only cases that
        # explicitly refer to the article in question (or any of it's
        # earlier incarnations) are selected. Put the top 15 results
        # as being ir:BM25FilteredResult

        # Step 6: Do whatever magic citation network analysis needed
        # to get a relevance score based on internal citation
        # patterns. Put the top 15 results as being
        # ir:CitationInternalResult

        # Step 7: Do a similar analysis, but use other citation
        # datasets as well, appropriately weighed. Put the top 15
        # results as being ir:CitationWeighedResult
        pass
        
if __name__ == "__main__":
    EurlexTreaties.run()
