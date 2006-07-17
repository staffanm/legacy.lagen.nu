# Create your views here.
import wingdbstub
from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponseRedirect
from ferenda.docview.models import LegalDocument
from ferenda.wiki.models import Article
import sys, codecs, re
sys.path.append("..")
import DocComments

def view(request,displayid):
    displayid = unicode(displayid,'utf-8').replace('_',' ')
    ld = get_object_or_404(LegalDocument, displayid=displayid)
    filename = ld.htmlpath
    try:
        c = Article.objects.get(title=displayid)
        ad = DocComments.AnnotatedDoc(filename)
        generated = ad.Combine(unicode(c.body, 'utf-8'))
    except Article.DoesNotExist:
        generated = codecs.open(filename,encoding='iso-8859-1').read().encode('utf-8')
    return render_to_response('docview/view.html', {'displayid':displayid,
                                                    'generated':generated})
