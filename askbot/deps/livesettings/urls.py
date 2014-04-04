from django.conf.urls import *

urlpatterns = patterns('askbot.deps.livesettings.views',
    url(r'^$', 'site_settings', {}, name='site_settings'),
    url(r'^export/$', 'export_as_python', {}, name='settings_export'),
    url(r'^(?P<group>[^/]+)/$', 'group_settings', name='group_settings'),
)
