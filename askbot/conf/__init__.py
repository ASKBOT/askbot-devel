#import these to compile code and install values
import askbot
import askbot.conf.minimum_reputation
import askbot.conf.vote_rules
import askbot.conf.reputation_changes
import askbot.conf.email
import askbot.conf.forum_data_rules
import askbot.conf.flatpages
import askbot.conf.site_settings
import askbot.conf.license
import askbot.conf.external_keys
import askbot.conf.skin_general_settings
import askbot.conf.sidebar_main
import askbot.conf.sidebar_question
import askbot.conf.sidebar_profile
import askbot.conf.spam_and_moderation
import askbot.conf.user_settings
import askbot.conf.markup
import askbot.conf.social_sharing
import askbot.conf.badges
import askbot.conf.login_providers
import askbot.conf.access_control
import askbot.conf.site_modes
import askbot.conf.widgets

#import main settings object
from askbot.conf.settings_wrapper import settings

from django.conf import settings as django_settings
def should_show_sort_by_relevance():
    """True if configuration support sorting
    questions by search relevance
    """
    return ('postgresql_psycopg2' in askbot.get_database_engine_name())
