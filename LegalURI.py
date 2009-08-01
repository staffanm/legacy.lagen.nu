#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""This module constructs URIs for a document based on the properties
of that document. Alternatively, given a URI for a document, parse the
different properties for the document"""

# system libs
import sys
import re
from pprint import pformat

# 3rdparty libs
from rdflib.Graph import Graph
from rdflib.BNode import BNode
from rdflib import Literal, Namespace, URIRef, RDF, RDFS

# my own libraries
from FilebasedTester import FilebasedTester
from DispatchMixin import DispatchMixin
from LegalRef import LegalRef
import Util

RINFO = Namespace(Util.ns['rinfo'])

# Maps keys used by the internal dictionaries that LegalRef
# constructs, which in turn are modelled after production rule names
# in the EBNF grammar.
predicate = {"type": RDF.type,
             "publikation": RINFO["rattsfallspublikation"],
             "artal": RINFO["artal"],
             "sidnummer": RINFO["sidnummer"]}

dictkey = dict([[v,k] for k,v in predicate.items()])

types = {LegalRef.RATTSFALL: RINFO["Rattsfallsreferat"],
         LegalRef.LAGRUM: RINFO["KonsolideradGrundforfattning"]}

dicttypes = dict([[v,k] for k,v in types.items()])

patterns = {LegalRef.RATTSFALL:
            re.compile("http://rinfo.lagrummet.se/publ/rattsfall/(?P<publikation>\w+)/(?P<artal>\d+)(?P<_delim>.)(?P<sidnummer>\d+)").match
            }

# The dictionary should be a number of properties of the document we
# wish to construct the URI for, e.g:
# {"type": LegalRef.RATTSFALL,
#  "publikation": "nja",
#  "artal": "2004"
#  "sidnr": "43"}
#
# The output is a URI like 'http://rinfo.lagrummet.se/publ/rattsfall/nja/2004s43'
def construct(dictionary):
    # Step 1: massage the data to a rdflib graph
    graph = Graph()
    bnode = BNode()
    for key in dictionary:
        if key == "type":
            graph.add((bnode,RDF.type,URIRef(types[dictionary[key]])))
        else:
            graph.add((bnode, predicate[key], Literal(dictionary[key])))
    # print graph.serialize(format="nt")
    return construct_from_graph(graph)

def _first_obj(graph,subject,predicate):
    l = list(graph.objects(subject,predicate))
    if not l:
        raise ValueError("No objects with predicate %s found in the graph" % predicate)
    else:
        return l[0]
                        

def construct_from_graph(graph):
    # assume every triple in the graph has the same bnode as subject
    bnode = list(graph)[0][0]
    assert(isinstance(bnode,BNode))
    rdftype = _first_obj(graph,bnode,RDF.type)
    if rdftype == RINFO["Rattsfallsreferat"]:
        publ = _first_obj(graph,bnode,RINFO["rattsfallspublikation"])
        if publ == "nja":
            uripart = "%s/%ss%s" % (publ,
                                    _first_obj(graph,bnode,RINFO["artal"]),
                                    _first_obj(graph,bnode,RINFO["sidnummer"]))
        else:
            raise ValueError("Don't know how to format a %s with rinfo:rattsfallspublikation %s" % (RINFO["Rattsfallsreferat"], publ))
        return "http://rinfo.lagrummet.se/publ/rattsfall/%s" % uripart
    elif rdftype == RINFO["KonsolideradGrundforfattning"]:
        pass
        
    
def parse(uri):
    graph = parse_to_graph(uri)
    dictionary = {}
    for (subj,pred,obj) in graph:
        if pred == RDF.type:
            dictionary["type"] = dicttypes[obj]
        else:
            dictionary[dictkey[pred]] = unicode(obj)

    return dictionary

def parse_to_graph(uri):
    dictionary = None
    for (pid, pattern) in patterns.items():
        m = pattern(uri)
        if m:
            dictionary = m.groupdict()
            dictionary["type"] = pid
            break

    if not dictionary:
        raise ValueError("Can't parse URI %s" % uri)

    graph = Graph()
    for key, value in Util.ns.items():
        graph.bind(key,  Namespace(value));
    bnode = BNode()
    for key in dictionary:
        if key.startswith("_"):
            continue
        if key == "type":
            graph.add((bnode,RDF.type,URIRef(types[dictionary[key]])))
        else:
            graph.add((bnode, predicate[key], Literal(dictionary[key])))

    return graph


class Tester(FilebasedTester):
    # By using the same set of tests, but switching which file
    # contains the testdata and which contains the answer, we get a
    # nice roundtrip test
    testparams = {'Parse': {'dir': u'test/LegalURI',
                            'testext':'.txt',
                            'answerext':'.py'},
                  'Construct': {'dir': u'test/LegalURI',
                                 'testext':'.py',
                                 'answerext':'.txt'}}

    def TestConstruct(self,data):
        # All test case writers are honorable, noble and thorough
        # persons, but just in case, let's make eval somewhat safer.
        d = eval(data.strip(),{"__builtins__":None},globals())
        uri = construct(d)
        return uri

    def TestParse(self,uri):
        d = parse(uri.strip())
        return pformat(d)

if __name__ == "__main__":
    Tester.__bases__ += (DispatchMixin,)
    t = Tester()
    t.Dispatch(sys.argv)
