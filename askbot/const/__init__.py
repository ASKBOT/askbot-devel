# encoding:utf-8
"""
All constants could be used in other modules
For reasons that models, views can't have unicode
text in this project, all unicode text go here.
"""
import os
import re
from django.utils.translation import gettext_lazy as _
from askbot import get_install_directory
#an exception import * because that file has only strings
from askbot.const.message_keys import * #pylint: disable=wildcard-import

DEFAULT_USER_DATA_EXPORT_DIR = os.path.abspath(
    os.path.join(get_install_directory(), '..', 'user_data'))

#todo: customize words
CLOSE_REASONS = (
    (1, _('duplicate question')),
    (2, _('question is off-topic or not relevant')),
    (3, _('too subjective and argumentative')),
    (4, _('not a real question')),
    (5, _('the question is answered, right answer was accepted')),
    (6, _('question is not relevant or outdated')),
    (7, _('question contains offensive or malicious remarks')),
    (8, _('spam or advertising')),
    (9, _('too localized')),
    (10, _('question is considered as answered')),
    (11, _('closed as inactive'))
)

LONG_TIME = 60*60*24*30 #30 days is a lot of time
DATETIME_FORMAT = '%I:%M %p, %d %b %Y'

SHARE_NOTHING = 0
SHARE_MY_POSTS = 1
SHARE_EVERYTHING = 2
SOCIAL_SHARING_MODE_CHOICES = (
    (SHARE_NOTHING, _('disable sharing')),
    (SHARE_MY_POSTS, _('my posts')),
    (SHARE_EVERYTHING, _('all posts'))
)

TYPE_REPUTATION = (
    (1, 'gain_by_upvoted'),
    (2, 'gain_by_answer_accepted'),
    (3, 'gain_by_accepting_answer'),
    (4, 'gain_by_downvote_canceled'),
    (5, 'gain_by_canceling_downvote'),
    (-1, 'lose_by_canceling_accepted_answer'),
    (-2, 'lose_by_accepted_answer_cancled'),
    (-3, 'lose_by_downvoted'),
    (-4, 'lose_by_flagged'),
    (-5, 'lose_by_downvoting'),
    (-6, 'lose_by_flagged_lastrevision_3_times'),
    (-7, 'lose_by_flagged_lastrevision_5_times'),
    (-8, 'lose_by_upvote_canceled'),
    #for reputation type 10 Repute.comment field is required
    (10, 'assigned_by_moderator'),
)

#do not translate keys
POST_SORT_METHODS = (
    ('age-desc', _('newest')),
    ('age-asc', _('oldest')),
    ('activity-desc', _('active')),
    ('activity-asc', _('inactive')),
    ('answers-desc', _('hottest')),
    ('answers-asc', _('coldest')),
    ('votes-desc', _('most voted')),
    ('votes-asc', _('least voted')),
    ('relevance-desc', _('relevance')),
)

POST_TYPES = ('answer', 'comment', 'question', 'tag_wiki', 'reject_reason')

SIMPLE_REPLY_SEPARATOR_TEMPLATE = '==== %s -=-=='

#values for SELF_NOTIFY_WHEN... settings use bits
NEVER = 'never'
FOR_FIRST_REVISION = 'first'
FOR_ANY_REVISION = 'any'
SELF_NOTIFY_EMAILED_POST_AUTHOR_WHEN_CHOICES = (
    (NEVER, _('Never')),
    (FOR_FIRST_REVISION, _('When new post is published')),
    (FOR_ANY_REVISION, _('When post is published or revised')),
)
#need more options for web posts b/c user is looking at the page
#when posting. when posts are made by email - user is not looking
#at the site and therefore won't get any feedback unless an email is sent back
#todo: rename INITIAL -> FIRST and make values of type string
#FOR_INITIAL_REVISION_WHEN_APPROVED = 1
#FOR_ANY_REVISION_WHEN_APPROVED = 2
#FOR_INITIAL_REVISION_ALWAYS = 3
#FOR_ANY_REVISION_ALWAYS = 4
#SELF_NOTIFY_WEB_POST_AUTHOR_WHEN_CHOICES = (
#    (NEVER, _('Never')),
#    (
#        FOR_INITIAL_REVISION_WHEN_APPROVED,
#        _('When inital revision is approved by moderator')
#    ),
#    (
#        FOR_ANY_REVISION_WHEN_APPROVED,
#        _('When any revision is approved by moderator')
#    ),
#    (
#        FOR_INITIAL_REVISION_ALWAYS,
#        _('Any time when inital revision is published')
#    ),
#    (
#        FOR_ANY_REVISION_ALWAYS,
#        _('Any time when revision is published')
#    )
#)

