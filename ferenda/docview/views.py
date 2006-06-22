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
        try:
            c = Article.objects.get(title=displayid)
            ad = DocComments.AnnotatedDoc(d.htmlpath)
            generated = ad.Combine(unicode(c.body, 'utf-8'))
        except Article.DoesNotExist:
            generated = unicode(d.getHtml(), 'iso-8859-1').encode('utf-8')
        return render_to_response('docview/view.html', {'doc':d,
                                                        'displayid':displayid,
                                                        'generated':generated})
    except LegalDocument.DoesNotExist:
        return render_to_response('docview/404.html')

