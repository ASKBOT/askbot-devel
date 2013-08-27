from askbot import startup_procedures
startup_procedures.run()

from django.contrib.auth.models import User
#set up a possibility for the users to follow others
try:
    import followit
    followit.register(User)
except ImportError:
    pass

import collections
import datetime
import hashlib
import logging
import re
import urllib
import uuid
from celery import states
from celery.task import task
from django.core.urlresolvers import reverse, NoReverseMatch
from django.db.models import signals as django_signals
from django.template import Context
from django.template.loader import get_template
from django.utils.translation import ugettext as _
from django.utils.translation import ungettext
from django.utils.safestring import mark_safe
from django.utils.html import escape
from django.db import models
from django.conf import settings as django_settings
from django.contrib.contenttypes.models import ContentType
from django.core import cache
from django.core import exceptions as django_exceptions
from django_countries.fields import CountryField
from askbot import exceptions as askbot_exceptions
from askbot import const
from askbot.const.message_keys import get_i18n_message
from askbot.conf import settings as askbot_settings
from askbot.models.question import Thread
from askbot.skins import utils as skin_utils
from askbot.mail import messages
from askbot.models.question import QuestionView, AnonymousQuestion
from askbot.models.question import DraftQuestion
from askbot.models.question import FavoriteQuestion
from askbot.models.tag import Tag, MarkedTag, TagSynonym
from askbot.models.tag import format_personal_group_name
from askbot.models.user import EmailFeedSetting, ActivityAuditStatus, Activity
from askbot.models.user import GroupMembership
from askbot.models.user import Group
from askbot.models.user import BulkTagSubscription
from askbot.models.post import Post, PostRevision
from askbot.models.post import PostFlagReason, AnonymousAnswer
from askbot.models.post import PostToGroup
from askbot.models.post import DraftAnswer
from askbot.models.reply_by_email import ReplyAddress
from askbot.models import signals
from askbot.models.badges import award_badges_signal, get_badge, BadgeData
from askbot.models.repute import Award, Repute, Vote
from askbot.models.widgets import AskWidget, QuestionWidget
from askbot import auth
from askbot.utils.decorators import auto_now_timestamp
from askbot.utils.markup import URL_RE
from askbot.utils.slug import slugify
from askbot.utils.html import replace_links_with_text
from askbot.utils.html import sanitize_html
from askbot.utils.html import site_url
from askbot.utils.diff import textDiff as htmldiff
from askbot.utils.url_utils import strip_path
from askbot import mail

from django import VERSION

#stores the 1.X version not the security release numbers
DJANGO_VERSION = VERSION[:2]

if DJANGO_VERSION > (1, 3):
    from askbot.models.message import Message

def get_model(model_name):
    """a shortcut for getting model for an askbot app"""
    return models.get_model('askbot', model_name)

def get_admin():
    """returns admin with the lowest user ID
    if there are no users at all - creates one
    with name "admin" and unusable password
    otherwise raises User.DoesNotExist
    """
    try:
        return User.objects.filter(
                        is_superuser=True
                    ).order_by('id')[0]
    except IndexError:
        if User.objects.filter(username='_admin_').count() == 0:
            admin = User.objects.create_user('_admin_', '')
            admin.set_unusable_password()
            admin.set_admin_status()
            admin.save()
            return admin
        else:
            raise User.DoesNotExist

def get_users_by_text_query(search_query, users_query_set = None):
    """Runs text search in user names and profile.
    For postgres, search also runs against user group names.
    """
    if getattr(django_settings, 'ENABLE_HAYSTACK_SEARCH', False):
        from askbot.search.haystack.searchquery import AskbotSearchQuerySet
        qs = AskbotSearchQuerySet().filter(content=search_query)
        qs = qs.models(User).get_django_queryset(User)
        return qs
    else:
        import askbot
        if users_query_set is None:
            users_query_set = User.objects.all()
        if 'postgresql_psycopg2' in askbot.get_database_engine_name():
            from askbot.search import postgresql
            return postgresql.run_user_search(users_query_set, search_query)
        else:
            return users_query_set.filter(
                models.Q(username__icontains=search_query) |
                models.Q(about__icontains=search_query)
            )
        #if askbot.get_database_engine_name().endswith('mysql') \
        #    and mysql.supports_full_text_search():
        #    return User.objects.filter(
        #        models.Q(username__search = search_query) |
        #        models.Q(about__search = search_query)
        #    )

class RelatedObjectSimulator(object):
    '''Objects that simulates the "messages_set" related field
    somehow django does not creates it automatically in django1.4.1'''

    def __init__(self, user, model_class):
        self.user = user
        self.model_class = model_class

    def all(self):
        return self.model_class.objects.all()

    def count(self, **kwargs):
        kwargs['user'] = self.user
        return self.model_class.objects.filter(**kwargs).count()

    def create(self, **kwargs):
        return self.model_class.objects.create(user=self.user, **kwargs)

    def filter(self, *args, **kwargs):
        return self.model_class.objects.filter(*args, **kwargs)


#django 1.4.1 and above
@property
def user_message_set(self):
    return RelatedObjectSimulator(self, Message)

#django 1.4.1 and above
def user_get_and_delete_messages(self):
    messages = []
    for message in Message.objects.filter(user=self):
        messages.append(message.message)
        message.delete()
    return messages

if DJANGO_VERSION > (1, 3):
    User.add_to_class('message_set', user_message_set)
    User.add_to_class('get_and_delete_messages', user_get_and_delete_messages)

User.add_to_class(
            'status',
            models.CharField(
                        max_length = 2,
                        default = const.DEFAULT_USER_STATUS,
                        choices = const.USER_STATUS_CHOICES
                    )
        )
User.add_to_class('is_fake', models.BooleanField(default=False))

User.add_to_class('email_isvalid', models.BooleanField(default=False)) #@UndefinedVariable
User.add_to_class('email_key', models.CharField(max_length=32, null=True))
#hardcoded initial reputaion of 1, no setting for this one
User.add_to_class('reputation',
    models.PositiveIntegerField(default=const.MIN_REPUTATION)
)
User.add_to_class('gravatar', models.CharField(max_length=32))
#User.add_to_class('has_custom_avatar', models.BooleanField(default=False))
User.add_to_class(
    'avatar_type',
    models.CharField(max_length=1,
        choices=const.AVATAR_STATUS_CHOICE,
        default='n')
)
User.add_to_class('gold', models.SmallIntegerField(default=0))
User.add_to_class('silver', models.SmallIntegerField(default=0))
User.add_to_class('bronze', models.SmallIntegerField(default=0))
User.add_to_class(
    'questions_per_page',  # TODO: remove me and const.QUESTIONS_PER_PAGE_USER_CHOICES, we're no longer used!
    models.SmallIntegerField(
        choices=const.QUESTIONS_PER_PAGE_USER_CHOICES,
        default=10
    )
)
User.add_to_class('last_seen',
                  models.DateTimeField(default=datetime.datetime.now))
User.add_to_class('real_name', models.CharField(max_length=100, blank=True))
User.add_to_class('website', models.URLField(max_length=200, blank=True))
#location field is actually city
User.add_to_class('location', models.CharField(max_length=100, blank=True))
User.add_to_class('country', CountryField(blank = True))
User.add_to_class('show_country', models.BooleanField(default = False))

User.add_to_class('date_of_birth', models.DateField(null=True, blank=True))
User.add_to_class('about', models.TextField(blank=True))
#interesting tags and ignored tags are to store wildcard tag selections only
User.add_to_class('interesting_tags', models.TextField(blank = True))
User.add_to_class('ignored_tags', models.TextField(blank = True))
User.add_to_class('subscribed_tags', models.TextField(blank = True))
User.add_to_class('email_signature', models.TextField(blank = True))
User.add_to_class('show_marked_tags', models.BooleanField(default = True))

User.add_to_class(
    'email_tag_filter_strategy',
    models.SmallIntegerField(
        choices=const.TAG_EMAIL_FILTER_FULL_STRATEGY_CHOICES,
        default=const.EXCLUDE_IGNORED
    )
)
User.add_to_class(
    'display_tag_filter_strategy',
    models.SmallIntegerField(
        choices=const.TAG_DISPLAY_FILTER_STRATEGY_CHOICES,
        default=const.INCLUDE_ALL
    )
)

User.add_to_class('new_response_count', models.IntegerField(default=0))
User.add_to_class('seen_response_count', models.IntegerField(default=0))
User.add_to_class('consecutive_days_visit_count', models.IntegerField(default = 0))
#list of languages for which user should receive email alerts
User.add_to_class(
    'languages',
    models.CharField(max_length=128, default=django_settings.LANGUAGE_CODE)
)

User.add_to_class(
    'twitter_access_token',
    models.CharField(max_length=256, default='')
)

User.add_to_class(
    'twitter_handle',
    models.CharField(max_length=32, default='')
)

User.add_to_class(
    'social_sharing_mode',
    models.IntegerField(
        default=const.SHARE_NOTHING,
        choices = const.SOCIAL_SHARING_MODE_CHOICES
    )
)

GRAVATAR_TEMPLATE = "//www.gravatar.com/avatar/%(gravatar)s?" + \
    "s=%(size)d&amp;d=%(type)s&amp;r=PG"

def user_get_gravatar_url(self, size):
    """returns gravatar url
    """
    return GRAVATAR_TEMPLATE % {
                'gravatar': self.gravatar,
                'type': askbot_settings.GRAVATAR_TYPE,
                'size': size,
            }

def user_get_default_avatar_url(self, size):
    """returns default avatar url
    """
    return skin_utils.get_media_url(askbot_settings.DEFAULT_AVATAR_URL)

def user_get_avatar_url(self, size=48):
    """returns avatar url - by default - gravatar,
    but if application django-avatar is installed
    it will use avatar provided through that app
    """
    if 'avatar' in django_settings.INSTALLED_APPS:
        if self.avatar_type == 'n':
            import avatar
            if askbot_settings.ENABLE_GRAVATAR: #avatar.settings.AVATAR_GRAVATAR_BACKUP:
                return self.get_gravatar_url(size)
            else:
                return self.get_default_avatar_url(size)
        elif self.avatar_type == 'a':
            kwargs = {'user_id': self.id, 'size': size}
            try:
                return reverse('avatar_render_primary', kwargs = kwargs)
            except NoReverseMatch:
                message = 'Please, make sure that avatar urls are in the urls.py '\
                          'or update your django-avatar app, '\
                          'currently it is impossible to serve avatars.'
                logging.critical(message)
                raise django_exceptions.ImproperlyConfigured(message)
        else:
            return self.get_gravatar_url(size)
    else:
        if askbot_settings.ENABLE_GRAVATAR:
            return self.get_gravatar_url(size)
        else:
            return self.get_default_avatar_url(size)

def user_update_avatar_type(self):
    """counts number of custom avatars
    and if zero, sets avatar_type to False,
    True otherwise. The method is called only if
    avatar application is installed.
    Saves the object.
    """

    if 'avatar' in django_settings.INSTALLED_APPS:
        if self.avatar_set.count() > 0:
            self.avatar_type = 'a'
        else:
            self.avatar_type = _check_gravatar(self.gravatar)
    else:
            self.avatar_type = _check_gravatar(self.gravatar)
    self.save()

def user_strip_email_signature(self, text):
    """strips email signature from the end of the text"""
    if self.email_signature.strip() == '':
        return text

    text = '\n'.join(text.splitlines())#normalize the line endings
    while text.endswith(self.email_signature):
        text = text[0:-len(self.email_signature)]
    return text

def _check_gravatar(gravatar):
    gravatar_url = "http://www.gravatar.com/avatar/%s?d=404" % gravatar
    code = urllib.urlopen(gravatar_url).getcode()
    if urllib.urlopen(gravatar_url).getcode() != 404:
        return 'g' #gravatar
    else:
        return 'n' #none

def user_get_old_vote_for_post(self, post):
    """returns previous vote for this post
    by the user or None, if does not exist

    raises assertion_error is number of old votes is > 1
    which is illegal
    """
    try:
        return Vote.objects.get(user=self, voted_post=post)
    except Vote.DoesNotExist:
        return None
    except Vote.MultipleObjectsReturned:
        raise AssertionError

def user_get_marked_tags(self, reason):
    """reason is a type of mark: good, bad or subscribed"""
    assert(reason in ('good', 'bad', 'subscribed'))
    if reason == 'subscribed':
        if askbot_settings.SUBSCRIBED_TAG_SELECTOR_ENABLED == False:
            return Tag.objects.none()

    return Tag.objects.filter(
        user_selections__user = self,
        user_selections__reason = reason
    )

MARKED_TAG_PROPERTY_MAP = {
    'good': 'interesting_tags',
    'bad': 'ignored_tags',
    'subscribed': 'subscribed_tags'
}
def user_get_marked_tag_names(self, reason):
    """returns list of marked tag names for a give
    reason: good, bad, or subscribed
    will add wildcard tags as well, if used
    """
    if reason == 'subscribed':
        if askbot_settings.SUBSCRIBED_TAG_SELECTOR_ENABLED == False:
            return list()

    tags = self.get_marked_tags(reason)
    tag_names = list(tags.values_list('name', flat = True))

    if askbot_settings.USE_WILDCARD_TAGS:
        attr_name = MARKED_TAG_PROPERTY_MAP[reason]
        wildcard_tags = getattr(self, attr_name).split()
        tag_names.extend(wildcard_tags)

    return tag_names

def user_has_affinity_to_question(self, question = None, affinity_type = None):
    """returns True if number of tag overlap of the user tag
    selection with the question is 0 and False otherwise
    affinity_type can be either "like" or "dislike"
    """
    if affinity_type == 'like':
        if askbot_settings.SUBSCRIBED_TAG_SELECTOR_ENABLED:
            tag_selection_type = 'subscribed'
            wildcards = self.subscribed_tags.split()
        else:
            tag_selection_type = 'good'
            wildcards = self.interesting_tags.split()
    elif affinity_type == 'dislike':
        tag_selection_type = 'bad'
        wildcards = self.ignored_tags.split()
    else:
        raise ValueError('unexpected affinity type %s' % str(affinity_type))

    question_tags = question.thread.tags.all()
    intersecting_tag_selections = self.tag_selections.filter(
                                                tag__in = question_tags,
                                                reason = tag_selection_type
                                            )
    #count number of overlapping tags
    if intersecting_tag_selections.count() > 0:
        return True
    elif askbot_settings.USE_WILDCARD_TAGS == False:
        return False

    #match question tags against wildcards
    for tag in question_tags:
        for wildcard in wildcards:
            if tag.name.startswith(wildcard[:-1]):
                return True
    return False


def user_has_ignored_wildcard_tags(self):
    """True if wildcard tags are on and
    user has some"""
    return (
        askbot_settings.USE_WILDCARD_TAGS \
        and self.ignored_tags != ''
    )


def user_has_interesting_wildcard_tags(self):
    """True in wildcard tags aro on and
    user has nome interesting wildcard tags selected
    """
    return (
        askbot_settings.USE_WILDCARD_TAGS \
        and self.interesting_tags != ''
    )

