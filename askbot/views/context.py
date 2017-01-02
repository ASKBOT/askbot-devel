"""functions, preparing parts of context for
the templates in the various views"""
from django.conf import settings as django_settings
import simplejson
from django.utils.translation import ugettext as _
from askbot.conf import settings as askbot_settings
from askbot import const
from askbot.const import message_keys as msg
from askbot.models import GroupMembership
from askbot.utils.loading import load_module

def get_for_tag_editor():
    #data for the tag editor
    data = {
        'tag_forbidden_first_chars': const.TAG_FORBIDDEN_FIRST_CHARS,
        'tags_are_required': askbot_settings.TAGS_ARE_REQUIRED,
        'max_tags_per_post': askbot_settings.MAX_TAGS_PER_POST,
        'max_tag_length': askbot_settings.MAX_TAG_LENGTH,
        'force_lowercase_tags': askbot_settings.FORCE_LOWERCASE_TAGS,
        'messages': {
            'required': _(msg.TAGS_ARE_REQUIRED_MESSAGE),
            'wrong_chars': _(msg.TAG_WRONG_CHARS_MESSAGE),
            'wrong_first_char': _(msg.TAG_WRONG_FIRST_CHAR_MESSAGE),
        }
    }
    return {'tag_editor_settings': simplejson.dumps(data)}

def get_for_inbox(user):
    """adds response counts of various types"""
    if user.is_anonymous():
        return None

    #get flags count
    flag_activity_types = (
        const.TYPE_ACTIVITY_MARK_OFFENSIVE,
        const.TYPE_ACTIVITY_MODERATED_NEW_POST,
        const.TYPE_ACTIVITY_MODERATED_POST_EDIT
    )

    #get group_join_requests_count
    group_join_requests_count = 0
    if user.is_administrator_or_moderator():
        pending_memberships = GroupMembership.objects.filter(
                                            group__in=user.get_groups(),
                                            level=GroupMembership.PENDING
                                        )
        group_join_requests_count = pending_memberships.count()

    re_count = user.new_response_count + user.seen_response_count
    return {
        're_count': re_count,
        'group_join_requests_count': group_join_requests_count,
        'need_inbox_sections_nav': int(re_count > 0) + int(group_join_requests_count) > 1
    }

def get_extra(context_module_setting, request, data):
    extra_context = getattr(django_settings, context_module_setting, None)
    if extra_context:
        extra_context_getter = load_module(extra_context)
        return extra_context_getter(request, data)
    return {}
