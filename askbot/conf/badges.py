"""
Settings for reputation changes that apply to
user in response to various actions by the same
users or others
"""
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import string_concat

from askbot.conf.settings_wrapper import settings
from askbot.conf.super_groups import REP_AND_BADGES
from askbot.deps.livesettings import ConfigurationGroup
from askbot.deps.livesettings import IntegerValue
from askbot.deps.livesettings import BooleanValue

BADGES = ConfigurationGroup(
    'BADGES', _('Badge settings'), ordering=2, super_group=REP_AND_BADGES)


def register_badge_settings(badge_slug=None, badge_name=None, params=None):
    settings.register(
        BooleanValue(
            BADGES,
            badge_slug + '_BADGE_ENABLED',
            default=True,
            description=_('Enable "%s" badge') % badge_name
        )
    )
    if params is None:
        return

    for param_slug, param_data in params.items():
        param_description = param_data[0]
        param_default = param_data[1]
        settings.register(
            IntegerValue(
                BADGES,
                badge_slug + '_BADGE_' + param_slug,
                description=string_concat(badge_name, ': ', param_description),
                default=param_default)
        )

register_badge_settings(
    'ASSOCIATE_EDITOR',
    _('Associate Editor'),
    params={
        'MIN_EDITS': (_('minimum number of edits'), 20)
    }
)

register_badge_settings('AUTOBIOGRAPHER', _('Autobiographer'))

register_badge_settings('CITIZEN_PATROL', _('Citizen Patrol'))

register_badge_settings(
    'CIVIC_DUTY',
    _('Civic Duty'),
    params={
        'MIN_VOTES': (_('minimum votes'), 100)
    }
)

register_badge_settings('CLEANUP', _('Cleanup'))

register_badge_settings(
    'COMMENTATOR',
    _('Commentator'),
    params={
        'MIN_COMMENTS': (_('minimum comments'), 10)
    }
)

register_badge_settings('CRITIC', _('Critic'))

register_badge_settings(
    'DISCIPLINED',
    _('Disciplined'),
    params={
        'MIN_UPVOTES': (_('minimum upvotes for deleted post'), 3)
    }
)

register_badge_settings('EDITOR', _('Editor'))

register_badge_settings(
    'ENLIGHTENED',
    _('Enlightened Duty'),
    params={
        'MIN_UPVOTES': (_('minimum upvotes'), 3)
    }
)

register_badge_settings(
    'ENTHUSIAST',
    _('Enthusiast'),
    params={
        'MIN_DAYS': (_('minimum days'), 5)
    }
)

register_badge_settings('EXPERT', _('Expert'))

register_badge_settings(
    'FAMOUS_QUESTION',
    _('Famous Question'),
    params={
        'MIN_VIEWS': (_('minimum views'), 50)
    }
)

register_badge_settings(
    'FAVORITE_QUESTION',
    _('Favorite Question'),
    params={
        'MIN_STARS': (_('minimum followers'), 3)
    }
)

register_badge_settings(
    'GOOD_ANSWER',
    _('Good Answer'),
    params={
        'MIN_UPVOTES': (_('minimum upvotes for the answer'), 3)
    }
)

register_badge_settings(
    'GOOD_QUESTION',
    _('Good Question'),
    params={
        'MIN_UPVOTES': (_('minimum upvotes for the question'), 3)
    }
)

register_badge_settings(
    'GREAT_ANSWER',
    _('Great Answer'),
    params={
        'MIN_UPVOTES': (_('minimum upvotes for the answer'), 5)
    }
)

register_badge_settings(
    'GREAT_QUESTION',
    _('Great Question'),
    params={
        'MIN_UPVOTES': (_('minimum upvotes for the question'), 5)
    }
)

register_badge_settings(
    'GURU',
    _('Guru'),
    params={
        'MIN_UPVOTES': (_('minimum upvotes'), 5)
    }
)

register_badge_settings(
    'NECROMANCER',
    _('Necromancer'),
    params={
        'MIN_UPVOTES': (_('minimum upvotes'), 1),
        'MIN_DELAY': (_('minimum delay in days'), 30)
    }
)

register_badge_settings(
    'NICE_QUESTION',
    _('Nice Question'),
    params={
        'MIN_UPVOTES': (_('minimum upvotes for the question'), 2)
    }
)

register_badge_settings(
    'NICE_ANSWER',
    _('Nice Answer'),
    params={
        'MIN_UPVOTES': (_('minimum upvotes for the answer'), 2)
    }
)

register_badge_settings(
    'NOTABLE_QUESTION',
    _('Notable Question'),
    params={
        'MIN_VIEWS': (_('minimum views'), 25)
    }
)

register_badge_settings('ORGANIZER', _('Organizer'))

register_badge_settings(
    'PEER_PRESSURE',
    _('Peer pressure'),
    params={
        'MIN_DOWNVOTES': (_('minimum downvotes for deleted post'), 3)
    }
)

register_badge_settings(
    'POPULAR_QUESTION',
    _('Popular Question'),
    params={
        'MIN_VIEWS': (_('minimum views'), 15)
    }
)

register_badge_settings('PUNDIT', _('Pundit'))

register_badge_settings('SCHOLAR', _('Scholar'))

register_badge_settings(
    'SELF_LEARNER',
    _('Self-Learner'),
    params={
        'MIN_UPVOTES': (_('minimum answer upvotes'), 1)
    }
)

register_badge_settings(
    'STELLAR_QUESTION',
    _('Stellar Question'),
    params={
        'MIN_STARS': (_('minimum followers'), 5)
    }
)

register_badge_settings('STUDENT', _('Student'))

register_badge_settings('SUPPORTER', _('Supporter'))

register_badge_settings(
    'TAXONOMIST',
    _('Taxonomist'),
    params={
        'MIN_USE_COUNT': (_('minimum tag use count'), 5)
    }
)

register_badge_settings(
    'TEACHER',
    _('Teacher'),
    params={
        'MIN_UPVOTES': (_('minimum upvotes for the answer'), 1)
    }
)

register_badge_settings(
    'RAPID_RESPONDER',
    _('Rapid Responder'),
    params={
        'MAX_DELAY': (_('maximum delay in hours'), 48),
        'EXPIRES': (_('badge expiration in days'), 48),
    }
)

