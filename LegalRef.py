#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""This module finds references to legal sources (including individual
sections, eg 'Upphovsrättslag (1960:729) 49 a §') in plaintext"""

import sys,os,re
import codecs
import traceback
from pprint import pprint
import locale
locale.setlocale(locale.LC_ALL,'') 

# 3rdparty libs
from simpleparse.parser import Parser
from simpleparse.stt.TextTools.TextTools import tag
from rdflib.Graph import Graph
from rdflib import Literal, Namespace, URIRef, RDF, RDFS

# my own libraries
from DispatchMixin import DispatchMixin
from DataObjects import UnicodeStructure, PredicateType, serialize
import Util

# The charset used for the bytestrings that is sent to/from
# simpleparse (which does not handle unicode)
# Choosing utf-8 makes § a two-byte character, which does not work well
SP_CHARSET='iso-8859-1' 

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
        self.verbose        = False
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


    def parse(self, indata, baseuri="http://lagen.nu/9999:999#K9P9S9P9"):
        if indata == "": return indata # this actually triggered a bug...
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
        # Det är är inte det enklaste sättet att göra det, men om man
        # gör enligt Simpleparse-dokumentationen byggs taggertabellen
        # om för varje anrop till parse
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
            print u"Problem (%d:%d) with %s / %s" % (taglist[-1]-8,taglist[-1]+8,fixedindata,indata)
            raise ParseError, "parsed %s chars of %s (...%s...)" %  (taglist[-1], len(indata), indata[(taglist[-1]-4):taglist[-1]+4])

        # "Normalize" the result, i.e concatenate adjacent text nodes
        normres = []
        for i in range(len(result)):
            text = self.re_descape.sub(r'\1',result[i])
            if isinstance(result[i], Link):
                normres.append(Link(text, uri=result[i].uri))
            else:
                if len(normres) > 0 and not isinstance(normres[-1],Link):
                    # print "concatenating %r" % text
                    if isinstance(text,unicode):
                        normres[-1] += text
                    else:
                        normres[-1] += text
                else:
                    normres.append(text)
        return normres


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
        return Link(part.text, uri=uri)

    def format_custom_link(self, attributes, text, production):
        try:
            uri = self.uriformatter[production](attributes)
        except KeyError:
            uri = self.sfs_format_uri(attributes)
        return Link(text,uri=uri)

    ################################################################
    # KOD FÖR LAGRUM
    def clear_state(self):
        self.currentlaw     = None
        self.currentchapter = None
        self.currentsection = None
        self.currentpiece   = None

    def normalize_sfsid(self,sfsid):
        # sometimes '1736:0123 2' is given as '1736:0123 s. 2'. This fixes that.
        return sfsid.replace('s. ','') # more advanced normalizations to come...

    def normalize_lawname(self,lawname):
        lawname=lawname.replace('|','').lower()
        if lawname.endswith('s'):
            lawname = lawname[:-1]
        return lawname
        
    def namedlaw_to_sfsid(self,text,normalize=True):
        if normalize:
            text = self.normalize_lawname(text)
        
        nolaw = [u'aktieslagen',
                 u'anslagen',
                 u'avslagen',
                 u'bolagen',
                 u'bergslagen', 
                 u'emballagen',
                 u'ersättningsslagen',
                 u'fissionsvederlagen',
                 u'föreslagen',
                 u'förslagen',
                 u'försäkringsbolagen',
                 u'inkomstslagen',
                 u'klockslagen',
                 u'kapitalunderlagen',
                 u'omslagen',
                 u'ordalagen',
                 u'slagen',
                 u'tillslagen',
                 u'trädslagen',
                 u'varuslagen'
                 ]
        if text in nolaw:
            return None

        if self.currentlynamedlaws.has_key(text):
            return self.currentlynamedlaws[text]
        elif self.namedlaws.has_key(text):
            return self.namedlaws[text]
        else:
            if self.verbose:
                print u"WARNING: I don't know the ID of named law '%s'" % text
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
                    print "WARNING: found reference to \"samma lag\", but self.lastlaw is not set"

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
        res = self.baseuri_attributes['baseuri']
        resolvetobase = True
        addfragment = False
        
        for key,val in attributes.items():
            if key == 'prop':
                res += "prop/%s" % val
            elif key == 'bet':
                res += "bet/%s" % val
            elif key == 'skrivelse':
                res += "rskr/%s" % val
            elif key == 'celex':
                res += "celex/%s" % val
        return res

    ################################################################
    # KOD FÖR EGLAGSTIFTNING
    def eglag_format_uri(self,attributes):
        res = self.baseuri_attributes['baseuri']
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
        if 'artikel' in attributes:
            res += "#%s" % attributes['artikel']
            if 'underartikel' in attributes:
                res += ".%s" % attributes['underartikel']

        return res


    ################################################################
    # KOD FÖR RATTFALL
    def rattsfall_format_uri(self,attributes):
        res = self.baseuri_attributes['baseuri']
        if attributes['domstol'] == u'NJA':
            res += u'NJA_%s_s_%s' % (attributes['ar'], attributes['lopnr'])
        elif attributes['domstol'] == u'RÅ':
            res += u'RÅ_%s_ref_%s' % (attributes['ar'], attributes['lopnr'])
        elif attributes['domstol'] == u'AD':
            res += u'AD_%s_nr_%s' % (attributes['ar'], attributes['lopnr'])
        else:
            res += u'%s_%s:%s' % (attributes['domstol'], attributes['ar'], attributes['lopnr'])
        return res


class TestLegalRef:

    
    def ParseTest(self,testfile,verbose=False,quiet=False):
        if not quiet:
            print("Running test %s\n------------------------------" % testfile)
        try:
            namedlaws = {}
            if testfile.startswith(os.path.sep.join(['test','data','LegalRef','sfs-'])):
                # p = SFSRefParser(verbose,namedlaws)
                p = LegalRef(LegalRef.LAGRUM)
            elif testfile.startswith(os.path.sep.join(['test','data','LegalRef','short-'])):
                # p = ShortenedRefParser(verbose,namedlaws)
                p = LegalRef(LegalRef.KORTLAGRUM)
            elif testfile.startswith(os.path.sep.join(['test','data','LegalRef','regpubl-'])):
                # p = PreparatoryRefParser(verbose,namedlaws)
                p = LegalRef(LegalRef.FORARBETEN)
            elif testfile.startswith(os.path.sep.join(['test','data','LegalRef','eglag-'])):
                p = LegalRef(LegalRef.EGLAGSTIFTNING)
            elif testfile.startswith(os.path.sep.join(['test','data','LegalRef','dv-'])):
                p = LegalRef(LegalRef.RATTSFALL)
            else:
                print u'WARNING: Har ingen aning om hur %s ska testas' % testfile
                return False
            
            p.verbose = verbose
            p.currentlynamedlaws = namedlaws
            
            testdata = codecs.open(testfile,encoding=SP_CHARSET).read()
            paragraphs = re.split('\r?\n\r?\n',testdata,1)
            if len(paragraphs) == 1:
                (test, key) = (testdata,None)
            elif len(paragraphs) == 2:
                (test,key) = re.split('\r?\n\r?\n',codecs.open(testfile,encoding=SP_CHARSET).read(),1)
            else:
                print "WARNING: len(paragraphs) > 2 for %s, that can't be good" % testfile
                return false

            testparas = re.split('\r?\n---\r?\n',test)
            if key:
                keyparas = re.split('\r?\n---\r?\n',key)
            resparas = []

            for i in range(len(testparas)):
                if testparas[i].startswith("RESET:"):
                    # namedlaws.clear()
                    p.currentlynamedlaws.clear()
                resparas.append(serialize(p.parse(testparas[i],u'http://lagen.nu/1:2#')))

            res = "\n---\n".join(resparas).replace("\r\n","\n").strip()
            if key:
                key = "\n---\n".join(keyparas).replace("\r\n","\n").strip()
                if res.strip() == key.strip():
                    result = "."
                else:
                    result = "F"
            else:
                result = "N"

        except Exception:
            result = "E"

        if quiet:
            sys.stdout.write(result)
        else:
            if result == '.':
                sys.stdout.write("OK %s" % testfile)
            elif result == 'F':
                sys.stdout.write("FAIL %s" % testfile)
                from difflib import Differ
                difflines = list(Differ().compare(key.split('\n'),res.split('\n')))
                print "----------------------------------------"
                sys.stdout.write(u'\n'.join(difflines))
                print "----------------------------------------"
            elif result == 'N':
                print "NOT IMPLEMENTED: %s" % testfile
                print "----------------------------------------"
                print "GOT:"
                print res
                print "----------------------------------------"
            elif result == 'E':
                tb = sys.exc_info()[2]
                formatted_tb = traceback.format_tb(sys.exc_info()[2])
                print (u" EXCEPTION:\nType: %s\nValue: %s\nTraceback:\n %s" %
                       (sys.exc_info()[0],
                        sys.exc_info()[1],
                        u''.join(formatted_tb)))
        return result == '.'

        
    def ParseTestString(self,s, verbose=True):
        p = LegalRef(LegalRef.LAGRUM)
        p.verbose = verbose
        print serialize(p.parse(s, u'http://lagen.nu/1:2#'))

    def ParseTestAll(self):
        results = []
        failures = []
        for f in Util.listDirs(u"test%sdata%sLegalRef" % (os.path.sep,os.path.sep), ".txt"):
            result = self.ParseTest(f,verbose=False,quiet=True)
            if not result:
                failures.append(f)
            results.append(result)

        succeeded = len([r for r in results if r])
        all       = len(results)
        print "\n%s/%s" % (succeeded,all)
        if failures:
            print "\n".join(failures)


    def NewAPI(self):
        p = LegalRef(LegalRef.LAGRUM, LegalRef.FORARBETEN,\
                     LegalRef.RATTSFALL, LegalRef.EGLAGSTIFTNING,\
                     LegalRef.KORTLAGRUM)

        print serialize(p.parse(u'Enligt Prop. 1998/99:123 ska 4 § och MB 14:7 tolkas i ljuset av artikel 4 i direktiv 1996/13/EG, vilket bekrftades i NJA 1992 s. 12.'))

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

    # Resultat för ParseTestAll just nu:
    # ................NN.........F...............................N.N.......F..
    # 66/72
    # test\data\LegalRef\sfs-basic-kungorelse-kapitel-paragrafer.txt
    # test\data\LegalRef\sfs-basic-kungorelse.txt
    # test\data\LegalRef\sfs-basic-punktlista.txt
    # test\data\LegalRef\sfs-tricky-overgangsbestammelse.txt
    # test\data\LegalRef\sfs-tricky-paragrafer-med-enstaka-paragraftecken.txt
    # test\data\LegalRef\sfs-tricky-vvfs.txt
    #
    # (sfs-basic-punktlista gick igenom förut, men slutade funka när
    # jag rationaliserade bort de flesta format_*-funktionerna). Den
    # funkar om man pillar på ItemRef-produktionen, men då slutar
    # sfs-tricky-punkt att funka. Svårt problem.)
    TestLegalRef.__bases__ += (DispatchMixin,)
    t = TestLegalRef()
    t.Dispatch(sys.argv)
