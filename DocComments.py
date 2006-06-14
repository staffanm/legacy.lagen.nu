#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""This module weaves together a legal document with commentary on it"""
# import elementtree.ElementTree as ET
import sys,re
import cElementTree as ET
import codecs
import pprint

def _findParent(element, parentmap, tagname, classname):
    node = element
    found = False
    
    while not found:
        if (node.tag == tagname and
            'class' in node.attrib and
            node.attrib['class'] == classname):
            found = True
        elif node not in parentmap[node]:
            return None
        else:
            node = parentmap[node]
    return node


def buildIndex(htmlfile):
    re_start_iter = re.compile(r'<!--start:(\w+)-->').finditer
    re_end_iter = re.compile(r'<!--end:(\w+)-->').finditer
    startindexes = {}
    endindexes = {}
    data = file(htmlfile).read()
    for m in re_start_iter(data):
        startindexes[m.group(1)] = m.start()
    for m in re_end_iter(data):
        endindexes[m.group(1)] = m.end()
    pprint.pprint(startindexes)
    pprint.pprint(endindexes)
    
    
def weave(htmlfile,indexes,comments):
    pass


def weaveXML(htmlbody,comments):
    # load data
    tree = ET.XML(htmlbody)
    parentmap = dict([(c,p) for p in tree.getiterator() for c in p])
    # load comments
    comments = {'R1':    u'Definerar skyddsobjektet. Verksbegreppet. Bla bla.',
                'K1P2':    u'De ekonomiska rättigheterna',
                'K1P3S1N1':u'Internetöverföringar'}

    nodes = {}
        
    for el in tree.getiterator("a"):
        if 'name' in el.attrib:
            # print "found <a name=%s>" % el.attrib['name']
            nodes[el.attrib['name']] = el

    for name, el in nodes.items():
        parent = parentmap[el]
        grandparent = parentmap[parent] 
        idx = 0
        # print "parent: %s, gp: %s" % (parent.tag, grandparent.tag)
        for c in grandparent.getchildren():
            # print "   %s(%s) = %s(%s)?" % (parent.tag, id(parent), c.tag, id(c))
            if c == parent:
                break
            idx = idx + 1
        else:
            pass
            # print "   --- couldn't find %s in %s" % (parent.tag, grandparent.tag)
        comment = ET.Element("p")
        comment.set("class", "comment")
        if name in comments:
            # parent = _findParent(el,parentmap,'div','outer')
            comment.text = "%s: %s" % (name, comments[name])
        else:
            comment.text = "%s: Clict to edit" % (name)
            
        grandparent.insert(idx,comment)
                
    return ET.tostring(tree)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "usage: %s [htmlfile] [commentsfile]" % sys.argv[0]
    else:
        buildIndex(sys.argv[1])