def user_can_create_tags(self):
    """true if user can create tags"""
    if askbot_settings.ENABLE_TAG_MODERATION:
        return self.is_administrator_or_moderator()
    else:
        return True

def user_can_have_strong_url(self):
    """True if user's homepage url can be
    followed by the search engine crawlers"""
    return (self.reputation >= askbot_settings.MIN_REP_TO_HAVE_STRONG_URL)

def user_can_post_by_email(self):
    """True, if reply by email is enabled
    and user has sufficient reputatiton"""

    if askbot_settings.REPLY_BY_EMAIL:
        if self.is_administrator_or_moderator():
            return True
        else:
            return self.reputation >= askbot_settings.MIN_REP_TO_POST_BY_EMAIL
    else:
        return False


def user_get_social_sharing_mode(self):
    """returns what user wants to share on his/her channels"""
    mode = self.social_sharing_mode
    if mode == const.SHARE_NOTHING:
        return 'share-nothing'
    elif mode == const.SHARE_MY_POSTS:
        return 'share-my-posts'
    else:
        assert(mode == const.SHARE_EVERYTHING)
        return 'share-everything'

def user_get_social_sharing_status(self, channel):
    """channel is only 'twitter' for now"""
    assert(channel == 'twitter')
    if self.twitter_handle:
        if self.get_social_sharing_mode() == 'share-nothing':
            return 'inactive'
        else:
            return 'enabled'
    else:
        return 'disabled'

def user_get_or_create_fake_user(self, username, email):
    """
    Get's or creates a user, most likely with the purpose
    of posting under that account.
    """
    assert(self.is_administrator())

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        user = User()
        user.username = username
        user.email = email
        user.is_fake = True
        user.set_unusable_password()
        user.save()
    return user

def user_notify_users(
    self, notification_type=None, recipients=None, content_object=None
):
    """A utility function that creates instance
    of :class:`Activity` and adds recipients
    * `notification_type` - value should be one of TYPE_ACTIVITY_...
    * `recipients` - an iterable of user objects
    * `content_object` - any object related to the notification

    todo: possibly add checks on the content_object, depending on the
    notification_type
    """
    activity = Activity(
                user=self,
                activity_type=notification_type,
                content_object=content_object
            )
    activity.save()
    activity.add_recipients(recipients)

def user_is_read_only(self):
    """True if user is allowed to change content on the site"""
    if askbot_settings.GROUPS_ENABLED:
        return bool(self.get_groups().filter(read_only=True).count())
    else:
        return False

def user_get_notifications(self, notification_types=None, **kwargs):
    """returns query set of activity audit status objects"""
    return ActivityAuditStatus.objects.filter(
                        user=self,
                        activity__activity_type__in=notification_types,
                        **kwargs
                    )

def _assert_user_can(
                        user = None,
                        post = None, #related post (may be parent)
                        admin_or_moderator_required = False,
                        owner_can = False,
                        suspended_owner_cannot = False,
                        owner_min_rep_setting = None,
                        blocked_error_message = None,
                        suspended_error_message = None,
                        min_rep_setting = None,
                        low_rep_error_message = None,
                        owner_low_rep_error_message = None,
                        general_error_message = None,
                    ):
    """generic helper assert for use in several
    User.assert_can_XYZ() calls regarding changing content

    user is required and at least one error message

    if assertion fails, method raises exception.PermissionDenied
    with appropriate text as a payload
    """
    if askbot_settings.GROUPS_ENABLED:
        if user.is_read_only():
            message = _('Sorry, but you have only read access')
            raise django_exceptions.PermissionDenied(message)

    if general_error_message is None:
        general_error_message = _('Sorry, this operation is not allowed')
    if blocked_error_message and user.is_blocked():
        error_message = blocked_error_message
    elif post and owner_can and user == post.get_owner():
        if owner_min_rep_setting:
            if post.get_owner().reputation < owner_min_rep_setting:
                if user.is_moderator() or user.is_administrator():
                    return
                else:
                    assert(owner_low_rep_error_message is not None)
                    raise askbot_exceptions.InsufficientReputation(
                                                owner_low_rep_error_message
                                            )
        if suspended_owner_cannot and user.is_suspended():
            if suspended_error_message:
                error_message = suspended_error_message
            else:
                error_message = general_error_message
            assert(error_message is not None)
            raise django_exceptions.PermissionDenied(error_message)
        else:
            return
        return
    elif suspended_error_message and user.is_suspended():
        error_message = suspended_error_message
    elif user.is_administrator() or user.is_moderator():
        return
    elif user.is_post_moderator(post):
        return
    elif low_rep_error_message and user.reputation < min_rep_setting:
        raise askbot_exceptions.InsufficientReputation(low_rep_error_message)
    else:
        if admin_or_moderator_required == False:
            return

    #if admin or moderator is required, then substitute the message
    if admin_or_moderator_required:
        error_message = general_error_message
    assert(error_message is not None)
    raise django_exceptions.PermissionDenied(error_message)

def user_assert_can_approve_post_revision(self, post_revision = None):
    _assert_user_can(
        user = self,
        admin_or_moderator_required = True
    )

def user_assert_can_unaccept_best_answer(self, answer = None):
    assert getattr(answer, 'post_type', '') == 'answer'
    blocked_error_message = _(
            'Sorry, you cannot accept or unaccept best answers '
            'because your account is blocked'
        )
    suspended_error_message = _(
            'Sorry, you cannot accept or unaccept best answers '
            'because your account is suspended'
        )

    if self.is_blocked():
        error_message = blocked_error_message
    elif self.is_suspended():
        error_message = suspended_error_message
    elif self == answer.thread._question_post().get_owner():
        if self == answer.get_owner():
            if not self.is_administrator():
                #check rep
                min_rep_setting = askbot_settings.MIN_REP_TO_ACCEPT_OWN_ANSWER
                low_rep_error_message = _(
                            ">%(points)s points required to accept or unaccept "
                            " your own answer to your own question"
                        ) % {'points': min_rep_setting}

                _assert_user_can(
                    user = self,
                    blocked_error_message = blocked_error_message,
                    suspended_error_message = suspended_error_message,
                    min_rep_setting = min_rep_setting,
                    low_rep_error_message = low_rep_error_message
                )
        return # success

    elif self.reputation >= askbot_settings.MIN_REP_TO_ACCEPT_ANY_ANSWER or \
        self.is_administrator() or self.is_moderator() or self.is_post_moderator(answer):

        will_be_able_at = (
            answer.added_at +
            datetime.timedelta(
                days=askbot_settings.MIN_DAYS_FOR_STAFF_TO_ACCEPT_ANSWER)
        )

        if datetime.datetime.now() < will_be_able_at:
            error_message = _(
                'Sorry, you will be able to accept this answer '
                'only after %(will_be_able_at)s'
                ) % {'will_be_able_at': will_be_able_at.strftime('%d/%m/%Y')}
        else:
            return

    else:
        question_owner = answer.thread._question_post().get_owner()
        error_message = _(
            'Sorry, only moderators or original author of the question '
            ' - %(username)s - can accept or unaccept the best answer'
        ) % {'username': question_owner.username}

    raise django_exceptions.PermissionDenied(error_message)

def user_assert_can_accept_best_answer(self, answer = None):
    assert getattr(answer, 'post_type', '') == 'answer'
    self.assert_can_unaccept_best_answer(answer)

def user_assert_can_vote_for_post(
                                self,
                                post = None,
                                direction = None,
                            ):
    """raises exceptions.PermissionDenied exception
    if user can't in fact upvote

    :param:direction can be 'up' or 'down'
    :param:post can be instance of question or answer
    """
    if self == post.author:
        raise django_exceptions.PermissionDenied(
            _('Sorry, you cannot vote for your own posts')
        )

    blocked_error_message = _(
                'Sorry your account appears to be blocked ' +
                'and you cannot vote - please contact the ' +
                'site administrator to resolve the issue'
            ),
    suspended_error_message = _(
                'Sorry your account appears to be suspended ' +
                'and you cannot vote - please contact the ' +
                'site administrator to resolve the issue'
            )

    assert(direction in ('up', 'down'))

    if direction == 'up':
        min_rep_setting = askbot_settings.MIN_REP_TO_VOTE_UP
        low_rep_error_message = _(
                    ">%(points)s points required to upvote"
                ) % \
                {'points': askbot_settings.MIN_REP_TO_VOTE_UP}
    else:
        min_rep_setting = askbot_settings.MIN_REP_TO_VOTE_DOWN
        low_rep_error_message = _(
                    ">%(points)s points required to downvote"
                ) % \
                {'points': askbot_settings.MIN_REP_TO_VOTE_DOWN}

    _assert_user_can(
        user = self,
        blocked_error_message = blocked_error_message,
        suspended_error_message = suspended_error_message,
        min_rep_setting = min_rep_setting,
        low_rep_error_message = low_rep_error_message
    )


def user_assert_can_upload_file(request_user):

    blocked_error_message = _('Sorry, blocked users cannot upload files')
    suspended_error_message = _('Sorry, suspended users cannot upload files')
    low_rep_error_message = _(
                        'sorry, file uploading requires karma >%(min_rep)s',
                    ) % {'min_rep': askbot_settings.MIN_REP_TO_UPLOAD_FILES }

    _assert_user_can(
        user = request_user,
        suspended_error_message = suspended_error_message,
        min_rep_setting = askbot_settings.MIN_REP_TO_UPLOAD_FILES,
        low_rep_error_message = low_rep_error_message
    )


def user_assert_can_post_text(self, text):
    """Raises exceptions.PermissionDenied, if user does not have
    privilege to post given text, depending on the contents
    """
    if re.search(URL_RE, text):
        min_rep = askbot_settings.MIN_REP_TO_SUGGEST_LINK
        if self.is_authenticated() and self.reputation < min_rep:
            message = _(
                'Could not post, because your karma is insufficient to publish links'
            )
            raise django_exceptions.PermissionDenied(message)


def user_assert_can_post_question(self):
    """raises exceptions.PermissionDenied with
    text that has the reason for the denial
    """

    blocked_message = get_i18n_message('BLOCKED_USERS_CANNOT_POST')
    suspended_message = get_i18n_message('SUSPENDED_USERS_CANNOT_POST')

    _assert_user_can(
            user = self,
            blocked_error_message = blocked_message,
            suspended_error_message = suspended_message
    )


def user_assert_can_post_answer(self, thread = None):
    """same as user_can_post_question
    """
    limit_answers = askbot_settings.LIMIT_ONE_ANSWER_PER_USER
    if limit_answers and thread.has_answer_by_user(self):
        message = _(
            'Sorry, you already gave an answer, please edit it instead.'
        )
        raise askbot_exceptions.AnswerAlreadyGiven(message)

    self.assert_can_post_question()


def user_assert_can_edit_comment(self, comment = None):
    """raises exceptions.PermissionDenied if user
    cannot edit comment with the reason given as message

    only owners, moderators or admins can edit comments
    """
    if self.is_administrator() or self.is_moderator():
        return
    else:
        if comment.author == self:
            if askbot_settings.USE_TIME_LIMIT_TO_EDIT_COMMENT:
                now = datetime.datetime.now()
                delta_seconds = 60 * askbot_settings.MINUTES_TO_EDIT_COMMENT
                if now - comment.added_at > datetime.timedelta(0, delta_seconds):
                    if comment.is_last():
                        return
                    error_message = ungettext(
                        'Sorry, comments (except the last one) are editable only '
                        'within %(minutes)s minute from posting',
                        'Sorry, comments (except the last one) are editable only '
                        'within %(minutes)s minutes from posting',
                        askbot_settings.MINUTES_TO_EDIT_COMMENT
                    ) % {'minutes': askbot_settings.MINUTES_TO_EDIT_COMMENT}
                    raise django_exceptions.PermissionDenied(error_message)
                return
            else:
                return

    error_message = _(
        'Sorry, but only post owners or moderators can edit comments'
    )
    raise django_exceptions.PermissionDenied(error_message)


def user_can_post_comment(self, parent_post = None):
    """a simplified method to test ability to comment
    """
    return True
    """
    #commented out to disable the min rep
    if self.reputation >= askbot_settings.MIN_REP_TO_LEAVE_COMMENTS:
        return True
    if parent_post and self == parent_post.author:
        return True
    if self.is_administrator_or_moderator():
        return True
    return False
    """


def user_assert_can_post_comment(self, parent_post = None):
    """raises exceptions.PermissionDenied if
    user cannot post comment

    the reason will be in text of exception
    """

    suspended_error_message = _(
                'Sorry, since your account is suspended '
                'you can comment only your own posts'
            )
    low_rep_error_message = _(
                'Sorry, to comment any post a minimum reputation of '
                '%(min_rep)s points is required. You can still comment '
                'your own posts and answers to your questions'
            ) % {'min_rep': 0}#askbot_settings.MIN_REP_TO_LEAVE_COMMENTS}

    blocked_message = get_i18n_message('BLOCKED_USERS_CANNOT_POST')

    try:
        _assert_user_can(
            user = self,
            post = parent_post,
            owner_can = True,
            blocked_error_message = blocked_message,
            suspended_error_message = suspended_error_message,
            min_rep_setting = 0,#askbot_settings.MIN_REP_TO_LEAVE_COMMENTS,
            low_rep_error_message = low_rep_error_message,
        )
    except askbot_exceptions.InsufficientReputation, e:
        if parent_post.post_type == 'answer':
            if self == parent_post.thread._question_post().author:
                return
        raise e

def user_assert_can_see_deleted_post(self, post = None):

    """attn: this assertion is independently coded in
    Question.get_answers call
    """

    error_message = _(
                        'This post has been deleted and can be seen only '
                        'by post owners, site administrators and moderators'
                    )
    _assert_user_can(
        user = self,
        post = post,
        admin_or_moderator_required = True,
        owner_can = True,
        general_error_message = error_message
    )

def user_assert_can_edit_deleted_post(self, post = None):
    assert(post.deleted == True)
    try:
        self.assert_can_see_deleted_post(post)
    except django_exceptions.PermissionDenied, e:
        error_message = _(
                    'Sorry, only moderators, site administrators '
                    'and post owners can edit deleted posts'
                )
        raise django_exceptions.PermissionDenied(error_message)

def user_assert_can_edit_post(self, post = None):
    """assertion that raises exceptions.PermissionDenied
    when user is not authorised to edit this post
    """

    if post.deleted == True:
        self.assert_can_edit_deleted_post(post)
        return


    blocked_error_message = _(
                'Sorry, since your account is blocked '
                'you cannot edit posts'
            )
    suspended_error_message = _(
                'Sorry, since your account is suspended '
                'you can edit only your own posts'
            )
    if post.wiki == True:
        low_rep_error_message = _(
                    'Sorry, to edit wiki posts, a minimum '
                    'reputation of %(min_rep)s is required'
                ) % \
                {'min_rep': askbot_settings.MIN_REP_TO_EDIT_WIKI}
        min_rep_setting = askbot_settings.MIN_REP_TO_EDIT_WIKI
    else:
        low_rep_error_message = _(
                    'Sorry, to edit other people\'s posts, a minimum '
                    'reputation of %(min_rep)s is required'
                ) % \
                {'min_rep': askbot_settings.MIN_REP_TO_EDIT_OTHERS_POSTS}
        min_rep_setting = askbot_settings.MIN_REP_TO_EDIT_OTHERS_POSTS

    _assert_user_can(
        user = self,
        post = post,
        owner_can = True,
        blocked_error_message = blocked_error_message,
        suspended_error_message = suspended_error_message,
        low_rep_error_message = low_rep_error_message,
        min_rep_setting = min_rep_setting,
    )


