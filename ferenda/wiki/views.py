# -*- coding: iso-8859-1 -*-
# Create your views here.
from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponseRedirect
from ferenda.wiki.models import Article
from datetime import datetime

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

def save(request,art_title):
    try:
        art = Article.objects.get(pk=art_title)
    except Article.DoesNotExist:
        art = Article()
        art.title = art_title

    art.body = request.POST['body']
    art.last_changed = datetime.now()
    art.save()
    return HttpResponseRedirect('/%s' % art_title)
