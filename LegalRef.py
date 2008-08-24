#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""This module finds references to legal sources (including individual
sections, eg 'Upphovsrättslag (1960:729) 49 a §') in plaintext"""

import sys,os,re
import codecs
import traceback
from StringIO import StringIO
from pprint import pprint
import hashlib
import locale
import logging
locale.setlocale(locale.LC_ALL,'') 

# 3rdparty libs
from simpleparse.parser import Parser
from simpleparse.stt.TextTools.TextTools import tag
from rdflib.Graph import Graph
from rdflib.BNode import BNode
from rdflib import Literal, Namespace, URIRef, RDF, RDFS

# my own libraries
from DispatchMixin import DispatchMixin
from DataObjects import UnicodeStructure, PredicateType, serialize
import Util

# The charset used for the bytestrings that is sent to/from
# simpleparse (which does not handle unicode)
# Choosing utf-8 makes § a two-byte character, which does not work well
SP_CHARSET='iso-8859-1' 

log = logging.getLogger(u'lr')


class Link(UnicodeStructure): # just a unicode string with a .uri property
    def __repr__(self):
        return u'Link(\'%s\',uri=%r)' % (unicode.__repr__(self),self.uri)

class LinkSubject(PredicateType, Link): pass # A RDFish link

class NodeTree:
    """Encapsuates the node structure from mx.TextTools in a tree oriented interface"""
    def __init__(self,root,data,offset=0,isRoot=True):
        self.data = data
        self.root = root
        self.isRoot = isRoot
        self.offset = offset 

    def __getattr__(self,name):
        if name == "text":
            return self.data.decode(SP_CHARSET)
        elif name == "tag":
            return (self.isRoot and 'root' or self.root[0])
        elif name == "nodes":
            res = []
            l = (self.isRoot and self.root[1] or self.root[3])
            if l:
                for p in l:
                    res.append(NodeTree(p,self.data[p[1]-self.offset:p[2]-self.offset],p[1],False))
            return res
        else:
            raise AttributeError

class ParseError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

# Lite om hur det hela funkar: Att hitta referenser i löptext är en
# tvåstegsprocess.
#
# I det första steget skapar simpleparse en nodstruktur från indata
# och en lämplig ebnf-grammatik. Väldigt lite kod i den här modulen
# hanterar första steget, simpleparse gör det tunga
# jobbet. Nodstrukturen kommer ha noder med samma namn som de
# produktioner som definerats i ebnf-grammatiken.
#
# I andra steget gås nodstrukturen igenom och omvandlas till en lista
# av omväxlande unicode- och Link-objekt. Att skapa Link-objekten är
# det svåra, och det mesta jobbet görs av formatter_dispatch. Den
# tittar på varje nod och försöker hitta ett lämpligt sätt att
# formattera den till ett Link-objekt med en uri-property. Eftersom
# vissa produktioner ska resultera i flera länkar och vissa bara i en
# kan detta inte göras av en enda formatteringsfunktion. För de enkla
# fallen räcker den generiska formatteraren format_tokentree till, men
# för svårare fall skrivs separata formatteringsfunktioner. Dessa har
# namn som matchar produktionerna (exv motsvaras produktionen
# ChapterSectionRefs av funktionen format_ChapterSectionRefs).
#
# Koden är tänkt att vara generell för all sorts referensigenkänning i
# juridisk text. Eftersom den växt från kod som bara hanterade rena
# lagrumsreferenser är det ganska mycket kod som bara är relevant för
# igenkänning av just svenska lagrumsänvisningar så som de förekommer
# i SFS. Sådana funktioner/avsnitt är markerat med "SFS-specifik
# [...]" eller "KOD FÖR LAGRUM"

class LegalRef:
    # Kanske detta borde vara 1,2,4,8 osv, så att anroparen kan be om
    # LAGRUM | FORESKRIFTER, och så vi kan definera samlingar av
    # vanliga kombinationer (exv ALL_LAGSTIFTNING = LAGRUM |
    # KORTLAGRUM | FORESKRIFTER | EGLAGSTIFTNING)
    LAGRUM = 1             # hänvisningar till lagrum i SFS
    KORTLAGRUM = 2         # SFS-hänvisningar på kortform
    FORESKRIFTER = 3       # hänvisningar till myndigheters författningssamlingar
    EGLAGSTIFTNING = 4     # EG-fördrag, förordningar och direktiv
    INTLLAGSTIFTNING = 5   # Fördrag, traktat etc
    FORARBETEN = 6         # proppar, betänkanden, etc
    RATTSFALL = 7          # Rättsfall i svenska domstolar
    MYNDIGHETSBESLUT = 8   # Myndighetsbeslut (JO, ARN, DI...)
    EGRATTSFALL = 9        # Rättsfall i EG-domstolen/förstainstansrätten 
    INTLRATTSFALL = 10     # Europadomstolen

    
    re_urisegments = re.compile(r'([\w]+://[^/]+/[^\d]*)(\d+:(bih\. |N|)?\d+( s\.\d+|))#?(K(\d+)|)(P(\d+)|)(S(\d+)|)(N(\d+)|)')
    re_escape = re.compile(r'\B(lagens?|balkens?|förordningens?|formens?|ordningens?)\b', re.LOCALE)
    re_descape = re.compile(r'\|(lagens?|balkens?|förordningens?|formens?|ordningens?)')

    def __init__(self,*args):
        # print repr(args)
        self.graph = Graph()
        self.graph.load("etc/sfs-extra.n3", format="n3")
        self.roots = []
        self.uriformatter = {}
        self.decl = ""
        self.namedlaws = {}
        self.load_ebnf("etc/base.ebnf")

        if self.LAGRUM in args:
            productions = self.load_ebnf("etc/lagrum.ebnf")
            for p in productions:
                self.uriformatter[p] = self.sfs_format_uri
            self.namedlaws.update(self.get_relations(RDFS.label))
            self.roots.append("sfsrefs")
            self.roots.append("sfsref")

        if self.KORTLAGRUM in args:
            # om vi inte redan laddat lagrum.ebnf måste vi göra det
            # nu, eftersom kortlagrum.ebnf beror på produktioner som
            # definerats där
            if not self.LAGRUM in args:
                self.load_ebnf("etc/lagrum.ebnf")
                
            productions = self.load_ebnf("etc/kortlagrum.ebnf")
            for p in productions:
                self.uriformatter[p] = self.sfs_format_uri
            DCT = Namespace("http://dublincore.org/documents/dcmi-terms/")
            d = self.get_relations(DCT['alternate'])
            self.namedlaws.update(d)
            self.decl += "LawAbbreviation ::= ('%s')\n" % "'/'".join([x.encode(SP_CHARSET) for x in d.keys()])
            self.roots.append("kortlagrumref")

        if self.EGLAGSTIFTNING in args:
            productions = self.load_ebnf("etc/eglag.ebnf")
            for p in productions:
                self.uriformatter[p] = self.eglag_format_uri
            self.roots.append("eglagref")
        if self.FORARBETEN in args:
            productions = self.load_ebnf("etc/forarbeten.ebnf")
            for p in productions:
                self.uriformatter[p] = self.forarbete_format_uri
            self.roots.append("forarbeteref")
        if self.RATTSFALL in args:
            productions = self.load_ebnf("etc/rattsfall.ebnf")
            for p in productions:
                self.uriformatter[p] = self.rattsfall_format_uri
            self.roots.append("rattsfallref")

        self.decl += "root ::= (%s/plain)+\n" % "/".join(self.roots)
        # pprint(productions)
        # print self.decl.decode(SP_CHARSET,'ignore')

        self.parser = Parser(self.decl, "root")
        self.tagger = self.parser.buildTagger("root")
        # print "tagger length: %d" % len(repr(self.tagger))
        self.verbose = False
        self.depth = 0

        # SFS-specifik kod
        self.currentlaw     = None
        self.currentchapter = None
        self.currentsection = None
        self.currentpiece   = None
        self.lastlaw        = None
        self.currentlynamedlaws = {}
        
    def load_ebnf(self,file):
        """Laddar in produktionerna i den angivna filen i den
        EBNF-deklaration som används, samt returnerar alla
        *Ref och *RefId-produktioner"""
        # print "%s: Loading %s" % (id(self), file)
        f = open(file)
        content = f.read()
        self.decl += content
        f.close()
        return [x.group(1) for x in re.finditer(r'(\w+(Ref|RefID))\s*::=', content)]

    def get_relations(self, predicate):
        d = {}
        for obj, subj in self.graph.subject_objects(predicate):
            d[unicode(subj)] = unicode(obj)
        return d


    def parse(self, indata, baseuri="http://rinfo.lagrummet.se/publ/sfs/9999:999#K9P9S9P9",predicate=None):
        if indata == "": return indata # this actually triggered a bug...
        # h = hashlib.sha1()
        # h.update(indata)
        # print "Called with %r (%s) (%s)" % (indata, h.hexdigest(), self.verbose)
        self.predicate = predicate
        m = self.re_urisegments.match(baseuri)
        self.baseuri_attributes = {'baseuri':m.group(1),
                                   'law':m.group(2),
                                   'chapter':m.group(6),
                                   'section':m.group(8),
                                   'piece':m.group(10),
                                   'item':m.group(12)}
        # Det är svårt att få EBNF-grammatiken att känna igen
        # godtyckliga ord som slutar på ett givet suffix (exv
        # 'bokföringslagen' med suffixet 'lagen'). Därför förbehandlar
        # vi indatasträngen och stoppar in ett '|'-tecken innan vissa
        # suffix
        fixedindata = self.re_escape.sub(r'|\1', indata)
        
        # SimpleParse har inget stöd för unicodesträngar, så vi
        # konverterar intdatat till en bytesträng
        if isinstance(fixedindata,unicode):
            fixedindata = fixedindata.encode(SP_CHARSET)

        # Parsea texten med TextTools.tag - inte det enklaste sättet
        # att göra det, men om man gör enligt
        # Simpleparse-dokumentationen byggs taggertabellen om för
        # varje anrop till parse()
        # print "calling tag with %s (%s)" % (fixedindata, self.verbose)
        # print "tagger length: %d" % len(repr(self.tagger))
        taglist = tag(fixedindata, self.tagger,0,len(fixedindata))
        
        result = []

        root = NodeTree(taglist,fixedindata)
        for part in root.nodes:
            if part.tag != 'plain' and self.verbose:
                sys.stdout.write(self.prettyprint(part))
            if part.tag in self.roots:
                self.clear_state()
                result.extend(self.formatter_dispatch(part))
            else:
                assert part.tag == 'plain',"Tag is %s" % part.tag
                result.append(part.text)
                
            # clear state
            if self.currentlaw != None: self.lastlaw = self.currentlaw
            self.currentlaw = None

        if taglist[-1] != len(fixedindata):
            log.error(u'Problem (%d:%d) with %r / %r' % (taglist[-1]-8,taglist[-1]+8,fixedindata,indata))

            raise ParseError, "parsed %s chars of %s (...%s...)" %  (taglist[-1], len(indata), indata[(taglist[-1]-4):taglist[-1]+4])

        # Normalisera resultatet, dvs konkatenera intilliggande
        # textnoder, och ta bort ev '|'-tecken som vi stoppat in
        # tidigare.
        normres = []
        for i in range(len(result)):
            # print "Doing a %s %s" % (result[i].__class__.__name__, result[i])
            if not self.re_descape.search(result[i]):
                node = result[i]
            else:
                text = self.re_descape.sub(r'\1',result[i])
                if isinstance(result[i], Link):
                    # Eftersom Link-objekt är immutable måste vi skapa
                    # ett nytt och kopiera dess attribut
                    if hasattr(result[i],'predicate'):
                        node = LinkSubject(text, predicate=result[i].predicate,
                                           uri=result[i].uri)
                    else:
                        node = Link(text,uri=result[i].uri)
                else:
                    node = text
            if (len(normres) > 0
                and not isinstance(normres[-1],Link) 
                and not isinstance(node,Link)):
                normres[-1] += node
            else:
                
                normres.append(node)
        return normres

    # Experimental stuff - modelled after URIMinter in
    # rinfosystem. The idea is to submit a rdf graph centered around a
    # BNode, and create the canonical URI for that BNode by leveraging
    # the existing *_format_uri methods, which operates on a much
    # simpler dictionary.
    def make_uri(self,node, graph):
        """Given a node and a RDF graph containing said node, construct a URI for the node"""
        rinfo = Namespace(Utils.ns['rinfo'])
        pred_to_attrib = {
            rinfo['rattsfallspublikation']: 'domstol',
            rinfo['artal']: 'ar',
            rinfo['sidnummer']: 'sidnr',
            rinfo['publikationsordinal']: 'lopnr'
            }
        type_to_method = {
            rinfo['KonsolideradGrundforfattning']:sfs_format_uri,
            rinfo['VagledandeDomstolsavgorande']:rattsfall_format_uri
            }
        attribs = {}
        # print "node: %s (%s)" % (node, type(node))
        # We SHOULD be able to just get the type by calling
        # graph.subjects(node, RDF.type), but that call does not
        # return any nodes for some reason
        for (o,p,s) in graph:
            # print "Node %s %s %s" % (o,p,s)
            if o == node and p == RDF.type:
                method = type_to_method[s]
                # print "setting method to %s" % method
            else:
                attribs[pred_to_attrib[p]] = str(s)
                # print "setting attrib %s to %s" % (pred_to_attrib[p], s)
        uri = method(attribs)
        return uri

    def find_attributes(self,parts,extra={}):
        """recurses through a parse tree and creates a dictionary of
        attributes"""
        d = {}
        
        self.depth += 1
        if self.verbose: print ". "*self.depth+"find_attributes: starting with %s"%d
        if extra:
            d.update(extra)
            
        for part in parts:
            current_part_tag = part.tag.lower()
            if current_part_tag.endswith('refid'):
                if ((current_part_tag == 'singlesectionrefid') or
                    (current_part_tag == 'lastsectionrefid')):
                    current_part_tag = 'sectionrefid'
                d[current_part_tag[:-5]] = part.text.strip()
                if self.verbose: print ". "*self.depth+"find_attributes: d is now %s" % d
                
            if part.nodes:
                d.update(self.find_attributes(part.nodes,d))
        if self.verbose: print ". "*self.depth+"find_attributes: returning %s" % d
        self.depth -= 1

        if self.currentlaw     and 'law' not in d    : d['law']     = self.currentlaw
        if self.currentchapter and 'chapter' not in d: d['chapter'] = self.currentchapter
        if self.currentsection and 'section' not in d: d['section'] = self.currentsection
        if self.currentpiece   and 'piece' not in d  : d['piece']   = self.currentpiece

        return d


    def find_node(self,root,nodetag):
        """Returns the first node in the tree that has a tag matching nodetag. The search is depth-first"""
        if root.tag == nodetag: # base case
            return root
        else:
            for node in root.nodes:
                x = self.find_node(node,nodetag)
                if x != None: return x
            return None

    def find_nodes(self,root,nodetag):
        if root.tag == nodetag:
            return [root]
        else:
            res = []
            for node in root.nodes:
                res.extend(self.find_nodes(node,nodetag))
            return res
                

    def flatten_tokentree(self,part,suffix):
        """returns a 'flattened' tokentree ie for the following tree and the suffix 'RefID'
           foo->bar->BlahongaRefID
              ->baz->quux->Blahonga2RefID
                         ->Blahonga3RefID
              ->Blahonga4RefID

           this should return [BlahongaRefID, Blahonga2RefID, Blahonga3RefID, Blahonga4RefID]"""
        l = []
        if part.tag.endswith(suffix): l.append(part)
        if not part.nodes: return l

        for subpart in part.nodes:
            l.extend(self.flatten_tokentree(subpart,suffix))
        return l

    def formatter_dispatch(self,part):
        self.depth += 1
        # Finns det en skräddarsydd formatterare?
        if "format_"+part.tag in dir(self): 
            formatter = getattr(self,"format_"+part.tag)
            if self.verbose: print (". "*self.depth)+ "formatter_dispatch: format_%s defined, calling it" % part.tag
            res = formatter(part)
            assert res != None, "Custom formatter for %s didn't return anything" % part.tag
        else:
            if self.verbose: print (". "*self.depth)+ "formatter_dispatch: no format_%s, using format_tokentree" % part.tag
            res = self.format_tokentree(part)

        if res == None: print (". "*self.depth)+ "something wrong with this:\n" + self.prettyprint(part)
        self.depth -= 1
        return res
        
    def format_tokentree(self,part):
        # This is the default formatter. It converts every token that
        # ends with a RefID into a Link object. For grammar
        # productions like SectionPieceRefs, which contain
        # subproductions that also end in RefID, this is not a good
        # function to use - use a custom formatter instead.

        res = []

        if self.verbose: print (". "*self.depth)+ "format_tokentree: called for %s" % part.tag
        # this is like the bottom case, or something
        if (not part.nodes) and (not part.tag.endswith("RefID")):
            res.append(part.text)
        else:
            if part.tag.endswith("RefID"):
                res.append(self.format_generic_link(part))
            elif part.tag.endswith("Ref"):
                res.append(self.format_generic_link(part))
            else:
                for subpart in part.nodes:
                    if self.verbose and part.tag == 'LawRef':
                        print (". "*self.depth) + "format_tokentree: part '%s' is a %s" % (subpart.text, subpart.tag)
                    res.extend(self.formatter_dispatch(subpart))
        if self.verbose: print (". "*self.depth)+ "format_tokentree: returning '%s' for %s" % (res,part.tag)
        return res
    

    def prettyprint(self,root,indent=0):
        res = u"%s'%s': '%s'\n" % ("    "*indent,root.tag,re.sub(r'\s+', ' ',root.text))
        if root.nodes != None:
            for subpart in root.nodes:
                res += self.prettyprint(subpart,indent+1)
            return res
        else: return u""


    def format_generic_link(self,part,uriformatter=None):
        try:
            uri = self.uriformatter[part.tag](self.find_attributes([part]))
        except KeyError:
            if uriformatter:
                uri = uriformatter(self.find_attributes([part]))
            else:
                uri = self.sfs_format_uri(self.find_attributes([part]))
        if self.verbose: print (". "*self.depth)+ "format_generic_link: uri is %s" % uri
        if not uri:
            # the formatting function decided not to return a URI for
            # some reason (maybe it was a partial/relative reference
            # without a proper base uri context
            return part.text
        elif self.predicate:
            return LinkSubject(part.text, uri=uri, predicate=self.predicate)
        else:
            return Link(part.text, uri=uri)
        
    # FIXME: unify this with format_generic_link
    def format_custom_link(self, attributes, text, production):
        try:
            uri = self.uriformatter[production](attributes)
        except KeyError:
            uri = self.sfs_format_uri(attributes)

        if not uri:
            # the formatting function decided not to return a URI for
            # some reason (maybe it was a partial/relative reference
            # without a proper base uri context
            return part.text
        elif self.predicate:
            return LinkSubject(text, uri=uri, predicate=self.predicate)
        else:
            return Link(text, uri=uri)


    ################################################################
    # KOD FÖR LAGRUM
    def clear_state(self):
        self.currentlaw     = None
        self.currentchapter = None
        self.currentsection = None
        self.currentpiece   = None

    def normalize_sfsid(self,sfsid):
        # sometimes '1736:0123 2' is given as '1736:0123 s. 2' or
        # '1736:0123.2'. This fixes that.
        sfsid = re.sub(r'(\d+:\d+)\.(\d)',r'\1 \2',sfsid)
        return sfsid.replace('s. ','').replace('s.','') # more advanced normalizations to come...

    def normalize_lawname(self,lawname):
        lawname=lawname.replace('|','').lower()
        if lawname.endswith('s'):
            lawname = lawname[:-1]
        return lawname
        
    def namedlaw_to_sfsid(self,text,normalize=True):
        if normalize:
            text = self.normalize_lawname(text)
        
        nolaw = [
            u'aktieslagen',
            u'anordningen',
            u'anordningen',
            u'anslagen',
            u'arbetsordningen',
            u'associationsformen',
            u'avfallsslagen',
            u'avslagen',
            u'avvittringsutslagen',
            u'bergslagen',
            u'beskattningsunderlagen',
            u'bolagen',
            u'bolagsordningen',
            u'bolagsordningen',
            u'dagordningen',
            u'djurslagen',
            u'dotterbolagen',
            u'emballagen',
            u'energislagen',
            u'ersättningsformen',
            u'ersättningsslagen',
            u'examensordningen',
            u'finansbolagen',
            u'finansieringsformen',
            u'fissionsvederlagen',
            u'flygbolagen',
            u'fondbolagen',
            u'förbundsordningen',
            u'föreslagen',
            u'företrädesordningen',
            u'förhandlingsordningen',
            u'förlagen',
            u'förmånsrättsordningen',
            u'förmögenhetsordningen',
            u'förordningen',
            u'förslagen',
            u'försäkringsaktiebolagen',
            u'försäkringsbolagen',
            u'gravanordningen',
            u'grundlagen',
            u'handelsplattformen',
            u'handläggningsordningen',
            u'inkomstslagen',
            u'inköpssamordningen',
            u'kapitalunderlagen',
            u'klockslagen',
            u'kopplingsanordningen',
            u'låneformen',
            u'mervärdesskatteordningen',
            u'nummerordningen',
            u'omslagen',
            u'ordalagen',
            u'pensionsordningen',
            u'renhållningsordningen',
            u'representationsreformen',
            u'rättegångordningen',
            u'rättegångsordningen',
            u'rättsordningen',
            u'samordningen',
            u'samordningen',
            u'skatteordningen',
            u'skatteslagen',
            u'skatteunderlagen',
            u'skolformen',
            u'skyddsanordningen',
            u'slagen',
            u'solvärmeanordningen',
            u'storslagen',
            u'studieformen',
            u'stödformen',
            u'stödordningen',
            u'stödordningen',
            u'säkerhetsanordningen',
            u'talarordningen',
            u'tillslagen',
            u'tivolianordningen',
            u'trafikslagen',
            u'transportanordningen',
            u'transportslagen',
            u'trädslagen',
            u'turordningen',
            u'underlagen',
            u'uniformen',
            u'uppställningsformen',
            u'utvecklingsbolagen',
            u'varuslagen',
            u'verksamhetsformen',
            u'vevanordningen',
            u'vårdformen',
            u'ägoanordningen',
            u'ägoslagen',
            u'ärendeslagen',
            u'åtgärdsförslagen',
                 ]
        if text in nolaw:
            return None

        if self.currentlynamedlaws.has_key(text):
            return self.currentlynamedlaws[text]
        elif self.namedlaws.has_key(text):
            return self.namedlaws[text]
        else:
            if self.verbose:
                log.warning("(unknown): I don't know the ID of named law [%s]" % text)
            return None

    def sfs_format_uri(self,attributes):
        piecemappings = {u'första' :'1',
                         u'andra'  :'2',
                         u'tredje' :'3',
                         u'fjärde' :'4',
                         u'femte'  :'5',
                         u'sjätte' :'6',
                         u'sjunde' :'7',
                         u'åttonde':'8',
                         u'nionde' :'9'}
        keymapping = {'lawref'  :'L',
                      'chapter' :'K',
                      'section' :'P',
                      'piece'   :'S',
                      'item'    :'N',
                      'element' :'O',
                      'sentence':'M', # is this ever used?
                      }
        attributeorder = ['law', 'lawref', 'chapter', 'section', 'element', 'piece', 'item', 'sentence']

        # print "sfs_format_uri: %r" % attributes
        if 'law' in attributes and attributes['law'].startswith('http://'):
            res = ''
        else:
            res = self.baseuri_attributes['baseuri']
        resolvetobase = True
        addfragment = False
        justincase = None
        for key in attributeorder:
            if attributes.has_key(key):
                resolvetobase = False
                val = attributes[key]
            elif (resolvetobase and self.baseuri_attributes.has_key(key)):
                val = self.baseuri_attributes[key]
            else:
                val = None

            if val:
                if addfragment:
                    res += '#'
                    addfragment = False
                if (key in ['piece', 'sentence'] and not val.isdigit()):
                    res += '%s%s' % (keymapping[key],piecemappings[val.lower()])
                else:
                    if key == 'law':
                        val = self.normalize_sfsid(val)
                        val = val.replace(" ", "_")
                        res += val
                        addfragment = True
                    else:
                        if justincase:
                            res += justincase
                            justincase = None
                        val = val.replace(" ", "")
                        val = val.replace("\n", "")
                        val = val.replace("\r", "")
                        res += '%s%s' % (keymapping[key],val)
            else:
                if key == 'piece':
                    justincase = "S1" 
        return res
        
    def format_ChapterSectionRefs(self,root):
        assert(root.tag == 'ChapterSectionRefs')
        assert(len(root.nodes) == 3) # ChapterRef, wc, SectionRefs
        
        part = root.nodes[0]
        self.currentchapter = part.nodes[0].text.strip()

        if self.currentlaw:
            res = [self.format_custom_link({'law':self.currentlaw,
                                            'chapter':self.currentchapter},
                                           part.text,
                                           part.tag)]
        else:
            res = [self.format_custom_link({'chapter':self.currentchapter},
                                           part.text,
                                           part.tag)]

        res.extend(self.formatter_dispatch(root.nodes[1]))
        res.extend(self.formatter_dispatch(root.nodes[2]))
        self.currentchapter = None
        return res

    def format_ChapterSectionPieceRefs(self,root):
        assert(root.nodes[0].nodes[0].tag == 'ChapterRefID')
        self.currentchapter = root.nodes[0].nodes[0].text.strip()
        res = []
        for node in root.nodes:
            res.extend(self.formatter_dispatch(node))
        return res

    def format_LastSectionRef(self, root):
        # the last section ref is a bit different, since we want the
        # ending double section mark to be part of the link text
        assert(root.tag == 'LastSectionRef')
        assert(len(root.nodes) == 3) # LastSectionRefID, wc, DoubleSectionMark
        sectionrefid = root.nodes[0]
        sectionid = sectionrefid.text
      
        return [self.format_generic_link(root)]


    def format_SectionPieceRefs(self, root):
        assert(root.tag == 'SectionPieceRefs')
        self.currentsection = root.nodes[0].nodes[0].text.strip()

        res = [self.format_custom_link(self.find_attributes([root.nodes[2]]),
                                       "%s %s" % (root.nodes[0].text, root.nodes[2].text),
                                       root.tag)]
        for node in root.nodes[3:]:
            res.extend(self.formatter_dispatch(node))
            
        self.currentsection = None
        return res

    def format_SectionPieceItemRefs(self,root):
        assert(root.tag == 'SectionPieceItemRefs')
        self.currentsection = root.nodes[0].nodes[0].text.strip()
        self.currentpiece = root.nodes[2].nodes[0].text.strip()

        res = [self.format_custom_link(self.find_attributes([root.nodes[2]]),
                                       "%s %s" % (root.nodes[0].text, root.nodes[2].text),
                                       root.tag)]

        for node in root.nodes[3:]:
            res.extend(self.formatter_dispatch(node))
            
        self.currentsection = None
        self.currentpiece =  None
        return res
        

    # This is a special case for things like '17-29 och 32 §§ i lagen
    # (2004:575)', which picks out the LawRefID first and stores it in
    # .currentlaw, so that find_attributes finds it
    # automagically. Although now it seems to be branching out and be
    # all things to all people.
    def format_ExternalRefs(self,root):
        assert(root.tag == 'ExternalRefs')
        # print "DEBUG: start of format_ExternalRefs; self.currentlaw is %s" % self.currentlaw

        lawrefid_node = self.find_node(root,'LawRefID')
        if lawrefid_node == None:
            # Ok, no explicit LawRefID found, lets see if this is a named law that we have the ID for
            # namedlaw_node = self.find_node(root, 'NamedLawExternalLawRef')
            namedlaw_node = self.find_node(root, 'NamedLaw')
            if namedlaw_node == None:
                # As a last chance, this might be a reference back to a previously mentioned law ("...enligt 4 § samma lag")
                samelaw_node = self.find_node(root, 'SameLaw')
                assert(samelaw_node != None)
                if self.lastlaw == None:
                    log.warning("(unknown): found reference to \"samma lag\", but self.lastlaw is not set")

                self.currentlaw = self.lastlaw
            else:
                # the NamedLaw case
                self.currentlaw = self.namedlaw_to_sfsid(namedlaw_node.text)
                if self.currentlaw == None:
                    # unknow law name - in this case it's better to
                    # bail out rather than resolving chapter/paragraph
                    # references relative to baseuri (which is almost
                    # certainly wrong)
                    return [root.text]
        else:
            self.currentlaw = lawrefid_node.text
            if self.find_node(root,'NamedLaw'):
                namedlaw = self.normalize_lawname(self.find_node(root,'NamedLaw').text)
                # print "remember that %s is %s!" % (namedlaw, self.currentlaw)
                self.currentlynamedlaws[namedlaw] = self.currentlaw

        #print "DEBUG: middle of format_ExternalRefs; self.currentlaw is %s" % self.currentlaw
        if self.lastlaw is None:
            # print "DEBUG: format_ExternalRefs: setting self.lastlaw to %s" % self.currentlaw
            self.lastlaw = self.currentlaw

        # if the node tree only contains a single reference, it looks
        # better if the entire expression, not just the
        # chapter/section part, is linked. But not if it's a
        # "anonymous" law ('1 § i lagen (1234:234) om blahonga')
        if (len(self.find_nodes(root,'GenericRefs')) == 1 and
            len(self.find_nodes(root,'SectionRefID')) == 1 and
            len(self.find_nodes(root,'AnonymousExternalLaw')) == 0):
            res = [self.format_generic_link(root)]
        else:
            res = self.format_tokentree(root)

        return res

    def format_SectionItemRefs(self,root):
        assert(root.nodes[0].nodes[0].tag == 'SectionRefID')
        self.currentsection = root.nodes[0].nodes[0].text.strip()
        res = self.formatter_dispatch(root.nodes[0]) # was formatter_dispatch(self.root)
        self.currentsection = None
        return res

    def format_PieceItemRefs(self,root):
        self.currentpiece = root.nodes[0].nodes[0].text.strip()
        res = [self.format_custom_link(self.find_attributes([root.nodes[2].nodes[0]]),
                                       "%s %s" % (root.nodes[0].text, root.nodes[2].nodes[0].text),
                                       root.tag)]
        for node in root.nodes[2].nodes[1:]:
            res.extend(self.formatter_dispatch(node))
        
        self.currentpiece = None
        return res

    def format_ChapterSectionRef(self,root):
        assert(root.nodes[0].nodes[0].tag == 'ChapterRefID')
        self.currentchapter = root.nodes[0].nodes[0].text.strip()
        return [self.format_generic_link(root)]

    def format_ExternalLaw(self,root):
        self.currentchapter = None
        return self.formatter_dispatch(root.nodes[0])

    def format_ChangeRef(self,root):
        id = self.find_node(root,'LawRefID').data
        return [self.format_custom_link({'lawref':id},
                                        root.text,
                                        root.tag)]

    def format_NamedExternalLawRef(self,root):
        resetcurrentlaw = False
        if self.currentlaw == None:
            resetcurrentlaw = True
            lawrefid_node = self.find_node(root,'LawRefID')
            if lawrefid_node == None:
                self.currentlaw = self.namedlaw_to_sfsid(root.text)
            else:
                self.currentlaw = lawrefid_node.text
                namedlaw = self.normalize_lawname(self.find_node(root,'NamedLaw').text)
                # print "remember that %s is %s!" % (namedlaw, self.currentlaw)
                self.currentlynamedlaws[namedlaw] = self.currentlaw

        if self.currentlaw == None: # if we can't find a ID for this law, better not <link> it
            res = [root.text]
        else:
            res = [self.format_generic_link(root)]
        if resetcurrentlaw:
            if self.currentlaw != None: self.lastlaw = self.currentlaw
            self.currentlaw = None
        return res

    ################################################################
    # KOD FÖR KORTLAGRUM
    def format_AbbrevLawNormalRef(self,root):
        lawabbr_node = self.find_node(root,'LawAbbreviation')
        self.currentlaw = self.namedlaw_to_sfsid(lawabbr_node.text,normalize=False)
        res = [self.format_generic_link(root)]
        if self.currentlaw != None: self.lastlaw = self.currentlaw
        self.currentlaw = None
        return res

    def format_AbbrevLawShortRef(self,root):
        assert(root.nodes[0].tag == 'LawAbbreviation')
        assert(root.nodes[2].tag == 'ShortChapterSectionRef')
        self.currentlaw = self.namedlaw_to_sfsid(root.nodes[0].text,normalize=False)
        shortsection_node = root.nodes[2]
        assert(shortsection_node.nodes[0].tag == 'ShortChapterRefID')
        assert(shortsection_node.nodes[2].tag == 'ShortSectionRefID')
        self.currentchapter = shortsection_node.nodes[0].text
        self.currentsection = shortsection_node.nodes[2].text
        
        res = [self.format_generic_link(root)]

        self.currentchapter = None
        self.currentsection = None
        self.currentlaw     = None
        return res

    
    ################################################################
    # KOD FÖR FORARBETEN
    def forarbete_format_uri(self,attributes):
        # res = self.baseuri_attributes['baseuri']
        res = 'http://rinfo.lagrummet.se/'
        resolvetobase = True
        addfragment = False
        
        for key,val in attributes.items():
            if key == 'prop':
                res += "publ/prop/%s" % val
            elif key == 'bet':
                res += "ext/bet/%s" % val
            elif key == 'skrivelse':
                res += "ext/rskr/%s" % val
            elif key == 'celex':
                res += "ext/celex/%s" % val
        return res

    ################################################################
    # KOD FÖR EGLAGSTIFTNING
    def eglag_format_uri(self,attributes):
        res = 'http://rinfo.lagrummet.se/ext/celex/'
        # Om hur CELEX-nummer konstrueras
        # https://www.infotorg.sema.se/infotorg/itweb/handbook/rb/hlp_celn.htm
        # https://www.infotorg.sema.se/infotorg/itweb/handbook/rb/hlp_celf.htm
        # Om hur länkning till EURLEX ska se ut:
        # http://eur-lex.europa.eu/sv/tools/help_syntax.htm
        # Absolut URI?
        if 'ar' in attributes and 'lopnummer' in attributes:
            sektor = '3'
            rattslig_form = {u'direktiv':'L',
                             u'förordning':'R'}
                
            if len(attributes['ar']) == 2:
                attributes['ar'] = '19'+attributes['ar']
            res += "%s%s%s%04d" % (sektor,attributes['ar'],
                                   rattslig_form[attributes['akttyp']],
                                   int(attributes['lopnummer']))
        else:
            if not self.baseuri_attributes['baseuri'].startswith(res):
                # FIXME: should we warn about this?
                # print "Relative reference, but base context %s is not a celex context" % self.baseuri_attributes['baseuri']
                return None

        if 'artikel' in attributes:
            res += "#%s" % attributes['artikel']
            if 'underartikel' in attributes:
                res += ".%s" % attributes['underartikel']

        return res


    ################################################################
    # KOD FÖR RATTSFALL
    def rattsfall_format_uri(self,attributes):
        # Listan härledd från containers.n3/rattsfallsforteckningar.n3 i
        # rinfoprojektets källkod - en ambitiösare lösning vore att läsa
        # in de faktiska N3-filerna i en rdflib-graf.
        containerid = {u'NJA': '/publ/rattsfall/nja/',
                       u'RH': '/publ/rattsfall/rh/',
                       u'MÖD': '/publ/rattsfall/mod/',
                       u'RÅ': '/publ/rattsfall/ra/',
                       u'MIG': '/publ/rattsfall/mig/',
                       u'AD': '/publ/rattsfall/ad/',
                       u'MD': '/publ/rattsfall/md/',
                       u'FÖD': '/publ/rattsfall/fod/'}

        # res = self.baseuri_attributes['baseuri']
        assert 'domstol' in attributes, "No court provided"
        assert attributes['domstol'] in containerid, "%s is an unknown court" % attributes['domstol']
        res = "http://rinfo.lagrummet.se"+containerid[attributes['domstol']]
        if ":" in attributes['lopnr']:
            (attributes['ar'], attributes['lopnr']) = lopnr.split(":", 1)
            
        if attributes['domstol'] == u'NJA':
            # FIXME: URIs should be based on publikationsordinal, not
            # pagenumber (which this in effect is) - but this requires
            # a big lookup table/database/graph with
            # pagenumber-to-ordinal-mappings
            res += '%ss%s' % (attributes['ar'], attributes['lopnr'])
        else:
            res += '%s:%s' % (attributes['ar'], attributes['lopnr'])
        return res

from FilebasedTester import FilebasedTester
class TestLegalRef(FilebasedTester):

    testparams = {'URI': {'dir': u'test/LegalRef/URI',
                          'testext':'.n3'},
                  'ParseLagrum': {'dir': u'test/LegalRef/SFS',
                                  'testext':'.txt'},
                  'ParseKortlagrum': {'dir': u'test/LegalRef/Short',
                                      'testext':'.txt'},
                  'ParseForarbeten': {'dir': u'test/LegalRef/Regpubl',
                                      'testext':'.txt'},
                  'ParseEGLagstiftning': {'dir': u'test/LegalRef/EGLag',
                                          'testext':'.txt'},
                  'ParseRattsfall': {'dir': u'test/LegalRef/DV',
                                     'testext':'.txt'},
                  }

    def TestURI(self,data):
        g = Graph()
        g.parse(StringIO(data),format="n3")
        #print "Loaded graph, %s tuples" % len(g)
        # find the bnode that has a RDF.type predicate
        for (o,p,s) in g:
            if p == RDF.type:
                bnode = o

        p = LegalRef(LegalRef.LAGRUM)
        #print "calling make_uri"
        res = p.make_uri(bnode,g)
        return res
        
    def TestParseLagrum(self,data):
        p = LegalRef(LegalRef.LAGRUM)
        return self.__test_parser(data,p)

    def TestParseKortlagrum(self,data):
        p = LegalRef(LegalRef.KORTLAGRUM)
        return self.__test_parser(data,p)

    def TestParseForarbeten(self,data):
        p = LegalRef(LegalRef.FORARBETEN)
        return self.__test_parser(data,p)

    def TestParseEGLagstiftning(self,data):
        p = LegalRef(LegalRef.EGLAGSTIFTNING)
        return self.__test_parser(data,p)

    def TestParseRattsfall(self,data):
        p = LegalRef(LegalRef.RATTSFALL)
        return self.__test_parser(data,p)

    def __test_parser(self,data,p):
        p.verbose = False # FIXME: How to set this from FilebasedTester if wanted?
        p.currentlynamedlaws = {}
        paras = re.split('\r?\n---\r?\n',data)
        resparas = []
        for i in range(len(paras)):
            if paras[i].startswith("RESET:"):
                p.currentlynamedlaws.clear()
            nodes = p.parse(paras[i],u'http://rinfo.lagrummet.se/publ/sfs/9999:999')
            resparas.append(serialize(nodes))
        res = "\n---\n".join(resparas).replace("\r\n","\n").strip()
        return res
        
    def ParseTestString(self,s, verbose=True):
        # p = LegalRef(LegalRef.RATTSFALL)
        p = LegalRef(LegalRef.LAGRUM)
        p.verbose = verbose
        print serialize(p.parse(s, u'http://rinfo.lagrummet.se/publ/sfs/9999:999#K9P9S9P9'))

    # Resultat för testsviterna just nu:
    #
    # C:\Users\staffan\wds\ferenda.lagen.nu>python LegalRef.py RunTest ParseForarbeten
    # .. 2/2
    # 
    # C:\Users\staffan\wds\ferenda.lagen.nu>python LegalRef.py RunTest URI
    # E 0/1
    # Failed tests:
    # test/LegalRef/URI\base.n3
    # 
    # C:\Users\staffan\wds\ferenda.lagen.nu>python LegalRef.py RunTest ParseRattsfall
    # ....N 4/5
    # Failed tests:
    # test/LegalRef/DV\dv-tricky-misc.txt
    # 
    # C:\Users\staffan\wds\ferenda.lagen.nu>python LegalRef.py RunTest ParseEGLagstiftning
    # .... 4/4
    # 
    # C:\Users\staffan\wds\ferenda.lagen.nu>python LegalRef.py RunTest ParseKortlagrum
    # .. 2/2
    # 
    # C:\Users\staffan\wds\ferenda.lagen.nu>python LegalRef.py RunTest ParseLagrum
    # ......NN..........F.................N..............N.N....N...F 55/63
    # Failed tests:
    # test/LegalRef/SFS\sfs-basic-kungorelse-kapitel-paragrafer.txt
    # test/LegalRef/SFS\sfs-basic-kungorelse.txt
    # test/LegalRef/SFS\sfs-basic-punktlista.txt
    # test/LegalRef/SFS\sfs-regression-obestamd-form.txt
    # test/LegalRef/SFS\sfs-tricky-overgangsbestammelse.txt
    # test/LegalRef/SFS\sfs-tricky-paragrafer-med-enstaka-paragraftecken.txt
    # test/LegalRef/SFS\sfs-tricky-sammalag.txt
    # test/LegalRef/SFS\sfs-tricky-vvfs.txt
    #
    # (sfs-basic-punktlista gick igenom förut, men slutade funka när
    # jag rationaliserade bort de flesta format_*-funktionerna). Den
    # funkar om man pillar på ItemRef-produktionen, men då slutar
    # sfs-tricky-punkt att funka. Svårt problem.)

if __name__ == "__main__":
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
    sys.stdout = codecs.getwriter(defaultencoding)(sys.__stdout__, 'replace')
    sys.stderr = codecs.getwriter(defaultencoding)(sys.__stderr__, 'replace')

    TestLegalRef.__bases__ += (DispatchMixin,)
    t = TestLegalRef()
    t.Dispatch(sys.argv)
