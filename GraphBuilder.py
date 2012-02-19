#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

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

try:
    from rdflib.Graph import Graph
except ImportError:
    from rdflib import Graph
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
                fontsize= 10

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

def create_graph(f, engine="dot", arguments="", filename="tmp.png", filetype="png"):
    start = time()
    dotfile = codecs.open("tmp.dot","w",encoding="utf-8", errors="replace")
    v = f.getvalue()
    dotfile.write(v)
    dotfile.close()
    cmdline = "%s %s -T%s -o%s tmp.dot" % (engine, arguments, filetype, filename)
    print "Running %s" % cmdline
    p = subprocess.Popen(cmdline, shell=True)
    ret = p.wait()
    print "Graph %s created in %.3f sec" % (filename, time() - start)

def build_csvfile_from_sparql_results(res):
    print "Writing %s rows to CSV file, YAY!" % len(res)
    import csv
    writer = csv.DictWriter(open("out.csv","w"), ['subj','pred','obj'])
    writer.writerows(res)
    
def sparql_select(sq):
    # store = SesameStore("http://localhost:8080/openrdf-sesame", "lagen.nu")
    store = SesameStore("http://localhost:8080/openrdf-sesame", "mysite")
    results = store.select(sq)
    tree = ET.fromstring(results)
    res = []
    resultnodes = tree.findall(".//{http://www.w3.org/2005/sparql-results#}result")
    print "%s rows in query result" %  len(resultnodes)
    for row in resultnodes:
        d = {}
        for element in row:
            key = element.attrib['name']
            value = element[0].text
            value = value.split("/")[-1]
            if "-" in value:
                value = value.split("-")[0]
            d[key] = value.encode("utf-8")
        res.append(d)
    return res

def build_dotfile_from_sparql_results(nodes, links, graphname):
    specials = {"61991J0267":"Keck\\n(C-267/91)",
                "61978J0120":"Cassis\\n(120/78)",
                "61974J0008":"Dassonville\\n(8/74)",
                "61984J0178":"German Beer\\n(178/84)",
                "61982J0174":"Sandoz\\n(174/82)",
                "61975J0104":"de Peijper\\n(104/75)",
                "61988J0202":"Terminal equipment\\n(C-202/88)",
                "61993J0427":"Bristol-Myers Squibb\\n(C-427/93)",
                #"61991J0146":"KYDEP\\n(C-146/91)",
                #"61993J0415":"Bosman\\(C-415/93)",
                #"61998J0379":"PreussenElektra\\n(C-379/98)",
                "62001J0101":"Bodil",
                #"61001A0006":"Matrazen\\n(T-6/01)",
                "62000J0465":u"Österreich. Rundfunk"}
                
    start = time()
    objs = defaultdict(dict)
    out = StringIO()
    out.write(u"""digraph G { 
         graph [fontname = "Arial",
		fontsize = 16,
                overlap = compress,
                model = subset,
		label = "%s",
                size=20,
		];
	node [	shape = box,
                style = rounded,
		fontname = "Arial",
                fontsize= 10,
                URL="http://eur-lex.europa.eu/LexUriServ/LexUriServ.do?uri=CELEX:\\N:EN:NOT"
                ];

""" % graphname)

    sizes = defaultdict(int)
    yearnodes = defaultdict(list)

    seen = {}
    for row in links:
        year = row['subj'][1:5]
        yearnodes[year].append(row['subj'])

    seen_links = {}
    seen_nodes = {}

    for row in nodes:
        # if not row['subj'] in seen_nodes:
            # print "Now I've seen %s" % row['subj']
        seen_nodes[row['subj']] = True
        sizes[row['subj']] = 0
        
    for row in links:
        if repr(row) in seen_links:
            continue
        seen_links[repr(row)] = True
        seen_nodes[row['subj']] = True
        sizes[row['obj']] += 1;

    seen_links = {}
    for row in links:
        if repr(row) in seen_links:
            # print "  Throwing away %s" % repr(row)
            continue
        # print "Continuing with %s" % repr(row)

        seen_links[repr(row)] = True
        try:
            if sizes[row['obj']] > 0:
                out.write(u"        \"%s\" -> \"%s\";\n" % (row['subj'], row['obj']))
        except UnicodeDecodeError:
            pass
        
    for (node,size) in sizes.items():
