#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

import xml.etree.cElementTree as ET
import sys

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
        
#    def __init__(self, *args, **kwargs):
#        super(UnicodeStructure,self).__init__(*args, **kwargs)

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

class TemporalStructure():
    """En TemporalStructure har ett antal olika tidsegenskaper
    (ikraftträder, upphör, meddelas) som anger de tidsmässiga ramarna
    för vad det nu är frågan om"""
    def __init__(self):
        self.entryintoforce = None
        self.expires = None

    def in_effect(self,date=None):
        if not date:
            date = datetime.datetime.now()
        return (date >= self.entryintoforce) and (date <= self.expires)


class OrdinalStructure():
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

def serialize(root):
    t = __serializeNode(root)
    __indentTree(t)
    return ET.tostring(t,'utf-8').decode('utf-8')

# http://infix.se/2007/02/06/gentlemen-indent-your-xml
def __indentTree(elem, level=0):
    i = "\n" + level*"  "
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
            if isinstance(val,unicode):
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
        raise TypeError("Can't serialize %r (%r)" % (type(node), node))
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

    #def __repr__(self):
    #    return u'%s(\'%s\',keyword=%s)'%(self.__class__.__name__,self,self.keyword)

class DerivedList(CompoundStructure, EvenMixin):
    pass
#    def __init__(self, *args, **kwargs):
#        super(DerivedList,self).__init__(*args, **kwargs)

class DerivedDict(MapStructure, EvenMixin):
    pass
#    def __init__(self, *args, **kwargs):
#        super(DerivedDict,self).__init__(*args, **kwargs)


if __name__ == '__main__':

    print "Testing DerivedUnicode"
    u = DerivedUnicode(u'blahonga', keyword='myunicode')
    print "\trepr(u): %s"   % repr(u)
    print "\tu[1:4]: %r"    % u[1:4]
    print "\tu.keyword: %r" % u.keyword
    print "\tu.iseven: %r"  % u.iseven()

    print "Testing DerivedList"
    l = DerivedList(['x','y','z'], keyword='mylist')
    print "\tl[1]: %r"      % l[1]
    print "\tl.keyword: %r" % l.keyword
    print "\tl.iseven: %r"  % l.iseven()

    print "Testing DerivedDict"
    d = DerivedDict({'a':'foo','b':'bar'}, keyword='mydict')
    print "\td['a']: %r"    % d['a']
    print "\td.keyword: %r" % d.keyword
    print "\td.iseven: %r"  % d.iseven()

    c = DerivedList([u,l,d])
    print serialize(c)
