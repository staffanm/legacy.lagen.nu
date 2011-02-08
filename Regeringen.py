#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# A abstract base class for fetching and parsing documents
# (particularly preparatory works) from regeringen.se 
import sys,os,re,datetime
import urllib
import urlparse
import logging

from mechanize import LinkNotFoundError
import BeautifulSoup
from rdflib import Literal, Namespace, URIRef, RDF, RDFS

from DocumentRepository import DocumentRepository
import Util

class Regeringen(DocumentRepository):
    start_url = "http://regeringen.se/sb/d/108"
    KOMMITTEDIREKTIV = 1
    DS = 2
    PROPOSITION = 3
    SKRIVELSE = 4
    SOU = 5
    SO = 6

    def download_everything(self,usecache=False):
        assert self.document_type != None
        
        self.log.info("Starting at %s" % self.start_url)
        self.browser.open(self.start_url)
        # tried self.browser.select_form(predicate=lambda
        # f:f.action.endswith("/sb/d/108")), but that doesn't work
        # with the self.browser["contentType"] = ["1"] call below
        for f in self.browser.forms():
            if f.action.endswith("/sb/d/108"):
                self.browser.form = f

        self.browser["contentTypes"] = [str(self.document_type)]
        self.browser.submit()
        done = False
        pagecnt = 1
        while not done:
            self.log.info(u'Result page #%s' % pagecnt)
            mainsoup = BeautifulSoup.BeautifulSoup(self.browser.response(), )
            for link in mainsoup.findAll(href=re.compile("/sb/d/108/a/")):
                desc = link.findNextSibling("span",{'class':'info'}).contents[0]
                try:
                    # use a strict regex first, then a more forgiving
                    m = self.re_basefile_strict.search(desc)
                    if not m:
                        m = self.re_basefile_lax.search(desc)
                        if not m:
                            self.log.error("Can't find Document ID from %s, forced to skip" % desc)
                            continue
                        else:
                            tmpurl = urlparse.urljoin(self.browser.geturl(),link['href'])
                            self.log.warning("%s (%s) not using preferred form: '%s'" %
                                             (m.group(1), tmpurl, m.group(0)))
                    basefile = m.group(1)
                    if usecache and os.path.exists(self.downloaded_path(basefile)):
                        self.log.debug("%s exists, not calling download_single" % basefile)
                        continue
                except AttributeError:
                    self.log.warning("Can't find basefile from %s, forced to skip" % desc)
                    continue
                absolute_url = urlparse.urljoin(self.browser.geturl(),link['href'])
                if self.download_single(basefile,usecache,absolute_url):
                    self.log.info("Downloaded %s" % basefile)
            try:
                self.browser.follow_link(text='Nästa sida')
                pagecnt += 1
            except LinkNotFoundError:
                self.log.info(u'No next page link found, this was the last page')
                done = True



    def remote_url(self,basefile):
        # do a search to find the proper url for the document
        self.log.info("Starting at %s" % self.start_url)
        self.browser.open(self.start_url)
        for f in self.browser.forms():
            if f.action.endswith("/sb/d/108"):
                self.browser.form = f
        self.browser["contentTypes"] = ["1"]
        self.browser["archiveQuery"] = basefile
        self.browser.submit()
        soup = BeautifulSoup.BeautifulSoup(self.browser.response())
        for link in soup.findAll(href=re.compile("/sb/d/108/a/")):
            desc = link.findNextSibling("span",{'class':'info'}).text
            if basefile in desc:
                url = urlparse.urljoin(self.browser.geturl(),link['href'])
        if not url:
            self.log.error("Could not find document with basefile %s" % basefile)
        return url

    def downloaded_path(self,basefile,leaf=None):
        # 2007:5 -> dir-polo/downloaded/2007/5/index.html
        # 2010/11:68 -> prop-polo/downloaded/2010-11/68/index.html
        if not leaf:
            leaf = "index.html"
        basefile = basefile.replace("/","-")
        segments = [self.base_dir, self.module_dir, u'downloaded']
        segments.extend(re.split("[/:]", basefile))
        segments.append(leaf)
        return os.path.sep.join(segments)
                
    def download_single(self,basefile,usecache=False,url=None):
        if not url:
            url = self.remote_url(basefile)
            if not url: # remote_url failed
                return
        filename = self.downloaded_path(basefile) # just the html page
        if not usecache or not os.path.exists(filename):
            existed = os.path.exists(filename)
            updated = self.download_if_needed(url,filename)
            docid = url.split("/")[-1]
            if existed:
                if updated:
                    self.log.debug("%s existed, but a new ver was downloaded" % filename)
                else:
                    self.log.debug("%s is unchanged -- checking PDF files" % filename)
            else:
                self.log.debug("%s did not exist, so it was downloaded" % filename)

            soup = BeautifulSoup.BeautifulSoup(open(filename))
            cnt = 0
            pdfupdated = False
            pdfgroup = soup.find('div', {'class':'multipleLinksPuff doc'})
            if pdfgroup:
                for link in pdfgroup.findAll('a', href=re.compile('/download/(\w+\.pdf).*')):
                    cnt += 1
                    pdffile = re.match(r'/download/(\w+\.pdf).*', link['href']).group(1)
                
                    # note; the pdfurl goes to a redirect script; however that
                    # part of the URL tree (/download/*) is off-limits for
                    # robots. But we can figure out the actual URL anyway!
                    if len(docid) > 4:
                        path = "c6/%02d/%s/%s" % (int(docid[:-4]),docid[-4:-2],docid[-2:])
                    else:
                        path = "c4/%02d/%s" % (int(docid[:-2]),docid[-2:])
                    pdfurl = "http://regeringen.se/content/1/%s/%s" % (path,pdffile)
                    pdffilename = self.downloaded_path(basefile,pdffile)
                    if self.download_if_needed(pdfurl,pdffilename):
                        pdfupdated = True
                        self.log.debug("    %s is new or updated" % pdffilename)
                    else:
                        self.log.debug("    %s is unchanged" % pdffilename)
            else:
                self.log.warning("%s (%s) has no downloadable PDF files" % (basefile,url))
            if updated or pdfupdated:
                # One or more of the resources was updated (or created) --
                # let's make a note of this in the RDF graph!
                uri = self.canonical_uri(basefile)
                self.store_triple(URIRef(uri), self.ns['dct']['modified'], Literal(datetime.datetime.now()))
                return True # Successful download of new or changed file
            else:
                self.log.debug("%s and all PDF files are unchanged" % filename)
        else:
            self.log.debug("%s already exists" % (filename))
        return False
