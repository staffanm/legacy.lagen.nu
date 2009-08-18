#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
import sys,os
import re

from rdflib import Namespace

from DocumentRepository import DocumentRepository
from DataObjects import UnicodeStructure, CompoundStructure, \
     MapStructure, IntStructure, DateStructure, PredicateType, \
     UnicodeSubject, Stycke, Sektion, \
     serialize
import Util
import LegalURI
from LegalRef import LegalRef, Link

__version__ = (1,6)
__author__  = u"Staffan Malmgren <staffan@tomtebo.org>"

RINFO   = Namespace(Util.ns['rinfo'])
RINFOEX = Namespace(Util.ns['rinfoex'])
DCT     = Namespace(Util.ns['dct'])

class JK(DocumentRepository):
    module_dir = "jk"

    start_url = "http://www.jk.se/beslut/default.asp"
    document_url = "http://www.jk.se/beslut/XmlToHtml.asp?XML=Files/%s.xml&XSL=../xsl/JK_Beslut.xsl"
    def download_everything(self,cache=False):
        self.browser.open(self.start_url)
        for avd in (self.browser.links(url_regex=r'Default.asp\?Type=\d+')):
            self.log.info(u"Retrieving section '%s'" % avd.text.decode('iso-8859-1'))
            self.browser.follow_link(avd)
            for dok in (self.browser.links(url_regex=r'XmlToHtml.asp\?XML=Files/\d+\w*-\d+-\d+')):
                m = re.search("(\d+\w*-\d+-\d+)",dok.url)
                self.download_single(m.group(1),cache)

    def parse_from_soup(self,soup):
        # Step 1: Find out basic metadata
        rubrik = soup.first("title").string
        beslutsdatum  = soup.first("meta",{'name':'SG_Beslutsdatum'})['content']
        diarienummer  = soup.first("meta",{'name':'SG_Dokumentbet'})['content']
        arendetyp     = soup.first("meta",{'name':'Subject'})['content']
        # the keywords for a documents is contained in a metatag
        # formatted like:
        #    <meta name="Keywords" content="hets_mot_folkgrupp\nmeddelarfrihet\åklagare">
        #
        # Transform this into an array like:
        #    [u'Hets mot folkgrupp', u'Meddelarfrihet', u'Åklagare']
        nyckelord_val = soup.first("meta",{'name':'Keywords'})['content'].replace("_", " ")
        nyckelord     = [Util.ucfirst(x).strip() for x in nyckelord_val.split("\n")]

        # Step 2: Map the basic metadata to RDF statements
        meta = MapStructure()
        meta[u'Rubrik'] = UnicodeSubject(rubrik, predicate=DCT['title'])
        meta[u'Beslutsdatum'] = UnicodeSubject(beslutsdatum, predicate=RINFO['beslutsdatum'])
        meta[u'Diarienummer'] = UnicodeSubject(diarienummer, predicate=RINFO['diarienummer'])
        meta[u'Ärendetyp'] = UnicodeSubject(arendetyp, predicate=RINFOEX['arendetyp'])
        meta[u'Sökord'] = [UnicodeSubject(s, predicate=DCT['subject']) for s in nyckelord]

        # Step 3: Using the metadata, construct the canonical URI for this document
        uri = LegalURI.construct({'type':LegalRef.MYNDIGHETSBESLUT,
                                  'myndighet':'jk',
                                  'dnr':meta[u'Diarienummer']})
        self.log.debug("URI: %s" % uri)

        meta['dct:identifier'] = "JK %s" % meta[u'Diarienummer']
        meta['rdfs:type'] = "rinfoex:Myndighetsbeslut"
        meta['xml:base'] = uri

        # Step 4: Process the actual text of the document
        self.parser = LegalRef(LegalRef.LAGRUM,
                               LegalRef.KORTLAGRUM,
                               LegalRef.RATTSFALL,
                               LegalRef.FORARBETEN)

        # newer documents have a semantic structure with h1 and h2
        # elements. Older have elements like <p class="Rubrik_1">. Try
        # to determine which one we're dealing with?
        tag = soup.find('a', {'name':"Start"})
        if tag:
            self.log.debug("Using new-style document structure")
            elements = tag.parent.findAllNext()
        else:
            self.log.debug("Using old-style document structure")
            elements = soup.findAll("p")
        self.log.debug("Found %d elements" % len(elements))
        from collections import deque
        elements = deque(elements)
        body = self.make_sektion(elements,u"Referat av beslut")

        # Step 5: Combine the metadata and the document, and return it
        doc = {'meta':meta,
               'body':body}
        return doc

    def make_sektion(self,elements,heading,level=0):
        sekt = Sektion(**{"rubrik":heading,
                          "niva":level})
        self.log.debug("%sCreated sektion(%d): '%s'" % ("  "*level,level,heading))
        while True:
            try:
                p = elements.popleft()
            except IndexError:
                return sekt
            text = Util.elementText(p)
            # self.log.debug("%sp.name: %s, p['class']: %s, 'class' in p.attrs: %s" % ("  "*level,p.name,p['class'], (u'class' in p.attrs[0])))
            new_level = None
            if p.name == "h1":
                new_level = 1
            elif p.name == "h2":
                new_level = 2
            elif p.name == "h3":
                new_level = 3
            elif ((p.name == "p") and
                  (len(p.attrs) > 0) and
                  ('class' in p.attrs[0]) and
                  (p['class'].startswith("Rubrik_"))):
                # self.log.debug("%sp.class: %s" % ("  "*level,p['class']))
                new_level = int(p['class'][7:])

            if new_level:
                if new_level > level:
                    sekt.append(self.make_sektion(elements,text,new_level))
                else:
                    elements.appendleft(p)
                    return sekt
            else:
                if text:
                    stycke = Stycke(self.parser.parse(text,
                                                      baseuri=None,
                                                      predicate="dct:references"))
                    # self.log.debug("%sCreated stycke: '%s'" % ("  "*level,stycke))
                    sekt.append(stycke)


if __name__ == "__main__":
    ExampleRepo.run()
