import os, sys

try:
    import mwclient
except:
    pass
import xml.etree.cElementTree as ET

HOST = "wiki.lagen.nu"
PATH = "/"
USER = "staffan"
PASS = "meneta"

def import_page(title,wikimarkup,site):
    page = site.Pages[title]
    try:
        page.save(wikimarkup, summary="Offline-redigering")
        print "Saved %s" % title
    except mwclient.errors.EditError:
        print "Couldn't save '%s'" % title

def extract_page(filename):
    tree = ET.parse(filename)
    title = tree.find("//{http://www.mediawiki.org/xml/export-0.3/}title").text
    wikimarkup = tree.find("//{http://www.mediawiki.org/xml/export-0.3/}text").text
    return (title,wikimarkup)


def process_files(dir, site):
    for f in os.listdir(dir):
        filename = "%s%s%s" % (dir,os.path.sep,f)
        (title, wikimarkup) = extract_page(filename)
        import_page(title,wikimarkup,site)

if __name__ == "__main__":
    site = mwclient.Site(HOST, PATH)
    site.login(USER,PASS)
    process_files(sys.argv[1],site)
