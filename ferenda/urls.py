from django.conf.urls.defaults import *
import os
STATIC_ROOT = '/Library/WebServer/Documents/ferenda.lagen.nu/ferenda/static'
if os.path.exists(STATIC_ROOT):
    document_root = STATIC_ROOT
else:
    document_root = 'ferenda/static'
    
urlpatterns = patterns(
    '',
    (r'^static/(.*)$', 'django.views.static.serve', {'document_root': document_root}),
    (r'^robots.txt$', 'django.views.static.serve', {'document_root': document_root}),    
    (r'^admin/', include('django.contrib.admin.urls')),
    (r'^accounts/login/$', 'django.contrib.auth.views.login', 
     {'template_name':'registration/login.html'}),
    (r'^accounts/logout/$', 'django.contrib.auth.views.logout',
     {'template_name':'registration/logout.html'}),     
    (r'^accounts/create/$', 'ferenda.wiki.views.createuser'),
    (r'^accounts/profile/$', 'ferenda.wiki.views.showprofile'),
    # several different patterns to match common legal document displaynames (eg "1960:729", "NJA_1985_s_142", etc)
    (r'^(?P<displayid>\d{4}:\d+)$', 'ferenda.docview.views.view',{'module':'sfs'}),
    (r'^(?P<displayid>NJA_\d{4}_s\.?_\d+)$', 'ferenda.docview.views.view',{'module':'dv'}),
    
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
