# -*- coding: iso-8859-1 -*-
# Create your views here.
import wingdbstub
from django.shortcuts import render_to_response, get_object_or_404
from django.core.mail import send_mail
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseServerError
from ferenda.wiki.models import Article
from datetime import datetime
import sys
sys.path.append("..")
from DocComments import AnnotatedDoc

def article(request,art_title="Blahonga"):
    #utitle = unicode(art_title,'utf-8')
    #ltitle = utitle.encode('iso-8859-1')
    if art_title == "":
        art_title = "Blahonga"
    try:
        art = Article.objects.get(pk=art_title)
        return render_to_response('wiki/display.html', {'article':art})
    except Article.DoesNotExist:
        return HttpResponseRedirect('/edit/%s' % art_title)

def edit(request,art_title):
    try:
        art = Article.objects.get(pk=art_title)
    except Article.DoesNotExist:
        art = Article()
        art.title = art_title
        art.body = "Skriv artikeltexten h&auml;r"
    return render_to_response('wiki/edit.html', {'article':art})

def save(request,art_title, art_section=None):
    try:
        art = Article.objects.get(pk=art_title)
    except Article.DoesNotExist:
        art = Article()
        art.title = art_title

    if art_section:
        ad = AnnotatedDoc()
        art.body = ad.Update(art.body,art_section,request.POST["text"])
    else:
        art.body = request.POST['text']
        
    art.last_changed = datetime.now()
    art.save()
    print "sending mail"
    send_mail(subject='[ferenda] %s andrad (save)' % (art_title),
              message='Ny text:\n\n%s' % unicode(request.POST["text"],'utf-8').encode('iso-8859-1'),
              from_email='ferenda@lagen.nu',
              recipient_list=['staffan@tomtebo.org'],
              fail_silently=False)
    print "sent mail"
    return HttpResponseRedirect('/%s' % art_title)

def savexhr(request,docid,docsection):
    print "savexhr called: %s, %s" % (docid,docsection)
    try:
        art = Article.objects.get(pk=docid)
    except Article.DoesNotExist:
        print "article %s does not exist" % docid
        return HttpResponseServerError("article %s does not exist" % docid)
    try:
        ad = AnnotatedDoc()
        art.body = ad.Update(art.body,docsection,request.POST["text"])
        art.last_changed = datetime.now()
        art.save()
        send_mail(subject=u'[ferenda] %s/%s andrad (savexhr)' % (docid,docsection),
                  # message=u'Ny text:\n\n%s' % unicode(request.POST["text"],'utf-8').encode('iso-8859-1'),
                  # message=u'Ny text:\n\n%s' % request.POST["text"],
                  message=u'Ny text: unicodestrul',
                  from_email='ferenda@lagen.nu',
                  recipient_list=['staffan@tomtebo.org'],
                  fail_silently=False)
                  
                  
        return HttpResponse(request.POST["text"])
    except Exception, e:
        print "General error: %s" % str(e)
        return HttpResponseServerError("Ett fel uppstod: %s " %str(e))
    
