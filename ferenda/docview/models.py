# -*- coding: iso-8859-1 -*-
from django.db import models
import codecs

class Predicate(models.Model):
    DESCRIPTION = u'http://purl.org/dc/elements/1.1/description'
    IDENTIFIER  = u'http://purl.org/dc/elements/1.1/identifier'
    SOURCE      = u'http://purl.org/dc/elements/1.1/source'
    TITLE       = u'http://purl.org/dc/elements/1.1/title'
    SUBJECT     = u'http://purl.org/dc/elements/1.1/subject'
    ALTERNATIVE = u'http://purl.org/dc/terms/alternative'
    CONFORMSTO  = u'http://purl.org/dc/terms/conformsTo'
    REFERENCES  = u'http://purl.org/dc/terms/references'
    REQUIRES    = u'http://purl.org/dc/terms/requires'
    # used in N3/RDF data, eg 'http://purl.org/dc/elements/1.1/title'
    uri = models.CharField(maxlength=80)
    # used in user interface (localized string) eg "Dokumenttitel"
    displayname = models.CharField(maxlength=80)
    # if true, accept literal strings, otherwise only URIs
    subjectIsLiteralString = models.BooleanField()
    
    def __str__(self):
        return self.uri

class Relation(models.Model):
    # I thought about modelling object as a foreign key, like this
    # object = models.ForeignKey(Document, to_field='urn',db_index=True)
    # but since 'object' should be able to handle fragment adressing (or whatever it's called, ie 'urn:x-sfs:1960:729#P49') it won't work.
    # and anyway, if we just keep stuffing data into the Relation table
    # we won't need Document for much longer...
    object = models.CharField(maxlength=100, db_index=True)
    objectFragment = models.CharField(maxlength=100)
    predicate = models.ForeignKey(Predicate)
    subject = models.ForeignKey('self', null=True, related_name='relations_set',db_index=True)
    subjectFragment = models.CharField(maxlength=100)
    subjectLiteral = models.CharField(maxlength=3000) # the longest verdict summary is 2096 characters utf-8 encoded...
    intrinsic = models.BooleanField() # if false, this was manually added
    comment = models.CharField(maxlength=255)
    class Admin:
        pass
    
    def __str__(self):
        if self.subject:
            return "<%s#%s> <%s> <%s#%s>." % (self.object,self.objectFragment,self.predicate,self.subject.object,self.subject.objectFragment)
        else:
            return "<%s#%s> <%s> \"%s\"." % (self.object,self.objectFragment,self.predicate,self.subjectLiteral)
        

# Only the Relation table is strictly neccesary -- the following tables are support tables to make certain lookups faster

class Document(models.Model):
    # eg 'urn:x-sfs:1960:729', 'urn:x-dv:hd:T1138-92'
    # unique=True should be set, but due to bad source data, we cannot
    # guarantee URN uniqueness (might have to patch the source data)
    urn = models.CharField(maxlength=100, db_index=True) 
    # eg '1960:729', 'NJA 1994 s 74'
    displayid = models.CharField(maxlength=100, db_index=True)
    # eg '1960/729', '6233'
    basefile = models.CharField(maxlength=50, unique=True, db_index=True)

    def __str__(self):
        return self.displayid;
    
    class Admin:
        pass
    
#class Fragment(models.Model):
    #fragmentid = models.CharField(maxlength=20)
    #order = models.IntegerField(null=True)
    #doc = models.ForeignKey(Document)

#class RefType(models.Model):
    #label = models.CharField(maxlength=40)
    #fragment = models.ForeignKey(Fragment)
    
#class Reference(models.Model):
    #displayid = models.CharField(maxlength=100)
    #urn = models.CharField(maxlength=100)
    #alternate = models.CharField(maxlength=100)
    #description = models.CharField(maxlength=3000)
    #type = models.ForeignKey(RefType)
