"""
Settings for reputation changes that apply to 
user in response to various actions by the same
users or others
"""
from askbot.conf.settings_wrapper import settings
from askbot.conf.super_groups import REP_AND_BADGES
from askbot.deps.livesettings import ConfigurationGroup, IntegerValue
from django.utils.translation import ugettext as _

BADGES = ConfigurationGroup(
                    'BADGES',
                    _('Badge settings'),
                    ordering=2,
                    super_group = REP_AND_BADGES
                )

settings.register(
    IntegerValue(
        BADGES,
        'DISCIPLINED_BADGE_MIN_UPVOTES',
        default=3,
        description=_('Disciplined: minimum upvotes for deleted post')
    )
)

settings.register(
    IntegerValue(
        BADGES,
        'PEER_PRESSURE_BADGE_MIN_DOWNVOTES',
        default=3,
        description=_('Peer Pressure: minimum downvotes for deleted post')
    )
)

settings.register(
    IntegerValue(
        BADGES,
        'TEACHER_BADGE_MIN_UPVOTES',
        default=1,
        description=_('Teacher: minimum upvotes for the answer')
    )
)

settings.register(
    IntegerValue(
        BADGES,
        'NICE_ANSWER_BADGE_MIN_UPVOTES',
        default=2,
        description=_('Nice Answer: minimum upvotes for the answer')
    )
)

settings.register(
    IntegerValue(
        BADGES,
        'GOOD_ANSWER_BADGE_MIN_UPVOTES',
        default=3,
        description=_('Good Answer: minimum upvotes for the answer')
    )
)

settings.register(
    IntegerValue(
        BADGES,
        'GREAT_ANSWER_BADGE_MIN_UPVOTES',
        default=5,
        description=_('Great Answer: minimum upvotes for the answer')
    )
)

settings.register(
    IntegerValue(
        BADGES,
        'NICE_QUESTION_BADGE_MIN_UPVOTES',
        default=2,
        description=_('Nice Question: minimum upvotes for the question')
    )
)

settings.register(
    IntegerValue(
        BADGES,
        'GOOD_QUESTION_BADGE_MIN_UPVOTES',
        default=3,
        description=_('Good Question: minimum upvotes for the question')
    )
)

settings.register(
    IntegerValue(
        BADGES,
        'GREAT_QUESTION_BADGE_MIN_UPVOTES',
        default=5,
        description=_('Great Question: minimum upvotes for the question')
    )
)

settings.register(
    IntegerValue(
        BADGES,
        'POPULAR_QUESTION_BADGE_MIN_VIEWS',
        default=150,
        description=_('Popular Question: minimum views')
    )
)

settings.register(
    IntegerValue(
        BADGES,
        'NOTABLE_QUESTION_BADGE_MIN_VIEWS',
        default=250,
        description=_('Notable Question: minimum views')
    )
)

settings.register(
    IntegerValue(
        BADGES,
        'FAMOUS_QUESTION_BADGE_MIN_VIEWS',
        default=500,
        description=_('Famous Question: minimum views')
    )
)

settings.register(
    IntegerValue(
        BADGES,
        'SELF_LEARNER_BADGE_MIN_UPVOTES',
        default=1,
        description=_('Self-Learner: minimum answer upvotes')
    )
)

settings.register(
    IntegerValue(
        BADGES,
        'CIVIC_DUTY_BADGE_MIN_VOTES',
        default=100,
        description=_('Civic Duty: minimum votes')
    )
)

settings.register(
    IntegerValue(
        BADGES,
        'ENLIGHTENED_BADGE_MIN_UPVOTES',
        default=3,
        description=_('Enlightened Duty: minimum upvotes')
    )
)

settings.register(
    IntegerValue(
        BADGES,
        'GURU_BADGE_MIN_UPVOTES',
        default=5,
        description=_('Guru: minimum upvotes')
    )
)

settings.register(
    IntegerValue(
        BADGES,
        'NECROMANCER_BADGE_MIN_UPVOTES',
        default=1,
        description=_('Necromancer: minimum upvotes')
    )
)

settings.register(
    IntegerValue(
        BADGES,
        'NECROMANCER_BADGE_MIN_DELAY',
        default=30,
        description=_('Necromancer: minimum delay in days')
    )
)

settings.register(
    IntegerValue(
        BADGES,
        'ASSOCIATE_EDITOR_BADGE_MIN_EDITS',
        default=20,
        description=_('Associate Editor: minimum number of edits')
    )
)

settings.register(
    IntegerValue(
        BADGES,
        'FAVORITE_QUESTION_BADGE_MIN_STARS',
        default=3,
        description=_('Favorite Question: minimum stars')
    )
)

settings.register(
    IntegerValue(
        BADGES,
        'STELLAR_QUESTION_BADGE_MIN_STARS',
        default=5,
        description=_('Stellar Question: minimum stars')
    )
)

settings.register(
    IntegerValue(
        BADGES,
        'COMMENTATOR_BADGE_MIN_COMMENTS',
        default=10,
        description=_('Commentator: minimum comments')
    )
)

settings.register(
    IntegerValue(
        BADGES,
        'TAXONOMIST_BADGE_MIN_USE_COUNT',
        default = 10,
        description = _('Taxonomist: minimum tag use count')
    )
)

settings.register(
    IntegerValue(
        BADGES,
        'ENTHUSIAST_BADGE_MIN_DAYS',
        default = 30,
        description = _('Enthusiast: minimum days')
    )
)
