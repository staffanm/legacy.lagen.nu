# -*- coding: iso-8859-1 -*-
from django.db import models
import codecs

class LegalDocument(models.Model):
    # nothing in this table is unique, it's just a cache that gets regenerated
    # by the legalsource modules (the Index method)
    
    # eg 'urn:x-sfs:1960:729'
    urn = models.CharField(maxlength=255, unique=True, db_index=True) 
    # eg '1960:729'
    displayid = models.CharField(maxlength=255) 
    # eg 'Lag (1960:729) om upphovsrätt till litterära och konstnärliga verk'
    title = models.CharField(maxlength=255) 
    htmlpath = models.CharField(maxlength=255)
    xmlpath = models.CharField(maxlength=255)

    def __str__(self):
        return self.displayid;
    
    class Admin:
        pass

class Predicate(models.Model):
    # used in N3/RDF data, eg 'http://purl.org/dc/elements/1.1/title'
    uri = models.CharField(maxlength=80, primary_key = True)
    # used in code, eg 'title'
    label = models.CharField(maxlength=20) 
    # used in user interface (localized string) eg "Dokumenttitel"
    displayname = models.CharField(maxlength=80)
    # if true, accept literal strings, otherwise only URIs
    subjectIsLiteralString = models.BooleanField()
    
    def __str__(self):
        return label

class Relation(models.Model):
    # I thought about modelling object as a foreign key, like this
    # object = models.ForeignKey(LegalDocument, to_field='urn',db_index=True)
    # but since 'object' should be able to handle fragment adressing (or whatever it's called, ie 'urn:x-sfs:1960:729#P49') it won't work.
    object = models.CharField(maxlength=100)
    predicate = models.ForeignKey(Predicate)
    # the longest verdict summary is 2096 characters utf-8 encoded...
    subject = models.CharField(maxlength=3000,db_index=True)
    intrinsic = models.BooleanField() # if false, this was manually added
    comment = models.CharField(maxlength=255)
    class Admin:
        pass
    
    def __str__(self):
        return "%s => %s (%s)" % (self.object,self.subject,self.predi)
    
