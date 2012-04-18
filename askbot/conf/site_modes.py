"""
Site modes settings:
    Support for site modes currently supports
    Bootstrap - for sites that are starting and
    Default - for sites that already have a momentum.
"""
from askbot.conf.settings_wrapper import settings
from askbot.conf.super_groups import REP_AND_BADGES
from askbot.deps.livesettings import ConfigurationGroup, BooleanValue
from django.utils.translation import ugettext as _

BOOTSTRAP_MODE_SETTINGS = {
    #minimum reputation settins.
    'MIN_REP_TO_VOTE_UP': 5,
    'MIN_REP_TO_VOTE_DOWN': 50,
    'MIN_REP_TO_ANSWER_OWN_QUESTION': 5,
    'MIN_REP_TO_ACCEPT_OWN_ANSWER': 20,
    'MIN_REP_TO_FLAG_OFFENSIVE': 5,
    'MIN_REP_TO_LEAVE_COMMENTS': 10,
    'MIN_REP_TO_DELETE_OTHERS_COMMENTS': 200,
    'MIN_REP_TO_DELETE_OTHERS_POSTS': 500,
    'MIN_REP_TO_UPLOAD_FILES': 10,
    'MIN_REP_TO_CLOSE_OWN_QUESTIONS': 25,
    'MIN_REP_TO_RETAG_OTHERS_QUESTIONS': 50,
    'MIN_REP_TO_REOPEN_OWN_QUESTIONS': 50,
    'MIN_REP_TO_EDIT_WIKI': 75,
    'MIN_REP_TO_EDIT_OTHERS_POSTS': 200,
    'MIN_REP_TO_VIEW_OFFENSIVE_FLAGS': 200,
    'MIN_REP_TO_CLOSE_OTHERS_QUESTIONS': 200,
    'MIN_REP_TO_LOCK_POSTS': 400,
    'MIN_REP_TO_HAVE_STRONG_URL': 25,
    #badge settings
    'NOTABLE_QUESTION_BADGE_MIN_VIEWS': 25,
    'POPULAR_QUESTION_BADGE_MIN_VIEWS': 15,
    'FAMOUS_QUESTION_BADGE_MIN_VIEWS': 50,
    'ENTHUSIAST_BADGE_MIN_DAYS': 5,
    'TAXONOMIST_BADGE_MIN_USE_COUNT': 5,
    #moderation rule settings
    'MIN_FLAGS_TO_HIDE_POST': 2,
    'MIN_FLAGS_TO_DELETE_POST': 3,
}

def bootstrap_callback(current_value, new_value):
    '''Callback to update settings'''

    if current_value == new_value:
        #do not overwrite settings in case that tha value 
        #is the same
        return new_value

    if new_value == True:
        for key, value in BOOTSTRAP_MODE_SETTINGS.items():
            settings.update(key, value)

    else:
        for key in BOOTSTRAP_MODE_SETTINGS:
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
        'ACTIVATE_BOOTSTRAP_MODE',
        default=False,
        description=_(
            'Activate a "Bootstrap" mode'),
        help_text=_(
            "Bootstrap mode lowers reputation and certain badge "
            "thresholds, to values, more suitable "
            "for the smaller communities, "
            "<strong>WARNING:</strong> your current value for "
            "Minimum reputation, "
            "Bagde Settings and "
            "Vote Rules will "
            "be changed after you modify this setting."
        ),
        update_callback = bootstrap_callback
    )
)
