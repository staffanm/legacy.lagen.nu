#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Utilities for combining a legal document in HTML format with
annotations/comments on it.

The module is primarly used from the web interface -- speed is
therefore important (consider a 500K+ document with 100s of
comments)."""
# import elementtree.ElementTree as ET
import sys,re
import cElementTree as ET
import codecs
import pprint
import cPickle
from cStringIO import StringIO
from DispatchMixin import DispatchMixin

class AnnotatedDoc:
    """Utility class for combining a legal document of some kind (in
    HTML format) with annotations/comments on it. Requires that the
    HTML document be prepared with markers in the form of HTML
    comments to indicate where the individual comments should go."""

    def __init__(self, filename=None):
        self.filename = filename

    def Prepare(self):
        """Create a index of where in the HTML file the comment markers
        are, so that Combine can locate them quickly. Typically done offline."""
        indexfname = self.fname +".idx"
        self.__saveIndex(indexfname,self.__buildIndex(htmlfname))

    def Combine(self):
        """Combines the HTML document with comments. Comments should be a
        free-form string (look at the testcases for details on how it
        should be formatted). Typically done at runtime (via the web
        interface)"""
        indexfname = htmlfname + ".idx"
        if not os.path.exists(indexfname):
            self.Prepare()
        return self.__weave(htmlfname,
                            self.__loadIndex(indexfname),
                            self.__parseComments(comments))

    def Test(self, commentfile):
        print "test(%s) called" % commentfile
        self.__parseComments(file(commentfile).read())
    

    def __buildIndex(self, htmlfname):
        """Builds an index over file positions in the HTML file where
        comments should go.

        The index is a list of tuples, where each tuple is (startpos,
        endpos, commentid)
        """
        start_or_end_iter = re.compile(r'<!--(start|end):(\w+)-->').finditer
        index = []

        data = file(htmlfname).read()
        startmatch = None
        endmatch = None
        for m in start_or_end_iter(data):
            if startmatch:
                endmatch = m
                assert(startmatch.group(1) == 'start')
                assert(endmatch.group(1) == 'end')
                assert(startmatch.group(2) == endmatch.group(2))
                index.append((startmatch.end(), endmatch.start(), startmatch.group(2)))
                startmatch = None
            else:
                startmatch = m
        return index

    def __saveIndex(self, indexfname,indexes):
        cPickle.dump(indexes, open(indexfname,"w"),cPickle.HIGHEST_PROTOCOL)

    def __loadIndex(self, indexfname):
        return cPickle.load(file(indexfname))

    def __weave(self, htmlfname,indexes=(),comments={}):
        """'Weave' together the HTML document with the comments"""
        # fsock = codecs.open(htmlfname, encoding="iso-8859-1")
        fsock = open(htmlfname)
        # strsock = StringIO()
        strsock = open(htmlfname.replace(".html", ".out.html"),"w")
        pos = 0
        # get first start idx
        for c in [c for c in indexes if c[2] in commentsMap]:
            numbytes = c[0] - pos
            print "%s writing %d bytes" % (c[2], numbytes)
            strsock.write(fsock.read(numbytes))
            numbytes = c[1] - c[0]
            # read and throw away
            print "%s throwing %d bytes" % (c[2],numbytes)
            fsock.read(numbytes)
            # write comment instead
            strsock.write('<div class="comment"><span class="commentid">%s</span>%s</span>' % (c[2], commentsMap[c[2]]))
            pos = c[1]
        strsock.write(fsock.read())
        strsock.close()
        if hasattr(strsock, "getvalue"):
            return strsock.getvalue()
        else:
            return file(htmlfname.replace(".html",".out.html").read())

    def __parseComments(self, comments=""):
        inSection = False
        sectionid = None
        sectioncomment = None
        sections = {}
        for line in comments.splitlines():
            if inSection == False and ":" in line:
                if sectionid: # add the previous section
                    sections[sectionid] = sectioncomment + "\n"
                sectionid, sectioncomment = line.split(":",1)
            elif line.strip() == "":
                inSection = False
            else:
                inSection = True
                sectioncomment = sectioncomment + line + "\n"
        sections[sectionid] = sectioncomment + "\n"
        pprint.pprint(sections)



# def weaveXML(htmlbodyfname,comments):
#     """Not used anymore"""
#     def _findParent(element, parentmap, tagname, classname):
#         node = element
#         found = False
# 
#         while not found:
#             if (node.tag == tagname and
#                 'class' in node.attrib and
#                 node.attrib['class'] == classname):
#                 found = True
#             elif node not in parentmap[node]:
#                 return None
#             else:
#                 node = parentmap[node]
#         return node
#     # load data
#     tree = ET.XML(htmlbodyfname)
#     parentmap = dict([(c,p) for p in tree.getiterator() for c in p])
#     # load comments
#     comments = {'R1':    u'Definerar skyddsobjektet. Verksbegreppet. Bla bla.',
#                 'K1P2S1':  u'De ekonomiska rättigheterna',
#                 'K1P3S1N1':u'Internetöverföringar'}
# 
#     nodes = {}
#         
#     for el in tree.getiterator("a"):
#         if 'name' in el.attrib:
#             # print "found <a name=%s>" % el.attrib['name']
#             nodes[el.attrib['name']] = el
# 
#     for name, el in nodes.items():
#         parent = parentmap[el]
#         grandparent = parentmap[parent] 
#         idx = 0
#         # print "parent: %s, gp: %s" % (parent.tag, grandparent.tag)
#         for c in grandparent.getchildren():
#             # print "   %s(%s) = %s(%s)?" % (parent.tag, id(parent), c.tag, id(c))
#             if c == parent:
#                 break
#             idx = idx + 1
#         else:
#             pass
#             # print "   --- couldn't find %s in %s" % (parent.tag, grandparent.tag)
#         comment = ET.Element("p")
#         comment.set("class", "comment")
#         if name in comments:
#             # parent = _findParent(el,parentmap,'div','outer')
#             comment.text = "%s: %s" % (name, comments[name])
#         else:
#             comment.text = "%s: Clict to edit" % (name)
#             
#         grandparent.insert(idx,comment)
#                 
#     return ET.tostring(tree)

if __name__ == "__main__":
    if len(sys.argv) < 1:
        print "usage: %s [htmlfile] [commentsfile]" % sys.argv[0]
    else:
        AnnotatedDoc.__bases__ += (DispatchMixin,)
        ad = AnnotatedDoc()
        ad.dispatch()
        # ad.Test("test/data/DocComments/01-comments.txt")
        # prep(sys.argv[1])
        # generate(sys.argv[1])
        # weaveXML(sys.argv[1], None)

