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
import Util
from DispatchMixin import DispatchMixin


log = logging.getLogger(u'ls')

__version__   = (1,6)
__author__    = u"Staffan Malmgren <staffan@tomtebo.org>"
__shortdesc__ = u"Nyckelord/sökord"
__moduledir__ = "keyword"
log = logging.getLogger(__moduledir__)

class KeywordDownloader(LegalSource.Downloader):
    def _get_module_dir(self):
        return __moduledir__

    def DownloadAll(self):
        pass # code to download the Wikipedia dump goes here

    def DownloadNew():
        pass # code to download the Wikipedia dump if the current is too old

class KeywordParser(LegalSource.Downloader):
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

    def Generate():
        log.info("Not implemented")
        # or is this the place to generate a page for every single keyword in the system?
    
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
