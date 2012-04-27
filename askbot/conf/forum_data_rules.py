"""
Settings for askbot data display and entry
"""
from askbot.conf.settings_wrapper import settings
from askbot.deps import livesettings
from askbot import const
from askbot.conf.super_groups import DATA_AND_FORMATTING
from django.utils.translation import ugettext as _

FORUM_DATA_RULES = livesettings.ConfigurationGroup(
                        'FORUM_DATA_RULES',
                        _('Data entry and display rules'),
                        super_group = DATA_AND_FORMATTING
                    )

settings.register(
    livesettings.BooleanValue(
        FORUM_DATA_RULES,
        'ENABLE_VIDEO_EMBEDDING',
        default = False,
        description = _('Enable embedding videos. '),
        help_text = _(
            '<em>Note: please read <a href="%(url)s">read this</a> first.</em>'
        ) % {'url': const.DEPENDENCY_URLS['embedding-video']}
    )
)

settings.register(
    livesettings.BooleanValue(
        FORUM_DATA_RULES,
        'WIKI_ON',
        default = True,
        description = _('Check to enable community wiki feature')
    )
)

settings.register(
    livesettings.BooleanValue(
        FORUM_DATA_RULES,
        'ALLOW_ASK_ANONYMOUSLY',
        default=True,
        description=_('Allow asking questions anonymously'),
        help_text=_(
            'Users do not accrue reputation for anonymous questions '
            'and their identity is not revealed until they change their '
            'mind'
        )
    )
)

settings.register(
    livesettings.BooleanValue(
        FORUM_DATA_RULES,
        'ALLOW_POSTING_BEFORE_LOGGING_IN',
        default = True,
        description = _('Allow posting before logging in'),
        help_text = _(
            'Check if you want to allow users start posting questions '
            'or answers before logging in. '
            'Enabling this may require adjustments in the '
            'user login system to check for pending posts '
            'every time the user logs in. The builtin Askbot login system '
            'supports this feature.'
        )
    )
)

settings.register(
    livesettings.BooleanValue(
        FORUM_DATA_RULES,
        'ALLOW_SWAPPING_QUESTION_WITH_ANSWER',
        default = False,
        description = _('Allow swapping answer with question'),
        help_text = _(
            'This setting will help import data from other forums '
            'such as zendesk, when automatic '
            'data import fails to detect the original question correctly.'
        )
    )
)

settings.register(
    livesettings.IntegerValue(
        FORUM_DATA_RULES,
        'MAX_TAG_LENGTH',
        default=20,
        description=_('Maximum length of tag (number of characters)')
    )
)

settings.register(
    livesettings.IntegerValue(
        FORUM_DATA_RULES,
        'MIN_TITLE_LENGTH',
        default=10,
        description=_('Minimum length of title (number of characters)')
    )
)

settings.register(
    livesettings.IntegerValue(
        FORUM_DATA_RULES,
        'MIN_QUESTION_BODY_LENGTH',
        default=10,
        description=_(
            'Minimum length of question body (number of characters)'
        )
    )
)

settings.register(
    livesettings.IntegerValue(
        FORUM_DATA_RULES,
        'MIN_ANSWER_BODY_LENGTH',
        default=10,
        description=_(
            'Minimum length of answer body (number of characters)'
        )
    )
)

settings.register(
    livesettings.BooleanValue(
        FORUM_DATA_RULES,
        'TAGS_ARE_REQUIRED',
        description = _('Are tags required?'),
        default = False,
    )
)

settings.register(
    livesettings.StringValue(
        FORUM_DATA_RULES,
        'MANDATORY_TAGS',
        description = _('Mandatory tags'),
        default = '',
        help_text = _(
            'At least one of these tags will be required for any new '
            'or newly edited question. A mandatory tag may be wildcard, '
            'if the wildcard tags are active.'
        )
    )
)

settings.register(
    livesettings.BooleanValue(
        FORUM_DATA_RULES,
        'FORCE_LOWERCASE_TAGS',
        default = False,
        description = _('Force lowercase the tags'),
        help_text = _(
            'Attention: after checking this, please back up the database, '
            'and run a management command: '
            '<code>python manage.py fix_question_tags</code> to globally '
            'rename the tags'
         )
    )
)

