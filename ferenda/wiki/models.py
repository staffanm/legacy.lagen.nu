# -*- coding: iso-8859-1 -*-
from django.db import models

# Create your models here.
from django.db import models

class Article(models.Model):
    title = models.CharField(maxlength=200, primary_key=True)
    body = models.TextField()
    last_changed = models.DateTimeField('Senast ändrad')
    class Admin:
        pass

    def __str__(self):
        return self.title;


    
    
class AddedRelation(models.Model):
    """Also see IntrinsicRelation in ferenda.wiki.models"""
    object = models.CharField(maxlength=100)
    relation = models.CharField(maxlength=100)
    subject = models.CharField(maxlength=100)
    class Admin:
        pass
    
    def __str__(self):
        return "%s -> %s (%s)" % (object,subject,relation)
    
