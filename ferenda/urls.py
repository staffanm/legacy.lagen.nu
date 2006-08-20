from django.conf.urls.defaults import *

urlpatterns = patterns(
    '',
    
    # (r'^static/(.*)$', 'django.views.static.serve', {'document_root': '/Library/WebServer/Documents/ferenda.lagen.nu/ferenda/static'}),
    (r'^static/(.*)$', 'django.views.static.serve', {'document_root': 'ferenda/static'}),
    
    (r'^admin/', include('django.contrib.admin.urls')),
    (r'^accounts/login/$', 'django.contrib.auth.views.login', 
     {'template_name':'registration/login.html'}),
    (r'^accounts/logout/$', 'django.contrib.auth.views.logout',
     {'template_name':'registration/logout.html'}),     
    (r'^accounts/create/$', 'ferenda.wiki.views.createuser'),
    
    # several different patterns to match common legal document displaynames (eg "1960:729", "NJA_1985_s_142", etc)
    (r'^(?P<displayid>\d{4}:\d+)$', 'ferenda.docview.views.view'),
    (r'^(?P<displayid>NJA_\d{4}_s\.?_\d+)$', 'ferenda.docview.views.view'),
    
    # index pages that list all legal documents of a certain kind
    (r'^(?P<source>sfs)$', 'ferenda.docview.views.list'),
    
    # wiki actions
    (r'^edit/(?P<art_title>.*)$', 'ferenda.wiki.views.edit'),
    (r'^save/(?P<art_title>[^/]*)$', 'ferenda.wiki.views.save'),
    (r'^savexhr/(?P<docid>[^/]*)/(?P<docsection>.*)$', 'ferenda.wiki.views.savexhr'),
    # last resort -- if we can't find anything else, try to show
    # a wiki page
    (r'^(?P<art_title>.*)$', 'ferenda.wiki.views.article')
)