def user_assert_can_edit_question(self, question = None):
    assert getattr(question, 'post_type', '') == 'question'
    self.assert_can_edit_post(question)


def user_assert_can_edit_answer(self, answer = None):
    assert getattr(answer, 'post_type', '') == 'answer'
    self.assert_can_edit_post(answer)


def user_assert_can_delete_post(self, post = None):
    post_type = getattr(post, 'post_type', '')
    if post_type == 'question':
        self.assert_can_delete_question(question = post)
    elif post_type == 'answer':
        self.assert_can_delete_answer(answer = post)
    elif post_type == 'comment':
        self.assert_can_delete_comment(comment = post)
    else:
        raise ValueError('Invalid post_type!')

def user_assert_can_restore_post(self, post = None):
    """can_restore_rule is the same as can_delete
    """
    self.assert_can_delete_post(post = post)

def user_assert_can_delete_question(self, question = None):
    """rules are the same as to delete answer,
    except if question has answers already, when owner
    cannot delete unless s/he is and adinistrator or moderator
    """

    #cheating here. can_delete_answer wants argument named
    #"question", so the argument name is skipped
    self.assert_can_delete_answer(question)
    if self == question.get_owner():
        #if there are answers by other people,
        #then deny, unless user in admin or moderator
        answer_count = question.thread.all_answers()\
                        .exclude(author=self).exclude(points__lte=0).count()

        if answer_count > 0:
            if self.is_administrator() or self.is_moderator():
                return
            else:
                msg = ungettext(
                    'Sorry, cannot delete your question since it '
                    'has an upvoted answer posted by someone else',
                    'Sorry, cannot delete your question since it '
                    'has some upvoted answers posted by other users',
                    answer_count
                )
                raise django_exceptions.PermissionDenied(msg)


def user_assert_can_delete_answer(self, answer = None):
    """intentionally use "post" word in the messages
    instead of "answer", because this logic also applies to
    assert on deleting question (in addition to some special rules)
    """
    blocked_error_message = _(
                'Sorry, since your account is blocked '
                'you cannot delete posts'
            )
    suspended_error_message = _(
                'Sorry, since your account is suspended '
                'you can delete only your own posts'
            )
    low_rep_error_message = _(
                'Sorry, to delete other people\'s posts, a minimum '
                'reputation of %(min_rep)s is required'
            ) % \
            {'min_rep': askbot_settings.MIN_REP_TO_DELETE_OTHERS_POSTS}
    min_rep_setting = askbot_settings.MIN_REP_TO_DELETE_OTHERS_POSTS


    _assert_user_can(
        user = self,
        post = answer,
        owner_can = True,
        blocked_error_message = blocked_error_message,
        suspended_error_message = suspended_error_message,
        low_rep_error_message = low_rep_error_message,
        min_rep_setting = min_rep_setting,
    )


def user_assert_can_close_question(self, question = None):
    assert(getattr(question, 'post_type', '') == 'question')
    blocked_error_message = _(
                'Sorry, since your account is blocked '
                'you cannot close questions'
            )
    suspended_error_message = _(
                'Sorry, since your account is suspended '
                'you cannot close questions'
            )
    low_rep_error_message = _(
                'Sorry, to close other people\' posts, a minimum '
                'reputation of %(min_rep)s is required'
            ) % \
            {'min_rep': askbot_settings.MIN_REP_TO_CLOSE_OTHERS_QUESTIONS}
    min_rep_setting = askbot_settings.MIN_REP_TO_CLOSE_OTHERS_QUESTIONS

    owner_min_rep_setting =  askbot_settings.MIN_REP_TO_CLOSE_OWN_QUESTIONS

    owner_low_rep_error_message = _(
                        'Sorry, to close own question '
                        'a minimum reputation of %(min_rep)s is required'
                    ) % {'min_rep': owner_min_rep_setting}


    _assert_user_can(
        user = self,
        post = question,
        owner_can = True,
        suspended_owner_cannot = True,
        owner_min_rep_setting = owner_min_rep_setting,
        blocked_error_message = blocked_error_message,
        suspended_error_message = suspended_error_message,
        low_rep_error_message = low_rep_error_message,
        owner_low_rep_error_message = owner_low_rep_error_message,
        min_rep_setting = min_rep_setting,
    )


def user_assert_can_reopen_question(self, question = None):
    assert(question.post_type == 'question')

    #for some reason rep to reopen own questions != rep to close own q's
    owner_min_rep_setting =  askbot_settings.MIN_REP_TO_REOPEN_OWN_QUESTIONS
    min_rep_setting = askbot_settings.MIN_REP_TO_CLOSE_OTHERS_QUESTIONS

    general_error_message = _(
                        'Sorry, only administrators, moderators '
                        'or post owners with reputation > %(min_rep)s '
                        'can reopen questions.'
                    ) % {'min_rep': owner_min_rep_setting }

    owner_low_rep_error_message = _(
                        'Sorry, to reopen own question '
                        'a minimum reputation of %(min_rep)s is required'
                    ) % {'min_rep': owner_min_rep_setting}

    blocked_error_message = _(
            'Sorry, you cannot reopen questions '
            'because your account is blocked'
        )

    suspended_error_message = _(
            'Sorry, you cannot reopen questions '
            'because your account is suspended'
        )

    _assert_user_can(
        user = self,
        post = question,
        owner_can = True,
        suspended_owner_cannot = True,
        owner_min_rep_setting = owner_min_rep_setting,
        min_rep_setting = min_rep_setting,
        owner_low_rep_error_message = owner_low_rep_error_message,
        general_error_message = general_error_message,
        blocked_error_message = blocked_error_message,
        suspended_error_message = suspended_error_message
    )


def user_assert_can_flag_offensive(self, post = None):

    assert(post is not None)

    double_flagging_error_message = _(
        'You have flagged this question before and '
        'cannot do it more than once'
    )

    if self.get_flags_for_post(post).count() > 0:
        raise askbot_exceptions.DuplicateCommand(double_flagging_error_message)

    blocked_error_message = _(
        'Sorry, since your account is blocked '
        'you cannot flag posts as offensive'
    )

    suspended_error_message = _(
        'Sorry, your account appears to be suspended and you cannot make new posts '
        'until this issue is resolved. You can, however edit your existing posts. '
        'Please contact the forum administrator to reach a resolution.'
    )

    low_rep_error_message = _(
        'Sorry, to flag posts as offensive a minimum reputation '
        'of %(min_rep)s is required'
    ) % \
                        {'min_rep': askbot_settings.MIN_REP_TO_FLAG_OFFENSIVE}
    min_rep_setting = askbot_settings.MIN_REP_TO_FLAG_OFFENSIVE

    _assert_user_can(
        user = self,
        post = post,
        blocked_error_message = blocked_error_message,
        suspended_error_message = suspended_error_message,
        low_rep_error_message = low_rep_error_message,
        min_rep_setting = min_rep_setting
    )
    #one extra assertion
    if self.is_administrator() or self.is_moderator():
        return
    else:
        flag_count_today = self.get_flag_count_posted_today()
        if flag_count_today >= askbot_settings.MAX_FLAGS_PER_USER_PER_DAY:
            flags_exceeded_error_message = _(
                'Sorry, you have exhausted the maximum number of '
                '%(max_flags_per_day)s offensive flags per day.'
            ) % {
                    'max_flags_per_day': \
                    askbot_settings.MAX_FLAGS_PER_USER_PER_DAY
                }
            raise django_exceptions.PermissionDenied(flags_exceeded_error_message)

def user_assert_can_remove_flag_offensive(self, post = None):

    assert(post is not None)

    non_existing_flagging_error_message = _('cannot remove non-existing flag')

    if self.get_flags_for_post(post).count() < 1:
        raise django_exceptions.PermissionDenied(non_existing_flagging_error_message)

    blocked_error_message = _(
        'Sorry, since your account is blocked you cannot remove flags'
    )

    suspended_error_message = _(
        'Sorry, your account appears to be suspended and you cannot remove flags. '
        'Please contact the forum administrator to reach a resolution.'
    )

    min_rep_setting = askbot_settings.MIN_REP_TO_FLAG_OFFENSIVE
    low_rep_error_message = ungettext(
        'Sorry, to flag posts a minimum reputation of %(min_rep)d is required',
        'Sorry, to flag posts a minimum reputation of %(min_rep)d is required',
        min_rep_setting
    ) % {'min_rep': min_rep_setting}

    _assert_user_can(
        user = self,
        post = post,
        blocked_error_message = blocked_error_message,
        suspended_error_message = suspended_error_message,
        low_rep_error_message = low_rep_error_message,
        min_rep_setting = min_rep_setting
    )
    #one extra assertion
    if self.is_administrator() or self.is_moderator():
        return

def user_assert_can_remove_all_flags_offensive(self, post = None):
    assert(post is not None)
    permission_denied_message = _("you don't have the permission to remove all flags")
    non_existing_flagging_error_message = _('no flags for this entry')

    # Check if the post is flagged by anyone
    post_content_type = ContentType.objects.get_for_model(post)
    all_flags = Activity.objects.filter(
                        activity_type = const.TYPE_ACTIVITY_MARK_OFFENSIVE,
                        content_type = post_content_type, object_id=post.id
                    )
    if all_flags.count() < 1:
        raise django_exceptions.PermissionDenied(non_existing_flagging_error_message)
    #one extra assertion
    if self.is_administrator() or self.is_moderator():
        return
    else:
        raise django_exceptions.PermissionDenied(permission_denied_message)


def user_assert_can_retag_question(self, question = None):

    if question.deleted == True:
        try:
            self.assert_can_edit_deleted_post(question)
        except django_exceptions.PermissionDenied:
            error_message = _(
                            'Sorry, only question owners, '
                            'site administrators and moderators '
                            'can retag deleted questions'
                        )
            raise django_exceptions.PermissionDenied(error_message)


    blocked_error_message = _(
                'Sorry, since your account is blocked '
                'you cannot retag questions'
            )
    suspended_error_message = _(
                'Sorry, since your account is suspended '
                'you can retag only your own questions'
            )
    low_rep_error_message = _(
                'Sorry, to retag questions a minimum '
                'reputation of %(min_rep)s is required'
            ) % \
            {'min_rep': askbot_settings.MIN_REP_TO_RETAG_OTHERS_QUESTIONS}
    min_rep_setting = askbot_settings.MIN_REP_TO_RETAG_OTHERS_QUESTIONS

    _assert_user_can(
        user = self,
        post = question,
        owner_can = True,
        blocked_error_message = blocked_error_message,
        suspended_error_message = suspended_error_message,
        low_rep_error_message = low_rep_error_message,
        min_rep_setting = min_rep_setting,
    )


def user_assert_can_delete_comment(self, comment = None):
    blocked_error_message = _(
                'Sorry, since your account is blocked '
                'you cannot delete comment'
            )
    suspended_error_message = _(
                'Sorry, since your account is suspended '
                'you can delete only your own comments'
            )
    low_rep_error_message = _(
                'Sorry, to delete comments '
                'reputation of %(min_rep)s is required'
            ) % \
            {'min_rep': askbot_settings.MIN_REP_TO_DELETE_OTHERS_COMMENTS}
    min_rep_setting = askbot_settings.MIN_REP_TO_DELETE_OTHERS_COMMENTS


    _assert_user_can(
        user = self,
        post = comment,
        owner_can = True,
        blocked_error_message = blocked_error_message,
        suspended_error_message = suspended_error_message,
        low_rep_error_message = low_rep_error_message,
        min_rep_setting = min_rep_setting,
    )


def user_assert_can_revoke_old_vote(self, vote):
    """raises exceptions.PermissionDenied if old vote
    cannot be revoked due to age of the vote
    """
    if (datetime.datetime.now().day - vote.voted_at.day) \
        >= askbot_settings.MAX_DAYS_TO_CANCEL_VOTE:
        raise django_exceptions.PermissionDenied(
            _('sorry, but older votes cannot be revoked')
        )

def user_get_unused_votes_today(self):
    """returns number of votes that are
    still available to the user today
    """
    today = datetime.date.today()
    one_day_interval = (today, today + datetime.timedelta(1))

    used_votes = Vote.objects.filter(
                                user = self,
                                voted_at__range = one_day_interval
                            ).count()

    available_votes = askbot_settings.MAX_VOTES_PER_USER_PER_DAY - used_votes
    return max(0, available_votes)

def user_post_comment(
                    self,
                    parent_post = None,
                    body_text = None,
                    timestamp = None,
                    by_email = False
                ):
    """post a comment on behalf of the user
    to parent_post
    """

    if body_text is None:
        raise ValueError('body_text is required to post comment')
    if parent_post is None:
        raise ValueError('parent_post is required to post comment')
    if timestamp is None:
        timestamp = datetime.datetime.now()

    self.assert_can_post_comment(parent_post = parent_post)

    comment = parent_post.add_comment(
                    user = self,
                    comment = body_text,
                    added_at = timestamp,
                    by_email = by_email
                )
    comment.add_to_groups([self.get_personal_group()])

    parent_post.thread.invalidate_cached_data()
    award_badges_signal.send(
        None,
        event = 'post_comment',
        actor = self,
        context_object = comment,
        timestamp = timestamp
    )
    return comment

def user_post_object_description(
                    self,
                    obj=None,
                    body_text=None,
                    timestamp=None
                ):
    """Creates an object description post and assigns it
    to the given object. Returns the newly created post"""
    description_post = Post.objects.create_new_tag_wiki(
                                            author=self,
                                            text=body_text
                                        )
    obj.description = description_post
    obj.save()
    return description_post


def user_post_anonymous_askbot_content(user, session_key):
    """posts any posts added just before logging in
    the posts are identified by the session key, thus the second argument

    this function is used by the signal handler with a similar name
    """
    aq_list = AnonymousQuestion.objects.filter(session_key = session_key)
    aa_list = AnonymousAnswer.objects.filter(session_key = session_key)


    is_on_read_only_group = user.get_groups().filter(read_only=True).count()
    if is_on_read_only_group:
        user.message_set.create(message = _('Sorry, but you have only read access'))
    #from askbot.conf import settings as askbot_settings
    if askbot_settings.EMAIL_VALIDATION == True:#add user to the record
        for aq in aq_list:
            aq.author = user
            aq.save()
        for aa in aa_list:
            aa.author = user
            aa.save()
        #maybe add pending posts message?
    else:
        if user.is_blocked():
            msg = get_i18n_message('BLOCKED_USERS_CANNOT_POST')
            user.message_set.create(message = msg)
        elif user.is_suspended():
            msg = get_i18n_message('SUSPENDED_USERS_CANNOT_POST')
            user.message_set.create(message = msg)
        else:
            for aq in aq_list:
                aq.publish(user)
            for aa in aa_list:
                aa.publish(user)


