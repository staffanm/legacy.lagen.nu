#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Utilities for combining a legal document in HTML format with
annotations/comments on it.

The module is primarly used from the web interface -- speed is
therefore important (consider a 500K+ document with 100s of
comments)."""
import sys,os,re
import os.path
import codecs
import pprint
import cgi
import pickle
from cStringIO import StringIO
# from DispatchMixin import DispatchMixin
import Util
try:
    import cElementTree as ET
except ImportError:
    import elementtree.ElementTree as ET


class AnnotatedDoc:
    """Utility class for combining a legal document of some kind (in
    HTML format) with annotations/comments on it. Requires that the
    HTML document be prepared with markers in the form of HTML 
    comments to indicate where the individual comments should go."""

    def __init__(self, filename=None):
        if filename:
            self.filename = os.path.join(os.path.dirname(__file__),filename)
            self.indexfname = self.filename + ".idx"
        

    def Prepare(self):
        """Create a index of where in the HTML file the comment markers
        are, so that Combine can locate them quickly. Typically done offline."""
        indexfname = self.filename +".idx"
        self.__saveIndex(indexfname,self.__buildIndex(self.filename))

    def Combine(self,comments="", references={}):
        """Combines the HTML document with comments. Comments should be a
        free-form string (look at the testcases for details on how it should
        be formatted). References shouls be the result of pickle.load() for
        the appropriate .dat file. Typically done at runtime (via the web
        interface)"""
        
        if not os.path.exists(self.indexfname):
            self.Prepare()
        res = self.__weave(self.filename,
                            self.__loadIndex(self.indexfname),
                            self.__parseComments(comments),
                            references)
        return res

    def GetfragmentIds(self):
        if not os.path.exists(self.indexfname):
            self.Prepare()
        indexes = self.__loadIndex(self.indexfname)
        return [f[2] for f in indexes]
            
    

    re_ChapterSection = re.compile(r'K(\d+\w?)P(\d+w?)S(\d+)N(\d+)')
    re_Headline = re.compile(r'R(\d+w?)')
    re_Paragraph = re.compile(r'S(\d+)')
    
    re_SFSfragmentId = re.compile(r'(K(?P<chapter>\d+[a-z]?)|)(P(?P<section>\d+[a-z]?)|)(S(?P<paragraph>\d+[a-z]?)|)(N(?P<item>\d+[a-z]?)|)')

    def __formatFragmentId(self,fragmentId):
        """Formats a given fragmentId (eg K2P4) to a humanreadable format (2 kap. 4 §)"""
        # this will always match, but possibly with a emptystring
        m = self.re_SFSfragmentId.match(fragmentId)
        if m.group(0) != '':
            res = ""
            if m.group('chapter'):
                res = res + u"%s kap. " % m.group('chapter')
            if m.group('section'):
                res = res + u"%s § " % m.group('section')
            if m.group('paragraph'):
                res = res + u"%s st. " % m.group('paragraph')
            if m.group('item'):
                res = res + u"%s p. " % m.group('item')
            return res.strip()
        
        m = self.re_Headline.match(fragmentId)
        if m:
            return u"Rub. %s" % (m.group(1))

        m = self.re_Paragraph.match(fragmentId)
        if m:
            return u"%s st." % (m.group(1))
    
        return fragmentId
            
    
    def FormatComments(self,comments="",includePlaceholders=False):
        """Returns a list of <p>'s containing comments -- no actual
        weaving/merging with the HTML file is done"""
        # maybe this should just return a ordered list and leave the formatting 
        # to the view and/or the template?
        indexfname = self.filename + ".idx"
        if not os.path.exists(indexfname):
            self.Prepare()
        
        buf = StringIO()
        outdata = codecs.getwriter('utf-8')(buf)    
        indexes = self.__loadIndex(indexfname)
        comments = self.__parseComments(comments)
        for c in [c for c in indexes]:
            if c[2] in comments:
                outdata.write(u'<p id="comment-%s" class="comment editable"><span class="fragmentid">%s</span>%s</p>\n' % (c[2], self.__formatFragmentId(c[2]), comments[c[2]]))
            elif includePlaceholders:
                outdata.write(u'<p id="comment-%s" class="comment placeholder editable"><span class="fragmentid">%s</span>Klicka för att kommentera</p>\n' % (c[2], self.__formatFragmentId(c[2])))

        if hasattr(buf, "getvalue"):
            return unicode(buf.getvalue(), 'utf-8')
            outdata.close()


    def Test(self, commentfile):
        print "test(%s) called" % commentfile
        # pprint.pprint(self.__parseComments(file(commentfile).read()))
        print self.Combine(codecs.open(commentfile, encoding='iso-8859-1').read())

    def Update(self, comments, id, comment):
        """Update the free-form comment string with a new comment (possibly
        replacing an old)"""
        commentDict = self.__parseComments(comments)
        if id in commentDict:
            oldcomment = commentDict[id]
        else:
            oldcomment = None
        commentDict[id] = comment
        print "Changing comment for %s from %s to %s" % (id, oldcomment, comment)
        return self.__serializeComments(commentDict);

    def __buildIndex(self, htmlfname):
        """Builds an index over file positions in the HTML file where
        comments should go.

        The index is a list of tuples, where each tuple is (startpos,
        endpos, fragmentId)
        """
        start_or_end_iter = re.compile(r'<!--(start|end):(\w+)-->').finditer
        index = []
        data = codecs.open(htmlfname, encoding="iso-8859-1").read()
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
        f = open(indexfname,"w")
        pickle.dump(indexes, f)
        f.close()
        
    def __loadIndex(self, indexfname):
        res = []
        for i in pickle.load(file(indexfname)):
            res.append([i[0],i[1],i[2].strip()])
        return res

    def __weave(self, htmlfname,indexes=(),comments={},references={}):
        """'Weave' together the HTML document with the comments"""
        indata = codecs.open(htmlfname, encoding="iso-8859-1")
        # fsock = open(htmlfname)
        buf = StringIO()
        outdata = codecs.getwriter('iso-8859-1')(buf)
        # buf = None
        # out = codecs.open(htmlfname.replace(".html", ".out.html"), "w", encoding="iso-8859-1", errors="replace")

        pos = 0
        # get first start idx
        for c in [c for c in indexes]:
            fragmentId = c[2]
            numbytes = c[0] - pos
            # print "%s writing %d bytes" % (fragmentId, numbytes)
            outdata.write(indata.read(numbytes))
            numbytes = c[1] - c[0]
            # read and throw away
            throw = indata.read(numbytes)
            # print "%s throwing %d bytes (%r)" % (fragmentId,numbytes,throw)
            outdata.write(u'<div class="leftcol" id="left-%s">' % fragmentId)
            if fragmentId in references:
                outdata.write(u'<div class="references"><span class="fragmentid">%s</span> %s</div>' % (self.__formatFragmentId(fragmentId), self.__formatReferences(references[fragmentId])))
            #else: 
            #    outdata.write(u'<div class="placeholder">%s</div>' % fragmentId)
            outdata.write(u'</div>\n<div class="rightcol" id="right-%s">' % fragmentId)
            if fragmentId in comments:
                outdata.write(u'<div class="comment" id="comment-%s"><span class="fragmentid">%s</span>%s</div>' % (fragmentId, self.__formatFragmentId(fragmentId), self.__formatComment(comments[fragmentId])))
            #else:
            #    outdata.write(u'<div class="placeholder">%s</div>' % fragmentId)
            outdata.write(u'</div>')
            pos = c[1]
        outdata.write(indata.read())
        if hasattr(buf, "getvalue"):
            return unicode(buf.getvalue(), 'iso-8859-1')
            outdata.close()
        else:
            outdata.close()
            return codecs.open(htmlfname.replace(".html",".out.html"), encoding="iso-8859-1").read()

    def __formatComment(self, comment):
        # add markdown parsing here
        return u'<i>%s</i>' % comment

    def __formatReferences(self,references):
        res = u''
        for reftype in references.keys():
            res += u'<b>%s</b>' % reftype
            for document in references[reftype]:
                if not document['desc']: document['desc'] = ''
                res += u'<a href="/%s" title="%s">%s</a> ' % (
                    document['displayid'].replace(' ','_'),
                    cgi.escape(document['desc'], True),
                    document['displayid'])
            res += '<br/>'
        return res
    
    def __parseComments(self, comments=""):
        # FIXME: the use of Util.normalizeSpace might not be a good idea if
        # we want to do real wiki formatting of text
        inSection = False
        sectionid = None
        sectioncomment = None
        sections = {}
        for line in comments.splitlines():
            if inSection == False and ":" in line:
                if sectionid: # add the previous section
                    sections[sectionid] = Util.normalizeSpace(sectioncomment)
                sectionid, sectioncomment = line.split(":",1)
                # print "%r->%r" % (sectionid,sectioncomment)
            elif line.strip() == "":
                inSection = False
            else:
                inSection = True
                sectioncomment = sectioncomment + "\n"
        if sectioncomment:
            sections[sectionid] = Util.normalizeSpace(sectioncomment)

        # pprint.pprint(sections)    
        return sections
        
       
    def __serializeComments(self, comments):
        return "\n\n".join(["%s: %s" % (k, v) for (k, v) in comments.items()])


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

# if __name__ == "__main__":
#     if len(sys.argv) < 1:
#         print "usage: %s [htmlfile] [commentsfile]" % sys.argv[0]
#     else:
#         AnnotatedDoc.__bases__ += (DispatchMixin,)
#         ad = AnnotatedDoc("testdata/sfs/generated/1960/729.html")
#         ad.Dispatch()
#         # ad.Test("test/data/DocComments/01-comments.txt")
#         # prep(sys.argv[1])
#         # generate(sys.argv[1])
#         # weaveXML(sys.argv[1], None)


