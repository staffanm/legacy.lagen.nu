# -*- coding: iso-8859-1 -*-
from django.db import models

from django.db.models import signals
from django.dispatch import dispatcher
from django.contrib.auth.models import User

class Article(models.Model):
    title = models.CharField(maxlength=200, primary_key=True)
    body = models.TextField()
    version = models.IntegerField()
    author = models.ForeignKey(User)
    comment = models.CharField(maxlength=200)
    timestamp = models.DateTimeField() 
    # and delete this:
    # last_changed = models.DateTimeField('Senast ändrad')

    class Admin:
        pass

    def __str__(self):
        return self.title;
    
    # override save to fix automatic archiving
    def save(self):
        try:
            self.version = ArticleArchive.objects.filter(title__exact=self.title).order_by('-version')[0].version + 1
        except IndexError:
            self.version = 1
        try:
            archived = ArticleArchive()
            archived.version = self.version - 1            
            # get art as it's currently in the db
            current = Article.objects.get(pk=self.title)
            archived.title=current.title
            archived.body = current.body
            archived.author = self.author
            archived.comment = current.comment
            archived.timestamp = current.timestamp
            archived.save()
    
        except Article.DoesNotExist:
            # this article doesn't exist yet (the save will create the
            # first version of it) -- no archiving to be done
            pass

        super(Article,self).save()

# not really sure if it's sensible to have a separate archive table, but
# mediawiki is built that way and it seems to work. it simplifies dumping the
# current data, anyhow
# 
# what would be cool is if articles were archived into a SVN 
# repository. Let's make that a 2.1 feature.
class ArticleArchive(models.Model):
    title = models.CharField(maxlength=200)
    body = models.TextField()
    version = models.IntegerField()    
    author = models.ForeignKey(User) 
    comment = models.CharField(maxlength=200)
    timestamp =  models.DateTimeField()
