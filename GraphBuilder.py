#!/usr/bin/env python
#
# Script to build graphwiz graphs from RDF data
import os
import sys
import locale
import codecs
import subprocess
from collections import defaultdict
from time import time
from StringIO import StringIO
import xml.etree.cElementTree as ET

from rdflib.Graph import Graph
from rdflib import URIRef, Literal

import Util
from SesameStore import SesameStore


locale.setlocale(locale.LC_ALL,'') 
if sys.platform == 'win32':
    if sys.stdout.encoding:
        defaultencoding = sys.stdout.encoding
    else:
        defaultencoding = 'cp850'
else:
    if sys.stdout.encoding:
        defaultencoding = sys.stdout.encoding
    else:
        defaultencoding = locale.getpreferredencoding()
# print "setting sys.stdout to a '%s' writer" % defaultencoding
sys.stdout = codecs.getwriter(defaultencoding)(sys.__stdout__, 'replace')
sys.stderr = codecs.getwriter(defaultencoding)(sys.__stderr__, 'replace')

def build_rdf_graph(d):
    start = time()
    g = Graph()
    c = 0
    for f in os.listdir(d):
        if f.endswith(".xht2"):
            c += 1
            try:
                g.load(d + os.path.sep + f, format="rdfa")
                sys.stdout.write(".")
            except Exception:
                print "loading %r failed" % f
    sys.stdout.write("\n")
    print "Graph with %d triples loaded from %d files in %.3f sec" % (len(g), c, time() - start)
    return g

def build_dotfile_from_rdf_graph(g):
    start = time()
    objs = defaultdict(dict)
    # out = sys.stdout
    out = StringIO()
    out.write(u"""digraph G { 
         graph [fontname = "Arial",
		fontsize = 16,
                overlap = compress,
                model = subset,
		label = "%s",
                
		];
	node [	shape = box,
                style = rounded,
		fontname = "Arial",
                fontsize= 10];

""" % sys.argv[1].decode('iso-8859-1').replace("\\", "\\\\"))
    identifier = URIRef(u'http://purl.org/dc/terms/identifier')
    description = URIRef(u'http://purl.org/dc/terms/description')
    dctsubject = URIRef(u'http://purl.org/dc/terms/subject')

    rattsfall = URIRef(u'http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#rattsfallshanvisning')
    
    
    for (o,p,s) in g:
        if isinstance(s, Literal):
            objs[o][p] = Util.normalizeSpace(s)
        else:
            objs[o][p] = s

    # Build nodes for all primary objects
    for k in objs.keys():
        try: 
            idstr = Util.normalizeSpace(objs[k][identifier])
        except KeyError:
            continue
        try:
            descstr = Util.normalizeSpace(objs[k][description][:20])
        except KeyError:
            print "Description for %s is missing" % k
            descstr = ""
        out.write(u"\"%s\"" % idstr)
        out.write(u" [label=<%s<BR/>%s...>];\n" %
                  (idstr,
                   descstr))

    # build nodes for all dct:subjects ("Sokord")
    dctsubjects = {}
    for (subj, obj) in g.subject_objects(dctsubject):
        obj = Util.normalizeSpace(obj)
        dctsubjects[obj] = 1;
    for k in dctsubjects.keys():
        out.write(u"\"%s\"" % k)
        out.write(u" [shape=ellipse]\n")

          
    # Build relations between primary objects
#    for k in objs.keys():
#        for s in g.subjects(rattsfall,k):
#            if s in objs:
#                try:
#                    out.write(u"\"%s\" -> \"%s\"\n" %
#                              (Util.normalizeSpace(objs[s][identifier]),
#                               Util.normalizeSpace(objs[k][identifier])))
#                except KeyError:
#                    continue
#            else:
#                print "Couldn't map %s to %s: No identifier" % (objs[k][identifier], s)
#

    # build relations between primary objects and their dct:subjects
    for (subj, obj) in g.subject_objects(dctsubject):
        obj = Util.normalizeSpace(obj)
        out.write("\"%s\" -> \"%s\"\n" % (objs[subj][identifier], obj))
                      
    out.write("}")
    print "dot graph created in %.3f sec" % (time() -start)
    return out

