#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Metamodul som korsrefererar nyckelord som hittats i domslut, andra
beslut, lagkommentarswikitext, osv"""

# system libraries
import logging
import sys, os, re, shutil
from collections import defaultdict
from pprint import pprint
from time import time
from tempfile import mktemp
import xml.etree.cElementTree as ET
import xml.etree.ElementTree as PET

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

class KeywordParser(LegalSource.Parser):
    def Parse(self,basefile,infile,config):
        # for a base name (term), create a skeleton xht2 file
        # containing a element of some kind for each term set this
        # term occurs in.
        baseuri = "http://lagen.nu/concept/%s" % basefile.replace(" ","_")
        
        root = ET.Element("html")
        root.set("xml:base", baseuri)
        root.set("xmlns", 'http://www.w3.org/2002/06/xhtml2/')
        root.set("xmlns:dct", Util.ns['dct'])
        head = ET.SubElement(root, "head")
        title = ET.SubElement(head, "title")
        title.text = basefile
        body = ET.SubElement(root,"body")
        heading = ET.SubElement(body,"h")
        heading.set("property", "dct:title")
        
        heading.text = basefile
        return ET.tostring(root,encoding='utf-8')
    

class KeywordManager(LegalSource.Manager):
    transtbl = {ord(u'?'):    None,
                ord(u' '):    u'_',
                ord(u'–'): u'-'}

    def __init__(self):
        super(KeywordManager,self).__init__()
        # self.moduleDir = "dv" # to fake Indexpages to load dv/parsed/rdf.nt -- will do for now
        
    def _get_module_dir(self):
        return __moduledir__

    def Parse(self,basefile,verbose=False):
        if verbose:
            print "Setting verbosity"
            log.setLevel(logging.DEBUG)
        start = time()
        basefile = basefile.replace(":","/")
        infile = os.path.sep.join([self.baseDir, __moduledir__, 'downloaded', basefile]) + ".xml"
        outfile = os.path.sep.join([self.baseDir, __moduledir__, 'parsed', basefile]) + ".xht2"
        force = self.config[__moduledir__]['parse_force'] == 'True'
        if not force and self._outfile_is_newer([infile],outfile):
            log.debug(u"%s: Överhoppad", basefile)
            return
        p = self.__parserClass()
        p.verbose = verbose
        parsed = p.Parse(basefile,infile,self.config)
        Util.ensureDir(outfile)

        tmpfile = mktemp()
        out = file(tmpfile, "w")
        out.write(parsed)
        out.close()
        Util.replace_if_different(tmpfile,outfile)
        log.info(u'%s: OK (%.3f sec)', basefile,time()-start)


    def Generate(self,term):
        infile = Util.relpath(self._xmlFileName(term))
        outfile = Util.relpath(self._htmlFileName(term))
        
        # Use SPARQL queries to create a rdf graph (to be used by the
        # xslt transform) containing enough information about all
        # cases using this term, as well as the wiki authored
        # dct:description for this term.

        # For proper SPARQL escaping, we need to change å to \u00E5
        # etc (there probably is a neater way of doing this).
        
        escterm = ''
        for c in term:
            if ord(c) > 127:
                escterm += '\u%04X' % ord(c)
            else:
                escterm += c
        
        sq = """
PREFIX dct:<http://purl.org/dc/terms/>
PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
PREFIX rinfo:<http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#>

SELECT ?desc
WHERE { ?uri dct:description ?desc . ?uri rdfs:label "%s"@sv }
""" % escterm

        wikidesc = self._store_select(sq)

        sq = """
PREFIX dct:<http://purl.org/dc/terms/>
PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
PREFIX rinfo:<http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#>

SELECT ?uri ?id ?desc
WHERE { ?uri dct:description ?desc .
        ?uri dct:identifier ?id .
        ?uri dct:subject "%s"@sv }
""" % escterm
        
        rattsfall = self._store_select(sq)

        root_node = PET.Element("rdf:RDF")
        for prefix in Util.ns:
            PET._namespace_map[Util.ns[prefix]] = prefix
            root_node.set("xmlns:" + prefix, Util.ns[prefix])

        main_node = PET.SubElement(root_node, "rdf:Description")
        main_node.set("rdf:about", "http://lagen.nu/concept/%s" % term.replace(" ","_"))
        
        for d in wikidesc:
            desc_node = PET.SubElement(main_node, "dct:description")
            xhtmlstr = "<xht2:div xmlns:xht2='%s'>%s</xht2:div>" % (Util.ns['xht2'], d['desc'])
            xhtmlstr = xhtmlstr.replace(' xmlns="http://www.w3.org/2002/06/xhtml2/"','')
            desc_node.append(PET.fromstring(xhtmlstr.encode('utf-8')))

        for r in rattsfall:
            subject_node = PET.SubElement(main_node, "dct:subject")
            rattsfall_node = PET.SubElement(subject_node, "rdf:Description")
            rattsfall_node.set("rdf:about",r['uri'])
            id_node = PET.SubElement(rattsfall_node, "dct:identifier")
            id_node.text = r['id']
            desc_node = PET.SubElement(rattsfall_node, "dct:description")
            desc_node.text = r['desc']

        Util.indent_et(root_node)
        tree = PET.ElementTree(root_node)
        tmpfile = mktemp()
        tree.write(tmpfile, encoding="utf-8")

        annotations = "%s/%s/intermediate/%s.ann.xml" % (self.baseDir, self.moduleDir, term)
        
        Util.replace_if_different(tmpfile,annotations)

        force = (self.config[__moduledir__]['generate_force'] == 'True')
        if not force and self._outfile_is_newer([infile,annotations],outfile):
            log.debug(u"%s: Överhoppad", term)
            return

        Util.mkdir(os.path.dirname(outfile))
        start = time()

        # xsltproc silently fails to open files through the document()
        # functions if the filename has non-ascii
        # characters. Therefore, we copy the annnotation file to a
        # separate temp copy first.
        tmpfile = mktemp()
        shutil.copy2(annotations,tmpfile)
        
        # FIXME: create a relative version of annotations, instead of
        # hardcoding self.baseDir like below
        params = {'annotationfile':tmpfile.replace("\\","/")}
        Util.transform("xsl/keyword.xsl",
                       infile,
                       outfile,
                       parameters = params,
                       validate=False)

        Util.robust_remove(tmpfile)
        
        log.info(u'%s: OK (%s, %.3f sec)', term, outfile, time()-start)
        return

        
        
    
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
