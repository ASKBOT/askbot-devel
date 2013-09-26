#import these to compile code and install values
from askbot import const
import askbot
import askbot.conf.minimum_reputation
import askbot.conf.vote_rules
import askbot.conf.reputation_changes
import askbot.conf.karma_and_badges_visibility
import askbot.conf.email
import askbot.conf.forum_data_rules
import askbot.conf.moderation
import askbot.conf.question_lists
import askbot.conf.flatpages
import askbot.conf.site_settings
import askbot.conf.license
import askbot.conf.external_keys
import askbot.conf.ldap
import askbot.conf.skin_general_settings
import askbot.conf.sidebar_main
import askbot.conf.sidebar_question
import askbot.conf.sidebar_profile
import askbot.conf.leading_sidebar
import askbot.conf.spam_and_moderation
import askbot.conf.user_settings
import askbot.conf.group_settings
import askbot.conf.markup
import askbot.conf.social_sharing
import askbot.conf.badges
import askbot.conf.login_providers
import askbot.conf.access_control
import askbot.conf.site_modes
import askbot.conf.button_settings

#import main settings object
from askbot.conf.settings_wrapper import settings

from django.conf import settings as django_settings
def should_show_sort_by_relevance():
    """True if configuration support sorting
    questions by search relevance
    """
    return ('postgresql_psycopg2' in askbot.get_database_engine_name())

def get_tag_display_filter_strategy_choices():
    from askbot.conf import settings as askbot_settings
    if askbot_settings.SUBSCRIBED_TAG_SELECTOR_ENABLED:
        return const.TAG_DISPLAY_FILTER_STRATEGY_CHOICES
    else:
        return const.TAG_DISPLAY_FILTER_STRATEGY_MINIMAL_CHOICES

def get_tag_email_filter_strategy_choices():
    """returns the set of choices appropriate for the configuration"""
    from askbot.conf import settings as askbot_settings
    if askbot_settings.SUBSCRIBED_TAG_SELECTOR_ENABLED:
        return const.TAG_EMAIL_FILTER_ADVANCED_STRATEGY_CHOICES
    else:
        return const.TAG_EMAIL_FILTER_SIMPLE_STRATEGY_CHOICES
