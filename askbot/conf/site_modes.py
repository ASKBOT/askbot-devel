"""
Site modes settings:
    Support for site modes currently supports
    Bootstrap - for sites that are starting and
    Default - for sites that already have a momentum.
"""
from askbot.conf.settings_wrapper import settings
from askbot.conf.super_groups import REP_AND_BADGES
from askbot.deps.livesettings import ConfigurationGroup
from askbot.deps.livesettings import BooleanValue
from django.utils.translation import ugettext_lazy as _

LARGE_SITE_MODE_SETTINGS = {
    #minimum reputation settins.
    'MIN_REP_TO_VOTE_UP': 15,
    'MIN_REP_TO_VOTE_DOWN': 100,
    'MIN_REP_TO_ANSWER_OWN_QUESTION': 25,
    'MIN_REP_TO_ACCEPT_OWN_ANSWER': 50,
    'MIN_REP_TO_FLAG_OFFENSIVE': 15,
    #'MIN_REP_TO_LEAVE_COMMENTS': 50,
    'MIN_REP_TO_DELETE_OTHERS_COMMENTS': 2000,
    'MIN_REP_TO_DELETE_OTHERS_POSTS': 5000,
    'MIN_REP_TO_UPLOAD_FILES': 60,
    'MIN_REP_TO_RETAG_OTHERS_QUESTIONS': 500,
    'MIN_REP_TO_EDIT_WIKI': 750,
    'MIN_REP_TO_EDIT_OTHERS_POSTS': 2000,
    'MIN_REP_TO_VIEW_OFFENSIVE_FLAGS': 2000,
    'MIN_REP_TO_CLOSE_OTHERS_QUESTIONS': 2000,
    'MIN_REP_TO_HAVE_STRONG_URL': 250,
    #badge settings
    'NOTABLE_QUESTION_BADGE_MIN_VIEWS': 250,
    'POPULAR_QUESTION_BADGE_MIN_VIEWS': 150,
    'FAMOUS_QUESTION_BADGE_MIN_VIEWS': 500,
    'ENTHUSIAST_BADGE_MIN_DAYS': 30,
    'TAXONOMIST_BADGE_MIN_USE_COUNT': 10,
    #moderation rule settings
    'MIN_FLAGS_TO_HIDE_POST': 3,
    'MIN_FLAGS_TO_DELETE_POST': 5,
}

def bootstrap_callback(current_value, new_value):
    '''Callback to update settings'''

    if current_value == new_value:
        #do not overwrite settings in case that tha value
        #is the same
        return new_value

    if new_value == True:
        for key, value in LARGE_SITE_MODE_SETTINGS.items():
            settings.update(key, value)

    else:
        for key in LARGE_SITE_MODE_SETTINGS:
            settings.reset(key)

    return new_value


SITE_MODES = ConfigurationGroup(
                    'SITE_MODES',
                    _('Bootstrap mode'),
                    super_group = REP_AND_BADGES
                )

settings.register(
    BooleanValue(
        SITE_MODES,
        'ACTIVATE_LARGE_SITE_MODE',
        default=False,
        description=_(
            'Activate a "Large site" mode'),
        help_text=_(
            "\"Large site\" mode increases reputation and certain badge "
            "thresholds, to values, more suitable "
            "for the larger communities, "
            "<strong>WARNING:</strong> your current values for "
            "Minimum reputation, "
            "Badge Settings and "
            "Vote Rules will "
            "be changed after you modify this setting."
        ),
        update_callback = bootstrap_callback
    )
)
