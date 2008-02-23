#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""This module finds references to legal sources (including individual
sections, eg 'Upphovsrättslag (1960:729) 49 a §') in plaintext"""
import os,pprint

import sys
import re
import codecs
from StringIO import StringIO
from simpleparse.parser import Parser

from DispatchMixin import DispatchMixin


# This should really be imported from SFS.py ("from SFS import
# SFSidToFilename"), but since that imports LegalRef that doesn't seem to be
# possible (circular reference problems?)

from DataObjects import UnicodeStructure, serialize

class Link(UnicodeStructure): # just a unicode string with a .uri property

    def __repr__(self):
        return u'Link(\'%s\',uri=%r)' % (unicode.__repr__(self),self.uri)


def SFSidToFilename(sfsid):
    """converts a SFS id to a filename, sans suffix, eg: '1909:bih. 29
    s.1' => '1909/bih._29_s.1'. Returns None if passed an invalid SFS
    id."""
    if sfsid.find(":") < 0: return None
    return re.sub(r'([A-Z]*)(\d{4}):',r'\2/\1',sfsid.replace(' ', '_'))

class NodeTree:
    """Encapsuates the node structure from mx.TextTools in a tree oriented interface"""
    def __init__(self,root,data,offset=0,isRoot=True):
        self.data = data
        self.root = root
        self.isRoot = isRoot
        self.offset = offset 

    def __getattr__(self,name):
        if name == "text":
            return self.data
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

class SFSRefParser:
    """Identifierar referenser till svensk lagtext i löpande text"""
    attributeorder = ['law', 'lawref', 'chapter', 'section', 'element', 'piece', 'item', 'sentence']
    pp = pprint.PrettyPrinter(indent=4)
    global_namedlaws = {}
    global_lawabbr   = {}
    re_escape = re.compile(r'\B(lagens?|balkens?|förordningens?)\b', re.LOCALE)
    re_descape = re.compile(r'\|(lagens?|balkens?|förordningens?)')
    re_urisegments = re.compile(r'http://[^/]*/(\d+:\d+)#?(K(\d+)|)(P(\d+)|)(S(\d+)|)(P(\d+)|)')

    # the first file contains all numbered laws that
    # find-named-laws.sh can find. It contains several ID's for the
    # same law and is generally messy.
    # for line in open(os.path.dirname(__file__)+'/named-law-references.txt').read().splitlines():
    #     m = re.match(r'([^ ]+) \((\d+:\d+)\)',line)
    #     global_namedlaws[m.group(1)] = m.group(2)

    # the second file contains laws that are never numbered --
    # "balkarna" -- and other hand-fixed laws. It takes predecense
    # over the first file.
    for line in open('etc/sfs.extra.txt').read().splitlines():
        fields = re.split("\t+", line)
        assert(2 <= len(fields) <= 3)
        name = fields[0]
        id = fields[1]
        global_namedlaws[name] = id
        if len(fields) == 3:
            for abbr in fields[2].split(","):
                # we need to go by unicode to get lower() to work
                # regardless of current locale
                # abbr = unicode(abbr,'iso-8859-1').lower().encode('iso-8859-1')
                # print "mapping %s to %s" % (abbr,id)
                global_lawabbr[abbr] = id
                
    decl = open('etc/sfs.ebnf').read()
    decl += "LawAbbreviation ::= ('%s')" % "'/'".join(global_lawabbr.keys())
    
    #parser = generator.buildParser(decl).parserbyname('root')
    simpleparser = Parser(decl, "root")

    def __init__(self,verbose=False,namedlaws={}):
        self.currentlaw     = None
        self.currentchapter = None
        self.currentsection = None
        self.currentpiece   = None
        self.lastlaw        = None
        self.verbose = verbose
        self.depth = 0
        self.namedlaws = namedlaws
        # print "__init__: number of namedlaws: %s" % len(namedlaws)
        # self.currentendidx  = 0
        
    def normalize_sfsid(self,sfsid):
        # sometimes '1736:0123 2' is given as '1736:0123 s. 2'. This fixes that.
        return sfsid.replace('s. ','') # more advanced normalizations to come...

    def normalize_lawname(self,lawname):
        lawname=lawname.replace('|','').lower()
        if lawname.endswith('s'):
            lawname = lawname[:-1]
        return lawname
        
    def namedlaw_to_sfsid(self,text):
        text = self.normalize_lawname(text)
        
        nolaw = ['anslagen',
                 'avslagen',
                 'bolagen',
                 'bergslagen',
                 'emballagen',
                 'ersättningsslagen',
                 'fissionsvederlagen',
                 'föreslagen',
                 'förslagen',
                 'försäkringsbolagen',
                 'inkomstslagen',
                 'klockslagen',
                 'kapitalunderlagen',
                 'omslagen',
                 'ordalagen',
                 'slagen',
                 'tillslagen',
                 'trädslagen',
                 'varuslagen'
                 ]
        if text in nolaw:
            return None

        if self.namedlaws.has_key(text):
            return self.namedlaws[text]
        elif self.global_namedlaws.has_key(text):
            return self.global_namedlaws[text]
        else:
            print "WARNING: I don't know the ID of named law '%s'" % text
            return None

    def lawabbr_to_sfsid(self,abbr):
        # abbr = unicode(abbr,'iso-8859-1').lower().encode('iso-8859-1')
        return self.global_lawabbr[abbr] 

    
    def format_attributes(self,attributes):
        piecemappings = {'första' :'1',
                         'andra'  :'2',
                         'tredje' :'3',
                         'fjärde' :'4',
                         'femte'  :'5',
                         'sjätte' :'6',
                         'sjunde' :'7',
                         'åttonde':'8',
                         'nionde' :'9'}
        res = ""
        for key in self.attributeorder:
            if attributes.has_key(key):
                val = attributes[key]
                # if key == 'chapter':
                #    self.currentchapter = attributes[key]
                if ((key == 'piece') or (key == 'sentence')) and not val.isdigit():
                    res += ' %s="%s"' % (key,piecemappings[val.lower()])
                else:
                    if key == 'law':
                        val = self.normalize_sfsid(val)
                        val = val.replace(" ", "_")
                    else:
                        val = val.replace(" ", "")
                    res += ' %s="%s"' % (key,val)
        return res

    def format_uri(self,attributes):
        piecemappings = {'första' :'1',
                         'andra'  :'2',
                         'tredje' :'3',
                         'fjärde' :'4',
                         'femte'  :'5',
                         'sjätte' :'6',
                         'sjunde' :'7',
                         'åttonde':'8',
                         'nionde' :'9'}
        keymapping = {'lawref':'L',
                      'chapter':'K',
                      'section':'P',
                      'piece':'S',
                      'item':'N',
                      'sentence':'M', # is this ever used?
                      }

        res = u'http://lagen.nu/sfs/'
        resolvetobase = True
        addfragment = False
        for key in self.attributeorder:
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
                        val = val.replace(" ", "")
                        res += '%s%s' % (keymapping[key],val)
        return res
        

    def find_attributes(self,parts,extra={}):
        """recurses through a parse tree and creates a dictionary of
        attributes"""
        d = {}
        
        self.depth += 1
        if self.verbose: print ". "*self.depth+"find_attributes: starting with %s"%d
        # if self.verbose: print ". "*self.depth+"find_attributes: currentchapter: %s" % self.currentchapter
        if extra:
            # print ". "*self.depth+"find_attributes: updating with extra attributes %s" % extra
            d.update(extra)
            
        for part in parts:
            current_part_tag = part.tag.lower()
            if current_part_tag.endswith('refid'):
                if ((current_part_tag == 'singlesectionrefid') or
                    (current_part_tag == 'lastsectionrefid')):
                    current_part_tag = 'sectionrefid'
                #elif current_part_tag == 'lawrefid':
                #    filename = "generated/text/%s.txt" % self.SFSidToFilename(self.normalize_sfsid(part.text))
                #    if not os.path.exists(filename):
                #        current_part_tag = 'lawrefrefid' # not my cleanest..
                    
                # strip away ending "refid"
                if self.verbose: print ". "*self.depth+"find_attributes: setting %s to %r" % (current_part_tag[:-5],part.text.strip())
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
                   
    def format_ChapterSectionRefs(self,root):
        assert(root.tag == 'ChapterSectionRefs')
        #print (". "*self.depth)+ len(root.nodes)
        #print (". "*self.depth)+ self.prettyprint(root)
        assert(len(root.nodes) == 3) # ChapterRef, wc, SectionRefs
        
        part = root.nodes[0]
        self.currentchapter = part.nodes[0].text.strip()

        if self.currentlaw:
            res = [self.format_custom_link({'law':self.currentlaw,
                                            'chapter':self.currentchapter},
                                           part.text)]
        else:
            res = [self.format_custom_link({'chapter':self.currentchapter},
                                           part.text)]

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
        #print (". "*self.depth)+ len(root.nodes)
        assert(len(root.nodes) == 3) # LastSectionRefID, wc, DoubleSectionMark
        sectionrefid = root.nodes[0]
        sectionid = sectionrefid.text
      
        return [self.format_generic_link(root)]


    def format_SectionPieceRefs(self, root):
        assert(root.tag == 'SectionPieceRefs')
        # assert(len(root.nodes) >= 7) # SectionRef, wc, (PieceRef, Comma, wc)*, PieceRef, wc, AndOr, wc, PieceRef
        self.currentsection = root.nodes[0].nodes[0].text.strip()

        res = [self.format_custom_link(self.find_attributes([root.nodes[2]]),
                                       "%s %s" % (root.nodes[0].text, root.nodes[2].text))]
        for node in root.nodes[3:]:
            #if self.verbose:
            #    print (". "*self.depth)+ "format_SectionPieceRefs: calling formatter_dispatch for '%s'" % node.tag
            res.extend(self.formatter_dispatch(node))
            #if self.verbose:
            #    print (". "*self.depth)+ "format_SectionPieceRefs: called formatter_dispatch for '%s'" % node.tag
            
        self.currentsection = None
        return res

    def format_SectionPieceItemRefs(self,root):
        assert(root.tag == 'SectionPieceItemRefs')
        self.currentsection = root.nodes[0].nodes[0].text.strip()
        self.currentpiece = root.nodes[2].nodes[0].text.strip()

        res = [self.format_custom_link(self.find_attributes([root.nodes[2]]),
                                       "%s %s" % (root.nodes[0].text, root.nodes[2].text))]

        for node in root.nodes[3:]:
            #if self.verbose:
            #    print (". "*self.depth)+ "format_SectionPieceRefs: calling formatter_dispatch for '%s'" % node.tag
            res.extend(self.formatter_dispatch(node))
            #if self.verbose:
            #    print (". "*self.depth)+ "format_SectionPieceRefs: called formatter_dispatch for '%s'" % node.tag
            
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
        else:
            self.currentlaw = lawrefid_node.text
            if self.find_node(root,'NamedLaw'):
                namedlaw = self.normalize_lawname(self.find_node(root,'NamedLaw').text)
                # print "remember that %s is %s!" % (namedlaw, self.currentlaw)
                self.namedlaws[namedlaw] = self.currentlaw

        #print "DEBUG: middle of format_ExternalRefs; self.currentlaw is %s" % self.currentlaw
        if self.lastlaw is None:
            # print "DEBUG: format_ExternalRefs: setting self.lastlaw to %s" % self.currentlaw
            self.lastlaw = self.currentlaw

        # if the node tree only contains a single reference, it looks
        # better if the entire expression, not just the
        # chapter/section part, is linked
        if (len(self.find_nodes(root,'GenericRefs')) == 1 and
            len(self.find_nodes(root,'SectionRefID')) == 1):
            res = self.format_generic_link(root)
        else:
            res = self.format_tokentree(root)    

        # print "DEBUG: about to return from format_ExternalRefs; self.currentlaw is %s" % self.currentlaw
        # self.currentlaw = None
        return res

    def format_SectionItemRefs(self,root):

        # if self.verbose: print "DEBUG: format_SectionItemRefs called"
        assert(root.nodes[0].nodes[0].tag == 'SectionRefID')
        self.currentsection = root.nodes[0].nodes[0].text.strip()
        # if self.verbose: print "DEBUG: self: %s" % dir(self)
        try:
            res = self.formatter_dispatch(root.nodes[0]) # was formatter_dispatch(self.root)
            # print ". "*self.depth+"format_SectionItemRefs: self.currentsection: %s" % self.currentsection
            self.currentsection = None
            # print ". "*self.depth+"format_SectionItemRefs: self.currentsection: %s" % self.currentsection
        except AttributeError:
            print "DEBUG: wow, got a AttributeError in format_SectionItemRefs, that can't be good"
        return res


    def format_PieceRef(self,root):
        assert(root.tag == 'PieceRef')
        assert(len(root.nodes) == 3 or len(root.nodes) == 5) #PieceRefID, wc, PieceOrPieces (Whitespace, ItemRef)
        return [self.format_generic_link(root)]
        
    
    def format_ChapterRef(self,root):
        return [self.format_generic_link(root)]

    def format_ChapterSectionRef(self,root):
        assert(root.nodes[0].nodes[0].tag == 'ChapterRefID')
        self.currentchapter = root.nodes[0].nodes[0].text.strip()
        return [self.format_generic_link(root)]

    def format_ExternalLawRef(self,root):
        self.currentchapter = None
        return self.formatter_dispatch(root.nodes[0])

    def format_ChangeRef(self,root):
        id = self.find_node(root,'LawRefID').data
        return [self.format_custom_link({'lawref':id},
                                        root.text)]
    
    # you know, there's a bunch of refactorings that could be done here...
    def format_ChapterSectionPieceRef(self,root):
        return [self.format_generic_link(root)]

    def format_ChapterSectionPieceItemRef(self,root):
        return [self.format_generic_link(root)]
        
    def format_SectionRef(self,root):
        return [self.format_generic_link(root)]

    def format_SectionPieceRef(self,root):
        return [self.format_generic_link(root)]

    def format_SectionPieceItemRef(self,root):
        return [self.format_generic_link(root)]

    def format_ExternalRef(self,root):
        return [self.format_generic_link(root)]

    def format_SectionSentenceRef(self,root):
        return [self.format_generic_link(root)]

    def format_SectionElementRef(self,root):
        return [self.format_generic_link(root)]

    def format_SectionItemRef(self,root):
        return [self.format_generic_link(root)]

    def format_AbbrevLawNormalRef(self,root):
        lawabbr_node = self.find_node(root,'LawAbbreviation')
        self.currentlaw = self.lawabbr_to_sfsid(lawabbr_node.text)
        res = [self.format_generic_link(root)]
        if self.currentlaw != None: self.lastlaw = self.currentlaw
        self.currentlaw = None
        return res
    
    def format_AbbrevLawShortRef(self,root):
        assert(root.nodes[0].tag == 'LawAbbreviation')
        assert(root.nodes[2].tag == 'ShortChapterSectionRef')
        self.currentlaw = self.lawabbr_to_sfsid(root.nodes[0].text)
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
                self.namedlaws[namedlaw] = self.currentlaw

        if self.currentlaw == None: # if we can't find a ID for this law, better not <link> it
            ret = root.text
        else:
            res = [self.format_generic_link(root)]
        if resetcurrentlaw:
            if self.currentlaw != None: self.lastlaw = self.currentlaw
            self.currentlaw = None
        return res
    
    def formatter_dispatch(self,part):
        self.depth += 1
        # do I have a method named format_(part.tag) ?
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
        # i'm not sure I understand this code, but basically we
        # recurse the token tree, and every token that ends with a
        # RefID gets converted into a <link>, which fixes the
        # interval case (each sectionref get turned into a
        # link). However, for a grammar production like
        # SectionPieceRefs, which contain subproductions that also end
        # in RefID, this is not a good function to use, you must use a
        # custom formatter instead.

        res = []

        if self.verbose: print (". "*self.depth)+ "format_tokentree: called for %s" % part.tag
        # this is like the bottom case, or something
        if (not part.nodes) and (not part.tag.endswith("RefID")):
            res.append(part.text.decode('iso-8859-1'))
        else:
            if part.tag.endswith("RefID"):
                res.append(self.format_generic_link(part))
            else:
                for subpart in part.nodes:
                    if self.verbose and part.tag == 'LawRef':
                        print (". "*self.depth) + "format_tokentree: part '%s' is a %s" % (subpart.text, subpart.tag)
                    res.extend(self.formatter_dispatch(subpart))
        #if self.verbose: print (". "*self.depth)+ "format_tokentree: returning '%s' for %s" % (res,part.tag)
        if self.verbose: print (". "*self.depth)+ "format_tokentree: returning '%s' for %s" % (res,part.tag)
        return res
    

    def prettyprint(self,root,indent=0):
        res = u"%s'%s': '%s'\n" % ("    "*indent,root.tag,re.sub(r'\s+', ' ',root.text.decode('iso-8859-1')))
        if root.nodes != None:
            for subpart in root.nodes:
                res += self.prettyprint(subpart,indent+1)
            return res
        else: return u""

    def format_generic_link(self,part):
        # if self.verbose: print (". "*self.depth)+ "format_generic_link: %s" % self.find_attributes([part])
        uri = self.format_uri(self.find_attributes([part]))
        if self.verbose: print (". "*self.depth)+ "format_generic_link: uri is %s" % uri
        if isinstance(part.text, str):
            return Link(part.text.decode('iso-8859-1'), uri=uri)
        else:
            return Link(part.text, uri=uri)

    def format_custom_link(self, attributes, text):
        uri = self.format_uri(attributes)
        if isinstance(text,str):
            return Link(text.decode('iso-8859-1'),uri=uri)
        else:
            return Link(text,uri=uri)
    
    
    def parse(self, indata, baseuri="http://lagen.nu/9999:999#K9P9S9P9"):
        if indata == "": return indata # this actually triggered a bug...
        m = self.re_urisegments.match(baseuri)
        self.baseuri_attributes = {'law':m.group(1),
                                   'chapter':m.group(3),
                                   'section':m.group(5),
                                   'piece':m.group(7),
                                   'item':m.group(9)}
        # there's one thing I can't get the EBNF grammar to do:
        # recognizing words that ends in a given substring, eg for the
        # substring 'lagen', recognize 'bokföringslagen'. Since any
        # such word can start with any number of characters (matched
        # by the 'word' production), which all of them could be
        # present in the word 'lagen', the greedyness of the parser
        # causes the entire word to be matched by the 'word'
        # production. Therefore, for words with those substrings, we
        # put in a '|' sign just before the substring (and then we
        # remove the pipe just before returning the marked-up string)
        # Assume proper locale has been set elsewhere
        fixedindata = self.re_escape.sub(r'|\1', indata)
        
        # SimpleParse has no unicode support... It might be possible
        # to convert to utf-8 if we convert sfs.ebnf
        if isinstance(fixedindata,unicode):
            fixedindata = fixedindata.encode('iso-8859-1')
        #taglist = TextTools.tag(fixedindata, self.parser)
        taglist = self.simpleparser.parse(fixedindata)
        result = []
        #print "Calling w %s" % fixedindata
        root = NodeTree(taglist,fixedindata)
        #        print "rootnode: %s" % r.tag
        #        for n in r.nodes:
        #            print "subnode: %s: %s" % (n.tag,n.text)
        #            if n.tag == 'refs':
        #                for sn in n.nodes:
        #                    print "    subnode: %s: %s" % (sn.tag,sn.text)
        for part in root.nodes:
            if part.tag != 'plain' and self.verbose:
                sys.stdout.write(self.prettyprint(part))
            if part.tag in ['ref', 'refs', 'preprefs', 'shortref']:
                result.extend(self.formatter_dispatch(part))
            else:
                assert(part.tag == 'plain')
                result.append(part.text.decode('iso-8859-1'))

            # clear state
            if self.currentlaw != None: self.lastlaw = self.currentlaw
            self.currentlaw = None


        if taglist[-1] != len(fixedindata):
            raise ParseError, "parsed %s chars of %s (...%s...)" %  (taglist[-1], len(self.indata), self.indata[(taglist[-1]-8):taglist[-1]+8])

        normres = []
        for i in range(len(result)):
            text = self.re_descape.sub(r'\1',result[i])
            if isinstance(result[i], Link):
                normres.append(Link(text, uri=result[i].uri))
            else:
                if len(normres) > 0 and not isinstance(normres[-1],Link):
                    normres[-1] += text
                else:
                    normres.append(text)
            
        return normres

class PreparatoryRefParser(SFSRefParser):
    """Subclass of SFSRefParser, but handles things like references to
    preparatory works, like propositions etc"""
    attributeorder = ['type','doctype','docid']
    decl = open('etc/sfs.ebnf').read()
    decl += "LawAbbreviation ::= 'blahonga'" # How to define a production that matches nothing?
    simpleparser = Parser(decl,'extroot')
    pp = pprint.PrettyPrinter(indent=4)


    def format_generic_link(self,part):
        attr = self.find_attributes([part])
        assert(len(attr.values()) == 1)
        docid = attr.values()[0]
        tagattr = {'type': 'docref',
                   'doctype': attr.keys()[0],
                   'docid'  : docid }
        return "<link%s>%s</link>" % (self.format_attributes(tagattr), part.text)

# class ShortenedRefParser(LawParser):
#     """Subclass of LawParser, but uses a different root production to
#     handle shortened references like '15 § AvtL' or 'JB 22:2'"""
#     
#     decl = open('law.def').read()
#     parser = generator.buildParser(decl).parserbyname('shortrefroot')
#     pp = pprint.PrettyPrinter(indent=4)