def user_mark_tags(
            self,
            tagnames = None,
            wildcards = None,
            reason = None,
            action = None
        ):
    """subscribe for or ignore a list of tags

    * ``tagnames`` and ``wildcards`` are lists of
      pure tags and wildcard tags, respectively
    * ``reason`` - either "good" or "bad"
    * ``action`` - eitrer "add" or "remove"
    """
    cleaned_wildcards = list()
    assert(action in ('add', 'remove'))
    if action == 'add':
        if askbot_settings.SUBSCRIBED_TAG_SELECTOR_ENABLED:
            assert(reason in ('good', 'bad', 'subscribed'))
        else:
            assert(reason in ('good', 'bad'))
    if wildcards:
        cleaned_wildcards = self.update_wildcard_tag_selections(
            action = action,
            reason = reason,
            wildcards = wildcards
        )
    if tagnames is None:
        tagnames = list()

    #figure out which tags don't yet exist
    existing_tagnames = Tag.objects.filter(
                            name__in=tagnames
                        ).values_list(
                            'name', flat=True
                        )
    non_existing_tagnames = set(tagnames) - set(existing_tagnames)
    #create those tags, and if tags are moderated make them suggested
    if (len(non_existing_tagnames) > 0):
        Tag.objects.create_in_bulk(tag_names=tagnames, user=self)

    #below we update normal tag selections
    marked_ts = MarkedTag.objects.filter(
                                    user = self,
                                    tag__name__in = tagnames
                                )
    #Marks for "good" and "bad" reasons are exclusive,
    #to make it impossible to "like" and "dislike" something at the same time
    #but the subscribed set is independent - e.g. you can dislike a topic
    #and still subscribe for it.
    if reason == 'subscribed':
        #don't touch good/bad marks
        marked_ts = marked_ts.filter(reason = 'subscribed')
    else:
        #and in this case don't touch subscribed tags
        marked_ts = marked_ts.exclude(reason = 'subscribed')

    #todo: use the user api methods here instead of the straight ORM
    cleaned_tagnames = list() #those that were actually updated
    if action == 'remove':
        logging.debug('deleting tag marks: %s' % ','.join(tagnames))
        marked_ts.delete()
    else:
        marked_names = marked_ts.values_list('tag__name', flat = True)
        if len(marked_names) < len(tagnames):
            unmarked_names = set(tagnames).difference(set(marked_names))
            ts = Tag.objects.filter(name__in = unmarked_names)
            new_marks = list()
            for tag in ts:
                MarkedTag(
                    user = self,
                    reason = reason,
                    tag = tag
                ).save()
                new_marks.append(tag.name)
            cleaned_tagnames.extend(marked_names)
            cleaned_tagnames.extend(new_marks)
        else:
            if reason in ('good', 'bad'):#to maintain exclusivity of 'good' and 'bad'
                marked_ts.update(reason=reason)
            cleaned_tagnames = tagnames

    return cleaned_tagnames, cleaned_wildcards

@auto_now_timestamp
def user_retag_question(
                    self,
                    question = None,
                    tags = None,
                    timestamp = None,
                    silent = False
                ):
    self.assert_can_retag_question(question)
    question.thread.retag(
        retagged_by = self,
        retagged_at = timestamp,
        tagnames = tags,
        silent = silent
    )
    question.thread.invalidate_cached_data()
    award_badges_signal.send(None,
        event = 'retag_question',
        actor = self,
        context_object = question,
        timestamp = timestamp
    )

@auto_now_timestamp
def user_accept_best_answer(
                self, answer = None,
                timestamp = None,
                cancel = False,
                force = False
            ):
    if cancel:
        return self.unaccept_best_answer(
                                answer = answer,
                                timestamp = timestamp,
                                force = force
                            )
    if force == False:
        self.assert_can_accept_best_answer(answer)
    if answer.accepted() == True:
        return

    prev_accepted_answer = answer.thread.accepted_answer
    if prev_accepted_answer:
        auth.onAnswerAcceptCanceled(prev_accepted_answer, self)

    auth.onAnswerAccept(answer, self, timestamp = timestamp)
    award_badges_signal.send(None,
        event = 'accept_best_answer',
        actor = self,
        context_object = answer,
        timestamp = timestamp
    )

@auto_now_timestamp
def user_unaccept_best_answer(
                self, answer = None,
                timestamp = None,
                force = False
            ):
    if force == False:
        self.assert_can_unaccept_best_answer(answer)
    if not answer.accepted():
        return
    auth.onAnswerAcceptCanceled(answer, self)

@auto_now_timestamp
def user_delete_comment(
                    self,
                    comment = None,
                    timestamp = None
                ):
    self.assert_can_delete_comment(comment = comment)
    #todo: we want to do this
    #comment.deleted = True
    #comment.deleted_by = self
    #comment.deleted_at = timestamp
    #comment.save()
    comment.delete()
    comment.thread.invalidate_cached_data()

@auto_now_timestamp
def user_delete_answer(
                    self,
                    answer = None,
                    timestamp = None
                ):
    self.assert_can_delete_answer(answer = answer)
    answer.deleted = True
    answer.deleted_by = self
    answer.deleted_at = timestamp
    answer.save()

    answer.thread.update_answer_count()
    answer.thread.invalidate_cached_data()
    logging.debug('updated answer count to %d' % answer.thread.answer_count)

    signals.delete_question_or_answer.send(
        sender = answer.__class__,
        instance = answer,
        delete_by = self
    )
    award_badges_signal.send(None,
                event = 'delete_post',
                actor = self,
                context_object = answer,
                timestamp = timestamp
            )


@auto_now_timestamp
def user_delete_question(
                    self,
                    question = None,
                    timestamp = None
                ):
    self.assert_can_delete_question(question = question)

    question.deleted = True
    question.deleted_by = self
    question.deleted_at = timestamp
    question.save()

    question.thread.deleted = True
    question.thread.save()

    for tag in list(question.thread.tags.all()):
        if tag.used_count == 1:
            tag.deleted = True
            tag.deleted_by = self
            tag.deleted_at = timestamp
        else:
            tag.used_count = tag.used_count - 1
        tag.save()

    signals.delete_question_or_answer.send(
        sender = question.__class__,
        instance = question,
        delete_by = self
    )
    award_badges_signal.send(None,
                event = 'delete_post',
                actor = self,
                context_object = question,
                timestamp = timestamp
            )


@auto_now_timestamp
def user_close_question(
                    self,
                    question = None,
                    reason = None,
                    timestamp = None
                ):
    self.assert_can_close_question(question)
    question.thread.set_closed_status(closed=True, closed_by=self, closed_at=timestamp, close_reason=reason)

@auto_now_timestamp
def user_reopen_question(
                    self,
                    question = None,
                    timestamp = None
                ):
    self.assert_can_reopen_question(question)
    question.thread.set_closed_status(closed=False, closed_by=self, closed_at=timestamp, close_reason=None)

@auto_now_timestamp
def user_delete_post(
                    self,
                    post = None,
                    timestamp = None
                ):
    """generic delete method for all kinds of posts

    if there is no use cases for it, the method will be removed
    """
    if post.post_type == 'comment':
        self.delete_comment(comment = post, timestamp = timestamp)
    elif post.post_type == 'answer':
        self.delete_answer(answer = post, timestamp = timestamp)
    elif post.post_type == 'question':
        self.delete_question(question = post, timestamp = timestamp)
    else:
        raise TypeError('either Comment, Question or Answer expected')
    post.thread.invalidate_cached_data()

def user_restore_post(
                    self,
                    post = None,
                    timestamp = None
                ):
    #here timestamp is not used, I guess added for consistency
    self.assert_can_restore_post(post)
    if post.post_type in ('question', 'answer'):
        post.deleted = False
        post.deleted_by = None
        post.deleted_at = None
        post.save()
        post.thread.invalidate_cached_data()
        if post.post_type == 'answer':
            post.thread.update_answer_count()
        else:
            #todo: make sure that these tags actually exist
            #some may have since been deleted for good
            #or merged into others
            for tag in list(post.thread.tags.all()):
                if tag.used_count == 1 and tag.deleted:
                    tag.deleted = False
                    tag.deleted_by = None
                    tag.deleted_at = None
                    tag.save()
    else:
        raise NotImplementedError()

def user_post_question(
                    self,
                    title = None,
                    body_text = '',
                    tags = None,
                    wiki = False,
                    is_anonymous = False,
                    is_private = False,
                    group_id = None,
                    timestamp = None,
                    by_email = False,
                    email_address = None,
                    language = None
                ):
    """makes an assertion whether user can post the question
    then posts it and returns the question object"""

    self.assert_can_post_question()

    if body_text == '':#a hack to allow bodyless question
        body_text = ' '

    if title is None:
        raise ValueError('Title is required to post question')
    if tags is None:
        raise ValueError('Tags are required to post question')
    if timestamp is None:
        timestamp = datetime.datetime.now()

    #todo: split this into "create thread" + "add question", if text exists
    #or maybe just add a blank question post anyway
    thread = Thread.objects.create_new(
                                    author=self,
                                    title=title,
                                    text=body_text,
                                    tagnames=tags,
                                    added_at=timestamp,
                                    wiki=wiki,
                                    is_anonymous=is_anonymous,
                                    is_private=is_private,
                                    group_id=group_id,
                                    by_email=by_email,
                                    email_address=email_address,
                                    language=language
                                )
    question = thread._question_post()
    if question.author != self:
        raise ValueError('question.author != self')
    question.author = self # HACK: Some tests require that question.author IS exactly the same object as self-user (kind of identity map which Django doesn't provide),
                           #       because they set some attributes for that instance and expect them to be changed also for question.author

    if askbot_settings.AUTO_FOLLOW_QUESTION_BY_OP:
        self.toggle_favorite_question(question)

    return question

@auto_now_timestamp
def user_edit_comment(
                    self,
                    comment_post=None,
                    body_text=None,
                    timestamp=None,
                    by_email=False,
                    suppress_email=False
                ):
    """apply edit to a comment, the method does not
    change the comments timestamp and no signals are sent
    todo: see how this can be merged with edit_post
    todo: add timestamp
    """
    self.assert_can_edit_comment(comment_post)
    comment_post.apply_edit(
                        text=body_text,
                        edited_at=timestamp,
                        edited_by=self,
                        by_email=by_email,
                        suppress_email=suppress_email
                    )
    comment_post.thread.invalidate_cached_data()

def user_edit_post(self,
                post=None,
                body_text=None,
                revision_comment=None,
                timestamp=None,
                by_email=False,
                is_private=False,
                suppress_email=False,
            ):
    """a simple method that edits post body
    todo: unify it in the style of just a generic post
    this requires refactoring of underlying functions
    because we cannot bypass the permissions checks set within
    """
    if post.post_type == 'comment':
        self.edit_comment(
                comment_post=post,
                body_text=body_text,
                by_email=by_email,
                suppress_email=suppress_email
            )
    elif post.post_type == 'answer':
        self.edit_answer(
            answer=post,
            body_text=body_text,
            timestamp=timestamp,
            revision_comment=revision_comment,
            by_email=by_email,
            suppress_email=suppress_email
        )
    elif post.post_type == 'question':
        self.edit_question(
            question=post,
            body_text=body_text,
            timestamp=timestamp,
            revision_comment=revision_comment,
            by_email=by_email,
            is_private=is_private,
            suppress_email=suppress_email,
        )
    elif post.post_type == 'tag_wiki':
        post.apply_edit(
            edited_at=timestamp,
            edited_by=self,
            text=body_text,
            #todo: summary name clash in question and question revision
            comment=revision_comment,
            wiki=True,
            by_email=False
        )
    else:
        raise NotImplementedError()

@auto_now_timestamp
def user_edit_question(
                self,
                question=None,
                title=None,
                body_text=None,
                revision_comment=None,
                tags=None,
                wiki=False,
                edit_anonymously=False,
                is_private=False,
                timestamp=None,
                force=False,#if True - bypass the assert
                by_email=False,
                suppress_email=False
            ):
    if force == False:
        self.assert_can_edit_question(question)

    question.apply_edit(
        edited_at = timestamp,
        edited_by = self,
        title = title,
        text = body_text,
        #todo: summary name clash in question and question revision
        comment = revision_comment,
        tags = tags,
        wiki = wiki,
        edit_anonymously = edit_anonymously,
        is_private = is_private,
        by_email = by_email,
        suppress_email=suppress_email
    )

    question.thread.invalidate_cached_data()

    award_badges_signal.send(None,
        event = 'edit_question',
        actor = self,
        context_object = question,
        timestamp = timestamp
    )

@auto_now_timestamp
def user_edit_answer(
                    self,
                    answer=None,
                    body_text=None,
                    revision_comment=None,
                    wiki=False,
                    is_private=False,
                    timestamp=None,
                    force=False,#if True - bypass the assert
                    by_email=False,
                    suppress_email=False,
                ):
    if force == False:
        self.assert_can_edit_answer(answer)

    answer.apply_edit(
        edited_at=timestamp,
        edited_by=self,
        text=body_text,
        comment=revision_comment,
        wiki=wiki,
        is_private=is_private,
        by_email=by_email,
        suppress_email=suppress_email
    )

    answer.thread.invalidate_cached_data()
    award_badges_signal.send(None,
        event = 'edit_answer',
        actor = self,
        context_object = answer,
        timestamp = timestamp
    )

@auto_now_timestamp
def user_create_post_reject_reason(
    self, title = None, details = None, timestamp = None
):
    """creates and returs the post reject reason"""
    reason = PostFlagReason(
        title = title,
        added_at = timestamp,
        author = self
    )

    #todo - need post_object.create_new() method
    details = Post(
        post_type = 'reject_reason',
        author = self,
        added_at = timestamp,
        text = details
    )
    details.parse_and_save(author=self)
    details.add_revision(
        author = self,
        revised_at = timestamp,
        text = details,
        comment = unicode(const.POST_STATUS['default_version'])
    )

    reason.details = details
    reason.save()
    return reason

@auto_now_timestamp
def user_edit_post_reject_reason(
    self, reason, title = None, details = None, timestamp = None
):
    reason.title = title
    reason.save()
    reason.details.apply_edit(
        edited_by = self,
        edited_at = timestamp,
        text = details
    )

