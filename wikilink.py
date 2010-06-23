import os, sys

try:
    import mwclient
except:
    pass
import xml.etree.cElementTree as ET

HOST = "wiki.lagen.nu"
PATH = "/w/"
USER = "staffan"
PASS = "meneta"

#def import_page(title,wikimarkup,site):
#    page = site.Pages[title]
#    try:
#        page.save(wikimarkup, summary="Offline-redigering")
#        print "Saved %s" % title
#    except mwclient.errors.EditError:
#        print "Couldn't save '%s'" % title
#
#def extract_page(filename):
#    tree = ET.parse(filename)
#    title = tree.find("//{http://www.mediawiki.org/xml/export-0.3/}title").text
#    wikimarkup = tree.find("//{http://www.mediawiki.org/xml/export-0.3/}text").text
#    return (title,wikimarkup)
#
#
#def process_files(dir, site):
#    for f in os.listdir(dir):
#        filename = "%s%s%s" % (dir,os.path.sep,f)
#        (title, wikimarkup) = extract_page(filename)
#        import_page(title,wikimarkup,site)

if __name__ == "__main__":
    site = mwclient.Site(HOST, PATH)
    site.login(USER,PASS)
    # get a list of all pages
    pages = list(site.Pages)
    keywords = {}
    
    print len(pages)
    for p in pages:
        if p.redirect:
            keywords[p.name] = list(p.links())[0].name
        else:
            keywords[p.name] = p.name

    print "%s pages, %s real pages" % (len(pages), len(keywords))