class TestLegalRef:
    def Run(self,filename,verbose=False,quiet=False):
        # print "testing %s" % filename
        # print open(filename).read().split("\n\n")
        testdata = codecs.open(filename,encoding='iso-8859-1').read()
        paragraphs = re.split('\r?\n\r?\n',testdata,1)
        if len(paragraphs) == 1:
            (test, answer) = (testdata,None)
        elif len(paragraphs) == 2:
            (test,answer) = re.split('\r?\n\r?\n',codecs.open(filename,encoding='iso-8859-1').read(),1)
        else:
            print "WARNING: len(paragraphs) > 2 for %s, that can't be good" % filename
            return false
        # print "Verbose is %s, test is %s" % (verbose, test)

        testparas   = re.split('\r?\n---\r?\n',test)
        if answer:
            answerparas = re.split('\r?\n---\r?\n',answer)
        resparas = []

        namedlaws = {}
        for i in range(len(testparas)):
            # print "Testing %s" % testparas[i]
            if testparas[i].startswith("RESET:"):
                namedlaws.clear()
            if filename.startswith("test/data/LegalRef/p_"):
                p = PreparatoryRefParser(testparas[i],verbose,namedlaws)
            else:
                p = SFSRefParser(testparas[i],verbose,namedlaws)
            resparas.append(p.parse())

        res = "\n---\n".join(resparas)
        if answer:
            answer = "\n---\n".join(answerparas)
        if not answer:
            print "NOT IMPLEMENTED: %s" % filename
            if verbose:
                print "----------------------------------------"
                print "GOT:"
                print res.encode('iso-8859-1')
                print "----------------------------------------"
            return False
        elif res.strip() == answer.strip():
            print "Pass: %s" % filename
            return True
        else:
            print "FAIL: %s" % filename
            if not quiet:
                print "----------------------------------------"
                print "EXPECTED:"
                print answer.encode('iso-8859-1')
                print "GOT:"
                print res.encode('iso-8859-1')
                print "----------------------------------------"
                return False
    #runtest = staticmethod(runtest)
        
    def RunString(self,s, verbose=True):
        p = SFSRefParser(s, verbose)
        print p.parse()
    #teststring = staticmethod(teststring)

    def prep_teststring(self,s):
        p = PreparatoryRefParser(s, True)
        print p.parse()
    #prep_teststring = staticmethod(prep_teststring)

#     def shortened_teststring(s):
#         p = ShortenedRefParser(s, True)
#         print p.parse()
#     shortened_teststring = staticmethod(shortened_teststring)   

    def RunAll(self,quiet=False):
        res = []
        for f in os.listdir("test/data/LegalRef"):
            if not f.endswith(".txt"): continue
            # print "trying %s..." % f

            res.append(self.Run('test/data/LegalRef/%s'%f, quiet=quiet))
        succeeded = len([r for r in res if r])
        all       = len(res)
                        
        print "%s/%s" % (succeeded,all)
        return(succeeded,all)
    #runalltests = staticmethod(runalltests)



if __name__ == "__main__":
    # 47/55 innan jag började ha sönder saker, alla implementerade tester funkar
    TestLegalRef.__bases__ += (DispatchMixin,)
    t = TestLegalRef()
    t.Dispatch(sys.argv)
    