REPLY_SEPARATOR_TEMPLATE = '==== %(user_action)s %(instruction)s -=-=='
REPLY_SEPARATOR_REGEX = re.compile(r'==== .* -=-==', re.MULTILINE|re.DOTALL)

ANSWER_SORT_METHODS = (
    ('latest', _('latest first')),
    ('oldest', _('oldest first')),
    ('votes', _('most voted first')),
)
DEFAULT_ANSWER_SORT_METHOD = 'votes'

TAGS_SORT_METHODS = (
    ('used', _('sorted by frequency of tag use')),
    ('name', _('sorted alphabetically'))
)
DEFAULT_TAGS_SORT_METHOD = 'used'

USER_SORT_METHODS = (
    ('reputation', _('see people with the highest reputation')),
    ('newest', _('see people who joined most recently')),
    ('last', _('see people who joined the site first')),
    ('name', _('see people sorted by name'))
)
DEFAULT_USER_SORT_METHOD = 'reputation'

#todo: add assertion here that all sort methods are unique
#because they are keys to the hash used in implementations
#of Q.run_advanced_search

DEFAULT_POST_SORT_METHOD = 'activity-desc'
#todo: customize words
POST_SCOPE_LIST = (
    ('all', _('all')),
    ('unanswered', _('unanswered')),
    ('followed', _('followed')),
)
DEFAULT_POST_SCOPE = 'all'

TAG_LIST_FORMAT_CHOICES = (
    ('list', _('list')),
    ('cloud', _('cloud')),
)

PAGE_SIZE_CHOICES = (('10', '10',), ('30', '30',), ('50', '50',),)
ANSWERS_PAGE_SIZE = 10
USER_POSTS_PAGE_SIZE = 10
QUESTIONS_PER_PAGE_USER_CHOICES = ((10, '10'), (30, '30'), (50, '50'),)
TAGS_PAGE_SIZE = 60

UNANSWERED_QUESTION_MEANING_CHOICES = (
    ('NO_ANSWERS', _('Question has no answers')),
    ('NO_ACCEPTED_ANSWERS', _('Question has no accepted answers')),
)
#todo: implement this
#    ('NO_UPVOTED_ANSWERS',),
#)

#todo:
#this probably needs to be language-specific
#and selectable/changeable from the admin interface
#however it will be hard to expect that people will type
#correct regexes - plus this must be an anchored regex
#to do full string match
#IMPRTANT: tag related regexes must be portable between js and python
TAG_CHARS = r'\wp{M}+.#-'
TAG_FIRST_CHARS = r'[\wp{M}]'
TAG_FORBIDDEN_FIRST_CHARS = r'#'
TAG_REGEX_BARE = r'%s[%s]+' % (TAG_FIRST_CHARS, TAG_CHARS)
TAG_REGEX = r'^%s$' % TAG_REGEX_BARE

TAG_STRIP_CHARS = ', '
TAG_SPLIT_REGEX = r'[%s]+' % TAG_STRIP_CHARS
TAG_SEP = ',' # has to be valid TAG_SPLIT_REGEX char and MUST NOT be in const.TAG_CHARS
#!!! see const.message_keys.TAG_WRONG_CHARS_MESSAGE

EMAIL_REGEX = re.compile(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,4}\b', re.I)

