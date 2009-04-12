#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Metamodul som korsrefererar nyckelord som hittats i domslut, andra
beslut, lagkommentarswikitext, osv"""

# system libraries
import logging
import sys, os, re
from collections import defaultdict

# 3rdparty libs
from configobj import ConfigObj
from genshi.template import TemplateLoader

# my libs
import Util
import LegalSource
from DispatchMixin import DispatchMixin




__version__   = (1,6)
__author__    = u"Staffan Malmgren <staffan@tomtebo.org>"
__shortdesc__ = u"Nyckelord/sökord"
__moduledir__ = "keyword"
log = logging.getLogger(__moduledir__)

class KeywordDownloader(LegalSource.Downloader):
    def _get_module_dir(self):
        return __moduledir__

    def DownloadAll(self):
        # Get all "term sets" (used dct:subject Objects, wiki pages
        # describing legal concepts, swedish wikipedia pages...)
        #
        # 1) Query the RDF DB for all dct:subject triples (is this
        # semantically sensible for a "download" action -- the
        # content isn't really external?) -- term set "subjects"
        #
        # 2) Download the wiki.lagen.nu dump from
        # http://wiki.lagen.nu/pages-articles.xml -- term set "wiki"
        #
        # 3) Download the Wikipedia dump from
        # http://download.wikimedia.org/svwiki/latest/svwiki-latest-all-titles-in-ns0.gz
        # -- term set "wikipedia"
        #
        # 4) Download all pages from Jureka, probably by starting at
        # pageid = 1 and incrementing until done -- term set "jureka"
        #
        # Possible future term sets: EUROVOC, Rikstermdatabasen (or a
        # subset thereof), various gov websites... Lawtext also
        # contains a number of term definitions, maybe marked up as
        # dct:defines.
        #
        # Store all terms under downloaded/[term] (for wikipedia,
        # store only those terms that occur in any of the other term
        # sets). The actual content of each text file contains one
        # line for each term set the term occurs in.

        pass

    def DownloadNew():
        # Same as above, except use http if-modified-since to avoid
        # downloading swedish wikipedia if not updated. Jureka uses a
        # page id parameter, so check if there are any new ones.
        
        pass 

class KeywordParser(LegalSource.Downloader):
    def Parse(self,basefile,files):
        # for a base name (term), create a skeleton xht2 file
        # containing a element of some kind for each term set this
        # term occurs in.
        pass
    

class KeywordManager(LegalSource.Manager):
    transtbl = {ord(u'?'):    None,
                ord(u' '):    u'_',
                ord(u'–'): u'-'}

    def __init__(self):
        super(KeywordManager,self).__init__()
        self.moduleDir = "dv" # to fake Indexpages to load dv/parsed/rdf.nt -- will do for now
        
    def _get_module_dir(self):
        return __moduledir__

    def Parse(self,basefile,verbose=False):
        log.info("Not implemented")

    def Generate(self,basefile):
        log.info("Not implemented")
        # Use a SPARQL query to create a rdf graph (to be used by the
        # xslt transform) containing enough information about all
        # cases using this term, as well as the wiki authored
        # dct:description for this term.
    
    __parserClass = KeywordParser
    def _build_indexpages(self, by_pred_obj, by_subj_pred):
        documents = defaultdict(lambda:defaultdict(list))
        pagetitles = {}
        pagelabels = {}
        lbl = u'Sökord/begrepp'
        dct_subject = Util.ns['dct']+'subject'
        dct_identifier = Util.ns['dct']+'identifier'
        count = 0
        for keyword in sorted(by_pred_obj[dct_subject]):
            if len(keyword) > 60:
                continue
            count += 1
            if count % 10 == 0:
                sys.stdout.write(".")

            letter = keyword[0].lower()
            if letter.isalpha():
                pagetitles[letter] = u'Sokord/begrepp som borjar pa "%s"' % letter.upper()
                pagelabels[letter]= letter.upper()
                documents[lbl][letter].append({'uri':u'/keyword/generated/%s.html' % keyword.translate(self.transtbl),
                                               'title':keyword,
                                               'sortkey':keyword})

            legalcases = {}
            for doc in list(set(by_pred_obj[dct_subject][keyword])):
                # print u"\tdoc %s (%s)" % (doc, by_subj_pred[doc][dct_identifier])
                legalcases[doc] = by_subj_pred[doc][dct_identifier]
            self._build_single_page(keyword,legalcases)

        sys.stdout.write("\n")

        for pageid in documents[lbl].keys():
            outfile = "%s/%s/generated/index/%s.html" % (self.baseDir, __moduledir__, pageid)
            title = pagetitles[pageid]
            self._render_indexpage(outfile,title,documents,pagelabels,lbl,pageid)

    def _build_single_page(self, keyword, legalcases):
        # build a xht2 page containing stuff - a link to
        # wikipedia and/or jureka if they have a page matching
        # the keyword, the wikitext for the keyword, and of
        # course a list of legal cases
        # print "Building a single page for %s (%s cases)" % (keyword, len(legalcases))
        outfile = "%s/%s/generated/%s.html" % (self.baseDir,
                                               __moduledir__,
                                               keyword.translate(self.transtbl))

        loader = TemplateLoader(['.' , os.path.dirname(__file__)], 
                                variable_lookup='lenient') 
        tmpl = loader.load("etc/keyword.template.xht2")

        stream = tmpl.generate(title=keyword,
                               legalcases=legalcases)
        #tmpfilename = mktemp()
        tmpfilename = outfile.replace(".html",".xht2")
        Util.ensureDir(tmpfilename)
        fp = open(tmpfilename,"w")
        fp.write(stream.render())
        fp.close()


        Util.ensureDir(outfile)
        Util.transform("xsl/static.xsl", tmpfilename, outfile, validate=False)
        log.info("rendered %s" % outfile)
        
if __name__ == "__main__":
    import logging.config
    logging.config.fileConfig('etc/log.conf')
    KeywordManager.__bases__ += (DispatchMixin,)
    mgr = KeywordManager()
    mgr.Dispatch(sys.argv)
