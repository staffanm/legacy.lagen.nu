# -*- coding: iso-8859-1 -*-
from django.db import models

from django.db.models import signals
from django.dispatch import dispatcher

class Article(models.Model):
    title = models.CharField(maxlength=200, primary_key=True)
    body = models.TextField()
    # FIXME: add the following fields (without destroying the data)
    # version = models.IntegerField()
    # author = some kind of User object from the auth framework
    # comment = models.CharFields(maxlength=200)
    # timestamp = models.DateTimeField() 
    # 
    # and delete this:
    last_changed = models.DateTimeField('Senast ändrad')
    
    
    class Admin:
        pass

    def __str__(self):
        return self.title;

# not really sure if it's sensible to have a separate archive table, but
# mediawiki is built that way and it seems to work
class ArticleArchive(models.Model):
    title = models.CharField(maxlength=200)
    body = models.TextField()
    version = models.IntegerField()    
    
    author = models.CharField(maxlength=50) # should be a User object in the future
    comment = models.CharField(maxlength=200)
    timestamp =  models.DateTimeField()

class AddedRelation(models.Model):
    """Also see IntrinsicRelation in ferenda.wiki.models"""
    object = models.CharField(maxlength=100)
    relation = models.CharField(maxlength=100)
    subject = models.CharField(maxlength=100)
    class Admin:
        pass
    
    def __str__(self):
        return "%s -> %s (%s)" % (object,subject,relation)
    
def archiveArticle(sender, instance, signal, *args, **kwargs):
    print "do magic here"
    try:
        nextversion = ArticleArchive.objects.filter(title__exact=instance.title).order_by('-version')[0].version + 1
    except IndexError:
        nextversion = 1
    current = Article.objects.get(pk=instance.title)
    archived = ArticleArchive()
    archived.title=current.title
    archived.version = nextversion
    archived.body = current.body
    archived.author='Fred Bloggs'
    archived.comment='Just fixing'
    archived.timestamp = current.last_changed
    archived.save()

    
dispatcher.connect(archiveArticle,signal=signals.pre_save, sender=Article)