TYPE_ACTIVITY_ASK_QUESTION = 1
TYPE_ACTIVITY_ANSWER = 2
TYPE_ACTIVITY_COMMENT_QUESTION = 3
TYPE_ACTIVITY_COMMENT_ANSWER = 4
TYPE_ACTIVITY_UPDATE_QUESTION = 5
TYPE_ACTIVITY_UPDATE_ANSWER = 6
TYPE_ACTIVITY_PRIZE = 7
TYPE_ACTIVITY_MARK_ANSWER = 8
TYPE_ACTIVITY_VOTE_UP = 9
TYPE_ACTIVITY_VOTE_DOWN = 10
TYPE_ACTIVITY_CANCEL_VOTE = 11
TYPE_ACTIVITY_DELETE_QUESTION = 12
TYPE_ACTIVITY_DELETE_ANSWER = 13
TYPE_ACTIVITY_MARK_OFFENSIVE = 14
TYPE_ACTIVITY_UPDATE_TAGS = 15
TYPE_ACTIVITY_FAVORITE = 16
TYPE_ACTIVITY_USER_FULL_UPDATED = 17
TYPE_ACTIVITY_EMAIL_UPDATE_SENT = 18
TYPE_ACTIVITY_MENTION = 19
TYPE_ACTIVITY_UNANSWERED_REMINDER_SENT = 20
TYPE_ACTIVITY_ACCEPT_ANSWER_REMINDER_SENT = 21
TYPE_ACTIVITY_CREATE_TAG_WIKI = 22
TYPE_ACTIVITY_UPDATE_TAG_WIKI = 23
TYPE_ACTIVITY_MODERATED_NEW_POST = 24
TYPE_ACTIVITY_MODERATED_POST_EDIT = 25
TYPE_ACTIVITY_CREATE_REJECT_REASON = 26
TYPE_ACTIVITY_UPDATE_REJECT_REASON = 27
TYPE_ACTIVITY_VALIDATION_EMAIL_SENT = 28
TYPE_ACTIVITY_POST_SHARED = 29
TYPE_ACTIVITY_ASK_TO_JOIN_GROUP = 30
TYPE_ACTIVITY_MODERATION_ALERT_SENT = 31
TYPE_ACTIVITY_FORBIDDEN_PHRASE_FOUND = 50 #added gap
TYPE_ACTIVITY_USER_REGISTERED = 51
TYPE_ACTIVITY_QUESTION_VIEWED = 52
TYPE_ACTIVITY_ANSWER_VIEWED = 53
#TYPE_ACTIVITY_EDIT_QUESTION = 17
#TYPE_ACTIVITY_EDIT_ANSWER = 18

#todo: rename this to TYPE_ACTIVITY_CHOICES
TYPE_ACTIVITY = (
    (TYPE_ACTIVITY_ASK_QUESTION, _('asked a question')),
    (TYPE_ACTIVITY_ANSWER, _('answered a question')),
    (TYPE_ACTIVITY_COMMENT_QUESTION, _('commented question')),
    (TYPE_ACTIVITY_COMMENT_ANSWER, _('commented answer')),
    (TYPE_ACTIVITY_UPDATE_QUESTION, _('edited question')),
    (TYPE_ACTIVITY_UPDATE_ANSWER, _('edited answer')),
    (TYPE_ACTIVITY_PRIZE, _('received badge')),
    (TYPE_ACTIVITY_MARK_ANSWER, _('marked best answer')),
    (TYPE_ACTIVITY_VOTE_UP, _('upvoted')),
    (TYPE_ACTIVITY_VOTE_DOWN, _('downvoted')),
    (TYPE_ACTIVITY_CANCEL_VOTE, _('canceled vote')),
    (TYPE_ACTIVITY_DELETE_QUESTION, _('deleted question')),
    (TYPE_ACTIVITY_DELETE_ANSWER, _('deleted answer')),
    (TYPE_ACTIVITY_MARK_OFFENSIVE, _('marked offensive')),
    (TYPE_ACTIVITY_UPDATE_TAGS, _('updated tags')),
    (TYPE_ACTIVITY_FAVORITE, _('selected favorite')),
    (TYPE_ACTIVITY_USER_FULL_UPDATED, _('completed user profile')),
    (TYPE_ACTIVITY_EMAIL_UPDATE_SENT, _('email update sent to user')),
    (TYPE_ACTIVITY_POST_SHARED, _('a post was shared')),
    (
        TYPE_ACTIVITY_UNANSWERED_REMINDER_SENT,
        _('reminder about unanswered questions sent'),
    ),
    (
        TYPE_ACTIVITY_ACCEPT_ANSWER_REMINDER_SENT,
        _('reminder about accepting the best answer sent'),
    ),
    (TYPE_ACTIVITY_MENTION, _('mentioned in the post')),
    (
        TYPE_ACTIVITY_CREATE_TAG_WIKI,
        _('created tag description'),
    ),
    (
        TYPE_ACTIVITY_UPDATE_TAG_WIKI,
        _('updated tag description')
    ),
    (TYPE_ACTIVITY_MODERATED_NEW_POST, _('made a new post')),
    (
        TYPE_ACTIVITY_MODERATED_POST_EDIT,
        _('made an edit')
    ),
    (
        TYPE_ACTIVITY_CREATE_REJECT_REASON,
        _('created post reject reason'),
    ),
    (
        TYPE_ACTIVITY_UPDATE_REJECT_REASON,
        _('updated post reject reason')
    ),
    (
        TYPE_ACTIVITY_VALIDATION_EMAIL_SENT,
        'sent email address validation message'#don't translate, internal
    ),
    (
        TYPE_ACTIVITY_MODERATION_ALERT_SENT,
        'sent moderation alert'#don't translate, internal
    ),
    (
        TYPE_ACTIVITY_USER_REGISTERED,
        _('joined')
    ),
    (
        TYPE_ACTIVITY_QUESTION_VIEWED,
        _('viewed question')
    ),
    (
        TYPE_ACTIVITY_ANSWER_VIEWED,
        _('viewed answer')
    ),
)

