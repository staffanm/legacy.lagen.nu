# Create your views here.

from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponseRedirect
from ferenda.docview.models import LegalDocument
from ferenda.wiki.models import Article
import sys
sys.path.append("..")
import DocComments

def view(request,displayid):
    try:
        d = LegalDocument.objects.get(displayid=displayid)
        #try:
        #    c = Article.objects.get(title=displayid)
        #    generated = DocComments.weave(d.getHtml(),c.body)
        #except Article.DoesNotExist:
        generated = d.getHtml()
        return render_to_response('docview/view.html', {'doc':d,
                                                        'generated':generated})
    except LegalDocument.DoesNotExist:
        return render_to_response('docview/404.html')

