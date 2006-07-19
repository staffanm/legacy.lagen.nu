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

class IntrinsicRelation(models.Model):
    # I thought about modelling object as a foreign key, like this
    # object = models.ForeignKey(LegalDocument, to_field='urn',db_index=True)
    # but since 'object' should be able to handle fragment adressing (or whatever it's called, ie 'urn:x-sfs:1960:729#P49') it won't work.
    object = models.CharField(maxlength=100)
    relation = models.CharField(maxlength=100)
    subject = models.CharField(maxlength=100,db_index=True)
    class Admin:
        pass
    
    def __str__(self):
        return "%s => %s (%s)" % (self.object,self.subject,self.relation)
    
