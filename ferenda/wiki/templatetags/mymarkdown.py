from django import template
import markdown
from ferenda.docview.models import Document

register = template.Library()


class WikiPattern (markdown.BasePattern):
    def handleMatch(self,m,doc):
        wikiword = m.group('wikiword')
        if '|' in wikiword:
            wikiword,linktext = wikiword.split('|', 1)
        else:
            try:
                d = Document.objects.get(displayid=wikiword.encode('utf-8'))
                linktext = d.title.decode('utf-8')
            except Document.DoesNotExist:
                linktext = wikiword
            
        wikiword = wikiword.replace(" ", "_").capitalize()
        a = doc.createElement('a')
        a.appendChild(doc.createTextNode(linktext))
        a.setAttribute('href', '/%s' % wikiword)
        return a

def mymarkdown(value, arg=''):
    if not isinstance(value,unicode):
        value = value.decode('utf-8')
        
    wp = WikiPattern(r'\[(?P<wikiword>[^\]]+)\]')
    md = markdown.Markdown(source=value,encoding='utf-8')
    md.inlinePatterns.append(wp)

    footnoteExt = markdown.FootnoteExtension()
    footnoteExt.extendMarkdown(md)
    md.source = value
    ret = unicode(md)
    return ret.encode('utf-8')

register.filter(mymarkdown)

def underscore(value,arg=''):
    return value.replace(' ','_');

register.filter(underscore)