TYPE_ACTIVITY_BY_USER = (
    TYPE_ACTIVITY_ASK_QUESTION,
    TYPE_ACTIVITY_ANSWER,
    TYPE_ACTIVITY_COMMENT_QUESTION,
    TYPE_ACTIVITY_COMMENT_ANSWER,
    TYPE_ACTIVITY_UPDATE_QUESTION,
    TYPE_ACTIVITY_UPDATE_ANSWER,
    TYPE_ACTIVITY_MARK_ANSWER,
    TYPE_ACTIVITY_VOTE_UP,
    TYPE_ACTIVITY_VOTE_DOWN,
    TYPE_ACTIVITY_CANCEL_VOTE,
    TYPE_ACTIVITY_DELETE_QUESTION,
    TYPE_ACTIVITY_DELETE_ANSWER,
    TYPE_ACTIVITY_MARK_OFFENSIVE,
    TYPE_ACTIVITY_UPDATE_TAGS,
    TYPE_ACTIVITY_FAVORITE,
    TYPE_ACTIVITY_USER_FULL_UPDATED,
    TYPE_ACTIVITY_POST_SHARED,
    TYPE_ACTIVITY_CREATE_TAG_WIKI,
    TYPE_ACTIVITY_UPDATE_TAG_WIKI,
    TYPE_ACTIVITY_MODERATED_NEW_POST,
    TYPE_ACTIVITY_MODERATED_POST_EDIT,
    TYPE_ACTIVITY_CREATE_REJECT_REASON,
    TYPE_ACTIVITY_UPDATE_REJECT_REASON,
    TYPE_ACTIVITY_USER_REGISTERED,
    TYPE_ACTIVITY_QUESTION_VIEWED,
    TYPE_ACTIVITY_ANSWER_VIEWED,
)

SIDEBAR_AVATARS_BLOCK_ACTIVITY_TYPES = (
    TYPE_ACTIVITY_ASK_QUESTION,
    TYPE_ACTIVITY_ANSWER,
    TYPE_ACTIVITY_UPDATE_QUESTION,
    TYPE_ACTIVITY_UPDATE_ANSWER
)

MODERATED_EDIT_ACTIVITY_TYPES = (
    TYPE_ACTIVITY_MODERATED_NEW_POST,
    TYPE_ACTIVITY_MODERATED_POST_EDIT
)
MODERATED_ACTIVITY_TYPES = MODERATED_EDIT_ACTIVITY_TYPES + (TYPE_ACTIVITY_MARK_OFFENSIVE,)


#MENTION activity is added implicitly, unfortunately
RESPONSE_ACTIVITY_TYPES_FOR_INSTANT_NOTIFICATIONS = (
    TYPE_ACTIVITY_COMMENT_QUESTION,
    TYPE_ACTIVITY_COMMENT_ANSWER,
    TYPE_ACTIVITY_UPDATE_ANSWER,
    TYPE_ACTIVITY_UPDATE_QUESTION,
    TYPE_ACTIVITY_ANSWER,
    TYPE_ACTIVITY_ASK_QUESTION,
    TYPE_ACTIVITY_POST_SHARED
)


