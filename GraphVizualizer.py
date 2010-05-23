#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
import sys
from cStringIO import StringIO

from rdflib import Literal, BNode, Namespace, URIRef, RDF
from rdflib.Graph import Graph
import pydot

from SesameStore import SesameStore



TRIPLESTORE = "http://localhost:8080/openrdf-sesame"
REPOSITORY = "lagen.nu"
DCT = Namespace('http://purl.org/dc/terms/')
RINFO = Namespace('http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#')

def sfs_label_transform(label):
    if "(1960:729)" in label:
        return "Upphovsrättslagen"
    elif "(1915:218)" in label:
        return "Avtalslagen";
    else:
        return re.sub(' \(\d+:\d+\)','',label)

def sfs_type_transform(rdftype):
    if rdftype == RINFO['KonsolideradGrundforfattning']:
        return "box"
    else:
        return "ellipse"
    
def parametrize_query(q,args):
    return None

def get_rdf_graph(store,queries):
    g = Graph()
    if not queries:
        print "getting serialized"
        nt = store.get_serialized("nt")
        print "parsing graph"
        g.parse(StringIO(nt),format="nt")
    else:
        for q in queries:
            g.add(store.construct(query))
    return g   

def rdf_to_dot(rdfgraph, label, link, labeltransform, typetransform):
    dotgraph = pydot.Dot()
    for (s,p,o) in rdfgraph:
        # possibly unify S
        node = pydot.Node(s)
        if not dotgraph.get_node(node):
            dotgraph.add_node(node)
        if p == label:
            node.label = labeltransform(o)
        if p == RDF.type:
            node.shape = typetransform(o)
        if p == link and type(o) == URIRef:
            target = pydot.Node(o)
            dotgraph.add_edge(node,target)

    return dotgraph
            
configs = {'sfs':{'context':'<urn:x-local:sfs>',
                 'label':DCT['title'],
                 'labeltransform':sfs_label_transform,
                 'typetransform':sfs_type_transform,
                 'link':DCT['references'],
                 'format':'dot', #maybe GEXF in the future
                 'renderer':'twopi'},
          }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "Usage: %s configuration [arguments]" % sys.argv[0]
        print "Available configurations: %s" % ", ".join(sorted(configs.keys()))
        sys.exit()
    confid = sys.argv[1]
    if len(sys.argv) > 1:
        args = sys.argv[2:]
    conf = configs[confid]
    store = SesameStore(TRIPLESTORE,REPOSITORY,conf['context'])
    queries = []
    if 'queries' in conf:
        for q in conf['queries']:
            queries.append(parametrize_query(q,args))

    print "Imma get graph!"
    rdfgraph = get_rdf_graph(store,queries)

    if conf['format'] == 'dot':
        print "converting rdf graph to dot graph"
        dotgraph = rdf_to_dot(rdfgraph,
                              conf['label'],
                              conf['link'],
                              conf['labeltransform'],
                              conf['typetransform'])
        print "serializing dot graph"
        dotgraph.write("out.dot")
        if 'renderer' in conf:
            print "rendering dot graph"
            dotgraph.write_png("out.png", prog=conf['renderer'])
