from django.conf import settings as django_settings
from django.shortcuts import render
from askbot.utils.analytics_utils import get_analytics_default_segment_config

def analytics_index(request):
    """analytics home page"""
    if django_settings.ASKBOT_ANALYTICS_NAMED_SEGMENTS:
        users_segment = 'all-users'
    else:
        users_segment = get_analytics_default_segment_config()['slug']
    return render(request, 'analytics/index.html', {'users_segment': users_segment})