#the same as for instant notifications for now
#MENTION activity is added implicitly, unfortunately
RESPONSE_ACTIVITY_TYPES_FOR_DISPLAY = (
    TYPE_ACTIVITY_ANSWER,
    TYPE_ACTIVITY_ASK_QUESTION,
    TYPE_ACTIVITY_COMMENT_QUESTION,
    TYPE_ACTIVITY_COMMENT_ANSWER,
    TYPE_ACTIVITY_UPDATE_ANSWER,
    TYPE_ACTIVITY_UPDATE_QUESTION,
    TYPE_ACTIVITY_POST_SHARED,
    #    TYPE_ACTIVITY_PRIZE,
    #    TYPE_ACTIVITY_MARK_ANSWER,
    #    TYPE_ACTIVITY_VOTE_UP,
    #    TYPE_ACTIVITY_VOTE_DOWN,
    #    TYPE_ACTIVITY_CANCEL_VOTE,
    #    TYPE_ACTIVITY_DELETE_QUESTION,
    #    TYPE_ACTIVITY_DELETE_ANSWER,
    #    TYPE_ACTIVITY_MARK_OFFENSIVE,
    #    TYPE_ACTIVITY_FAVORITE,
)

RESPONSE_ACTIVITY_TYPE_MAP_FOR_TEMPLATES = {
    TYPE_ACTIVITY_COMMENT_QUESTION: 'question_comment',
    TYPE_ACTIVITY_COMMENT_ANSWER: 'answer_comment',
    TYPE_ACTIVITY_UPDATE_ANSWER: 'answer_update',
    TYPE_ACTIVITY_UPDATE_QUESTION: 'question_update',
    TYPE_ACTIVITY_ANSWER: 'new_answer',
    TYPE_ACTIVITY_ASK_QUESTION: 'new_question',
    TYPE_ACTIVITY_POST_SHARED: 'post_shared'
}

assert(
    set(RESPONSE_ACTIVITY_TYPES_FOR_INSTANT_NOTIFICATIONS) \
    == set(RESPONSE_ACTIVITY_TYPE_MAP_FOR_TEMPLATES.keys())
)

POST_STATUS = {
    'closed': _('[closed]'),
    'deleted': _('[deleted]'),
    'default_version': _('initial version'),
    'retagged': _('retagged'),
    'private': _('[private]')
}

# codes used in the askbot.views.commands.vote view
VOTE_ACCEPT_ANSWER = '0'
VOTE_FAVORITE = '4'

VOTE_UPVOTE_QUESTION, VOTE_DOWNVOTE_QUESTION = '1', '2'
VOTE_UPVOTE_ANSWER, VOTE_DOWNVOTE_ANSWER = '5', '6'

VOTE_REPORT_QUESTION = '7'
VOTE_CANCEL_REPORT_QUESTION = '7.5'
VOTE_CANCEL_REPORT_QUESTION_ALL = '7.6'

VOTE_REPORT_ANSWER = '8'
VOTE_CANCEL_REPORT_ANSWER = '8.5'
VOTE_CANCEL_REPORT_ANSWER_ALL = '8.6'

VOTE_REMOVE_QUESTION, VOTE_REMOVE_ANSWER = '9', '10'
#VOTE_SUBSCRIBE_QUESTION, VOTE_UNSUBSCRIBE_QUESTION = '11', '12'

# list of vote commands to manage posts voting
VOTE_TYPES_VOTING = (
    VOTE_UPVOTE_QUESTION,
    VOTE_DOWNVOTE_QUESTION,
    VOTE_UPVOTE_ANSWER,
    VOTE_DOWNVOTE_ANSWER,
)

# list of vote commands to manage posts flagging
VOTE_TYPES_REPORTING = (
    VOTE_REPORT_QUESTION,
    VOTE_CANCEL_REPORT_QUESTION,
    VOTE_CANCEL_REPORT_QUESTION_ALL,
    VOTE_REPORT_ANSWER,
    VOTE_CANCEL_REPORT_ANSWER,
    VOTE_CANCEL_REPORT_ANSWER_ALL,
)

# list of vote commands which cause post deletion
VOTE_TYPES_REMOVAL = (
    VOTE_REMOVE_QUESTION,
    VOTE_REMOVE_ANSWER,
)

