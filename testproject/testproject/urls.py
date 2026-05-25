"""
main url configuration file for the askbot site
"""
from django.conf import settings
from django.conf.urls import handler404
from django.contrib import admin
from django.urls import include, re_path as url
from django.views import static as StaticViews

from askbot import is_multilingual
from askbot.views.error import internal_error as handler500

admin.autodiscover()

if is_multilingual():
    from django.conf.urls.i18n import i18n_patterns
    urlpatterns = i18n_patterns(
        url(r'%s' % settings.ASKBOT_URL, include('askbot.urls'))
    )
else:
    urlpatterns = [
        url(r'%s' % settings.ASKBOT_URL, include('askbot.urls'))
    ]

urlpatterns += [
    url(r'^admin/', admin.site.urls),
    #(r'^cache/', include('keyedcache.urls')), - broken views disable for now
    #(r'^settings/', include('askbot.deps.livesettings.urls')),
    url(r'^followit/', include('followit.urls')),
    url(r'^tinymce/', include('tinymce.urls')),
    url( # TODO: replace with django.conf.urls.static ?
        r'^%s(?P<path>.*)$' % settings.MEDIA_URL[1:],
        StaticViews.serve,
        {'document_root': settings.MEDIA_ROOT.replace('\\','/')},
    )
]

handler500 = 'askbot.views.error.internal_error'