def create_graph(f, engine="dot", arguments=""):
    start = time()
    dotfile = codecs.open("tmp.dot","w",encoding="utf-8", errors="replace")
    v = f.getvalue()
    dotfile.write(v)
    dotfile.close()
    p = subprocess.Popen("%s %s -Tpng -oout.png tmp.dot" % (engine, arguments))
    ret = p.wait()
    print "PNG graph created in %.3f sec" % (time() - start)

def build_csvfile_from_sparql_results(res):
    print "Writing %s rows to CSV file, YAY!" % len(res)
    import csv
    writer = csv.DictWriter(open("out.csv","w"), ['subj','pred','obj'])
    writer.writerows(res)
    
def sparql_select(sq):
    store = SesameStore("http://localhost:8080/openrdf-sesame", "inmemory")
    results = store.select(sq)
    tree = ET.fromstring(results)
    res = []
    for row in tree.findall(".//{http://www.w3.org/2005/sparql-results#}result"):
        d = {}
        for element in row:
            key = element.attrib['name']
            value = element[0].text
            value = value.split("/")[-1]
            d[key] = value.encode("utf-8")
        res.append(d)
    return res

def build_dotfile_from_sparql_results(res):
    start = time()
    objs = defaultdict(dict)
    out = StringIO()
    out.write(u"""digraph G { 
         graph [fontname = "Arial",
		fontsize = 16,
                overlap = compress,
                model = subset,
		label = "%s",
                size=20
		];
	node [	shape = box,
                style = rounded,
		fontname = "Arial",
                fontsize= 10];

""" % "Test graph")

    sizes = defaultdict(int)
    for (row) in res:
        try:
            out.write(u"        \"%s\" -> \"%s\";\n" % (row['subj'], row['obj']))
            sizes[row['obj']] += 1;
        except UnicodeDecodeError:
            pass

    for (node,size) in sizes.items():
        out.write(u"     \"%s\" [width=%.1f, height=%.1f];\n" % (node,size/1.3,size/2))
        
    out.write(u"}\n");
    print "dot graph created in %.3f sec" % (time() -start)
    return out

if __name__ == "__main__":
    # g = build_rdf_graph(sys.argv[1].decode('iso-8859-1'))
    # f = build_dotfile(g)
    # create_graph(f)

    # Query 1: Find citations to cases (we should really have ?obj
    # rdf:type eurlex:Judgment triples, so we could avoid this regex
    # kludge)
    sq1 = """
PREFIX eurlex:<http://lagen.nu/eurlex#>
SELECT DISTINCT ?subj ?pred ?obj WHERE {
    ?subj ?pred ?obj .
    FILTER ((?pred = eurlex:cites) && regex(str(?obj), "^http://lagen.nu/ext/celex/6"))
}
"""

    # Query 2: Find cases that interprets any article in the treaties
    sq2 = """
PREFIX eurlex:<http://lagen.nu/eurlex#>
SELECT DISTINCT ?subj ?pred ?obj WHERE {
    ?subj ?pred ?obj .
    ?subj eurlex:interprets ?article .
    FILTER ((?pred = eurlex:cites) &&
            (regex(str(?obj), "^http://lagen.nu/ext/celex/6")) &&
            (regex(str(?article), "^http://lagen.nu/ext/celex/1")))
}
"""

    # Query 3: Find cases that interprets Article 34 (Art 28
    # Amsterdam, Art 30 Maastricht)
    sq3 = """
PREFIX eurlex:<http://lagen.nu/eurlex#>
SELECT DISTINCT ?subj ?pred ?obj WHERE {
    ?subj ?pred ?obj .
    { ?subj eurlex:interprets <http://lagen.nu/ext/celex/11957E030> }
    UNION { ?subj eurlex:interprets <http://lagen.nu/ext/celex/11992E030> }
    UNION { ?subj eurlex:interprets <http://lagen.nu/ext/celex/11997E028> }
    UNION { ?subj eurlex:interprets <http://lagen.nu/ext/celex/12008E034> }
    FILTER (regex(str(?obj), "^http://lagen.nu/ext/celex/6") && ?pred = eurlex:cites)
}
"""

    res = sparql_select(sq2)
    build_csvfile_from_sparql_results(res)
    #f = build_dotfile_from_sparql_results(res)
    #create_graph(f,engine="neato")
