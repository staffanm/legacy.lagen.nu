#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
import sys,os
import re
import datetime

from rdflib import Namespace, URIRef, Literal, RDF
from rdflib.Graph import Graph
from mechanize import LinkNotFoundError
from whoosh import analysis, qparser
from whoosh.index import create_in, open_dir
from whoosh.fields import Schema, TEXT, ID

from DocumentRepository import DocumentRepository
import Util
import LegalURI
from LegalRef import LegalRef, Link
from DataObjects import UnicodeStructure, CompoundStructure, Stycke


__version__ = (1,6)
__author__  = u"Staffan Malmgren <staffan@tomtebo.org>"

class Body(CompoundStructure): pass
class Paragraph(Stycke): pass

class EurlexCaselaw(DocumentRepository):
    module_dir = "ecj" # European Court of Justice
    start_url = "http://eur-lex.europa.eu/JURISIndex.do"
    document_url = "http://eur-lex.europa.eu/LexUriServ/LexUriServ.do?uri=CELEX:%s:EN:NOT"
    vocab_url = "http://lagen.nu/eurlex#"
    source_encoding = "utf-8"

    re_celexno = re.compile('(6)(\d{4})(\w)(\d{4})(\(\d{2}\)|)')

    def download_everything(self,cache=False):
        startyear = 2009 # eg 1954
        for year in range(startyear,datetime.date.today().year+1):
            list_url = "http://eur-lex.europa.eu/Result.do?T1=V6&T2=%d&T3=&RechType=RECH_naturel" % year
            self.log.debug("Searching for %d"% year)
            self.browser.open(list_url)
            pagecnt = 0
            done = False
            while not done:
                pagecnt += 1
                self.log.debug("Result page #%s" % pagecnt)
                # For some reason, Mechanize can't find the link to
                # the HTML version of the case text. So we just get
                # the whole page as a string and find unique CELEX ids
                # in the tagsoup.
                pagetext = self.browser.response().read()
                celexnos = self.re_celexno.findall(pagetext)
                for celexno in Util.uniqueList(celexnos):
                    # the number will be split up in components - concatenate
                    celexno = "".join(celexno)
                    # only download actual judgements
                    # J: Judgment of the Court
                    # A: Judgment of the Court of First Instance
                    # W: Judgement of the Civil Service Tribunal
                    # T: (old) Judgement of the Court
                    if ('J' in celexno or 'A' in celexno
                        or 'W' in celexno or 'T' in celexno):
                        self.log.debug("Downloading case %s" % celexno)
                        self.download_single(celexno,cache=True)
                    else:
                        pass
                        #self.log.debug("Not downloading doc %s" % celexno)
                            
                # see if there are any "next" pages
                try:
                    self.browser.follow_link(text='>')
                except LinkNotFoundError:
                    self.log.info(u'No next page link found, we must be done')
                    done = True
                
                        

            
                            
    @classmethod
    def basefile_from_path(cls,path):
        seg = os.path.splitext(path)[0].split(os.sep)
        return "/".join(seg[seg.index(cls.module_dir)+3:])

    def downloaded_path(self,basefile):
        m = self.re_celexno.match(basefile)
        year = m.group(2)
        return os.path.sep.join([self.base_dir, self.module_dir, u'downloaded', year, basefile+'.html'])
    
    def parsed_path(self,basefile):
        m = self.re_celexno.match(basefile)
        year = m.group(2)
        return os.path.sep.join([self.base_dir, self.module_dir, u'parsed', year, basefile+'.xhtml'])

    def distilled_path(self,basefile):
        m = self.re_celexno.match(basefile)
        year = m.group(2)
        return os.path.sep.join([self.base_dir, self.module_dir, u'distilled', year, basefile+'.rdf'])
    
        
    def parse_from_soup(self,soup,basefile):
        # AVAILABLE METADATA IN CASES
        #
        # For now, we create a nonofficial eurlex vocab with namespace http://lagen.nu/eurlex#
        # - celex number (first h1) :celex (:celexnum?)
        #   
        # - [Title and reference]
        #   - decision type and date "Judgment of the Court (Third Chamber) of 17 December 2009."
        #      :courtdecision (as opposed to :commissiondecision)
        #   - :party (or parties) "M v Agence européenne des médicaments (EMEA)."
        #   - :referingcourt "Reference for a preliminary ruling: Administrativen sad Sofia-grad - Bulgaria."   
        #   - :legalissue - short description and/or(?) keywords (not always present, eg 62009J0403), hyphen sep:
        #     - "Review of the judgment in Case T-12/08 P"
        #     - "Whether the state of the proceedings permits final judgment to be given"
        #     - "Fair hearing"
        #     - "Rule that the parties should be heard"
        #     - "Whether the unity or consistency of Community law is affected."
        #   - :casenum Case number + unknown letters:
        #     - "Case C-197/09 RX-II."
        #     - "Joined cases T-117/03 to T-119/03 and T-171/03."
        #   - :casereporter Case reporter cite "European Court reports 2009 Page 00000"
        # - [Text]
        #   - :availablelang - Available languages ("bg", "es", "cs", "da" ....)
        # - :authenticlang - Authentic language ("fr" or "French")
        # - [Dates]
        #   - :decisiondate - Date of document (decision/judgement)
        #   - :applicationdate - Date of application
        # - [Classifications] (different from description/keywords above)
        #   - :subjectmatter Subject Matter, comma sep:
        #     - "Staff regulations and employment conditions - EC"
        #     - "Provisions governing the Institutions"
        #   - :directorycode - Case Law Directory Code (where is the full code list?), NL sep:
        #      - "B-09.03 EEC/EC / State aid / Exceptions to the prohibition of aid"
        #      - "B-20.05 EEC/EC / Acts of the institutions / Statement of the reasons on which a measure is based"
        #      - "B-09.03 EEC/EC / State aid / Exceptions to the prohibition of aid"
        #      - "B-09.04 EEC/EC / State aid / Review of aid by the Commission - Rules of procedure"
        # - [Miscellaneous information]
        #   - dct:author Author: "Court of Justice of the European Communities"
        #   - :form Form: "Judgement"
        # - [Procedure]
        #   - :proceduretype - Type of procedure, comma sep:
        #     - "Staff cases"
        #     - "Action for damages"
        #     - "Appeal"
        #     - "REEX=OB"
        #   - :applicant - Applicant: "Official"
        #   - :defendant - Defendant: "EMEA, Institutions"
        #   - :observation - Observations: "Italy, Poland, Member States, European Parliament, Council, Commission, Institutions"
        #   - :judgerapporteur - Judge-Rapporteur: "von Danwitz"
        #   - :advocategeneral - Advocate General: "Mazák"
        # - [Relationships between documents]
        #   - :treaty Treaty: "European Communities"
        #   - :caseaffecting Case affecting, NL-sep:
        #     - "Interprets [CELEXNO + pinpoint]"
        #     - "Declares void 61995A0091"
        #     - "Confirms 31996D0666"
        #   - :"Instruments cited in case law" (celex numbers with pinpoint locations?), nl-sep
        #     - "12001C/PRO/02-A61"
        #     - "12001C/PRO/02-NA13P1"
        #     - "31991Q0530-A114"
        #     - "62007K0023"
        #     - "62008A0012"

        # convenience nested functions
        def add_literal(predicate,literal):
            g.add((URIRef(uri),
                   voc[predicate],
                   Literal(literal, lang=lang)))

        def add_celex_object(predicate,celexno):
            g.add((URIRef(uri),
                   voc[predicate],
                   URIRef("http://lagen.nu/ext/celex/%s" % celexno)))

        def get_predicate(predicate):
            predicates = list(g.objects(URIRef(uri),voc[predicate]))
            return predicates != []
            
        # These are a series of refinments for the "Affecting"
        # relationship. "Cites" doesn't have these (or similar), but
        # "is affected by" has (the inverse properties)
        affects_predicates = {"Interprets": "interprets",
                              "Interprets the judgment":
                                  "interpretsJudgment",
                              "Declares void": "declaresVoid",
                              "Confirms": "confirms",
                              "Declares valid (incidentally)":
                                  "declaresValidIncidentally",
                              "Declares valid (by a preliminary ruling)":
                                  "declaresValidByPreliminaryRuling",
                              "Incidentally declares invalid":
                                  "declaresInvalidIncidentally",
                              "Declares invalid (by a preliminary ruling)":
                                  "declaresInvalidByPreliminaryRuling",
                              "Amends": "amends",
                              "Failure concerning":"failureConcerning"}

        isaffected_predicates = {"Interpreted by": "interpretedBy",
                                 "Confirmed by": "confirmedBy",
                                 "Declared void by": "declaredVoidBy",
                                 "Annulment requested by":
                                     "annulmentRequestedBy"}

        # 1. Express metadata about our document as a RDF graph
        g = Graph()
        voc = Namespace(self.vocab_url)
        g.bind('dct',self.ns['dct'])
        g.bind('eurlex',voc)
        # :celex - first <h1>
        celexnum = soup.h1.string.strip()
        if celexnum == "No documents matching criteria.":
            self.log.warning("%s: No document found!" % basefile)
            raise Exception("No document found!")

        assert celexnum == basefile, "Celex number in file (%s) differ from filename (%s)" % (celexnum,basefile)
        lang = soup.html['lang']
        # 1.1 Create canonical URI for our document. To keep things
        # simple, let's use the celex number as the basis (in the
        # future, we should extend LegalURI to do it)
        uri = "http://lagen.nu/ext/celex/%s" % celexnum

        m = self.re_celexno.match(celexnum)
        rdftype = {'J': voc['Judgment'],
                   'A': voc['JudgmentFirstInstance'],
                   'W': voc['JudgmentCivilService']}[m.group(3)]
                   
        g.add((URIRef(uri), RDF.type, rdftype))

        add_literal('celexnum', celexnum)
        
        # The first section, following <h2>Title and reference</h2>
        # contains :courtdecision, :party (one or two items),
        # :referingcourt (optional), :legalissue (list of strings),
        # :casenum, :casereporter. Since some are optional, we do a
        # little heuristics to find out what we're looking at at any
        # given moment.
        for section in soup.findAll(["h1","h2"]):
            if section.name == "h1" and section.a and section.a.string == "Text": 
                break 
            if section.string == u"Title and reference":
                for para in section.findNextSiblings("p"):
                    if not para.string: continue
                    string = para.string.strip()

                    if not get_predicate('courtdecision'): # optional: do sanitychecks to see if this really is a :courtdecision
                        add_literal('courtdecision',string)
                    elif not get_predicate('party'):
                        # this will be one or two items. Are they position dependent?
                        for party in string.split(" v "):
                            add_literal('party', party)
                    elif (not get_predicate('referingcourt') and
                          (string.startswith("Reference for a preliminary ruling") or
                           string.startswith("Preliminary ruling requested"))):
                        add_literal('referingcourt', string)
                    elif (not get_predicate('casenum') and
                          (string.lower().startswith("case ") or
                           string.lower().startswith("joined cases "))):
                        add_literal('casenum',string)
                    elif para.em: # :casereporter is enclosed in an em
                        for row in para.findAll(text=True):
                            add_literal('casereporter',row.strip())
                    elif get_predicate('legalissue'):
                        # fixme: Split this up somehow
                        add_literal('legalissue', string)
                    pass
            elif section.string == "Relationship between documents":
                for item in section.findNextSibling("ul").findAll("li"):
                    predicate = None
                    subpredicate = None
                    for node in item.childGenerator():
                        if not hasattr(node,"name"):
                            nodetext = node.strip()
                            if re.match("([ABCDEFGIJKLNPRST]+\d*)+$",nodetext): continue 
                            if re.match("\d[\d\-]*[ABC]?$",nodetext): continue 
                            if predicate == "affects" and nodetext:
                                if nodetext in affects_predicates:
                                    subpredicate = affects_predicates[nodetext]
                                else:
                                    self.log.warning("Can't express '%s' as a affects predicate" % nodetext)
                            elif predicate == "isaffected" and nodetext:
                                if nodetext in isaffected_predicates:
                                    subpredicate = isaffected_predicates[nodetext]
                                else:
                                    self.log.warning("Can't express '%s' as a isaffected predicate" % nodetext)
                                
                        elif node.name == "strong":
                            subpredicate = None
                            if node.string == "Treaty:":
                                predicate = "treaty"
                            elif node.string == "Affected by case:":
                                predicate = "isaffected"
                            elif node.string == "Case affecting:":
                                predicate = "affects"
                            elif node.string == "Instruments cited in case law:":
                                predicate = "cites"
                            else:
                                self.log.warning("Don't know how to handle key '%s'" % node.string)
                        elif node.name == "a" and predicate:
                            p = predicate
                            if subpredicate:
                                p = subpredicate
                            # FIXME: If the
                            # predicate is "cites", the celex number
                            # may have extra crap
                            # (eg. "31968R0259(01)-N2A1L6") indicating
                            # pinpoint location. Transform these to a
                            # fragment identifier.
                            add_celex_object(p,node.string.strip())

        # Process text and create DOM
        self.parser = LegalRef(LegalRef.EGRATTSFALL)
        body = Body()

        textdiv = soup.find("div","texte")
        if textdiv:
            for node in textdiv.childGenerator():
                if node.string:
                    # Here we should start analyzing for things like
                    # "C-197/09". Note that the Eurlex data does not use
                    # the ordinary hyphen like above, but rather
                    # 'NON-BREAKING HYPHEN' (U+2011) - LegaRef will mangle
                    # this to an ordinary hyphen.
                    subnodes = self.parser.parse(node.string,
                                                 predicate="dct:references")
                    body.append(Paragraph(subnodes))
        else:
            self.log.warning("%s: No fulltext available!" % celexnum)

        return {'meta':g,
                'body':body,
                'lang':'en',
                'uri':uri}



    @classmethod
    def relate_all_setup(cls, config):
        # before extracting all RDFa, create a Whoosh index
        print "Doing subclass-specific setup (that can be done w/o an instance)"
        if ('whoosh_indexing' in config[cls.module_dir] and
            config[cls.module_dir]['whoosh_indexing'] == 'True'):
            print "We're doing whoosh_indexing!"
        else:
            print "No whoosh_indexing :-("
        
        indexdir = os.path.sep.join([config['datadir'],cls.module_dir,'index'])
        if not os.path.exists(indexdir):
            os.mkdir(indexdir)

        print "Creating a new index"
        ana = analysis.StemmingAnalyzer()
        schema = Schema(title=TEXT(stored=True),
                        basefile=ID(stored=True, unique=True),
                        content=TEXT)
        # FIXME: Get a keyword list, correct title, and list of treaty
        # references (celex nums as keywords or uris or...)
        whoosh_ix = create_in(indexdir, schema)

        base_dir = config['datadir']
        
        from time import time
        
        for basefile in cls.get_iterable_for("relate_all",base_dir):
            if not ("J" in basefile or "A" in basefile or "K" in basefile):
                continue
            readstart = time()
            # just save the text from the document, strip out the tags
            from BeautifulSoup import BeautifulSoup
            m = cls.re_celexno.match(basefile)
            year = m.group(2)
            parsed_file = os.path.sep.join([base_dir, cls.module_dir, u'parsed', year, basefile+'.xhtml'])
            
            soup = BeautifulSoup(open(parsed_file).read())
            text = ''.join(soup.findAll(text=True))
            # Skip the first 150 chars (XML junk) and normalize space
            text = ' '.join(text[150:].split())
            if text:
                indexstart = time()
                writer = whoosh_ix.writer()
                writer.update_document(title="Case "+ basefile,basefile=basefile,content=text)
                writer.commit()
                print "Added %s '%s...' %.1f kb in %.3f + %.3f s" % (basefile, text[:39], len(text)/1024, indexstart-readstart, time()-indexstart)
            else:
                print "Noadd %s (no text)" % (basefile)
            

        searcher = whoosh_ix.searcher()
        results = searcher.find("content", "quantitative imports equivalent prohibited", limit=10)
        for i in range(len(results)):
            print "%s: %s" % (results[i]['title'], results.score(i))

            
if __name__ == "__main__":
    EurlexCaselaw.run()
