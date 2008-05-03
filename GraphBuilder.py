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

from rdflib.Graph import Graph
from rdflib import URIRef, Literal
import Util
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

def build_dotfile(g):
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
    identifier = URIRef(u'http://dublincore.org/documents/dcmi-terms/identifier')
    description = URIRef(u'http://dublincore.org/documents/dcmi-terms/description')
    dctsubject = URIRef(u'http://dublincore.org/documents/dcmi-terms/subject')

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

def create_graph(f):
    start = time()
    dotfile = codecs.open("tmp.dot","w","utf-8")
    dotfile.write(f.getvalue())
    dotfile.close()
    p = subprocess.Popen("neato -x -Tpng -oout.png tmp.dot")
    ret = p.wait()
    print "PNG graph created in %.3f sec" % (time() - start)

if __name__ == "__main__":
    g = build_rdf_graph(sys.argv[1].decode('iso-8859-1'))
    f = build_dotfile(g)
    create_graph(f)
    
