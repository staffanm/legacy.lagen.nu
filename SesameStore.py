from rdflib import Literal, BNode, Namespace, URIRef
try:
    from rdflib.Graph import Graph
    from rdflib.syntax.parsers.ntriples import NTriplesParser
except:
    from rdflib import Graph
    from rdflib.plugins.parsers.ntriples import NTriplesParser
    

from urllib2 import urlopen, Request, HTTPError
import urllib
import xml.etree.cElementTree as ET

class SparqlError(Exception): pass
class SesameError(Exception): pass

class SesameStore():
    """Simple wrapper of the Sesame REST HTTP API, for bulk inserts of
    RDF statements and queries. It does not implement the RDFlib Store
    interface."""
    # Inspired by http://www.openvest.com/trac/browser/rdfalchemy/trunk/rdfalchemy/sparql/sesame2.py
    # see Sesame REST API doc at http://www.openrdf.org/doc/sesame2/system/ch08.html

    contenttype = {"xml":"application/rdf+xml",
                   "sparql":"application/sparql-results+xml",
                   "nt":"text/plain",
                   "ttl":"application/x-turtle",
                   "n3":"text/rdf+n3",
                   "trix":"application/trix",
                   "trig":"application/x-trig",
                   "json":"application/sparql-results+json",
                   "binary":"application/x-binary-rdf-results-table"}

    def __init__(self,url,repository,context=None):
        self.url = url
        self.repository = repository
        self.context = context
        self.pending_graph = Graph()
        self.namespaces = {}
        if self.context:
            if not (self.context.startswith("<") and self.context.endswith(">")):
                self.context = "<"+self.context+">"
            self.statements_url = ("%s/repositories/%s/statements?context=%s" %
                                   (self.url, self.repository, self.context))
            self.endpoint_url =  ("%s/repositories/%s?context=%s&" %
                                   (self.url, self.repository, self.context))
        else:
            self.statements_url = ("%s/repositories/%s/statements" %
                                   (self.url, self.repository))
            self.endpoint_url = ("%s/repositories/%s" %
                                   (self.url, self.repository))

        # Ping the server and see what we have
        # req = Request(self.url+'/protocol')
        # proto = urlopen(req).read()
        # req = Request(self.url+'/repositories/'+self.repository+'/size')
        # statements = urlopen(req).read()

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

    def select(self,query,format="sparql"):
        """query: A SPARQL query with all neccessary prefixes defined.

        format: Either one of the standard Sesame formats for queries
        ("sparql", "json" or "binary") -- returns whatever
        urlopen.read() returns -- or the special value "python" which
        returns a python list of dicts representing rows and columns.
        """
        
        # Tried briefly to use SPARQLtree to get the selected graph as
        # a nice tree, but never really figured out how to do it --
        # but below is how you use treeify_results with SPARQLwrapper.
        # 
        # import SPARQLWrapper
        # from oort.sparqltree.autotree import treeify_results
        # sparql = SPARQLWrapper.SPARQLWrapper(self.endpoint_url)
        # sparql.setQuery(query)
        # sparql.setReturnFormat(SPARQLWrapper.JSON)
        # results = treeify_results(sparql.queryAndConvert())

        # This code instead uses the raw REST API found in SesameStore
        url = self.endpoint_url
        if not self.context:
            url += "?"
        url += "query=" + urllib.quote(query.replace("\n", " "))

        # print url
        req = Request(url)

        if format == "python":
            req.add_header('Accept',self.contenttype["sparql"])
        else:
            req.add_header('Accept',self.contenttype[format])
        req.data = query
        try:
            results = self.__urlopen(req)
            if format == "python":
                return self.sparql_results_to_list(results)
            else:
                return results
        except HTTPError, e:
            raise SparqlError(e.read())

    def sparql_results_to_list(self,results):
        res = []
        tree = ET.fromstring(results)
        for row in tree.findall(".//{http://www.w3.org/2005/sparql-results#}result"):
            d = {}
            for element in row:
                #print element.tag # should be "binding"
                key = element.attrib['name']
                value = element[0].text
                d[key] = value
            res.append(d)
        return res
        
        
    def construct(self,query,format="nt"):
        query = " ".join(query.split()) # normalize space 
        url = self.endpoint_url
        if not self.context:
            url += "?"
        url += "query=" + urllib.quote(query.replace("\n", " "))
        print url
        req = Request(url)
        req.add_header('Accept',self.contenttype[format])
        req.data = query
        try:
            results = self.__urlopen(req)
            #print results.decode('utf-8')
            return results
        except HTTPError, e:
            raise SparqlError(e.read())
        
    def clear(self):
        # print "Deleting all triples from %s" % self.statements_url
        req = Request(self.statements_url)
        req.get_method = lambda : "DELETE"
        return self.__urlopen(req)

    def clear_subject(self, subject):
        #print "Deleting all triples where subject is %s from %s" % (subject, self.statements_url)
        req = Request(self.statements_url + "?subj=%s" % subject)
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
        data = self.pending_graph.serialize(format="nt")

        # RDFlibs nt serializer mistakenly serializes to UTF-8, not
        # the unicode escape sequence format mandated by the ntriples
        # spec -- fix this:
        data = ''.join([ord(c) > 127 and '\u%04X' % ord(c) or c for c in data.decode('utf-8')])

        # reinitialize pending_graph
        self.pending_graph = Graph()
        for prefix,namespace in self.namespaces.items():
            self.pending_graph.bind(prefix,namespace)

        return self.add_serialized(data,"nt")

    def add_serialized(self,data,format="nt"):
        req = Request(self.statements_url)
        req.get_method = lambda : "POST"
        req.add_header('Content-Type',self.contenttype[format]+";charset=UTF-8")
        req.data = data
        try:
            return self.__urlopen(req)
        except HTTPError, e:
            err = e.read()
            import re
            m = re.search("line (\d+)", err)
            if m:
                lineno = int(m.group(1))
                line = data.split("\n")[lineno-1]
                print "Malformed line: %s" % line
            raise SesameError(err)
    
if __name__ == "__main__":
    store = SesameStore("http://localhost:8080/openrdf-sesame", "lagen.nu")
    store.clear()
