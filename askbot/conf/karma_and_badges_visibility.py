"""
Settings for making the karma and badge systems visible to
the users at a different degree
"""
from django.utils.translation import ugettext_lazy as _
from askbot.conf.settings_wrapper import settings
from askbot.deps import livesettings
from askbot.conf.super_groups import REP_AND_BADGES

KARMA_AND_BADGE_VISIBILITY = livesettings.ConfigurationGroup(
    'KARMA_AND_BADGE_VISIBILITY',
    _('Karma & Badge visibility'),
    super_group=REP_AND_BADGES
)


settings.register(
    livesettings.StringValue(
        KARMA_AND_BADGE_VISIBILITY,
        'KARMA_MODE',
        default='public',
        choices=(
            ('public', 'show publicly'),
            ('private', 'show to owners only'),
            ('hidden', 'hide completely'),
        ),  # TODO: Later implement hidden mode
        description=_("Visibility of karma"),
        clear_cache=True,
        help_text=_(
            "User's karma may be shown publicly or only to the owners"
        )
    )
)

settings.register(
    livesettings.StringValue(
        KARMA_AND_BADGE_VISIBILITY,
        'BADGES_MODE',
        default='public',
        choices=(
            ('public', 'show publicly'),
            ('hidden', 'hide completely')
        ),  # TODO: Later implement private mode
        description=_("Visibility of badges"),
        clear_cache=True,
        help_text=_('Badges can be either publicly shown or completely hidden')
    )
)
