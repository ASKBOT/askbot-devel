from django.conf import settings as django_settings

def is_named_segment(segment_slug):
    """True, if segment_slug is in the slugs of any of the named segments"""
    conf_items = django_settings.ASKBOT_ANALYTICS_NAMED_SEGMENTS
    return any(segment_slug == item['slug'] for item in conf_items)


def get_all_named_segment_group_ids():
    """Returns a list of group_ids for all named segments"""
    named_segment_configs = django_settings.ASKBOT_ANALYTICS_NAMED_SEGMENTS
    group_ids = []
    for segment_config in named_segment_configs:
        group_ids.extend(segment_config['group_ids'])
    return group_ids


def get_named_segment_config_by_slug(segment_slug):
    """Returns a list of group_ids for a named segment"""
    named_segment_configs = django_settings.ASKBOT_ANALYTICS_NAMED_SEGMENTS
    for segment_config in named_segment_configs:
        if segment_config['slug'] == segment_slug:
            return segment_config
    return None


def get_named_segment_config_by_group_id(group_id):
    """Returns the named segment config for a given group_id or None"""
    named_segment_configs = django_settings.ASKBOT_ANALYTICS_NAMED_SEGMENTS
    for segment_config in named_segment_configs:
        if group_id in segment_config['group_ids']:
            return segment_config
    return None

def get_segment_name(segment_slug):
    """Returns the name of the segment"""
    segment_config = get_named_segment_config_by_slug(segment_slug)
    if segment_config:
        return segment_config['name']
    default_segment_config = django_settings.ASKBOT_ANALYTICS_DEFAULT_SEGMENT
    if segment_slug == default_segment_config['slug']:
        return default_segment_config['name']
    return None