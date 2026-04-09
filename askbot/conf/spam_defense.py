"""Livesettings for the spam defense system (Bayesian filter + first-post confirmation)."""
from django.utils.translation import gettext_lazy as _
from livesettings import values as livesettings
from askbot.conf.settings_wrapper import settings
from askbot.conf.super_groups import EXTERNAL_SERVICES

SPAM_DEFENSE = livesettings.ConfigurationGroup(
    'SPAM_DEFENSE',
    _('Spam defense settings'),
    super_group=EXTERNAL_SERVICES
)

settings.register(
    livesettings.BooleanValue(
        SPAM_DEFENSE,
        'FIRST_POST_EMAIL_CONFIRMATION',
        description=_('Require email confirmation for first post'),
        help_text=_(
            'When enabled, watched users must confirm their first post '
            'via an email link before it goes live.'
        ),
        default=False
    )
)

settings.register(
    livesettings.BooleanValue(
        SPAM_DEFENSE,
        'FIRST_POST_MODERATE_AFTER_CONFIRMATION',
        description=_('Require moderator approval after email confirmation'),
        help_text=_(
            'When enabled, first posts that pass email confirmation are '
            'placed in the moderator queue for approval. When disabled, '
            'confirmed posts go live immediately.'
        ),
        default=True
    )
)

settings.register(
    livesettings.BooleanValue(
        SPAM_DEFENSE,
        'DELETE_BLOCKED_USERS',
        description=_('Delete blocked spammer accounts entirely'),
        help_text=_(
            'When enabled, blocking a spammer deletes the user account '
            'along with all their content, preventing accumulation of '
            'dead accounts. When disabled, the account is kept with '
            'blocked status (original behavior).'
        ),
        default=True
    )
)

settings.register(
    livesettings.BooleanValue(
        SPAM_DEFENSE,
        'BAYESIAN_SPAM_SILENT_DELETE',
        description=_('Silently delete obvious spam from new users'),
        help_text=_(
            'When enabled, first posts that are flagged as spam (but not ham) '
            'result in silent deletion of the user and post.'
        ),
        default=False
    )
)
