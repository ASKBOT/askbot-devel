"""
Utilities for use in the analytics views
"""
from django.urls import reverse
from django.conf import settings as django_settings
from django.contrib.contenttypes.models import ContentType
from askbot.models import Post
from askbot.models.user import Group as AskbotGroup

def get_named_segment_group_ids():
    """Returns the list of group ids for named segments"""
    named_segments_config = django_settings.ASKBOT_ANALYTICS_NAMED_SEGMENTS
    group_ids = []
    for named_segment in named_segments_config:
        group_ids.extend(named_segment['group_ids'])
    return group_ids


def filter_events_by_users_segment(events, users_segment):
    """Filters events by users segment"""
    if users_segment == 'all-users':
        return events

    if users_segment.startswith('group:'):
        group_id = int(users_segment.split(':')[1])
        return events.filter(session__user__groups__id__in=[group_id])
    if users_segment.startswith('user:'):
        user_id = int(users_segment.split(':')[1])
        return events.filter(session__user__id=user_id)

    default_segment_slug = django_settings.ASKBOT_ANALYTICS_DEFAULT_SEGMENT['slug']
    if users_segment == default_segment_slug:
        # default segment is all groups used for analytics except named segments
        group_ids = get_named_segment_group_ids()
        groups = AskbotGroup.objects.filter(used_for_analytics=True).exclude(id__in=group_ids)
        return events.filter(session__user__groups__in=groups)

    named_segment_configs = django_settings.ASKBOT_ANALYTICS_NAMED_SEGMENTS
    for named_segment_config in named_segment_configs:
        if named_segment_config['slug'] == users_segment:
            group_ids = named_segment_config['group_ids']
            return events.filter(session__user__groups__in=group_ids)

    return events


def filter_events_by_content_segment(events, content_segment):
    """Filters events by content segment"""
    if content_segment.startswith('thread:'):
        thread_id = int(content_segment.split(':')[1])
        # get all post ids for the thread
        post_ids = Post.objects.filter(thread_id=thread_id).values_list('id', flat=True)
        post_content_type = ContentType.objects.get_for_model(Post)
        return events.filter(object_id__in=post_ids, content_type=post_content_type)

    if content_segment.startswith('post:'):
        post_id = int(content_segment.split(':')[1])
        post_content_type = ContentType.objects.get_for_model(Post)
        return events.filter(object_id=post_id, content_type=post_content_type)

    assert content_segment == 'all-content'
    return events


def get_named_segment_slug(group_id):
    """Returns the slug for a named segment"""
    named_segments_config = django_settings.ASKBOT_ANALYTICS_NAMED_SEGMENTS
    for named_segment_config in named_segments_config:
        if group_id in named_segment_config['group_ids']:
            return named_segment_config['slug']
    return None


def get_date_selector_url_func(view_name, **fixed_params):
    """
    Returns a function that will generate a URL for the given view name,
    with all parameters in fixed_params bound, except for the dates parameter.
    """
    def date_selector_url_func(dates):
        """
        Generates a URL with the given dates and all other parameters
        from the outer function.
        """
        params = fixed_params.copy()
        params['dates'] = dates
        return reverse(view_name, kwargs=params)
        
    return date_selector_url_func