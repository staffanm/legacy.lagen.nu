# -*- coding: iso-8859-1 -*-
# Create your views here.
# import wingdbstub

from django.shortcuts import render_to_response, get_object_or_404
from django.core.mail import send_mail
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseServerError

from ferenda.wiki.models import Article
from ferenda.docview.models import IntrinsicRelation

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
    relations = IntrinsicRelation.objects.filter(subject__exact=art.title)
    return render_to_response('wiki/display.html', {'article':art,
                                                    'relations':relations})
        
    
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
        # pass utf-8 data unchanged from browser to db
        art.body = request.POST['text']
        
    art.last_changed = datetime.now()
    art.save()
    
    subject = u'[ferenda] %s ändrad (save)' % art_title.decode('utf-8')
    message = u'Ny text:\n\n%s' % request.POST["text"].decode('utf-8')
    
    send_mail(subject=subject.encode('utf-8'),
              message=message.encode('utf-8'),
              from_email='ferenda@lagen.nu',
              recipient_list=['staffan@tomtebo.org'],
              fail_silently=False)
    
    return HttpResponseRedirect('/%s' % art_title)

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
        art.last_changed = datetime.now()
        art.save()
        
        subject = u'[ferenda] %s/%s ändrad (savexhr)' % (docid,docsection)
        message = u'Ny text:\n\n%s' % unicode(request.POST["text"],'utf-8')

        send_mail(subject=subject.encode('utf-8'),
                  message=message.encode('utf-8'),
                  from_email=u'ferenda@lagen.nu',
                  recipient_list=[u'staffan@tomtebo.org'],
                  fail_silently=False)
        return HttpResponse(request.POST["text"])
    except Exception, e:
        print "General error: %s" % str(e)
        return HttpResponseServerError("Ett fel uppstod: %s " %str(e))
    