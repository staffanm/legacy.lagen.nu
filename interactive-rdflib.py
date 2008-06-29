import rdflib
from rdflib.Graph import ConjunctiveGraph as Graph
from rdflib import plugin
from rdflib.store import Store, NO_STORE, VALID_STORE, CORRUPTED_STORE
from rdflib import Namespace
from rdflib import Literal
from rdflib import URIRef
import sys, time

def clearstore():
    store.destroy(configString)
    store.open(configString, create=True)

def normalizeSpace(string):
    return u' '.join(string.split())

def timeit(callable, *args, **kwargs):
    start = time.time()
    res = callable(*args, **kwargs)
    elapsed = time.time()-start
    return (elapsed, res)

def query(sparql):
    args = [sparql]
    kwargs = {'initNs':dict(rinfo=rinfo_ns, dct=dct_ns, dc=dc_ns, foaf=foaf_ns)}
    
    (elapsed, res) = timeit(graph.query, *args, **kwargs)
    print "%s results in %.3f sec" % (len(res), elapsed)
    for tup in res:
        for fld in tup:
            sys.stdout.write("%r\t" % normalizeSpace(fld))
        sys.stdout.write("\n")

if __name__ == "__main__":
    configString = "host=localhost,user=rdflib,password=rdflib,db=rdfstore"
    lagen_ns = Namespace('http://lagen.nu/')
    rinfo_ns = Namespace('http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#')
    dc_ns   = Namespace('http://dublincore.org/documents/dcmi-terms/')
    dct_ns   = Namespace('http://dublincore.org/documents/dcmi-terms/')
    foaf_ns  = Namespace('http://xmlns.com/foaf/0.1/')
    default_graph_uri = "http://lagen.nu/rdfstore"
    examplequery = 'SELECT ?a WHERE { ?a dct:subject "Sekretess" . ?a dct:identifier ?aid }'
    

    store = plugin.get('MySQL', Store)('rdfstore')
    rt = store.open(configString,create=False)
    print "Store opened: %s" % rt
    

    graph = Graph(store, identifier = URIRef(default_graph_uri))
    graph.bind('rinfo', rinfo_ns)
    
