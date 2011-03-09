#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
import sys
from cStringIO import StringIO

from rdflib import Literal, BNode, Namespace, URIRef, RDF
from rdflib.Graph import Graph
try: 
    import pydot
    import networkx as nx
except ImportError:
    pass

from SesameStore import SesameStore



TRIPLESTORE = "http://localhost:8080/openrdf-sesame"
REPOSITORY = "lagen.nu"
DCT = Namespace('http://purl.org/dc/terms/')
RINFO = Namespace('http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#')
EURLEX = Namespace('http://lagen.nu/eurlex#')

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

# TODO: implement parametrization (once we learn in what way we wish
# it to work)
def parametrize_query(q,args):
    return q

def get_rdf_graph(store,queries):
    g = Graph()
    if not queries:
        # get every single triple in the store
        print "getting serialized"
        nt = store.get_serialized("nt")
        print "parsing graph"
        g.parse(StringIO(nt),format="nt")
    else:
        for q in queries:
            nt = store.construct(q,format="nt")
            g.parse(StringIO(nt),format="nt")
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

def rdf_to_nx(rdfgraph):
    nxgraph = nx.DiGraph()
    for (s,p,o) in rdfgraph:
        if p == EURLEX["cites"]:
            s1 = s.split("/")[-1]
            o1 = o.split("/")[-1]
            print "Adding %s -> %s" % (s1,o1)
            nxgraph.add_edge(s1,o1)
    return nxgraph

configs = {'sfs':{'context':'<urn:x-local:sfs>',
                 'label':DCT['title'],
                 'labeltransform':sfs_label_transform,
                 'typetransform':sfs_type_transform,
                 'link':DCT['references'],
                 'format':'dot', #maybe GEXF in the future
                 'renderer':'twopi'},
           'ecj': {'queries':["""PREFIX eurlex: <http://lagen.nu/eurlex#>
                                 PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> 
                                 CONSTRUCT { ?x eurlex:casenum ?z .
                                             ?x eurlex:cites ?y }
                                 WHERE { ?x eurlex:cites ?y . 
                                         ?y rdf:type ?w . 
                                         ?x eurlex:casenum ?z }"""],
                   'label':EURLEX['casenum'],
                   'context':'<urn:x-local:ecj>',
                   'format':'networkx'}
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

    print "Getting graph from %d queries" % len(queries)
    rdfgraph = get_rdf_graph(store,queries)
    print "Graph contains %s triples" % len(rdfgraph)
    
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
    elif conf['format'] == 'networkx':
        print "Converting rdf graph to networkx graph"
        nxgraph = rdf_to_nx(rdfgraph)
        import matplotlib.pyplot as plt
        nx.write_graphml(nxgraph, "out.graphml")
        print "out.graphml created"
        ranked = nx.pagerank(nxgraph)
        import pprint
        pprint.pprint(ranked)
    else:
        print "Unknown graph format %s" % conf['format']

