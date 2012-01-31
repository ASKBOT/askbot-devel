"""
main url configuration file for the askbot site
"""
from django.conf.urls.defaults import patterns, include, handler404, handler500, url
from django.conf import settings

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    (r'%s' % settings.ASKBOT_URL, include('askbot.urls')),
    (r'^admin/', include(admin.site.urls)),
    #(r'^cache/', include('keyedcache.urls')), - broken views disable for now
    (r'^settings/', include('askbot.deps.livesettings.urls')),
    (r'^followit/', include('followit.urls')),
    (r'^robots.txt$', include('robots.urls')),
    url(r'^analytics/', 'djchart.views.site_analytics', name='site_analytics'),
    url(r'^chart/(?P<chart_pk>\d+)/data.json', 'djchart.views.chart_data',
		name='chart_data'),
    url( # TODO: replace with django.conf.urls.static ?
        r'^%s(?P<path>.*)$' % settings.MEDIA_URL[1:], 
        'django.views.static.serve',
        {'document_root': settings.MEDIA_ROOT.replace('\\','/')},
    ),
)

if 'rosetta' in settings.INSTALLED_APPS:
    urlpatterns += patterns('',
                    url(r'^rosetta/', include('rosetta.urls')),
                )