def user_post_answer(
                    self,
                    question = None,
                    body_text = None,
                    follow = False,
                    wiki = False,
                    is_private = False,
                    timestamp = None,
                    by_email = False
                ):

    #todo: move this to assertion - user_assert_can_post_answer
    if self == question.author and not self.is_administrator():

        # check date and rep required to post answer to own question

        delta = datetime.timedelta(askbot_settings.MIN_DAYS_TO_ANSWER_OWN_QUESTION)

        now = datetime.datetime.now()
        asked = question.added_at
        #todo: this is an assertion, must be moved out
        if (now - asked  < delta and self.reputation < askbot_settings.MIN_REP_TO_ANSWER_OWN_QUESTION):
            diff = asked + delta - now
            days = diff.days
            hours = int(diff.seconds/3600)
            minutes = int(diff.seconds/60)

            if days > 2:
                if asked.year == now.year:
                    date_token = asked.strftime("%b %d")
                else:
                    date_token = asked.strftime("%b %d '%y")
                left = _('on %(date)s') % { 'date': date_token }
            elif days == 2:
                left = _('in two days')
            elif days == 1:
                left = _('tomorrow')
            elif minutes >= 60:
                left = ungettext('in %(hr)d hour','in %(hr)d hours',hours) % {'hr':hours}
            else:
                left = ungettext('in %(min)d min','in %(min)d mins',minutes) % {'min':minutes}
            day = ungettext('%(days)d day','%(days)d days',askbot_settings.MIN_DAYS_TO_ANSWER_OWN_QUESTION) % {'days':askbot_settings.MIN_DAYS_TO_ANSWER_OWN_QUESTION}
            error_message = _(
                'New users must wait %(days)s before answering their own question. '
                ' You can post an answer %(left)s'
                ) % {'days': day,'left': left}
            assert(error_message is not None)
            raise django_exceptions.PermissionDenied(error_message)

    self.assert_can_post_answer(thread = question.thread)

    if getattr(question, 'post_type', '') != 'question':
        raise TypeError('question argument must be provided')
    if body_text is None:
        raise ValueError('Body text is required to post answer')
    if timestamp is None:
        timestamp = datetime.datetime.now()
#    answer = Answer.objects.create_new(
#        thread = question.thread,
#        author = self,
#        text = body_text,
#        added_at = timestamp,
#        email_notify = follow,
#        wiki = wiki
#    )
    answer_post = Post.objects.create_new_answer(
        thread = question.thread,
        author = self,
        text = body_text,
        added_at = timestamp,
        email_notify = follow,
        wiki = wiki,
        is_private = is_private,
        by_email = by_email
    )
    #add to the answerer's group
    answer_post.add_to_groups([self.get_personal_group()])

    answer_post.thread.invalidate_cached_data()
    award_badges_signal.send(None,
        event = 'post_answer',
        actor = self,
        context_object = answer_post
    )
    return answer_post

def user_visit_question(self, question = None, timestamp = None):
    """create a QuestionView record
    on behalf of the user represented by the self object
    and mark it as taking place at timestamp time

    and remove pending on-screen notifications about anything in
    the post - question, answer or comments
    """
    if timestamp is None:
        timestamp = datetime.datetime.now()

    try:
        QuestionView.objects.filter(
            who=self, question=question
        ).update(
            when = timestamp
        )
    except QuestionView.DoesNotExist:
        QuestionView(
            who=self,
            question=question,
            when = timestamp
        ).save()

    #filter memo objects on response activities directed to the qurrent user
    #that refer to the children of the currently
    #viewed question and clear them for the current user
    ACTIVITY_TYPES = const.RESPONSE_ACTIVITY_TYPES_FOR_DISPLAY
    ACTIVITY_TYPES += (const.TYPE_ACTIVITY_MENTION,)

    audit_records = ActivityAuditStatus.objects.filter(
                        user = self,
                        status = ActivityAuditStatus.STATUS_NEW,
                        activity__question = question
                    )

    cleared_record_count = audit_records.filter(
                                activity__activity_type__in = ACTIVITY_TYPES
                            ).update(
                                status=ActivityAuditStatus.STATUS_SEEN
                            )
    if cleared_record_count > 0:
        self.update_response_counts()

    #finally, mark admin memo objects if applicable
    #the admin response counts are not denormalized b/c they are easy to obtain
    if self.is_moderator() or self.is_administrator():
        audit_records.filter(
                activity__activity_type = const.TYPE_ACTIVITY_MARK_OFFENSIVE
        ).update(
            status=ActivityAuditStatus.STATUS_SEEN
        )


def user_is_username_taken(cls,username):
    try:
        cls.objects.get(username=username)
        return True
    except cls.MultipleObjectsReturned:
        return True
    except cls.DoesNotExist:
        return False

def user_is_administrator(self):
    """checks whether user in the forum site administrator
    the admin must be both superuser and staff member
    the latter is because staff membership is required
    to access the live settings"""
    return (self.is_superuser and self.is_staff)

def user_remove_admin_status(self):
    self.is_staff = False
    self.is_superuser = False

def user_set_admin_status(self):
    self.is_staff = True
    self.is_superuser = True

def user_add_missing_askbot_subscriptions(self):
    from askbot import forms#need to avoid circular dependency
    form = forms.EditUserEmailFeedsForm()
    need_feed_types = form.get_db_model_subscription_type_names()
    have_feed_types = EmailFeedSetting.objects.filter(
                                            subscriber = self
                                        ).values_list(
                                            'feed_type', flat = True
                                        )
    missing_feed_types = set(need_feed_types) - set(have_feed_types)
    for missing_feed_type in missing_feed_types:
        attr_key = 'DEFAULT_NOTIFICATION_DELIVERY_SCHEDULE_%s' % missing_feed_type.upper()
        freq = getattr(askbot_settings, attr_key)
        feed_setting = EmailFeedSetting(
                            subscriber = self,
                            feed_type = missing_feed_type,
                            frequency = freq
                        )
        feed_setting.save()

def user_is_moderator(self):
    return (self.status == 'm' and self.is_administrator() == False)

def user_is_post_moderator(self, post):
    """True, if user and post have common groups
    with moderation privilege"""
    if askbot_settings.GROUPS_ENABLED:
        group_ids = self.get_groups().values_list('id', flat=True)
        post_groups = PostToGroup.objects.filter(post=post, group__id__in=group_ids)
        return post_groups.filter(group__is_vip=True).count() > 0
    else:
        return False

def user_is_administrator_or_moderator(self):
    return (self.is_administrator() or self.is_moderator())

def user_is_suspended(self):
    return (self.status == 's')

def user_is_blocked(self):
    return (self.status == 'b')

def user_is_watched(self):
    return (self.status == 'w')

def user_is_approved(self):
    return (self.status == 'a')

def user_is_owner_of(self, obj):
    """True if user owns object
    False otherwise
    """
    if isinstance(obj, Post) and obj.post_type == 'question':
        return self == obj.author
    else:
        raise NotImplementedError()

def get_name_of_anonymous_user():
    """Returns name of the anonymous user
    either comes from the live settyngs or the language
    translation

    very possible that this function does not belong here
    """
    if askbot_settings.NAME_OF_ANONYMOUS_USER:
        return askbot_settings.NAME_OF_ANONYMOUS_USER
    else:
        return _('Anonymous')

def user_get_anonymous_name(self):
    """Returns name of anonymous user
    - convinience method for use in the template
    macros that accept user as parameter
    """
    return get_name_of_anonymous_user()

def user_set_status(self, new_status):
    """sets new status to user

    this method understands that administrator status is
    stored in the User.is_superuser field, but
    everything else in User.status field

    there is a slight aberration - administrator status
    can be removed, but not added yet

    if new status is applied to user, then the record is
    committed to the database
    """
    #d - administrator
    #m - moderator
    #s - suspended
    #b - blocked
    #w - watched
    #a - approved (regular user)
    assert(new_status in ('d', 'm', 's', 'b', 'w', 'a'))
    if new_status == self.status:
        return

    #clear admin status if user was an administrator
    #because this function is not dealing with the site admins

    if new_status == 'd':
        #create a new admin
        self.set_admin_status()
    else:
        #This was the old method, kept in the else clause when changing
        #to admin, so if you change the status to another thing that
        #is not Administrator it will simply remove admin if the user have
        #that permission, it will mostly be false.
        if self.is_administrator():
            self.remove_admin_status()

    #when toggling between blocked and non-blocked status
    #we need to invalidate question page caches, b/c they contain
    #user's url, which must be hidden in the blocked state
    if 'b' in (new_status, self.status) and new_status != self.status:
        threads = Thread.objects.get_for_user(self)
        for thread in threads:
            thread.invalidate_cached_post_data()

    self.status = new_status
    self.save()

@auto_now_timestamp
def user_moderate_user_reputation(
                                self,
                                user = None,
                                reputation_change = 0,
                                comment = None,
                                timestamp = None
                            ):
    """add or subtract reputation of other user
    """
    if reputation_change == 0:
        return
    if comment == None:
        raise ValueError('comment is required to moderate user reputation')

    new_rep = user.reputation + reputation_change
    if new_rep < 1:
        new_rep = 1 #todo: magic number
        reputation_change = 1 - user.reputation

    user.reputation = new_rep
    user.save()

    #any question. This is necessary because reputes are read in the
    #user_reputation view with select_related('question__title') and it fails if
    #ForeignKey is nullable even though it should work (according to the manual)
    #probably a bug in the Django ORM
    #fake_question = Question.objects.all()[:1][0]
    #so in cases where reputation_type == 10
    #question record is fake and is ignored
    #this bug is hidden in call Repute.get_explanation_snippet()
    repute = Repute(
                        user = user,
                        comment = comment,
                        #question = fake_question,
                        reputed_at = timestamp,
                        reputation_type = 10, #todo: fix magic number
                        reputation = user.reputation
                    )
    if reputation_change < 0:
        repute.negative = -1 * reputation_change
    else:
        repute.positive = reputation_change
    repute.save()

def user_get_status_display(self, soft = False):
    if self.is_administrator():
        return _('Site Adminstrator')
    elif self.is_moderator():
        return _('Forum Moderator')
    elif self.is_suspended():
        return  _('Suspended User')
    elif self.is_blocked():
        return _('Blocked User')
    elif soft == True:
        return _('Registered User')
    elif self.is_watched():
        return _('Watched User')
    elif self.is_approved():
        return _('Approved User')
    else:
        raise ValueError('Unknown user status')


def user_can_moderate_user(self, other):
    if self.is_administrator():
        return True
    elif self.is_moderator():
        if other.is_moderator() or other.is_administrator():
            return False
        else:
            return True
    else:
        return False


def user_get_followed_question_alert_frequency(self):
    feed_setting, created = EmailFeedSetting.objects.get_or_create(
                                    subscriber=self,
                                    feed_type='q_sel'
                                )
    return feed_setting.frequency

def user_subscribe_for_followed_question_alerts(self):
    """turns on daily subscription for selected questions
    otherwise does nothing

    Returns ``True`` if the subscription was turned on and
    ``False`` otherwise
    """
    feed_setting, created = EmailFeedSetting.objects.get_or_create(
                                                        subscriber = self,
                                                        feed_type = 'q_sel'
                                                    )
    if feed_setting.frequency == 'n':
        feed_setting.frequency = 'd'
        feed_setting.save()
        return True
    return False

def user_get_tag_filtered_questions(self, questions = None):
    """Returns a query set of questions, tag filtered according
    to the user choices. Parameter ``questions`` can be either ``None``
    or a starting query set.
    """
    if questions is None:
        questions = Post.objects.get_questions()

    if self.email_tag_filter_strategy == const.EXCLUDE_IGNORED:

        ignored_tags = Tag.objects.filter(
                                user_selections__reason = 'bad',
                                user_selections__user = self
                            )

        wk = self.ignored_tags.strip().split()
        ignored_by_wildcards = Tag.objects.get_by_wildcards(wk)

        return questions.exclude(
                        thread__tags__in = ignored_tags
                    ).exclude(
                        thread__tags__in = ignored_by_wildcards
                    ).distinct()
    elif self.email_tag_filter_strategy == const.INCLUDE_INTERESTING:
        if askbot_settings.SUBSCRIBED_TAG_SELECTOR_ENABLED:
            reason = 'subscribed'
            wk = self.subscribed_tags.strip().split()
        else:
            reason = 'good'
            wk = self.interesting_tags.strip().split()

        selected_tags = Tag.objects.filter(
                                user_selections__reason = reason,
                                user_selections__user = self
                            )

        selected_by_wildcards = Tag.objects.get_by_wildcards(wk)

        tag_filter = models.Q(thread__tags__in = list(selected_tags)) \
                    | models.Q(thread__tags__in = list(selected_by_wildcards))

        return questions.filter( tag_filter ).distinct()
    else:
        return questions

def get_messages(self):
    messages = []
    for m in self.message_set.all():
        messages.append(m.message)
    return messages

def delete_messages(self):
    self.message_set.all().delete()

#todo: find where this is used and replace with get_absolute_url
def user_get_profile_url(self, profile_section=None):
    """Returns the URL for this User's profile."""
    url = reverse(
            'user_profile',
            kwargs={'id':self.id, 'slug':slugify(self.username)}
        )
    if profile_section:
        url += "?sort=" + profile_section
    return url

def user_get_absolute_url(self):
    return self.get_profile_url()

def user_get_primary_language(self):
    if getattr(django_settings, 'ASKBOT_MULTILINGUAL', False):
        return django_settings.LANGUAGE_CODE
    else:
        return self.languages.split()[0]

def get_profile_link(self):
    profile_link = u'<a href="%s">%s</a>' \
        % (self.get_profile_url(), escape(self.username))

    return mark_safe(profile_link)

def user_get_groups(self, private=False):
    """returns a query set of groups to which user belongs"""
    #todo: maybe cache this query
    return Group.objects.get_for_user(self, private=private)

def user_get_personal_group(self):
    group_name = format_personal_group_name(self)
    return Group.objects.get(name=group_name)

def user_get_foreign_groups(self):
    """returns a query set of groups to which user does not belong"""
    #todo: maybe cache this query
    user_group_ids = self.get_groups().values_list('id', flat = True)
    return Group.objects.exclude(id__in = user_group_ids)

def user_get_primary_group(self):
    """a temporary function - returns ether None or
    first non-personal non-everyone group
    works only for one real private group per-person
    """
    groups = self.get_groups(private=True)
    for group in groups:
        if group.is_personal():
            continue
        return group
    return None

def user_can_make_group_private_posts(self):
    """simplest implementation: user belongs to at least one group"""
    return (self.get_primary_group() != None)

def user_get_group_membership(self, group):
    """returns a group membership object or None
    if it is not there
    """
    try:
        return GroupMembership.objects.get(user=self, group=group)
    except GroupMembership.DoesNotExist:
        return None


def user_get_groups_membership_info(self, groups):
    """returns a defaultdict with values that are
    dictionaries with the following keys and values:
    * key: acceptance_level, value: 'closed', 'moderated', 'open'
    * key: membership_level, value: 'none', 'pending', 'full'

    ``groups`` is a group tag query set
    """
    group_ids = groups.values_list('id', flat = True)
    memberships = GroupMembership.objects.filter(
                                user__id = self.id,
                                group__id__in = group_ids
                            )

    info = collections.defaultdict(
        lambda: {'acceptance_level': 'closed', 'membership_level': 'none'}
    )
    for membership in memberships:
        membership_level = membership.get_level_display()
        info[membership.group_id]['membership_level'] = membership_level

    for group in groups:
        info[group.id]['acceptance_level'] = group.get_openness_level_for_user(self)

    return info

