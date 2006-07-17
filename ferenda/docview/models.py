# -*- coding: iso-8859-1 -*-
from django.db import models
import codecs

class LegalDocument(models.Model):
    urn = models.CharField(maxlength=255)
    # we would like to use db_index and unique = True, but sometimes that ain't the case (DV/1200 and 1201, for instance)
    # displayid = models.CharField(maxlength=255,db_index=True,unique=True)
    displayid = models.CharField(maxlength=255)
    htmlpath = models.CharField(maxlength=255)
    xmlpath = models.CharField(maxlength=255)
    #def getHtml(self):
        #return codecs.open(self.htmlpath,encoding='iso-8859-1').read()

    def __str__(self):
        return self.displayid;
    
    class Admin:
        pass
    
class IntrinsicRelation(models.Model):
    object = models.CharField(maxlength=100)
    relation = models.CharField(maxlength=100)
    subject = models.CharField(maxlength=100)
    class Admin:
        pass
    
    def __str__(self):
        return "%s => %s (%s)" % (object,subject,relation)
    
