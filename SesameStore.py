from rdflib import Literal, BNode, Namespace, URIRef
from rdflib.Graph import Graph
from rdflib.syntax.parsers.ntriples import NTriplesParser

from urllib2 import urlopen, Request, HTTPError
from urllib import urlencode

class SesameStore():
    """Simple wrapper of the Sesame REST HTTP API, for bulk inserts of
    RDF statements and queries. It does not implement the RDFlib Store
    interface."""
    # Inspired by http://www.openvest.com/trac/browser/rdfalchemy/trunk/rdfalchemy/sparql/sesame2.py
    # see Sesame REST API doc at http://www.openrdf.org/doc/sesame2/system/ch08.html

    def __init__(self,url,repository,context=None):
        self.url = url
        self.repository = repository
        self.context = context
        # print "setting context to %s" % self.context
        self.pending_graph = Graph()
        self.namespaces = {}

        # Ping the server and see what we have
        req = Request(self.url+'/protocol')
        proto = urlopen(req).read()
        req = Request(self.url+'/repositories/'+self.repository+'/size')
        statements = urlopen(req).read()

        print "Connection to %s successful, protocol version %s, %s has %s statements" % (self.url, proto, repository, statements)




    def bind(self,prefix, namespace):
        self.namespaces[prefix] = namespace
        # print "binding %s as %s" % (namespace,prefix)
        self.pending_graph.bind(prefix, namespace)

    def clear(self):
        if self.context:
            url = self.url+"/repositories/%s/statements?context=%s" % (self.repository,
                                                                       self.context)
        else:
            url = self.url+'/repositories/'+self.repository+"/statements"
        print "Deleting all triples from %s" % url
        
        req = Request(url)
        req.get_method = lambda : "DELETE"
        try:
            res = urlopen(req).read()
        except HTTPError, e:
            if e.code == 204:
                # print "A-OK!"
                return
            else:
                raise e

        return res            
        
    def add_graph(self,graph):
        self.pending_graph += graph

    def add_triple(self,(s,p,o)):
        self.pending_graph.add((s,p,o))

    def commit(self):
        if len(self.pending_graph) == 0:
            return

        if self.context:
            url = self.url+"/repositories/%s/statements?context=%s" % (self.repository,
                                                                       self.context)
        else:
            url = self.url+'/repositories/'+self.repository + "/statements"
        # print "Committing %s triples to %s" % (len(self.pending_graph), url)

        data = self.pending_graph.serialize(format="n3")

        req = Request(url)

        req.get_method = lambda : "POST"
        req.add_header('Content-Type','text/rdf+n3; charset=utf-8')
        req.data = data

        # reinitialize pending_graph
        self.pending_graph = Graph()
        for prefix,namespace in self.namespaces.items():
            self.pending_graph.bind(prefix,namespace)

        try:
            res = urlopen(req).read()
        except HTTPError, e:
            if e.code == 204:
                # print "A-OK!"
                return
            else:
                raise e
        return res
    
if __name__ == "__main__":
    store = SesameStore("http://localhost:8080/openrdf-sesame", "lagen.nu")
    store.clear()