def user_get_karma_summary(self):
    """returns human readable sentence about
    status of user's karma"""
    return _("%(username)s karma is %(reputation)s") % \
            {'username': self.username, 'reputation': self.reputation}

def user_get_badge_summary(self):
    """returns human readable sentence about
    number of badges of different levels earned
    by the user. It is assumed that user has some badges"""
    if self.gold + self.silver + self.bronze == 0:
        return ''

    badge_bits = list()
    if self.gold:
        bit = ungettext(
                'one gold badge',
                '%(count)d gold badges',
                self.gold
            ) % {'count': self.gold}
        badge_bits.append(bit)
    if self.silver:
        bit = ungettext(
                'one silver badge',
                '%(count)d silver badges',
                self.silver
            ) % {'count': self.silver}
        badge_bits.append(bit)
    if self.bronze:
        bit = ungettext(
                'one bronze badge',
                '%(count)d bronze badges',
                self.bronze
            ) % {'count': self.bronze}
        badge_bits.append(bit)

    if len(badge_bits) == 1:
        badge_str = badge_bits[0]
    elif len(badge_bits) > 1:
        last_bit = badge_bits.pop()
        badge_str = ', '.join(badge_bits)
        badge_str = _('%(item1)s and %(item2)s') % \
                    {'item1': badge_str, 'item2': last_bit}
    return _("%(user)s has %(badges)s") % {'user': self.username, 'badges':badge_str}

#series of methods for user vote-type commands
#same call signature func(self, post, timestamp=None, cancel=None)
#note that none of these have business logic checks internally
#these functions are used by the askbot app and
#by the data importer jobs from say stackexchange, where internal rules
#may be different
#maybe if we do use business rule checks here - we should add
#some flag allowing to bypass them for things like the data importers
def toggle_favorite_question(
                        self, question,
                        timestamp = None,
                        cancel = False,
                        force = False#this parameter is not used yet
                    ):
    """cancel has no effect here, but is important for the SE loader
    it is hoped that toggle will work and data will be consistent
    but there is no guarantee, maybe it's better to be more strict
    about processing the "cancel" option
    another strange thing is that this function unlike others below
    returns a value

    todo: the on-screen follow and email subscription is not
    fully merged yet - see use of FavoriteQuestion and follow/unfollow question
    btw, names of the objects/methods is quite misleading ATM
    """
    try:
        #this attempts to remove the on-screen follow
        fave = FavoriteQuestion.objects.get(thread=question.thread, user=self)
        fave.delete()
        result = False
        question.thread.update_favorite_count()
        #this removes email subscription
        if question.thread.is_followed_by(self):
            self.unfollow_question(question)

    except FavoriteQuestion.DoesNotExist:
        if timestamp is None:
            timestamp = datetime.datetime.now()
        fave = FavoriteQuestion(
            thread = question.thread,
            user = self,
            added_at = timestamp,
        )
        fave.save()

        #this removes email subscription
        if question.thread.is_followed_by(self) is False:
            self.follow_question(question)

        result = True
        question.thread.update_favorite_count()
        award_badges_signal.send(None,
            event = 'select_favorite_question',
            actor = self,
            context_object = question,
            timestamp = timestamp
        )
    return result

VOTES_TO_EVENTS = {
    (Vote.VOTE_UP, 'answer'): 'upvote_answer',
    (Vote.VOTE_UP, 'question'): 'upvote_question',
    (Vote.VOTE_DOWN, 'question'): 'downvote',
    (Vote.VOTE_DOWN, 'answer'): 'downvote',
    (Vote.VOTE_UP, 'comment'): 'upvote_comment',
}
@auto_now_timestamp
def _process_vote(user, post, timestamp=None, cancel=False, vote_type=None):
    """"private" wrapper function that applies post upvotes/downvotes
    and cancelations
    """
    #get or create the vote object
    #return with noop in some situations
    try:
        vote = Vote.objects.get(user = user, voted_post=post)
    except Vote.DoesNotExist:
        vote = None
    if cancel:
        if vote == None:
            return
        elif vote.is_opposite(vote_type):
            return
        else:
            #we would call vote.delete() here
            #but for now all that is handled by the
            #legacy askbot.auth functions
            #vote.delete()
            pass
    else:
        if vote == None:
            vote = Vote(
                    user = user,
                    voted_post=post,
                    vote = vote_type,
                    voted_at = timestamp,
                )
        elif vote.is_opposite(vote_type):
            vote.vote = vote_type
        else:
            return

    #do the actual work
    if vote_type == Vote.VOTE_UP:
        if cancel:
            auth.onUpVotedCanceled(vote, post, user, timestamp)
        else:
            auth.onUpVoted(vote, post, user, timestamp)
    elif vote_type == Vote.VOTE_DOWN:
        if cancel:
            auth.onDownVotedCanceled(vote, post, user, timestamp)
        else:
            auth.onDownVoted(vote, post, user, timestamp)

    post.thread.invalidate_cached_data()

    if post.post_type == 'question':
        #denormalize the question post score on the thread
        post.thread.points = post.points
        post.thread.save()
        post.thread.update_summary_html()

    if cancel:
        return None

    event = VOTES_TO_EVENTS.get((vote_type, post.post_type), None)
    if event:
        award_badges_signal.send(None,
                    event = event,
                    actor = user,
                    context_object = post,
                    timestamp = timestamp
                )
    return vote

def user_fix_html_links(self, text):
    """depending on the user's privilege, allow links
    and hotlinked images or replace them with plain text
    url
    """
    is_simple_user = not self.is_administrator_or_moderator()
    has_low_rep = self.reputation < askbot_settings.MIN_REP_TO_INSERT_LINK
    if is_simple_user and has_low_rep:
        result = replace_links_with_text(text)
        if result != text:
            message = ungettext(
                'At least %d karma point is required to post links',
                'At least %d karma points is required to post links',
                askbot_settings.MIN_REP_TO_INSERT_LINK
            ) % askbot_settings.MIN_REP_TO_INSERT_LINK
            self.message_set.create(message=message)
        return result
    return text

def user_unfollow_question(self, question = None):
    self.followed_threads.remove(question.thread)

def user_follow_question(self, question = None):
    self.followed_threads.add(question.thread)

def user_is_following_question(user, question):
    """True if user is following a question"""
    return question.thread.followed_by.filter(id=user.id).exists()


def upvote(self, post, timestamp=None, cancel=False, force = False):
    #force parameter not used yet
    return _process_vote(
        self,
        post,
        timestamp=timestamp,
        cancel=cancel,
        vote_type=Vote.VOTE_UP
    )

def downvote(self, post, timestamp=None, cancel=False, force = False):
    #force not used yet
    return _process_vote(
        self,
        post,
        timestamp=timestamp,
        cancel=cancel,
        vote_type=Vote.VOTE_DOWN
    )

@auto_now_timestamp
def user_approve_post_revision(user, post_revision, timestamp = None):
    """approves the post revision and, if necessary,
    the parent post and threads"""
    user.assert_can_approve_post_revision()

    post_revision.approved = True
    post_revision.approved_by = user
    post_revision.approved_at = timestamp

    post_revision.save()

    post = post_revision.post
    post.approved = True
    post.save()

    if post_revision.post.post_type == 'question':
        thread = post.thread
        thread.approved = True
        thread.save()
    post.thread.invalidate_cached_data()

    #send the signal of published revision
    signals.post_revision_published.send(
        None, revision = post_revision, was_approved = True
    )

@auto_now_timestamp
def flag_post(
    user, post, timestamp=None, cancel=False, cancel_all=False, force=False
):
    if cancel_all:
        # remove all flags
        if force == False:
            user.assert_can_remove_all_flags_offensive(post=post)
        post_content_type = ContentType.objects.get_for_model(post)
        all_flags = Activity.objects.filter(
                        activity_type=const.TYPE_ACTIVITY_MARK_OFFENSIVE,
                        content_type=post_content_type,
                        object_id=post.id
                    )
        for flag in all_flags:
            auth.onUnFlaggedItem(post, flag.user, timestamp=timestamp)

    elif cancel:#todo: can't unflag?
        if force == False:
            user.assert_can_remove_flag_offensive(post = post)
        auth.onUnFlaggedItem(post, user, timestamp=timestamp)

    else:
        if force == False:
            user.assert_can_flag_offensive(post=post)
        auth.onFlaggedItem(post, user, timestamp=timestamp)
        award_badges_signal.send(None,
            event = 'flag_post',
            actor = user,
            context_object = post,
            timestamp = timestamp
        )

def user_get_flags(self):
    """return flag Activity query set
    for all flags set by te user"""
    return Activity.objects.filter(
                        user = self,
                        activity_type = const.TYPE_ACTIVITY_MARK_OFFENSIVE
                    )

def user_get_flag_count_posted_today(self):
    """return number of flags the user has posted
    within last 24 hours"""
    today = datetime.date.today()
    time_frame = (today, today + datetime.timedelta(1))
    flags = self.get_flags()
    return flags.filter(active_at__range = time_frame).count()

def user_get_flags_for_post(self, post):
    """return query set for flag Activity items
    posted by users for a given post obeject
    """
    post_content_type = ContentType.objects.get_for_model(post)
    flags = self.get_flags()
    return flags.filter(content_type = post_content_type, object_id=post.id)

def user_update_response_counts(user):
    """Recount number of responses to the user.
    """
    ACTIVITY_TYPES = const.RESPONSE_ACTIVITY_TYPES_FOR_DISPLAY
    ACTIVITY_TYPES += (const.TYPE_ACTIVITY_MENTION,)

    user.new_response_count = ActivityAuditStatus.objects.filter(
                                    user = user,
                                    status = ActivityAuditStatus.STATUS_NEW,
                                    activity__activity_type__in = ACTIVITY_TYPES
                                ).count()
    user.seen_response_count = ActivityAuditStatus.objects.filter(
                                    user = user,
                                    status = ActivityAuditStatus.STATUS_SEEN,
                                    activity__activity_type__in = ACTIVITY_TYPES
                                ).count()
    user.save()


def user_receive_reputation(self, num_points):
    new_points = self.reputation + num_points
    if new_points > 0:
        self.reputation = new_points
    else:
        self.reputation = const.MIN_REPUTATION

def user_update_wildcard_tag_selections(
                                    self,
                                    action = None,
                                    reason = None,
                                    wildcards = None,
                                ):
    """updates the user selection of wildcard tags
    and saves the user object to the database
    """
    if askbot_settings.SUBSCRIBED_TAG_SELECTOR_ENABLED:
        assert reason in ('good', 'bad', 'subscribed')
    else:
        assert reason in ('good', 'bad')

    new_tags = set(wildcards)
    interesting = set(self.interesting_tags.split())
    ignored = set(self.ignored_tags.split())
    subscribed = set(self.subscribed_tags.split())

    if reason == 'good':
        target_set = interesting
        other_set = ignored
    elif reason == 'bad':
        target_set = ignored
        other_set = interesting
    elif reason == 'subscribed':
        target_set = subscribed
        other_set = None
    else:
        assert(action == 'remove')

    if action == 'add':
        target_set.update(new_tags)
        if reason in ('good', 'bad'):
            other_set.difference_update(new_tags)
    else:
        target_set.difference_update(new_tags)
        if reason in ('good', 'bad'):
            other_set.difference_update(new_tags)

    self.interesting_tags = ' '.join(interesting)
    self.ignored_tags = ' '.join(ignored)
    self.subscribed_tags = ' '.join(subscribed)
    self.save()
    return new_tags


def user_edit_group_membership(self, user=None, group=None,
                               action=None, force=False):
    """allows one user to add another to a group
    or remove user from group.

    If when adding, the group does not exist, it will be created
    the delete function is not symmetric, the group will remain
    even if it becomes empty

    returns instance of GroupMembership (if action is "add") or None
    """
    if action == 'add':
        #calculate new level
        openness = group.get_openness_level_for_user(user)

        #let people join these special groups, but not leave
        if not force:
            if group.name == askbot_settings.GLOBAL_GROUP_NAME:
                openness = 'open'
            elif group.name == format_personal_group_name(user):
                openness = 'open'

            if openness == 'open':
                level = GroupMembership.FULL
            elif openness == 'moderated':
                level = GroupMembership.PENDING
            elif openness == 'closed':
                raise django_exceptions.PermissionDenied()
        else:
            level = GroupMembership.FULL

        membership, created = GroupMembership.objects.get_or_create(
                        user=user, group=group, level=level
                    )
        return membership

    elif action == 'remove':
        GroupMembership.objects.get(user = user, group = group).delete()
        return None
    else:
        raise ValueError('invalid action')

def user_join_group(self, group, force=False):
    return self.edit_group_membership(group=group, user=self,
                                      action='add', force=force)

def user_leave_group(self, group):
    self.edit_group_membership(group=group, user=self, action='remove')

def user_is_group_member(self, group=None):
    """True if user is member of group,
    where group can be instance of Group
    or name of group as string
    """
    if isinstance(group, str):
        return GroupMembership.objects.filter(
                user=self, group__name=group
            ).count() == 1
    else:
        return GroupMembership.objects.filter(
                                user=self, group=group
                            ).count() == 1