# list of vote commands which shall cause the thread cache to be invalidated
VOTE_TYPES_INVALIDATE_CACHE = (
    VOTE_ACCEPT_ANSWER,
    VOTE_REPORT_QUESTION,
    VOTE_CANCEL_REPORT_QUESTION,
    VOTE_CANCEL_REPORT_QUESTION_ALL,
    VOTE_REPORT_ANSWER,
    VOTE_CANCEL_REPORT_ANSWER,
    VOTE_CANCEL_REPORT_ANSWER_ALL,
    VOTE_REMOVE_QUESTION,
    VOTE_REMOVE_ANSWER,
)

# mapping of VOTE commands to command specific arguments in the form:
#
#    (post_type, *command_specific_args)
#
VOTE_TYPES = {
    VOTE_ACCEPT_ANSWER: ('answer', ),
    VOTE_FAVORITE: None, #maybe not used
    # args: (post_type, vote_directiom)
    VOTE_UPVOTE_QUESTION: ('question', 'up'),
    VOTE_DOWNVOTE_QUESTION: ('question', 'down'),
    VOTE_UPVOTE_ANSWER: ('answer', 'up'),
    VOTE_DOWNVOTE_ANSWER: ('answer', 'down'),

    # args: (post_type, cancel, cancel_all)
    VOTE_REPORT_QUESTION: ('question', False, False),
    VOTE_CANCEL_REPORT_QUESTION: ('question', True, False),
    VOTE_CANCEL_REPORT_QUESTION_ALL: ('question', False, True),
    VOTE_REPORT_ANSWER: ('answer', False, False),
    VOTE_CANCEL_REPORT_ANSWER: ('answer', True, False),
    VOTE_CANCEL_REPORT_ANSWER_ALL: ('answer', False, True),

    VOTE_REMOVE_QUESTION: ('question', ),
    VOTE_REMOVE_ANSWER: ('answer', ),

    #VOTE_SUBSCRIBE_QUESTION: ('question', ),
    #VOTE_UNSUBSCRIBE_QUESTION: ('question', ),
}


# choices used in email and display filters
INCLUDE_ALL = 0
EXCLUDE_IGNORED = 1
INCLUDE_INTERESTING = 2
INCLUDE_SUBSCRIBED = 3
TAG_DISPLAY_FILTER_STRATEGY_MINIMAL_CHOICES = (
    (INCLUDE_ALL, _('all tags')),
    (EXCLUDE_IGNORED, _('exclude ignored tags')),
    (INCLUDE_INTERESTING, _('only interesting tags'))
)
TAG_DISPLAY_FILTER_STRATEGY_CHOICES = \
    TAG_DISPLAY_FILTER_STRATEGY_MINIMAL_CHOICES + \
    ((INCLUDE_SUBSCRIBED, _('only subscribed tags')),)

TAG_EMAIL_FILTER_SIMPLE_STRATEGY_CHOICES = (
    (INCLUDE_ALL, _('all tags')),
    (EXCLUDE_IGNORED, _('exclude ignored tags')),
    (INCLUDE_INTERESTING, _('only interesting tags')),
)

TAG_EMAIL_FILTER_ADVANCED_STRATEGY_CHOICES = (
    (INCLUDE_ALL, _('all tags')),
    (EXCLUDE_IGNORED, _('exclude ignored tags')),
    (INCLUDE_SUBSCRIBED, _('only subscribed tags')),
)

TAG_EMAIL_FILTER_FULL_STRATEGY_CHOICES = (
    (INCLUDE_ALL, _('all tags')),
    (EXCLUDE_IGNORED, _('exclude ignored tags')),
    (INCLUDE_INTERESTING, _('only interesting tags')),
    (INCLUDE_SUBSCRIBED, _('only subscribed tags')),
)

NOTIFICATION_DELIVERY_SCHEDULE_CHOICES = (
    ('i', _('instantly')),
    ('d', _('daily')),
    ('w', _('weekly')),
    ('n', _('never')),
)

NOTIFICATION_DELIVERY_SCHEDULE_CHOICES_Q_NOANS = (
    ('d', _('daily')),
    ('w', _('weekly')),
    ('n', _('never')),
)

USERNAME_REGEX_STRING = r'^[\w \-.@+\']+$'

GRAVATAR_TYPE_CHOICES = (('identicon', _('identicon')),
                         ('monsterid', _('monsterid')),
                         ('wavatar', _('wavatar')),
                         ('retro', _('retro')),
                         ('mm', _('mystery-man')))

AVATAR_TYPE_CHOICES_FOR_NEW_USERS = (
    ('n', _('Default avatar')),
    ('g', _('Gravatar')),#only if user has real uploaded gravatar
)