settings.register(
    livesettings.StringValue(
        FORUM_DATA_RULES,
        'TAG_LIST_FORMAT',
        default = 'list',
        choices=const.TAG_LIST_FORMAT_CHOICES,
        description = _('Format of tag list'),
        help_text = _(
                        'Select the format to show tags in, '
                        'either as a simple list, or as a '
                        'tag cloud'
                     )
    )
)

settings.register(
    livesettings.BooleanValue(
        FORUM_DATA_RULES,
        'USE_WILDCARD_TAGS',
        default = False,
        description = _('Use wildcard tags'),
        help_text = _(
                        'Wildcard tags can be used to follow or ignore '
                        'many tags at once, a valid wildcard tag has a single '
                        'wildcard at the very end'
                    )
    )
)

settings.register(
    livesettings.IntegerValue(
        FORUM_DATA_RULES,
        'MAX_COMMENTS_TO_SHOW',
        default=5,
        description=_(
            'Default max number of comments to display under posts'
        )
    )
)

settings.register(
    livesettings.IntegerValue(
        FORUM_DATA_RULES,
        'MAX_COMMENT_LENGTH',
        default=300,
        description=_(
                'Maximum comment length, must be < %(max_len)s'
            ) % {'max_len': const.COMMENT_HARD_MAX_LENGTH }
    )
)

settings.register(
    livesettings.BooleanValue(
        FORUM_DATA_RULES,
        'USE_TIME_LIMIT_TO_EDIT_COMMENT',
        default = True,
        description = _('Limit time to edit comments'),
        help_text = _(
                        'If unchecked, there will be no time '
                        'limit to edit the comments'
                    )
    )
)

settings.register(
    livesettings.IntegerValue(
        FORUM_DATA_RULES,
        'MINUTES_TO_EDIT_COMMENT',
        default = 10,
        description = _('Minutes allowed to edit a comment'),
        help_text = _('To enable this setting, check the previous one')
    )
)

settings.register(
    livesettings.BooleanValue(
        FORUM_DATA_RULES,
        'SAVE_COMMENT_ON_ENTER',
        default = True,
        description = _('Save comment by pressing <Enter> key')
    )
)

settings.register(
    livesettings.IntegerValue(
        FORUM_DATA_RULES,
        'MIN_SEARCH_WORD_LENGTH',
        default=4,
        description=_('Minimum length of search term for Ajax search'),
        help_text=_('Must match the corresponding database backend setting'),
    )
)

settings.register(
    livesettings.BooleanValue(
        FORUM_DATA_RULES,
        'DECOUPLE_TEXT_QUERY_FROM_SEARCH_STATE',
        default=False,
        description=_('Do not make text query sticky in search'),
        help_text=_(
            'Check to disable the "sticky" behavior of the search query. '
            'This may be useful if you want to move the search bar away '
            'from the default position or do not like the default '
            'sticky behavior of the text search query.'
        )
    )
)

settings.register(
    livesettings.IntegerValue(
        FORUM_DATA_RULES,
        'MAX_TAGS_PER_POST',
        default=5,
        description=_('Maximum number of tags per question')
    )
)

#todo: looks like there is a bug in askbot.deps.livesettings 
#that does not allow Integer values with defaults and choices
settings.register(
    livesettings.StringValue(
        FORUM_DATA_RULES,
        'DEFAULT_QUESTIONS_PAGE_SIZE',
        choices=const.PAGE_SIZE_CHOICES,
        default='30',
        description=_('Number of questions to list by default')
    )
)

settings.register(
    livesettings.StringValue(
        FORUM_DATA_RULES,
        'UNANSWERED_QUESTION_MEANING',
        choices=const.UNANSWERED_QUESTION_MEANING_CHOICES,
        default='NO_ACCEPTED_ANSWERS',
        description=_('What should "unanswered question" mean?')
    )
)
