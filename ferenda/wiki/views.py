# -*- coding: iso-8859-1 -*-
# Create your views here.
# import wingdbstub

from django.shortcuts import render_to_response, get_object_or_404
from django.core.mail import send_mail
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseServerError
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import authenticate,login

from django.template import RequestContext

from ferenda.wiki.models import Article
from ferenda.docview.models import Relation, Predicate

from datetime import datetime
import sys
sys.path.append("..")
sys.path.append("3rdparty")
from DocComments import AnnotatedDoc

def article(request,art_title="Huvudsida"):
    #utitle = unicode(art_title,'utf-8')
    #ltitle = utitle.encode('iso-8859-1')
    if art_title == "":
        art_title = u'Huvudsida'
    else:
        # most browsers (IE, Safari, Opera, Konq) sends URLs that the user
        # typed in by hand as UTF-8. Firefox sends as latin-1. Try as utf-8
        # first and if that fails, redirect to the URL-escaped utf-8
        # representation. I believe this is how wikipedia does it
        try: 
            art_title = art_title.decode('utf-8')
        except UnicodeDecodeError:
            import urllib
            redirectUrl = '/%s' % urllib.quote(art_title.decode('iso-8859-1').encode('utf-8'))
            return HttpResponseRedirect(redirectUrl)
    try:
        art = Article.objects.get(pk=art_title.encode('utf-8'))
    except Article.DoesNotExist:
        art = Article()
        art.title = art_title.encode('utf-8')
        art.body = u'(det finns ingen artikeltext här än)'
        # return HttpResponseRedirect('/edit/%s' % art_title.encode('utf-8'))
    # now here we find out all IntrinsicRelations that has this keyword for subject
    # this query gives a better resultset
    # select d.urn, d.displayid, left(r2.subjectLiteral,40) from docview_relation r, docview_relation r2, docview_document d where r.object = d.urn and r.object = r2.object and r2.predicate_id = 1 and r.subjectLiteral = 'Skadestånd';

    relations = Relation.objects.filter(subjectLiteral__exact=art.title)
    
    
    return render_to_response('wiki/display.html', 
                              {'article':art,
                               'relations':relations},
                              context_instance=RequestContext(request))

def createuser(request):
    if request.method == "POST":
        u = User.objects.create_user(request.POST['username'],request.POST['email'],request.POST['password'])
        subject = u'[ferenda] Ny användare %s' % u.username
        message = u'Användare %s (%s) har skapats' % (u.username,u.email)
        send_mail(subject=subject.encode('utf-8'),
                  message=message.encode('utf-8'),
                  from_email='ferenda@lagen.nu',
                  recipient_list=['staffan@tomtebo.org'],
                  fail_silently=False)
        user = authenticate(username=request.POST['username'],
                            password=request.POST['password'])
        login(request,user)
        return HttpResponseRedirect('/')
    else:
        return render_to_response('registration/create.html')
    
    
def showprofile(request):
    return HttpResponseRedirect('/')

@login_required    
def edit(request,art_title):
    try:
        art = Article.objects.get(pk=art_title)
    except Article.DoesNotExist:
        art = Article()
        art.title = art_title
        art.body = "Skriv artikeltexten h&auml;r"
    return render_to_response('wiki/edit.html', 
                              {'article':art},
                              context_instance=RequestContext(request))

@login_required
def save(request,art_title):
    try:
        art = Article.objects.get(pk=art_title)
    except Article.DoesNotExist:
        art = Article()
        art.title = art_title

    art.body = request.POST['text']
    art.author = request.user
    art.comment = "some comment"
    art.timestamp = datetime.now()
    art.save()
    
    subject = u'[ferenda] %s ändrad (save)' % art_title.decode('utf-8')
    
    message = u'Ändrat av: %s\nNy text:\n\n%s' % (request.user.username,request.POST["text"].decode('utf-8'))
    
    send_mail(subject=subject.encode('utf-8'),
              message=message.encode('utf-8'),
              from_email='ferenda@lagen.nu',
              recipient_list=['staffan@tomtebo.org'],
              fail_silently=False)
    
    return HttpResponseRedirect('/%s' % art_title)

@login_required
def savexhr(request,docid,docsection):
    print "savexhr called: %s, %s" % (docid,docsection)
    try:
        art = Article.objects.get(pk=docid)
    except Article.DoesNotExist:
        art = Article()
        art.title = docid
        #print "article %s does not exist" % docid
        #return HttpResponseServerError("article %s does not exist" % docid)
    try:
        ad = AnnotatedDoc()
        art.body = ad.Update(art.body,docsection,request.POST["text"])
        art.author = request.user
        art.timestamp = datetime.now()
        art.save()
        
        subject = u'[ferenda] %s/%s ändrad (savexhr)' % (docid,docsection)
        message = u'Ändrat av: %s\nNy text:\n\n%s' % (request.user.username,unicode(request.POST["text"],'utf-8'))

        send_mail(subject=subject.encode('utf-8'),
                  message=message.encode('utf-8'),
                  from_email=u'ferenda@lagen.nu',
                  recipient_list=[u'staffan@tomtebo.org'],
                  fail_silently=False)
        return HttpResponse(request.POST["text"])
    except Exception, e:
        print "General error: %s" % str(e)
        return HttpResponseServerError("Ett fel uppstod: %s " %str(e))
    
