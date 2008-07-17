#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Several base datatypes that inherit from native types
(unicode,list,dict, etc) or python defined types (datetime), but adds
support for general properties. Once a class has been instansiated,
you cannot add any more properties."""

import datetime
import xml.etree.cElementTree as ET

class AbstractStructure(object):

    def __new__(cls):
        obj = super(AbstractStructure,cls).__new__(cls)
        object.__setattr__(obj,'__initialized',False)
        return obj

    def __init__(self, *args, **kwargs):
        for (key,val) in kwargs.items():
            object.__setattr__(self,key,val)
            
        # Declare this instance ready for usage. Note that derived
        # objects must do their own initialization first, before
        # calling the superclass constructor (i.e. this function),
        # since this effectively "seals" the instance.
        #
        # (we need to call object.__setattr__ directly to bypass our
        # own __setattr__ implementation)
        object.__setattr__(self, '__initialized', True)

    def __setattr__(self,name,value):
        if object.__getattribute__(self,'__initialized'):
            # initialization phase is over -- no new attributes should
            # be created. Check to see if the attribute exists -- if it
            # doesn't, we raise an AttributeError (with a sensible
            # error message)
            try:
                object.__getattribute__(self,name)
                object.__setattr__(self,name,value)
            except AttributeError:
                raise AttributeError("Can't set attribute '%s' on object '%s' after initialization" % (name, self.__class__.__name__))
        else:
            # Still in initialization phase -- ok to create new
            # attributes
            object.__setattr__(self,name,value)

class UnicodeStructure(AbstractStructure,unicode):
    """En UnicodeStructure är bärare av ett värde (en textsträng av
    något slag). Den kan även ha andra egenskaper (ordningsnummer,
    ikraftträdandedatum etc)."""

    # immutable objects (like strings, unicode, etc) must provide a __new__ method
    def __new__(cls,arg=u'', *args, **kwargs):
        if not isinstance(arg,unicode):
               raise TypeError("%r is not unicode" % arg)
        obj = unicode.__new__(cls, arg)
        object.__setattr__(obj,'__initialized',False) 
        return obj
        
    #def __init__(self, *args, **kwargs):
    #    print "UnicodeStructure.__init__ called"
    #    super(UnicodeStructure,self).__init__(*args, **kwargs)

class IntStructure(AbstractStructure,int):
    """En IntStructure är en int som även kan ha andra egenskaper
    (ordningsnummer, ikraftträdandedatum etc)."""

    # immutable objects must provide a __new__ method
    def __new__(cls,arg=0, *args, **kwargs):
        if not isinstance(arg,int):
               raise TypeError("%r is not int" % arg)
        obj = int.__new__(cls, arg)
        object.__setattr__(obj,'__initialized',False) 
        return obj
        
class DateStructure(AbstractStructure,datetime.date):
    """En DateStructure är ett datetime.date som även kan ha andra
    egenskaper (ordningsnummer, ikraftträdandedatum etc)."""

    # immutable objects must provide a __new__ method
    def __new__(cls,arg=datetime.date.today(), *args, **kwargs):
        if not isinstance(arg,datetime.date):
               raise TypeError("%r is not datetime.date" % arg)
        obj = datetime.date.__new__(cls, arg.year, arg.month, arg.day)
        object.__setattr__(obj,'__initialized',False) 
        return obj
        
class CompoundStructure(AbstractStructure,list):
    """En CompoundStructure fungerar som en lista av andra Structureobjekt. 
    Den kan också  ha egna egenskaper (kapitelrubrik, paragrafnummer etc)"""
    def __new__(cls,arg=[], *args, **kwargs):
        # ideally, we'd like to do just "obj = list.__new__(cls,arg)"
        # but that doesn't seem to work
        obj = list.__new__(cls)
        obj.extend(arg)
        object.__setattr__(obj,'__initialized',False)
        return obj

#    def __init__(self, *args, **kwargs):
#        super(CompoundStructure,self).__init__(*args, **kwargs)

class MapStructure(AbstractStructure,dict):
    """En MapStructure är en anpassad map/dictionary"""
    def __new__(cls,arg={}, *args, **kwargs):
        # ideally, we'd like to do just "obj = dict.__new__(cls,arg)"
        # but that doesn't seem to work
        obj = dict.__new__(cls, arg)
        obj.update(arg)
        object.__setattr__(obj,'__initialized',False)
        return obj

#    def __init__(self, *args, **kwargs):
#        super(MapStructure,self).__init__(*args, **kwargs)

# Abstrakta klasser avsedda att användas vid multipelt arv, som
# lägger till vanliga egenskaper

class TemporalStructure(object):
    """En TemporalStructure har ett antal olika tidsegenskaper
    (ikraftträder, upphör, meddelas) som anger de tidsmässiga ramarna
    för vad det nu är frågan om"""
    def __init__(self):
        self.entryintoforce = None
        self.expires = None

    def in_effect(self,date=None):
        if not date:
            date = datetime.date.today()
        return (date >= self.entryintoforce) and (date <= self.expires)


class OrdinalStructure(object):
    """En OrdinalStructure har ett explicit
    ordningsnummer. Ordningsnumret behöver inte vara strikt numeriskt,
    utan kan även vara exv '6 a', när lagstiftaren tyckt sig behöva en
    ny paragraf mellan 6 och 7"""
    def __init__(self):
        self.ordinal = None

    # FIXME: gör en ordentlig smart mestadels-numerisk jämförelse ("2 a" < "20", "2" < "10")
    def __lt__(self,other):
        return self.ordinal < other.ordinal

    def __le__(self,other):
        return self.ordinal <= other.ordinal

    def __eq__(self,other):
        return self.ordinal == other.ordinal

    def __ne__(self,other):
        return self.ordinal != other.ordinal

    def __gt__(self,other):
        return self.ordinal > other.ordinal

    def __ge__(self,other):
        return self.ordinal == other.ordinal


import Util
class PredicateType(object):
    """Inheriting from this gives the subclass a predicate attribute,
    which describes the RDF predicate to which the class is the RDF
    subject (eg. if you want to model the title of a document, you
    would inherit from UnicodeStructure and this, and then set
    .predicate to
    rdflib.URIRef('http://purl.org/dc/elements/1.1/title')"""
    def __init__(self, *args, **kwargs):
        if 'predicate' in kwargs:
            self.predicate = kwargs['predicate']
            # switch the full uriref
            # (http://rinfo.lagrummet...#paragraf) to one using a
            # namespace prefix, if we know of one:
            shorten = False
            for (prefix, ns) in Util.ns.items():
                if kwargs['predicate'].startswith(ns):
                    predicateuri = kwargs['predicate']
                    kwargs['predicate'] = kwargs['predicate'].replace(ns, prefix+":")
                    # print "Shorten predicate %s to: %s" % (predicateuri, kwargs['predicate'])
                    shorten = True
            #if not shorten:
            #   print "Couldn't shorten predicate: %s" % self.predicate
        else:
            # From the RDF Schema spec: 'This is the class of
            # everything. All other classes are subclasses of this
            # class.'
            from rdflib import RDFS
            self.predicate = RDFS.Resource 
        super(PredicateType,self).__init__(*args, **kwargs)


def serialize(root):
    t = __serializeNode(root)
    __indentTree(t)
    return ET.tostring(t,'utf-8').decode('utf-8')

def deserialize(xmlstr):
    t = ET.fromstring(xmlstr)
    for e in t:
        print "element %r" % e.tag

        

# http://infix.se/2007/02/06/gentlemen-indent-your-xml
def __indentTree(elem, level=0):
    i = "\r\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for e in elem:
            indent(e, level+1)
            if not e.tail or not e.tail.strip():
                e.tail = i + "  "
        if not e.tail or not e.tail.strip():
            e.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

def __serializeNode(node):
    # print "serializing: %s" % node.__class__.__name__
    e = ET.Element(node.__class__.__name__)
    if hasattr(node,'__dict__'):
        for key in [x for x in node.__dict__.keys() if not x.startswith('__')]:
            val = node.__dict__[key]
            if (isinstance(val,unicode) or isinstance(val,str)):
                e.set(key,val)
            else:
                e.set(key,repr(val))
                
    if isinstance(node,unicode):
        e.text = node
    elif isinstance(node,str):
        e.text = node
    elif isinstance(node,int):
        e.text = unicode(node)
    elif isinstance(node,list):
        for x in node:
            e.append(__serializeNode(x))
    elif isinstance(node,dict):
        for x in node.keys():
            k = ET.Element("Key")
            k.append(__serializeNode(x))
            e.append(k)

            v = ET.Element("Value")
            v.append(__serializeNode(node[x]))
            e.append(v)
    else:
        e.text = repr(node)
        # raise TypeError("Can't serialize %r (%r)" % (type(node), node))
    return e

# in-place prettyprint formatter

def indent(elem, level=0):
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for elem in elem:
            indent(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i



#----------------------------------------------------------------
# Exempel på andra mixinklasser och ärvda klasser

class EvenMixin():
    def iseven(self):
        return (len(self.keyword) % 2 == 0)


class DerivedUnicode(UnicodeStructure, EvenMixin):
    # an example on how to customize object initialization, while still
    # letting the base class do it's initialization
    def __init__(self, *args, **kwargs):
        if kwargs['keyword']:
            self.keyword = kwargs['keyword'].upper()
            del kwargs['keyword']
        super(DerivedUnicode,self).__init__(*args, **kwargs)

class DerivedList(CompoundStructure, EvenMixin): pass

class DerivedDict(MapStructure, EvenMixin): pass

class DerivedInt(IntStructure, EvenMixin): pass

class DerivedDate(DateStructure, EvenMixin):  pass

class RDFString(PredicateType,UnicodeStructure):
    # N.B: if we inherit from (UnicodeStructure,PredicateType)
    # instead, PredicateType.__init__ never gets called! But this way,
    # AbstractStructure.__init__ never gets called. I think i must
    # read descrintro again...
    pass
    

if __name__ == '__main__':

    # print "Testing DerivedUnicode"
    u = DerivedUnicode(u'blahonga', keyword=u'myunicode')
    # print "\trepr(u): %s"   % repr(u)
    # print "\tu[1:4]: %r"    % u[1:4]
    # print "\tu.keyword: %r" % u.keyword
    # print "\tu.iseven: %r"  % u.iseven()

    # print "Testing DerivedList"
    l = DerivedList(['x','y','z'], keyword=u'mylist')
    # print "\tl[1]: %r"      % l[1]
    # print "\tl.keyword: %r" % l.keyword
    # print "\tl.iseven: %r"  % l.iseven()

    # print "Testing DerivedDict"
    d = DerivedDict({'a':'foo','b':'bar'}, keyword=u'mydict')
    # print "\td['a']: %r"    % d['a']
    # print "\td.keyword: %r" % d.keyword
    # print "\td.iseven: %r"  % d.iseven()

    # print "Testing DerivedInt"
    i = DerivedInt(42, keyword=u'myint')
    # print "\ti: %r"    % i
    # print "\ti+5: %r"  % (i+5)
    # print "\ti.keyword: %r" % d.keyword
    # print "\ti.iseven: %r"  % d.iseven()

    # print "Testing DerivedDate"
    nativedate = datetime.date(2008,3,15)
    dt = DerivedDate(nativedate, keyword=u'mydate')
    # print "\tdt: %r"    % dt
    # print "\tdt.keyword: %r" % dt.keyword
    # print "\tdt.iseven: %r"  % dt.iseven()

    # print "Testing RDFString"
    r = RDFString(u'Typisk dokumentrubrik', keyword=u'mysubject')
    # print "\trepr(r): %s"   % repr(r)
    # print "\tr[1:4]: %r"    % r[1:4]
    # print "\tr.keyword: %r" % r.keyword
    # print "\tr.predicate: %r" % r.predicate
    from rdflib import URIRef
    r.predicate = URIRef('http://purl.org/dc/terms/title')
    # print "\tr.predicate: %r" % r.predicate

    c = DerivedList([u,l,d,i,dt,r])
    x = serialize(c)
    deserialize(x)
