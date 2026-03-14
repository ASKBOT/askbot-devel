"""
:synopsis: django view functions for the askbot project
"""
from askbot.views.analytics import analytics_users
from askbot.views.analytics import analytics_activity
from askbot.views.analytics import analytics_home
from askbot.views import api_v1
from askbot.views import commands
from askbot.views import emails
from askbot.views import meta
from askbot.views import moderation
from askbot.views import readers
from askbot.views import sharing
from askbot.views import users
from askbot.views import writers
from django.conf import settings as django_settings
if 'avatar' in django_settings.INSTALLED_APPS:
    from askbot.views import avatar_views
