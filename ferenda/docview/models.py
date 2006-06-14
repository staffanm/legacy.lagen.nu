# -*- coding: iso-8859-1 -*-
from django.db import models
import codecs

class LegalDocument(models.Model):
    urn = models.CharField(maxlength=255)
    displayid = models.CharField(maxlength=255,db_index=True,unique=True)
    htmlpath = models.CharField(maxlength=255)
    xmlpath = models.CharField(maxlength=255)
    def getHtml(self):
        return codecs.open(self.htmlpath,encoding='iso-8859-1').read()

    def __str__(self):
        return self.displayid;
    
    class Admin:
        pass
    