User.add_to_class(
    'add_missing_askbot_subscriptions',
    user_add_missing_askbot_subscriptions
)
User.add_to_class(
    'is_username_taken',
    classmethod(user_is_username_taken)
)
User.add_to_class(
    'get_followed_question_alert_frequency',
    user_get_followed_question_alert_frequency
)
User.add_to_class(
    'subscribe_for_followed_question_alerts',
    user_subscribe_for_followed_question_alerts
)
User.add_to_class('get_absolute_url', user_get_absolute_url)
User.add_to_class('get_avatar_url', user_get_avatar_url)
User.add_to_class('get_default_avatar_url', user_get_default_avatar_url)
User.add_to_class('get_gravatar_url', user_get_gravatar_url)
User.add_to_class('get_or_create_fake_user', user_get_or_create_fake_user)
User.add_to_class('get_marked_tags', user_get_marked_tags)
User.add_to_class('get_marked_tag_names', user_get_marked_tag_names)
User.add_to_class('get_groups', user_get_groups)
User.add_to_class('get_foreign_groups', user_get_foreign_groups)
User.add_to_class('get_group_membership', user_get_group_membership)
User.add_to_class('get_personal_group', user_get_personal_group)
User.add_to_class('get_primary_group', user_get_primary_group)
User.add_to_class('get_notifications', user_get_notifications)
User.add_to_class('strip_email_signature', user_strip_email_signature)
User.add_to_class('get_groups_membership_info', user_get_groups_membership_info)
User.add_to_class('get_anonymous_name', user_get_anonymous_name)
User.add_to_class('get_social_sharing_mode', user_get_social_sharing_mode)
User.add_to_class('get_social_sharing_status', user_get_social_sharing_status)
User.add_to_class('update_avatar_type', user_update_avatar_type)
User.add_to_class('post_question', user_post_question)
User.add_to_class('edit_question', user_edit_question)
User.add_to_class('retag_question', user_retag_question)
User.add_to_class('post_answer', user_post_answer)
User.add_to_class('edit_answer', user_edit_answer)
User.add_to_class('edit_post', user_edit_post)
User.add_to_class(
    'post_anonymous_askbot_content',
    user_post_anonymous_askbot_content
)
User.add_to_class('post_comment', user_post_comment)
User.add_to_class('edit_comment', user_edit_comment)
User.add_to_class('create_post_reject_reason', user_create_post_reject_reason)
User.add_to_class('edit_post_reject_reason', user_edit_post_reject_reason)
User.add_to_class('delete_post', user_delete_post)
User.add_to_class('post_object_description', user_post_object_description)
User.add_to_class('visit_question', user_visit_question)
User.add_to_class('upvote', upvote)
User.add_to_class('downvote', downvote)
User.add_to_class('flag_post', flag_post)
User.add_to_class('receive_reputation', user_receive_reputation)
User.add_to_class('get_flags', user_get_flags)
User.add_to_class(
    'get_flag_count_posted_today',
    user_get_flag_count_posted_today
)
User.add_to_class('get_flags_for_post', user_get_flags_for_post)
User.add_to_class('get_profile_url', user_get_profile_url)
User.add_to_class('get_profile_link', get_profile_link)
User.add_to_class('get_tag_filtered_questions', user_get_tag_filtered_questions)
User.add_to_class('get_messages', get_messages)
User.add_to_class('delete_messages', delete_messages)
User.add_to_class('toggle_favorite_question', toggle_favorite_question)
User.add_to_class('fix_html_links', user_fix_html_links)
User.add_to_class('follow_question', user_follow_question)
User.add_to_class('unfollow_question', user_unfollow_question)
User.add_to_class('is_following_question', user_is_following_question)
User.add_to_class('mark_tags', user_mark_tags)
User.add_to_class('update_response_counts', user_update_response_counts)
User.add_to_class('can_create_tags', user_can_create_tags)
User.add_to_class('can_have_strong_url', user_can_have_strong_url)
User.add_to_class('can_post_by_email', user_can_post_by_email)
User.add_to_class('can_post_comment', user_can_post_comment)
User.add_to_class('can_make_group_private_posts', user_can_make_group_private_posts)
User.add_to_class('is_administrator', user_is_administrator)
User.add_to_class('is_administrator_or_moderator', user_is_administrator_or_moderator)
User.add_to_class('set_admin_status', user_set_admin_status)
User.add_to_class('edit_group_membership', user_edit_group_membership)
User.add_to_class('join_group', user_join_group)
User.add_to_class('leave_group', user_leave_group)
User.add_to_class('is_group_member', user_is_group_member)
User.add_to_class('remove_admin_status', user_remove_admin_status)
User.add_to_class('is_moderator', user_is_moderator)
User.add_to_class('is_post_moderator', user_is_post_moderator)
User.add_to_class('is_approved', user_is_approved)
User.add_to_class('is_watched', user_is_watched)
User.add_to_class('is_suspended', user_is_suspended)
User.add_to_class('is_blocked', user_is_blocked)
User.add_to_class('is_owner_of', user_is_owner_of)
User.add_to_class('has_interesting_wildcard_tags', user_has_interesting_wildcard_tags)
User.add_to_class('has_ignored_wildcard_tags', user_has_ignored_wildcard_tags)
User.add_to_class('can_moderate_user', user_can_moderate_user)
User.add_to_class('has_affinity_to_question', user_has_affinity_to_question)
User.add_to_class('moderate_user_reputation', user_moderate_user_reputation)
User.add_to_class('set_status', user_set_status)
User.add_to_class('get_badge_summary', user_get_badge_summary)
User.add_to_class('get_primary_language', user_get_primary_language)
User.add_to_class('get_status_display', user_get_status_display)
User.add_to_class('get_old_vote_for_post', user_get_old_vote_for_post)
User.add_to_class('get_unused_votes_today', user_get_unused_votes_today)
User.add_to_class('delete_comment', user_delete_comment)
User.add_to_class('delete_question', user_delete_question)
User.add_to_class('delete_answer', user_delete_answer)
User.add_to_class('restore_post', user_restore_post)
User.add_to_class('close_question', user_close_question)
User.add_to_class('reopen_question', user_reopen_question)
User.add_to_class('accept_best_answer', user_accept_best_answer)
User.add_to_class('unaccept_best_answer', user_unaccept_best_answer)
User.add_to_class(
    'update_wildcard_tag_selections',
    user_update_wildcard_tag_selections
)
User.add_to_class('approve_post_revision', user_approve_post_revision)
User.add_to_class('notify_users', user_notify_users)
User.add_to_class('is_read_only', user_is_read_only)

#assertions
User.add_to_class('assert_can_vote_for_post', user_assert_can_vote_for_post)
User.add_to_class('assert_can_revoke_old_vote', user_assert_can_revoke_old_vote)
User.add_to_class('assert_can_upload_file', user_assert_can_upload_file)
User.add_to_class('assert_can_post_question', user_assert_can_post_question)
User.add_to_class('assert_can_post_answer', user_assert_can_post_answer)
User.add_to_class('assert_can_post_comment', user_assert_can_post_comment)
User.add_to_class('assert_can_post_text', user_assert_can_post_text)
User.add_to_class('assert_can_edit_post', user_assert_can_edit_post)
User.add_to_class('assert_can_edit_deleted_post', user_assert_can_edit_deleted_post)
User.add_to_class('assert_can_see_deleted_post', user_assert_can_see_deleted_post)
User.add_to_class('assert_can_edit_question', user_assert_can_edit_question)
User.add_to_class('assert_can_edit_answer', user_assert_can_edit_answer)
User.add_to_class('assert_can_close_question', user_assert_can_close_question)
User.add_to_class('assert_can_reopen_question', user_assert_can_reopen_question)
User.add_to_class('assert_can_flag_offensive', user_assert_can_flag_offensive)
User.add_to_class('assert_can_remove_flag_offensive', user_assert_can_remove_flag_offensive)
User.add_to_class('assert_can_remove_all_flags_offensive', user_assert_can_remove_all_flags_offensive)
User.add_to_class('assert_can_retag_question', user_assert_can_retag_question)
#todo: do we need assert_can_delete_post
User.add_to_class('assert_can_delete_post', user_assert_can_delete_post)
User.add_to_class('assert_can_restore_post', user_assert_can_restore_post)
User.add_to_class('assert_can_delete_comment', user_assert_can_delete_comment)
User.add_to_class('assert_can_edit_comment', user_assert_can_edit_comment)
User.add_to_class('assert_can_delete_answer', user_assert_can_delete_answer)
User.add_to_class('assert_can_delete_question', user_assert_can_delete_question)
User.add_to_class('assert_can_accept_best_answer', user_assert_can_accept_best_answer)
User.add_to_class(
    'assert_can_unaccept_best_answer',
    user_assert_can_unaccept_best_answer
)
User.add_to_class(
    'assert_can_approve_post_revision',
    user_assert_can_approve_post_revision
)

#todo: move this to askbot/mail ?
def format_instant_notification_email(
                                        to_user = None,
                                        from_user = None,
                                        post = None,
                                        reply_address = None,
                                        alt_reply_address = None,
                                        update_type = None,
                                        template = None,
                                    ):
    """
    returns text of the instant notification body
    and subject line

    that is built when post is updated
    only update_types in const.RESPONSE_ACTIVITY_TYPE_MAP_FOR_TEMPLATES
    are supported
    """
    origin_post = post.get_origin_post()

    if update_type == 'question_comment':
        assert(isinstance(post, Post) and post.is_comment())
        assert(post.parent and post.parent.is_question())
    elif update_type == 'answer_comment':
        assert(isinstance(post, Post) and post.is_comment())
        assert(post.parent and post.parent.is_answer())
    elif update_type == 'answer_update':
        assert(isinstance(post, Post) and post.is_answer())
    elif update_type == 'new_answer':
        assert(isinstance(post, Post) and post.is_answer())
    elif update_type == 'question_update':
        assert(isinstance(post, Post) and post.is_question())
    elif update_type == 'new_question':
        assert(isinstance(post, Post) and post.is_question())
    elif update_type == 'post_shared':
        pass
    else:
        raise ValueError('unexpected update_type %s' % update_type)

    if update_type.endswith('update'):
        assert('comment' not in update_type)
        revisions = post.revisions.all()[:2]
        assert(len(revisions) == 2)
        content_preview = htmldiff(
                sanitize_html(revisions[1].html),
                sanitize_html(revisions[0].html),
                ins_start = '<b><u style="background-color:#cfc">',
                ins_end = '</u></b>',
                del_start = '<del style="color:#600;background-color:#fcc">',
                del_end = '</del>'
            )
        #todo: remove hardcoded style
    else:
        content_preview = post.format_for_email(is_leaf_post = True)

    #add indented summaries for the parent posts
    content_preview += post.format_for_email_as_parent_thread_summary()

    #content_preview += '<p>======= Full thread summary =======</p>'
    #content_preview += post.thread.format_for_email(user=to_user)

    if update_type == 'post_shared':
        user_action = _('%(user)s shared a %(post_link)s.')
    elif post.is_comment():
        if update_type.endswith('update'):
            user_action = _('%(user)s edited a %(post_link)s.')
        else:
            user_action = _('%(user)s posted a %(post_link)s')
    elif post.is_answer():
        if update_type.endswith('update'):
            user_action = _('%(user)s edited an %(post_link)s.')
        else:
            user_action = _('%(user)s posted an %(post_link)s.')
    elif post.is_question():
        if update_type.endswith('update'):
            user_action = _('%(user)s edited a %(post_link)s.')
        else:
            user_action = _('%(user)s posted a %(post_link)s.')
    else:
        raise ValueError('unrecognized post type')

    post_url = site_url(post.get_absolute_url())
    user_url = site_url(from_user.get_absolute_url())
    user_action = user_action % {
        'user': '<a href="%s">%s</a>' % (user_url, from_user.username),
        'post_link': '<a href="%s">%s</a>' % (post_url, _(post.post_type))
        #'post_link': '%s <a href="%s">>>></a>' % (_(post.post_type), post_url)
    }

    can_reply = to_user.can_post_by_email()

    if can_reply:
        reply_separator = const.SIMPLE_REPLY_SEPARATOR_TEMPLATE % \
                    _('To reply, PLEASE WRITE ABOVE THIS LINE.')
        if post.post_type == 'question' and alt_reply_address:
            data = {
                'addr': alt_reply_address,
                'subject': urllib.quote(
                        ('Re: ' + post.thread.title).encode('utf-8')
                    )
            }
            reply_separator += '<p>' + \
                const.REPLY_WITH_COMMENT_TEMPLATE % data
            reply_separator += '</p>'
        else:
            reply_separator = '<p>%s</p>' % reply_separator

        reply_separator += user_action
    else:
        reply_separator = user_action

    user_subscriptions_url = reverse(
                                    'user_subscriptions',
                                    kwargs = {
                                        'id': to_user.id,
                                        'slug': slugify(to_user.username)
                                    }
                                )
    update_data = {
        'admin_email': askbot_settings.ADMIN_EMAIL,
        'recipient_user': to_user,
        'update_author_name': from_user.username,
        'receiving_user_name': to_user.username,
        'receiving_user_karma': to_user.reputation,
        'reply_by_email_karma_threshold': askbot_settings.MIN_REP_TO_POST_BY_EMAIL,
        'can_reply': can_reply,
        'content_preview': content_preview,
        'update_type': update_type,
        'post_url': post_url,
        'origin_post_title': origin_post.thread.title,
        'user_subscriptions_url': site_url(user_subscriptions_url),
        'reply_separator': reply_separator,
        'reply_address': reply_address,
        'is_multilingual': getattr(django_settings, 'ASKBOT_MULTILINGUAL', False)
    }
    subject_line = _('"%(title)s"') % {'title': origin_post.thread.title}

    content = template.render(Context(update_data))

    return subject_line, content

def get_reply_to_addresses(user, post):
    """Returns one or two email addresses that can be
    used by a given `user` to reply to the `post`
    the first address - always a real email address,
    the second address is not ``None`` only for "question" posts.

    When the user is notified of a new question -
    i.e. `post` is a "quesiton", he/she
    will need to choose - whether to give a question or a comment,
    thus we return the second address - for the comment reply.

    When the post is a "question", the first email address
    is for posting an "answer", and when post is either
    "comment" or "answer", the address will be for posting
    a "comment".
    """
    #these variables will contain return values
    primary_addr = django_settings.DEFAULT_FROM_EMAIL
    secondary_addr = None
    if user.can_post_by_email():
        if user.reputation >= askbot_settings.MIN_REP_TO_POST_BY_EMAIL:

            reply_args = {
                'post': post,
                'user': user,
                'reply_action': 'post_comment'
            }
            if post.post_type in ('answer', 'comment'):
                reply_args['reply_action'] = 'post_comment'
            elif post.post_type == 'question':
                reply_args['reply_action'] = 'post_answer'

            primary_addr = ReplyAddress.objects.create_new(
                                                    **reply_args
                                                ).as_email_address()

            if post.post_type == 'question':
                reply_args['reply_action'] = 'post_comment'
                secondary_addr = ReplyAddress.objects.create_new(
                                                    **reply_args
                                                ).as_email_address()
    return primary_addr, secondary_addr


def notify_author_of_published_revision(
    revision = None, was_approved = None, **kwargs
):
    """notifies author about approved post revision,
    assumes that we have the very first revision
    """
    #only email about first revision
    if revision.should_notify_author_about_publishing(was_approved):
        from askbot.tasks import notify_author_of_published_revision_celery_task
        notify_author_of_published_revision_celery_task.delay(revision)


#todo: move to utils
def calculate_gravatar_hash(instance, **kwargs):
    """Calculates a User's gravatar hash from their email address."""
    if kwargs.get('raw', False):
        return
    clean_email = instance.email.strip().lower()
    instance.gravatar = hashlib.md5(clean_email).hexdigest()


def record_post_update_activity(
        post,
        newly_mentioned_users=None,
        updated_by=None,
        suppress_email=False,
        timestamp=None,
        created=False,
        diff=None,
        **kwargs
    ):
    """called upon signal askbot.models.signals.post_updated
    which is sent at the end of save() method in posts

    this handler will set notifications about the post
    """
    if post.needs_moderation():
        #do not give notifications yet
        #todo: it is possible here to trigger
        #moderation email alerts
        return

    assert(timestamp != None)
    assert(updated_by != None)
    if newly_mentioned_users is None:
        newly_mentioned_users = list()

    from askbot import tasks

    tasks.record_post_update_celery_task.delay(
        post_id=post.id,
        post_content_type_id=ContentType.objects.get_for_model(post).id,
        newly_mentioned_user_id_list=[u.id for u in newly_mentioned_users],
        updated_by_id=updated_by.id,
        suppress_email=suppress_email,
        timestamp=timestamp,
        created=created,
        diff=diff,
    )


