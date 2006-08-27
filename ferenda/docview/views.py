# -*- coding: iso-8859-1 -*-
# Create your views here.
try:
    import wingdbstub
except ImportError:
    pass
from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.template import RequestContext
from django.conf import settings

from ferenda.docview.models import Document, Relation, Predicate
from ferenda.wiki.models import Article
import sys, codecs, re
sys.path.append("..")
<<<<<<< .mine
sys.path.append(".")
=======

>>>>>>> .r52
import DocComments
from SFS import SFSManager
from DV import DVManager
from DocComments import AnnotatedDoc
import pickle 
identifierPredicate = Predicate.objects.get(uri=Predicate.IDENTIFIER)

def view(request,displayid,module):
    displayid = unicode(displayid,'utf-8').replace('_',' ')
    ld = get_object_or_404(Document, displayid=displayid)
    if module == 'sfs':
        mgr = SFSManager(settings.BASE_DIR,'sfs')
    elif module == 'dv':
        mgr = DVManager(settings.BASE_DIR,'dv')
        
    
    htmlFile = mgr._htmlFileName(ld.basefile)
    referenceFile = mgr._refFileName(ld.basefile)
    references = mgr._deserializeReferences(referenceFile)
    
    ad = AnnotatedDoc(htmlFile)
    try:
        comments = Article.objects.get(pk=displayid).body.decode('utf-8')
    except Article.DoesNotExist:
        comments = u''

    content = ad.Combine(comments,references)
    return render_to_response('docview/view.html', 
                              {'displayid':displayid,
                               'content':content},
                              context_instance=RequestContext(request))
    
    # document = codecs.open(filename,encoding='iso-8859-1').read().encode('utf-8')
    # references = mgr._referencesAsArray(mgr._displayIdToBasefile(displayid,'urn:x-sfs'))
    comments = mgr._commentsAsArray(mgr._displayIdToBasefile(displayid,'urn:x-sfs'))
    #return render_to_response('docview/view.html', 
                              #{'displayid':displayid,
                               #'document':document,
                               #'references':references,
                               #'comments':comments},
                              #context_instance=RequestContext(request))


def list(request,source):
    docs = Document.objects.filter(urn__startswith='urn:x-%s' % source)[:500]
    return render_to_response('docview/list.html',
                              {'docs':docs},
                              context_instance=RequestContext(request))
                              

# not used anymore
def __buildReferences(urn):
    """build a big-ass five level deep datastructure to 
    represent all references to this document. a typical path is:
    references['K2P4']['Rättsfall'][3]['title']"""
    # This code could be slimmer if the rules were refactored to
    # datastructures but let's not to that until i'm sure of the requirements
    #
    # First, find out all documents that refer to (some part of)
    # this document
    thisDoc = Relation.objects.get(object=urn,predicate=identifierPredicate)
    # referenceObjects = Relation.objects.filter(subject=thisDoc).order_by('object')
    # but in order to display these documents as something 
    # friendlier than "urn:x-dv:hd:t-1234-34" etc we need all
    # relations for *those* documents. Using in_bulk means
    # it should be relatively zippy
    # propertyObjects= Relation.objects.order_by('object').in_bulk([r.object for r in referenceObjects])
    
    # sorts these secondary relations (properties) per document
    props = {}
    relationsCache = {}
    for doc in thisDoc.relations_set.all():
        docUri = doc.object
        if doc.object not in props:
            props[docUri] = {}
        if doc.object not in relationsCache:
            relationsCache[docUri] = Relation.objects.filter(object=docUri)
            
        for prop in relationsCache[docUri]:
            doc_props = props[docUri]
            doc_props['urn'] = docUri
            # build a dict for this doc, suitable for creating links
            if prop.predicate.uri == Predicate.DESCRIPTION:
                doc_props['longdesc'] = prop.subjectLiteral
            if prop.predicate.uri == Predicate.IDENTIFIER:
                doc_props['title'] = prop.subjectLiteral
            if prop.predicate.uri == Predicate.ALTERNATIVE:
                doc_props['alternative'] = prop.subjectLiteral
            # FIXME: if we start using source relations for 
            # legal documents that we actually publish ourselves
            # this won't look pretty
            if prop.predicate.uri == Predicate.SOURCE:
                doc_props['url'] = prop.subjectLiteral

    #  if we don't have a source property, we construct the url from
    # other properties 
    for doc_props in props.values():
        if not 'url' in doc_props:
            if doc_props['urn'].startswith('urn:x-sfs'):
                doc_props['url'] = "/" + doc_uri.split(':',2)[2]
            else:
                doc_props['url'] = "/" + doc_props['title'].replace(' ','_')            
    # ok, we have information on every reference neatly arranged for easy
    # hyperlink construction. Now arrange them in by the fragment they refer
    # to (a verdict typically points to a particular paragraph, not the law
    # itself), and what kind of document they come from
    references = {}
    for r in thisDoc.relations_set.all():
        doc_props = props[r.object]
        if doc_props['urn'].startswith('urn:x-dv'):
            label = u'Rättsfall'.encode('utf-8')
        elif doc_props['urn'].startswith('urn:x-sfs'):
            label = u'Lagändringar'.encode('utf-8')
        else:
            label = 'Övrigt'
        
        base = r.subject.object
        fragment = r.subjectFragment
        
        if not fragment:
            fragment = "top"
        if fragment not in references:
            references[fragment] = {}
        if label not in references[fragment]:
            references[fragment][label] = []
        
        references[fragment][label].append(doc_props)
    
    # lastly, convert the dictionary-based structure to a list/dict-based structure
    # for easy use from django templates
    ref_list = []
    for fragment in references.keys():
        documentTypes = []
        for doctype in references[fragment].keys():
            documentTypes.append({'label':doctype,
                                  'documents':references[fragment][doctype]})
        ref_list.append({'fragmentid':fragment,
                         'documenttypes':documentTypes})
    
    return ref_list
    