AVATAR_TYPE_CHOICES = AVATAR_TYPE_CHOICES_FOR_NEW_USERS + (
    #avatar uploaded locally - with django-avatar app
    ('a', _('Uploaded Avatar')),
)

#chars that can go before or after @mention
TWITTER_STYLE_MENTION_TERMINATION_CHARS = '\n ;:,.!?<>"\''

COMMENT_HARD_MAX_LENGTH = 2048

#user status ch
USER_STATUS_CHOICES = (
    ('d', _('administrator')), #admin = moderator + access to settings
    ('m', _('moderator')), #user with moderation privilege
    ('a', _('approved')), #regular user
    ('w', _('watched')), #regular user placed on the moderation watch
    ('s', _('suspended')), #suspended user who cannot post new stuff
    ('b', _('blocked')), #blocked
    #terminated account, personal data deleted, content anonymized and retained
    ('t', _('terminated'))
)
DEFAULT_USER_STATUS = 'w'

#number of items to show in user views
USER_VIEW_DATA_SIZE = 50

#not really dependency, but external links, which it would
#be nice to test for correctness from time to time
DEPENDENCY_URLS = {
    'akismet': 'https://akismet.com/signup/',
    'cc-by-sa': 'http://creativecommons.org/licenses/by-sa/3.0/legalcode',
    'embedding-video': \
        'http://askbot.org/doc/optional-modules.html#embedding-video',
    'favicon': 'http://en.wikipedia.org/wiki/Favicon',
    'facebook-apps': 'http://www.facebook.com/developers/createapp.php',
    'google-webmaster-tools': 'https://www.google.com/webmasters/tools/home',
    'identica-apps': 'http://identi.ca/settings/oauthapps',
    'noscript': 'https://www.google.com/support/bin/answer.py?answer=23852',
    'linkedin-apps': 'https://www.linkedin.com/secure/developer',
    'mathjax': 'http://www.mathjax.org/resources/docs/?installation.html',
    'recaptcha': 'http://google.com/recaptcha',
    'twitter-apps': 'http://dev.twitter.com/apps/',
    'mediawiki-oauth-extension': 'https://www.mediawiki.org/wiki/Extension:OAuth',
    'yammer-apps': 'https://www.yammer.com/client_applications',
    'windows-live-apps': 'https://apps.dev.microsoft.com/#/appList',
    'microsoft-azure-apps': 'https://apps.dev.microsoft.com/#/appList',
}

PASSWORD_MIN_LENGTH = 8

GOLD_BADGE = 1
SILVER_BADGE = 2
BRONZE_BADGE = 3
BADGE_TYPE_CHOICES = ((GOLD_BADGE, _('gold')),
                      (SILVER_BADGE, _('silver')),
                      (BRONZE_BADGE, _('bronze')))

BADGE_CSS_CLASSES = {
    GOLD_BADGE: 'badge with-gold-badge-icon',
    SILVER_BADGE: 'badge with-silver-badge-icon',
    BRONZE_BADGE: 'badge with-bronze-badge-icon',
}
BADGE_DISPLAY_SYMBOL = '&#9679;'

MIN_REPUTATION = 1

SEARCH_ORDER_BY = (('-added_at', _('date descendant')),
                   ('added_at', _('date ascendant')),
                   ('-last_activity_at', _('most recently active')),
                   ('last_activity_at', _('least recently active')),
                   ('-answer_count', _('more responses')),
                   ('answer_count', _('fewer responses')),
                   ('-points', _('more votes')),
                   ('points', _('less votes')))

DEFAULT_QUESTION_WIDGET_STYLE = """
@import url('http://fonts.googleapis.com/css?family=Yanone+Kaffeesatz:300,400,700');
body {
    overflow: hidden;
}

#container {
    width: 200px;
    height: 350px;
}
ul {
    list-style: none;
    padding: 5px;
    margin: 5px;
}
li {
    border-bottom: #CCC 1px solid;
    padding-bottom: 5px;
    padding-top: 5px;
}
li:last-child {
    border: none;
}
a {
    text-decoration: none;
    color: #464646;
    font-family: 'Yanone Kaffeesatz', sans-serif;
    font-size: 15px;
}
"""

PROFILE_WEBSITE_URL_MAX_LENGTH = 200