def record_award_event(instance, created, **kwargs):
    """
    After we awarded a badge to user, we need to
    record this activity and notify user.
    We also recaculate awarded_count of this badge and user information.
    """
    if created:
        #todo: change this to community user who gives the award
        activity = Activity(
                        user=instance.user,
                        active_at=instance.awarded_at,
                        content_object=instance,
                        activity_type=const.TYPE_ACTIVITY_PRIZE
                    )
        activity.save()
        activity.add_recipients([instance.user])

        instance.badge.awarded_count += 1
        instance.badge.save()

        badge = get_badge(instance.badge.slug)

        if badge.level == const.GOLD_BADGE:
            instance.user.gold += 1
        if badge.level == const.SILVER_BADGE:
            instance.user.silver += 1
        if badge.level == const.BRONZE_BADGE:
            instance.user.bronze += 1
        instance.user.save()

def notify_award_message(instance, created, **kwargs):
    """
    Notify users when they have been awarded badges by using Django message.
    """
    if askbot_settings.BADGES_MODE != 'public':
        return
    if created:
        user = instance.user

        badge = get_badge(instance.badge.slug)

        msg = _(u"Congratulations, you have received a badge '%(badge_name)s'. "
                u"Check out <a href=\"%(user_profile)s\">your profile</a>.") \
                % {
                    'badge_name':badge.name,
                    'user_profile':user.get_profile_url()
                }

        user.message_set.create(message=msg)

def record_answer_accepted(instance, created, **kwargs):
    """
    when answer is accepted, we record this for question author
    - who accepted it.
    """
    if instance.post_type != 'answer':
        return

    question = instance.thread._question_post()

    if not created and instance.accepted():
        activity = Activity(
                        user=question.author,
                        active_at=datetime.datetime.now(),
                        content_object=question,
                        activity_type=const.TYPE_ACTIVITY_MARK_ANSWER,
                        question=question
                    )
        activity.save()
        recipients = instance.get_author_list(
                                    exclude_list = [question.author]
                                )
        activity.add_recipients(recipients)

def record_user_visit(user, timestamp, **kwargs):
    """
    when user visits any pages, we update the last_seen and
    consecutive_days_visit_count
    """
    prev_last_seen = user.last_seen or datetime.datetime.now()
    user.last_seen = timestamp
    consecutive_days = user.consecutive_days_visit_count
    if (user.last_seen.date() - prev_last_seen.date()).days == 1:
        user.consecutive_days_visit_count += 1
        consecutive_days = user.consecutive_days_visit_count
        award_badges_signal.send(None,
            event = 'site_visit',
            actor = user,
            context_object = user,
            timestamp = timestamp
        )
    #somehow it saves on the query as compared to user.save()
    update_data = {
        'last_seen': timestamp,
        'consecutive_days_visit_count': consecutive_days
    }
    User.objects.filter(id=user.id).update(**update_data)


def record_vote(instance, created, **kwargs):
    """
    when user have voted
    """
    if created:
        if instance.vote == 1:
            vote_type = const.TYPE_ACTIVITY_VOTE_UP
        else:
            vote_type = const.TYPE_ACTIVITY_VOTE_DOWN

        activity = Activity(
                        user=instance.user,
                        active_at=instance.voted_at,
                        content_object=instance,
                        activity_type=vote_type
                    )
        #todo: problem cannot access receiving user here
        activity.save()


def record_cancel_vote(instance, **kwargs):
    """
    when user canceled vote, the vote will be deleted.
    """
    activity = Activity(
                    user=instance.user,
                    active_at=datetime.datetime.now(),
                    content_object=instance,
                    activity_type=const.TYPE_ACTIVITY_CANCEL_VOTE
                )
    #todo: same problem - cannot access receiving user here
    activity.save()


#todo: weird that there is no record delete answer or comment
#is this even necessary to keep track of?
def record_delete_question(instance, delete_by, **kwargs):
    """
    when user deleted the question
    """
    if instance.post_type == 'question':
        activity_type = const.TYPE_ACTIVITY_DELETE_QUESTION
    elif instance.post_type == 'answer':
        activity_type = const.TYPE_ACTIVITY_DELETE_ANSWER
    else:
        return

    activity = Activity(
                    user=delete_by,
                    active_at=datetime.datetime.now(),
                    content_object=instance,
                    activity_type=activity_type,
                    question = instance.get_origin_post()
                )
    #no need to set receiving user here
    activity.save()

def record_flag_offensive(instance, mark_by, **kwargs):
    activity = Activity(
                    user=mark_by,
                    active_at=datetime.datetime.now(),
                    content_object=instance,
                    activity_type=const.TYPE_ACTIVITY_MARK_OFFENSIVE,
                    question=instance.get_origin_post()
                )
    activity.save()
#   todo: report authors that their post is flagged offensive
#    recipients = instance.get_author_list(
#                                        exclude_list = [mark_by]
#                                    )
    activity.add_recipients(instance.get_moderators())

def remove_flag_offensive(instance, mark_by, **kwargs):
    "Remove flagging activity"
    content_type = ContentType.objects.get_for_model(instance)

    activity = Activity.objects.filter(
                    user=mark_by,
                    content_type = content_type,
                    object_id = instance.id,
                    activity_type=const.TYPE_ACTIVITY_MARK_OFFENSIVE,
                    question=instance.get_origin_post()
                )
    activity.delete()


def record_update_tags(thread, tags, user, timestamp, **kwargs):
    """
    This function sends award badges signal on each updated tag
    the badges that respond to the 'ta
    """
    for tag in tags:
        award_badges_signal.send(None,
            event = 'update_tag',
            actor = user,
            context_object = tag,
            timestamp = timestamp
        )

    question = thread._question_post()

    activity = Activity(
                    user=user,
                    active_at=datetime.datetime.now(),
                    content_object=question,
                    activity_type=const.TYPE_ACTIVITY_UPDATE_TAGS,
                    question = question
                )
    activity.save()

def record_favorite_question(instance, created, **kwargs):
    """
    when user add the question in him favorite questions list.
    """
    if created:
        activity = Activity(
                        user=instance.user,
                        active_at=datetime.datetime.now(),
                        content_object=instance,
                        activity_type=const.TYPE_ACTIVITY_FAVORITE,
                        question=instance.thread._question_post()
                    )
        activity.save()
        recipients = instance.thread._question_post().get_author_list(
                                            exclude_list = [instance.user]
                                        )
        activity.add_recipients(recipients)

def record_user_full_updated(instance, **kwargs):
    activity = Activity(
                    user=instance,
                    active_at=datetime.datetime.now(),
                    content_object=instance,
                    activity_type=const.TYPE_ACTIVITY_USER_FULL_UPDATED
                )
    activity.save()

def send_respondable_email_validation_message(
    user = None, subject_line = None, data = None, template_name = None
):
    """sends email validation message to the user

    We validate email by getting user's reply
    to the validation message by email, which also gives
    an opportunity to extract user's email signature.
    """
    reply_address = ReplyAddress.objects.create_new(
                                    user = user,
                                    reply_action = 'validate_email'
                                )
    data['email_code'] = reply_address.address

    template = get_template(template_name)
    body_text = template.render(Context(data))#todo: set lang

    reply_to_address = 'welcome-%s@%s' % (
                            reply_address.address,
                            askbot_settings.REPLY_BY_EMAIL_HOSTNAME
                        )

    mail.send_mail(
        subject_line = subject_line,
        body_text = body_text,
        recipient_list = [user.email, ],
        activity_type = const.TYPE_ACTIVITY_VALIDATION_EMAIL_SENT,
        headers = {'Reply-To': reply_to_address}
    )


def add_user_to_global_group(sender, instance, created, **kwargs):
    """auto-joins user to the global group
    ``instance`` is an instance of ``User`` class
    """
    if created:
        instance.edit_group_membership(
            group=Group.objects.get_global_group(),
            user=instance,
            action='add'
        )


def add_user_to_personal_group(sender, instance, created, **kwargs):
    """auto-joins user to his/her personal group
    ``instance`` is an instance of ``User`` class
    """
    if created:
        #todo: groups will indeed need to be separated from tags
        #so that we can use less complicated naming scheme
        #in theore here we may have two users that will have
        #identical group names!!!
        group_name = format_personal_group_name(instance)
        group = Group.objects.get_or_create(
                    name=group_name, user=instance
                )
        instance.edit_group_membership(
                    group=group, user=instance, action='add'
                )


def greet_new_user(user, **kwargs):
    """sends welcome email to the newly created user

    todo: second branch should send email with a simple
    clickable link.
    """
    if askbot_settings.NEW_USER_GREETING:
        user.message_set.create(message = askbot_settings.NEW_USER_GREETING)

    if askbot_settings.REPLY_BY_EMAIL:#with this on we also collect signature
        template_name = 'email/welcome_lamson_on.html'
    else:
        template_name = 'email/welcome_lamson_off.html'

    data = {
        'site_name': askbot_settings.APP_SHORT_NAME,
        'site_url': site_url(reverse('questions')),
        'ask_address': 'ask@' + askbot_settings.REPLY_BY_EMAIL_HOSTNAME,
        'can_post_by_email': user.can_post_by_email()
    }
    send_respondable_email_validation_message(
        user=user,
        subject_line=_('Welcome to %(site_name)s') % data,
        data=data,
        template_name=template_name
    )


def complete_pending_tag_subscriptions(sender, request, *args, **kwargs):
    """save pending tag subscriptions saved in the session"""
    if 'subscribe_for_tags' in request.session:
        (pure_tag_names, wildcards) = request.session.pop('subscribe_for_tags')
        if askbot_settings.SUBSCRIBED_TAG_SELECTOR_ENABLED:
            reason = 'subscribed'
        else:
            reason = 'good'
        request.user.mark_tags(
                    pure_tag_names,
                    wildcards,
                    reason = reason,
                    action = 'add'
                )
        request.user.message_set.create(
            message = _('Your tag subscription was saved, thanks!')
        )

def add_missing_subscriptions(sender, instance, created, **kwargs):
    """``sender`` is instance of ``User``. When the ``User``
    is created, any required email subscription settings will be
    added by this handler"""
    if created:
        instance.add_missing_askbot_subscriptions()

def add_missing_tag_subscriptions(sender, instance, created, **kwargs):
    '''``sender` is instance of `User``. When the user is created
    it add the tag subscriptions to the user via BulkTagSubscription
    and MarkedTags.
    '''
    if created:
        if askbot_settings.SUBSCRIBED_TAG_SELECTOR_ENABLED and \
                askbot_settings.GROUPS_ENABLED:
            user_groups = instance.get_groups()
            for subscription in BulkTagSubscription.objects.filter(groups__in = user_groups):
                tag_list = subscription.tag_list()
                instance.mark_tags(tagnames = tag_list,
                                reason='subscribed', action='add')

def post_anonymous_askbot_content(
                                sender,
                                request,
                                user,
                                session_key,
                                signal,
                                *args,
                                **kwargs):
    """signal handler, unfortunately extra parameters
    are necessary for the signal machinery, even though
    they are not used in this function"""
    user.post_anonymous_askbot_content(session_key)

def set_user_avatar_type_flag(instance, created, **kwargs):
    instance.user.update_avatar_type()

def update_user_avatar_type_flag(instance, **kwargs):
    instance.user.update_avatar_type()

def make_admin_if_first_user(instance, **kwargs):
    """first user automatically becomes an administrator
    the function is run only once in the interpreter session
    """
    import sys
    #have to check sys.argv to satisfy the test runner
    #which fails with the cache-based skipping
    #for real the setUp() code in the base test case must
    #clear the cache!!!
    if 'test' not in sys.argv and cache.cache.get('admin-created'):
        #no need to hit the database every time!
        return
    user_count = User.objects.all().count()
    if user_count == 0:
        instance.set_admin_status()
    cache.cache.set('admin-created', True)

def moderate_group_joining(sender, instance=None, created=False, **kwargs):
    if created and instance.level == GroupMembership.PENDING:
        user = instance.user
        group = instance.group
        user.notify_users(
                notification_type=const.TYPE_ACTIVITY_ASK_TO_JOIN_GROUP,
                recipients = group.get_moderators(),
                content_object = group
            )

def tweet_new_post(sender, user=None, question=None, answer=None, form_data=None, **kwargs):
    """seends out tweets about the new post"""
    from askbot.tasks import tweet_new_post_task
    post = question or answer
    tweet_new_post_task.delay(post.id)

#signal for User model save changes
django_signals.pre_save.connect(make_admin_if_first_user, sender=User)
django_signals.pre_save.connect(calculate_gravatar_hash, sender=User)
django_signals.post_save.connect(add_missing_subscriptions, sender=User)
django_signals.post_save.connect(add_user_to_global_group, sender=User)
django_signals.post_save.connect(add_user_to_personal_group, sender=User)
django_signals.post_save.connect(add_missing_tag_subscriptions, sender=User)
django_signals.post_save.connect(record_award_event, sender=Award)
django_signals.post_save.connect(notify_award_message, sender=Award)
django_signals.post_save.connect(record_answer_accepted, sender=Post)
django_signals.post_save.connect(record_vote, sender=Vote)
django_signals.post_save.connect(record_favorite_question, sender=FavoriteQuestion)
django_signals.post_save.connect(moderate_group_joining, sender=GroupMembership)

if 'avatar' in django_settings.INSTALLED_APPS:
    from avatar.models import Avatar
    django_signals.post_save.connect(set_user_avatar_type_flag,sender=Avatar)
    django_signals.post_delete.connect(update_user_avatar_type_flag, sender=Avatar)

django_signals.post_delete.connect(record_cancel_vote, sender=Vote)

#change this to real m2m_changed with Django1.2
signals.delete_question_or_answer.connect(record_delete_question, sender=Post)
signals.flag_offensive.connect(record_flag_offensive, sender=Post)
signals.remove_flag_offensive.connect(remove_flag_offensive, sender=Post)
signals.tags_updated.connect(record_update_tags)
signals.user_registered.connect(greet_new_user)
signals.user_updated.connect(record_user_full_updated, sender=User)
signals.user_logged_in.connect(complete_pending_tag_subscriptions)#todo: add this to fake onlogin middleware
signals.user_logged_in.connect(post_anonymous_askbot_content)
signals.post_updated.connect(record_post_update_activity)
signals.new_answer_posted.connect(tweet_new_post)
signals.new_question_posted.connect(tweet_new_post)

#probably we cannot use post-save here the point of this is
#to tell when the revision becomes publicly visible, not when it is saved
signals.post_revision_published.connect(notify_author_of_published_revision)
signals.site_visited.connect(record_user_visit)

__all__ = [
        'signals',

        'Thread',

        'QuestionView',
        'FavoriteQuestion',
        'AnonymousQuestion',
        'DraftQuestion',

        'AnonymousAnswer',
        'DraftAnswer',

        'Post',
        'PostRevision',
        'PostToGroup',

        'Tag',
        'Vote',
        'PostFlagReason',
        'MarkedTag',
        'TagSynonym',

        'BadgeData',
        'Award',
        'Repute',

        'Activity',
        'ActivityAuditStatus',
        'EmailFeedSetting',
        'GroupMembership',
        'Group',

        'User',

        'ReplyAddress',

        'get_model',
]
