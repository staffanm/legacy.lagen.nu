#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
import sys,os
import re
import datetime

from rdflib import Namespace, URIRef, Literal, RDF
from rdflib.Graph import Graph
from mechanize import LinkNotFoundError

from DocumentRepository import DocumentRepository
import Util
import LegalURI
from LegalRef import LegalRef, Link
from DataObjects import UnicodeStructure, CompoundStructure, Stycke

from whoosh.index import create_in, open_dir
from whoosh.fields import Schema, TEXT, ID

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
    def download_everything_old(self,cache=False):
        # Request every month from now back to circa 1990 (the DB
        # *should* contain earlier cases, but it doesn't - an
        # alternative way might be to just guess CELEX numbers by
        # incrementing year and case numbers, and see if they exist)
        for year in reversed(range(1990,datetime.date.today().year+1)):
            for month in reversed(range(1,13)):
                list_url = "http://eur-lex.europa.eu/JURISMonth.do?year=%d&month=%02d" % (year,month)
                self.log.debug("Downloading list for %d/%d" % (year,month))
                self.browser.open(list_url)
                links = list(self.browser.links(text='Bibliographic notice'))
                self.log.debug("%d/%d has %s documents" % (year,month, len(links)))
                for link in links:
                    m = self.re_celexno.search(link.url)
                    if m:
                        celexno = m.group(0)
                        # only download actual judgements
                        # J: Judgment of the Court
                        # A: Judgment of the Court of First Instance
                        # W: Judgement of the Civil Service Tribunal
                        # T: (old) Judgement of the Court
                        if ('J' in m or 'A' in m or 'W' in m):
                            self.log.debug("Downloading case %s" % celexno)
                            self.download_single(celexno,cache=True)


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

        # 1 Find basic metadata
        meta = {}
        # :celex - first <h1>
        meta['celexnum'] = soup.first("h1").string.strip()
        
        # :courtdecision, :party (one or two items), :referingcourt
        # (optional), :legalissue (list of strings), :casenum -
        # <strong>/<p> following <h2>Title and reference</h2>

        # :casereporter - the last p, contains an <em> tag
        title_paras = soup.find("h2").findNextSiblings("p")
        for para in title_paras:
            # self.log.debug(u"Handling para %s" % para)
            if not 'courtdecision' in meta: # optional: do sanitychecks to see if this really is a :courtdecision
                meta['courtdecision'] = para.string.strip()
            # self.log.debug("  Filed as courtdecision")
            elif not 'party' in meta:
                meta['party'] = para.string # split up if needed (if the string " v " occurs)
                # self.log.debug("  Filed as party")
            elif (not 'referingcourt' in meta and para.string and
                  para.string.startswith("Reference for a preliminary ruling")):
                meta['referingcourt'] = para.string
                # self.log.debug("  Filed as referingcourt")
            elif (not 'casenum' in meta and para.string and
                  (para.string.strip().lower().startswith("case ") or
                   para.string.strip().lower().startswith("joined cases "))):
                meta['casenum'] = para.string.strip() # optionally trim trailing characters?
                # self.log.debug("  Filed as casenum")
            elif para.em:
                meta['casereporter'] = ''.join(para.findAll(text=True)).strip()
                # self.log.debug("  Filed as casereporter")
            elif not 'legalissue' in meta:
                meta['legalissue'] = para.string # split this up
                # self.log.debug("  Filed as legalissue")
            pass
        
        # 2 Create canonical URI for our document (deliverable A) The
        # URI could either be based upon case number or celex
        # number. These can be transformed into one another (eg
        # C-357/09 -> 62009J0357). To keep things simple, let's use
        # the celex number as the basis (in the future, we should
        # extend LegalURI to do it)
        uri = "http://lagen.nu/ext/celex/%s" % meta['celexnum']
        # 3 Create RDF graph from basic metadata (deliverable B)
        g = Graph()
        voc = Namespace(self.vocab_url)
        g.bind('dct',self.ns['dct'])
        g.bind('eurlex',voc)
        g.add((URIRef(uri),voc['celexnum'],Literal(meta['celexnum'],lang="en")))
        g.add((URIRef(uri),voc['courtdecision'],Literal(meta['courtdecision'], lang="en")))
        g.add((URIRef(uri),voc['casenum'],Literal(meta['casenum'], lang="en")))
        # add more later...

        # 4 Process text and create DOM (deliverable C)
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
            self.log.warning("%s: No fulltext available!" % meta['celexnum'])

        return {'meta':g,
                'body':body,
                'lang':'en',
                'uri':uri}

    @classmethod
    def relate_all_setup(cls, config):
        # before extracting all RDFa, create a Whoosh index
        print "Doing subclass-specific setup (that can be done w/o an instance)"

        indexdir = os.path.sep.join([config['datadir'],cls.module_dir,'index'])
        if not os.path.exists(indexdir):
            os.mkdir(indexdir)

        print "Creating a new index"
        schema = Schema(title=TEXT(stored=True),
                        basefile=ID(stored=True, unique=True),
                        content=TEXT)
        # FIXME: Get a keyword list, correct title, and list of treaty
        # references (celex nums as keywords or uris or...)
        whoosh_ix = create_in(indexdir, schema)
        writer = whoosh_ix.writer()

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
            indexstart = time()
            writer.update_document(title="Case "+ basefile,basefile=basefile,content=text)
            writer.commit()
            print "Added %s '%s...' %.1f kb in %.3f + %.3f s" % (basefile, text[:39], len(text)/1024, indexstart-readstart, time()-indexstart) 
            
        writer.commit()
        searcher = whoosh_ix.searcher()
        results = searcher.find("content", "citizen move reside", limit=10)
        for i in range(len(results)):
            print "%s: %s" % (results[i]['title'], results.score(i))

        # then call the super method to clear the RDF DB

    # skip the actual relation 
    def relate(self,basefile):
        pass

            
if __name__ == "__main__":
    EurlexCaselaw.run()
