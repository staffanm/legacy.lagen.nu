# Create your views here.
#try:
    #import wingdbstub
#except ImportError:
    #pass
from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponseRedirect
from ferenda.docview.models import LegalDocument, Relation, Predicate
from ferenda.wiki.models import Article
import sys, codecs, re
sys.path.append("..")
import DocComments

def view(request,displayid):
    displayid = unicode(displayid,'utf-8').replace('_',' ')
    ld = get_object_or_404(LegalDocument, displayid=displayid)
    filename = ld.htmlpath
    ad = DocComments.AnnotatedDoc(filename)
    try:
        c = Article.objects.get(title=displayid)
        comments = ad.FormatComments(unicode(c.body, 'utf-8'))
    except Article.DoesNotExist:
        comments = ad.FormatComments(u'')
        
        
    document = codecs.open(filename,encoding='iso-8859-1').read().encode('utf-8')
    references = Relation.objects.filter(subject__startswith=ld.urn)
    return render_to_response('docview/view.html', 
                              {'displayid':displayid,
                               'document':document[62:-8],
                               'references':references,
                               'comments':comments},
                              context_instance=RequestContext(request))