#        if not size > 0:
#            continue
        if node in specials:
            out.write(u"	\"%s\" [width=%.1f, height=%.1f, fixedsize=True, fontsize=%.1f, color=lightblue2, style=\"filled,rounded\", shape=box, label=\"%s\\n%s\\n[%d]\"];\n" % (node,size/1.3,size/2, (size*4)+8, specials[node],node, size))
        else:
            out.write(u"	\"%s\" [width=%.1f, height=%.1f, fontsize=%.1f, label=\"%s\\n[%s]\"];\n" % (node,size/1.3,size/2,(size*4)+8, node, size))

    out.write(u"}\n");
    print "dot graph (%s nodes, %s vertices) created in %.3f sec" % (len(seen_nodes),len(seen_links),time() -start)
    return out

def query_cite(celexid):
    # mapping between the most recent article (eg art 34 TFEU) and its
    # previous incarnations (article 28 EC, article 30 EEC etc)
    equiv = {'12008E034':['11997E028','11992E030','11957E030'],
             '12008E036':['11997E030','11992E036','11957E036'],
             '12008E267':['11997E234','11992E177','11957E177']}

    q = "{ ?subj eurlex:cites <http://lagen.nu/ext/celex/%s> }\n" % celexid
    if celexid in equiv:
        for e in equiv[celexid]:
            q += "    UNION { ?subj eurlex:cites <http://lagen.nu/ext/celex/%s> }\n" % e
    return """
PREFIX eurlex:<http://lagen.nu/eurlex#>
SELECT DISTINCT ?subj ?pred ?obj WHERE {

    %s
    FILTER (regex(str(?obj), "^http://lagen.nu/ext/celex/6") && ?pred = eurlex:cites)
}
""" % q

def query_link(celexid):
    # mapping between the most recent article (eg art 34 TFEU) and its
    # previous incarnations (article 28 EC, article 30 EEC etc)
    equiv = {'12008E034':['11997E028','11992E030','11957E030'],
             '12008E036':['11997E030','11992E036','11957E036'],
             '12008E267':['11997E234','11992E177','11957E177']}

    q = "{ ?subj eurlex:cites <http://lagen.nu/ext/celex/%s> }\n" % celexid
    if celexid in equiv:
        for e in equiv[celexid]:
            q += "    UNION { ?subj eurlex:cites <http://lagen.nu/ext/celex/%s> }\n" % e
    return """
PREFIX eurlex:<http://lagen.nu/eurlex#>
SELECT DISTINCT ?subj ?pred ?obj WHERE {
    ?subj ?pred ?obj .
    %s
    FILTER (regex(str(?obj), "^http://lagen.nu/ext/celex/6") && ?pred = eurlex:cites)
}
""" % q


# matches the prefix of the URL, ie 31996L0009 will match
# <http://lagen.nu/ext/celex/31996L0009> but also
# <http://lagen.nu/ext/celex/31996L0009-A03P1>
def query_citeroot(celexid):
    return """
PREFIX eurlex:<http://lagen.nu/eurlex#>
SELECT DISTINCT ?subj ?pred ?obj WHERE {
    ?subj ?pred ?obj .
    FILTER (regex(str(?obj), "^http://lagen.nu/ext/celex/%s") &&
            (?pred = eurlex:cites || ?pred = eurlex:interprets))
}
""" % celexid

def query_linkroot(celexid):
    return """
PREFIX eurlex:<http://lagen.nu/eurlex#>
SELECT DISTINCT ?subj ?pred ?obj WHERE {
    ?subj ?pred ?obj .
    ?obj  ?pred2 ?obj2 .
    ?subj  ?pred3 ?obj3 .
    FILTER (regex(str(?obj2), "^http://lagen.nu/ext/celex/%s") &&
            regex(str(?obj3), "^http://lagen.nu/ext/celex/%s") &&
            (?pred = eurlex:cites || ?pred = eurlex:interprets))
}
""" % (celexid,celexid)


if __name__ == "__main__":
    querytype = sys.argv[1]
    queryarg = sys.argv[2]
    if len(sys.argv) <= 3:
        outfile = querytype+"_"+queryarg+".pdf"
    else:
        outfile = sys.argv[3]
    filetype = outfile.split(".")[1]

    if querytype == "cite":
        nodes_sq = query_cite(queryarg)
        links_sq = query_link(queryarg)
    elif querytype == "citeroot":
        nodes_sq = query_citeroot(queryarg)
        links_sq = query_linkroot(queryarg)
    else:
        raise ValueError("Unknown query type %s" % querytype)
    print nodes_sq
    nodes = sparql_select(nodes_sq)

    print links_sq
    links = sparql_select(links_sq)

    f = build_dotfile_from_sparql_results(nodes, links, querytype + " " + queryarg)
    create_graph(f,engine="dot", filename=outfile, filetype=filetype)

