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

    contenttype = {"xml":"application/rdf+xml",
                   "nt":"text/plain",
                   "ttl":"application/x-turtle",
                   "n3":"text/rdf+n3",
                   "trix":"application/trix",
                   "trig":"application/x-trig"}

    def __init__(self,url,repository,context=None):
        self.url = url
        self.repository = repository
        self.context = context
        self.pending_graph = Graph()
        self.namespaces = {}
        if self.context:
            self.statements_url = ("%s/repositories/%s/statements?context=%s" %
                                   (self.url, self.repository, self.context))
        else:
            self.statements_url = ("%s/repositories/%s/statements" %
                                   (self.url, self.repository))

        # Ping the server and see what we have
        req = Request(self.url+'/protocol')
        proto = urlopen(req).read()
        req = Request(self.url+'/repositories/'+self.repository+'/size')
        statements = urlopen(req).read()

    # print "Connection to %s successful, protocol version %s, %s has %s statements" % (self.url, proto, repository, statements)

    def __urlopen(self,req):
        try:
            res = urlopen(req).read()
        except HTTPError, e:
            if e.code == 204:
                # print "A-OK!"
                return
            else:
                raise e
        return res

    def bind(self,prefix, namespace):
        self.namespaces[prefix] = namespace
        # print "binding %s as %s" % (namespace,prefix)
        self.pending_graph.bind(prefix, namespace)

    def get_serialized(self,format="nt"):
        """Returns a string containing all statements in the store,
        serialized in the selected format"""
        req = Request(self.statements_url)
        req.add_header('Accept',self.contenttype[format])
        return self.__urlopen(req)

    #def get_graph(self):
    #    """Returns all statements in the store, as a rdflib.Graph"""
    #    g = Graph()
    #    g.parse(self.get_serialized("n3"),format="n3")
    #    return g
        
    def query(self,query,format="nt"):
        pass

    def clear(self):
        print "Deleting all triples from %s" % self.statements_url
        req = Request(self.statements_url)
        req.get_method = lambda : "DELETE"
        return self.__urlopen(req)
        
    def add_graph(self,graph):
        """Prepares adding a rdflib.Graph to the store (use commit to actually store it)"""
        self.pending_graph += graph

    def add_triple(self,(s,p,o)):
        """Prepares adding a single rdflib triple to the store (use
        commit to actually store it)"""
        self.pending_graph.add((s,p,o))

    def commit(self):
        if len(self.pending_graph) == 0:
            return

        # print "Committing %s triples to %s" % (len(self.pending_graph), self.statements_url)
        data = self.pending_graph.serialize(format="n3")

        # reinitialize pending_graph
        self.pending_graph = Graph()
        for prefix,namespace in self.namespaces.items():
            self.pending_graph.bind(prefix,namespace)

        return self.add_serialized(data,"n3")

    def add_serialized(self,data,format="nt"):
        req = Request(self.statements_url)
        req.get_method = lambda : "POST"
        req.add_header('Content-Type',self.contenttype[format]+";charset=UTF-8")
        req.data = data
        return self.__urlopen(req)
    
if __name__ == "__main__":
    store = SesameStore("http://localhost:8080/openrdf-sesame", "lagen.nu")
    store.clear()
