"""
Settings for reputation changes that apply to 
user in response to various actions by the same
users or others
"""
from askbot.conf.settings_wrapper import settings
from askbot.deps.livesettings import ConfigurationGroup, IntegerValue
from django.utils.translation import ugettext as _
from askbot.conf.super_groups import REP_AND_BADGES

REP_CHANGES = ConfigurationGroup(
                    'REP_CHANGES',
                    _('Karma loss and gain rules'),
                    super_group = REP_AND_BADGES,
                    ordering=2
                )

settings.register(
    IntegerValue(
        REP_CHANGES,
        'MAX_REP_GAIN_PER_USER_PER_DAY',
        default=200,
        description=_('Maximum daily reputation gain per user')
    )
)

settings.register(
    IntegerValue(
        REP_CHANGES,
        'REP_GAIN_FOR_RECEIVING_UPVOTE',
        default=10,
        description=_('Gain for receiving an upvote')
    )
)

settings.register(
    IntegerValue(
        REP_CHANGES,
        'REP_GAIN_FOR_RECEIVING_ANSWER_ACCEPTANCE',
        default=15,
        description=_('Gain for the author of accepted answer')
    )
)

settings.register(
    IntegerValue(
        REP_CHANGES,
        'REP_GAIN_FOR_ACCEPTING_ANSWER',
        default=2,
        description=_('Gain for accepting best answer')
    )
)

settings.register(
    IntegerValue(
        REP_CHANGES,
        'REP_GAIN_FOR_RECEIVING_DOWNVOTE_CANCELATION',
        default=2,
        description=_('Gain for post owner on canceled downvote')
    )
)

settings.register(
    IntegerValue(
        REP_CHANGES,
        'REP_GAIN_FOR_CANCELING_DOWNVOTE',
        default=1,
        description=_('Gain for voter on canceling downvote')
    )
)
#'gain_by_canceling_downvote', 

settings.register(
    IntegerValue(
        REP_CHANGES,
        'REP_LOSS_FOR_CANCELING_ANSWER_ACCEPTANCE',
        default=-2,
        description=_('Loss for voter for canceling of answer acceptance')
    )
)
#'lose_by_canceling_accepted_answer', 

settings.register(
    IntegerValue(
        REP_CHANGES,
        'REP_LOSS_FOR_RECEIVING_CANCELATION_OF_ANSWER_ACCEPTANCE',
        default=-5,
        description=_('Loss for author whose answer was "un-accepted"')
    )
)
#'lose_by_accepted_answer_cancled', 

settings.register(
    IntegerValue(
        REP_CHANGES,
        'REP_LOSS_FOR_DOWNVOTING',
        default=-2,
        description=_('Loss for giving a downvote')
    )
)
#'lose_by_downvoted', 

settings.register(
    IntegerValue(
        REP_CHANGES,
        'REP_LOSS_FOR_RECEIVING_FLAG',
        default=-2,
        description=_('Loss for owner of post that was flagged offensive')
    )
)
#'lose_by_flagged', 

settings.register(
    IntegerValue(
        REP_CHANGES,
        'REP_LOSS_FOR_RECEIVING_DOWNVOTE',
        default=-1,
        description=_('Loss for owner of post that was downvoted')
    )
)
#'lose_by_downvoting', 

settings.register(
    IntegerValue(
        REP_CHANGES,
        'REP_LOSS_FOR_RECEIVING_THREE_FLAGS_PER_REVISION',
        default=-30,
        description=_('Loss for owner of post that was flagged 3 times per same revision')
    )
)
#'lose_by_flagged_lastrevision_3_times', 

settings.register(
    IntegerValue(
        REP_CHANGES,
        'REP_LOSS_FOR_RECEIVING_FIVE_FLAGS_PER_REVISION',
        default=-100,
        description=_('Loss for owner of post that was flagged 5 times per same revision')
    )
)
#'lose_by_flagged_lastrevision_5_times', 

settings.register(
    IntegerValue(
        REP_CHANGES,
        'REP_LOSS_FOR_RECEIVING_UPVOTE_CANCELATION',
        default=-10,
        description=_('Loss for post owner when upvote is canceled')
    )
)
#'lose_by_upvote_canceled',
