import sys,re
from BeautifulSoup import BeautifulSoup

if sys.argv[1].startswith("http://") or sys.argv[1].startswith("https://"):
    import urllib2
    print "Fetching %s from web" % sys.argv[1]
    fp = urllib2.urlopen(sys.argv[1])
else:
    fp = open(sys.argv[1])

soup = BeautifulSoup(fp)
