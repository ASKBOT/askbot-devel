"""
Settings for making the reputation and badge systems visible to 
the users at a different degree
"""
from django.utils.translation import ugettext as _
from askbot.conf.settings_wrapper import settings
from askbot.deps import livesettings
from askbot.conf.super_groups import REP_AND_BADGES

REPUTATION_AND_BADGE_VISIBILITY = livesettings.ConfigurationGroup(
                    'REPUTATION_AND_BADGE_VISIBILITY',
                    _('Reputation & Badge visibility'),
                    super_group = REP_AND_BADGES
                )


settings.register(
    livesettings.StringValue(
        REPUTATION_AND_BADGE_VISIBILITY,
        'REPUTATION_MODE',
        default = 'public',
        choices = (
            ('public', 'show publicly'),
            ('private', 'show to owners only'),
            ('hidden', 'hide completely'),
        ),#todo: later implement hidden mode
        description = _("Visibility of reputation"),
        clear_cache = True,
        help_text = _(
            "User's reputation may be shown publicly or only to the owners"
        )
    )
)

settings.register(
    livesettings.StringValue(
        REPUTATION_AND_BADGE_VISIBILITY,
        'BADGES_MODE',
        default = 'public',
        choices = (
            ('public', 'show publicly'),
            ('hidden', 'hide completely')
        ),#todo: later implement private mode
        description = _("Visibility of badges"),
        clear_cache = True,
        help_text = _(
            'Badges can be either publicly shown or completely hidden'
        )
    )
)
