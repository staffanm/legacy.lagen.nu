#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-



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
    """En UnicodeStructure �r b�rare av ett v�rde (en textstr�ng av
    n�got slag). Den kan �ven ha andra egenskaper (ordningsnummer,
    ikrafttr�dandedatum etc)."""

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
    Den kan ocks�  ha egna egenskaper (kapitelrubrik, paragrafnummer etc)"""
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
    """En MapStructure �r en anpassad map/dictionary"""
    def __new__(cls,arg={}, *args, **kwargs):
        # ideally, we'd like to do just "obj = dict.__new__(cls,arg)"
        # but that doesn't seem to work
        obj = dict.__new__(cls, arg)
        obj.update(arg)
        object.__setattr__(obj,'__initialized',False)
        return obj

#    def __init__(self, *args, **kwargs):
#        super(MapStructure,self).__init__(*args, **kwargs)

# Abstrakta klasser avsedda att anv�ndas vid multipelt arv, som
# l�gger till vanliga egenskaper

class TemporalStructure():
    """En TemporalStructure har ett antal olika tidsegenskaper
    (ikrafttr�der, upph�r, meddelas) som anger de tidsm�ssiga ramarna
    f�r vad det nu �r fr�gan om"""
    def __init__(self):
        self.entryintoforce = None
        self.expires = None

    def in_effect(self,date=None):
        if not date:
            date = datetime.datetime.now()
        return (date >= self.entryintoforce) and (date <= self.expires)


class OrdinalStructure():
    """En OrdinalStructure har ett explicit
    ordningsnummer. Ordningsnumret beh�ver inte vara strikt numeriskt,
    utan kan �ven vara exv '6 a', n�r lagstiftaren tyckt sig beh�va en
    ny paragraf mellan 6 och 7"""
    def __init__(self):
        self.ordinal = None

    # FIXME: g�r en ordentlig smart mestadels-numerisk j�mf�relse ("2 a" < "20", "2" < "10")
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

#----------------------------------------------------------------
# Exempel p� andra mixinklasser och �rvda klasser

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

