from django.conf.urls.defaults import *

urlpatterns = patterns(
    '',
    # Uncomment this for admin:
    (r'^static/(.*)$', 'django.views.static.serve', {'document_root': '/Users/staffan/svn-wd/ferenda/static'}),
    (r'^admin/', include('django.contrib.admin.urls')),
    (r'^(?P<displayid>\d{4}:\d+)$', 'ferenda.docview.views.view'),
    (r'^NJA_(?P<nja_year>\d{4})_s_(?P<nja_page>\d+)$', 'ferenda.docview.views.njadisplay'),
    (r'^edit/(?P<art_title>.*)$', 'ferenda.wiki.views.edit'),
    (r'^save/(?P<art_title>.*)$', 'ferenda.wiki.views.save'),
    (r'^(?P<art_title>.*)$', 'ferenda.wiki.views.article')
)
