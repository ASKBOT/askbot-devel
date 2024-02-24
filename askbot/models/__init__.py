#pylint: disable=wrong-import-order
from askbot import startup_procedures
startup_procedures.run()

from django.contrib.auth.models import User

import collections
import datetime
import hashlib
import logging
import os
import re
import urllib.request, urllib.parse, urllib.error
from functools import partial
from django.urls import reverse, NoReverseMatch
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import signals as django_signals
from django.utils import translation
from django.utils.translation import gettext as _
from django.utils.translation import override, ngettext
from django.utils.safestring import mark_safe
from django.utils.html import escape
from django.utils.text import format_lazy
from django.utils import timezone
from django.apps import apps
from django.db import models
from django.db.models import Count, Q
from django.conf import settings as django_settings
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core import exceptions as django_exceptions

import askbot
from askbot import exceptions as askbot_exceptions
from askbot import const
from askbot.const import message_keys
from askbot.conf import settings as askbot_settings
from askbot.models.question import Thread
from askbot.skins import utils as skin_utils
from askbot.mail.messages import (WelcomeEmail,
                                  WelcomeEmailRespondable,
                                  AccountManagementRequest)
from askbot.models.question import QuestionView, AnonymousQuestion
from askbot.models.question import DraftQuestion
from askbot.models.question import FavoriteQuestion
from askbot.models.message import Message
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
from askbot.models.user_profile import (
                                add_profile_properties,
                                UserProfile,
                                LocalizedUserProfile,
                                get_localized_profile_cache_key
                            )
from askbot.models.reply_by_email import ReplyAddress
from askbot.models.badges import award_badges_signal, get_badge
from askbot.models.repute import Award, Repute, Vote, BadgeData
from askbot.models.widgets import AskWidget, QuestionWidget
from askbot.models.meta import ImportRun, ImportedObjectInfo
from askbot.models.role import Role, get_role_set
from askbot import auth
from askbot.utils.functions import generate_random_key
from askbot.utils.decorators import auto_now_timestamp
from askbot.utils.decorators import reject_forbidden_phrases
from askbot.utils.markup import URL_RE
from askbot.utils.slug import slugify, ascii_slugify
from askbot.utils.celery_utils import defer_celery_task
from askbot.utils.translation import get_language
from askbot.utils.html import replace_links_with_text
from askbot.utils import functions
from askbot import mail
from askbot import signals

from jsonfield import JSONField

register_user_signal = partial(signals.register_generic_signal, sender=User)


def get_model(model_name):
    """a shortcut for getting model for an askbot app"""
    return apps.get_model('askbot', model_name)


def get_admin():
    """returns admin with the lowest user ID
    if there are no users at all - creates one
    with name "admin" and unusable password
    otherwise raises User.DoesNotExist
    """
    try:
        return User.objects.filter(
                        askbot_profile__status='d'
                    ).order_by('id')[0]
    except IndexError:
        if User.objects.filter(username='_admin_').count() == 0:
            admin = User.objects.create_user('_admin_', '')
            admin.set_unusable_password()
            admin.set_status('d')
            return admin
        else:
            raise User.DoesNotExist


def get_moderators():
    return User.objects.filter(askbot_profile__status__in=('m', 'd')).filter(is_active = True)


def get_users_by_role(role_name):
    """Returns query set of users matching
    the given role name"""
    return User.objects.filter(askbot_roles__role=role_name, is_active=True)


def get_users_by_text_query(search_query, users_query_set = None):
    """Runs text search in user names and profile.
    For postgres, search also runs against user group names.
    """
    if getattr(django_settings, 'ENABLE_HAYSTACK_SEARCH', False):
        from askbot.search.haystack.helpers import get_users_from_query
        return get_users_from_query(search_query)
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
                models.Q(localized_askbot_profiles__about__icontains=search_query)
            )
        #if askbot.get_database_engine_name().endswith('mysql') \
        #    and mysql.supports_full_text_search():
        #    return User.objects.filter(
        #        models.Q(username__search = search_query) |
        #        models.Q(localized_user_profiles__about__search = search_query)
        #    )

class RelatedObjectSimulator:
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

User.add_to_class('message_set', user_message_set)
User.add_to_class('get_and_delete_messages', user_get_and_delete_messages)

#monkeypatches the auth.models.User class with properties
#that access properties of the askbot.models.UserProfile
add_profile_properties(User)

GRAVATAR_TEMPLATE = "%(gravatar_url)s/%(gravatar)s?" + \
    "s=%(size)s&amp;d=%(type)s&amp;r=PG"

def user_get_gravatar_url(self, size):
    """returns gravatar url
    """
    return GRAVATAR_TEMPLATE % {
                'gravatar_url': askbot_settings.GRAVATAR_BASE_URL,
                'gravatar': self.gravatar,
                'type': askbot_settings.GRAVATAR_TYPE,
                'size': size,
            }

def user_get_reputation(self):
    if askbot.is_multilingual() and askbot_settings.REPUTATION_LOCALIZED:
        return self.get_localized_profile().get_reputation()
    return self.reputation

def user_get_default_avatar_url(self, size):
    """returns default avatar url
    """
    return skin_utils.get_media_url(askbot_settings.DEFAULT_AVATAR_URL)

def user_get_avatar_type(self):
    """returns user avatar type, taking into account
    avatar_type value and how use of avatar and/or gravatar
    is configured
    Value returned is one of 'n', 'a', 'g'.
    """
    if 'avatar' in django_settings.INSTALLED_APPS:
        if self.avatar_type == 'g':
            if askbot_settings.ENABLE_GRAVATAR:
                return 'g'
            else:
                #fallback to default avatar if gravatar is disabled
                return 'n'
        assert(self.avatar_type in ('a', 'n'))#only these are allowed
        return self.avatar_type

    #if we don't have an uploaded avatar, always use gravatar
    return 'g'


def user_get_avatar_url(self, size=48):
    """returns avatar url for a given size
    JSONField .avatar_urls is used as "cache"
    to avoid multiple db hits to fetch avatar urls
    """
    size = str(size)
    url = self.avatar_urls.get(size)
    if not url:
        url = self.calculate_avatar_url(size)
        self.avatar_urls[size] = url
    return url


#todo: find where this is used and replace with get_absolute_url
def user_get_profile_url(self, profile_section=None, language_code=None):
    """Returns the URL for this User's profile."""
    cur_lang = get_language()

    if language_code and cur_lang != language_code:
        translation.activate(language_code)

    url = reverse(
            'user_profile',
            kwargs={'id': self.id, 'slug': slugify(self.username)}
        )

    if language_code and cur_lang != language_code:
        translation.activate(cur_lang)

    if profile_section:
        url += "?sort=" + profile_section
    return url


def user_get_absolute_url(self, language_code=None):
    return self.get_profile_url(language_code=language_code)


def user_get_unsubscribe_url(self):
    url = reverse('user_unsubscribe')
    email_key = self.get_or_create_email_key()
    return f'{url}?key={email_key}&email={self.email}'


def user_get_subscriptions_url(self):
    return reverse(
            'user_subscriptions',
            kwargs={'id': self.id, 'slug': slugify(self.username)}
        )


def user_calculate_avatar_url(self, size=48):
    """returns avatar url - by default - gravatar,
    but if application django-avatar is installed
    it will use avatar provided through that app
    """
    avatar_type = self.get_avatar_type()
    size = int(size)

    if avatar_type == 'n':
        return self.get_default_avatar_url(size)
    elif avatar_type == 'a':
        from avatar.conf import settings as avatar_settings
        sizes = avatar_settings.AVATAR_AUTO_GENERATE_SIZES
        if size not in sizes:
            logging.critical(
                'add values %d to setting AVATAR_AUTO_GENERATE_SIZES',
                size
            )

        try:
            from avatar.utils import get_primary_avatar
        except ImportError as error:
            # If the updated version of django-avatar isn't installed
            # Let's fall back
            from avatar.util import get_primary_avatar
            logging.warning("Using deprecated version of django-avatar")

        avatar = get_primary_avatar(self, width=size, height=size)
        if avatar:
            return avatar.avatar_url(size)
        return self.get_default_avatar_url(size)

    assert(avatar_type == 'g')
    return self.get_gravatar_url(size)


def user_clear_cached_data(self):
    """Calls .clear_cached_data() on threads where
    user contributed any content"""
    posts = self.posts.all().only('thread_id')
    for post in posts:
        if hasattr(post, 'thread_id'):
            post.thread.clear_cached_data()


def user_clear_avatar_urls(self):
    """Assigns avatar urls for each required size.
    """
    self.avatar_urls = {}


def user_init_avatar_urls(self):
    """Assigns missing avatar urls,
    assumes that remaining avatars are correct"""
    from avatar.conf import settings as avatar_settings
    sizes = avatar_settings.AVATAR_AUTO_GENERATE_SIZES
    for size in sizes:
        if size not in self.avatar_urls:
            self.avatar_urls[size] = self.calculate_avatar_url(size)


def user_get_top_answers_paginator(self, visitor=None):
    """get paginator for top answers by the user for a
    specific visitor"""
    answers = self.posts.get_answers(
                                visitor
                            ).filter(
                                deleted=False,
                                thread__deleted=False
                            ).select_related(
                                'thread'
                            ).order_by(
                                '-points', '-added_at'
                            )
    return Paginator(answers, const.USER_POSTS_PAGE_SIZE)

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

def user_strip_email_signature(self, text):
    """strips email signature from the end of the text"""
    if self.email_signature.strip() == '':
        return text

    text = '\n'.join(text.splitlines())#normalize the line endings
    while text.endswith(self.email_signature):
        text = text[0:-len(self.email_signature)]
    return text

def _check_gravatar(gravatar):
    return 'n'
    #todo: think of whether we need this and if so
    #how to check the avatar type appropriately
    gravatar_url = askbot_settings.GRAVATAR_BASE_URL + "/%s?d=404" % gravatar
    code = urllib.request.urlopen(gravatar_url).getcode()
    if urllib.request.urlopen(gravatar_url).getcode() != 404:
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
        user_selections__user=self,
        user_selections__reason=reason,
        language_code=get_language()
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


def user_has_group_permission(self, permission): #pylint: disable=missing-docstring
    if not askbot_settings.GROUPS_ENABLED:
        return True

    if permission == 'post_questions':
        return self.get_groups().filter(can_post_questions=True).exists()

    if permission == 'post_answers':
        return self.get_groups().filter(can_post_answers=True).exists()

    if permission == 'post_comments':
        return self.get_groups().filter(can_post_comments=True).exists()

    return True


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

def user_has_badge(self, badge):
    """True, if user was awarded a given badge,
    ``badge`` is instance of BadgeData
    """
    return Award.objects.filter(user=self, badge=badge).count() > 0


def user_can_anonymize_account(self, user):
    """`True`, if `self` can anonymize and disable account of `user`"""
    perm = askbot_settings.WHO_CAN_ANONYMIZE_ACCOUNTS
    if perm == 'admins':
        return self.is_administrator() and self.pk != user.pk
    elif self.is_administrator_or_moderator():
        return perm in ('mods', 'users')
    elif perm == 'users':
        return self.pk == user.pk # owner can
    return False


def user_can_create_tags(self):
    """true if user can create tags"""
    if askbot_settings.ENABLE_TAG_MODERATION:
        return self.is_administrator_or_moderator()
    return True


def user_can_terminate_account(self, user):
    """True, if `self` can terminate account of `user`"""
    perm = askbot_settings.WHO_CAN_TERMINATE_ACCOUNTS
    is_admin = self.has_role('terminate_accounts')
    if self.pk == user.pk:
        if is_admin: #admin can't remove own account, as as safeguard
            return False
        return perm == 'users'
    return is_admin


def user_can_manage_account(self, user):
    """True, if `self` can see the "manage account" page of `user`"""
    return self.pk == user.pk or \
           self.can_terminate_account(user) or \
           self.has_role('download_user_data') or \
           self.can_anonymize_account(user)


def user_has_role(self, role_name):
    """True, if `self` has `role_name` Role in their role set"""
    return self.is_active and self.askbot_roles.filter(role=role_name).exists()


def user_get_roles(self):
    """Returns set of user role names"""
    return set(self.askbot_roles.values_list('role', flat=True))


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


def user_can_see_karma(user, karma_owner):
    """True, if user can see other users karma"""
    if askbot_settings.KARMA_MODE == 'public':
        return True

    if askbot_settings.KARMA_MODE == 'private':
        if user.is_administrator_or_moderator():
            return True
        if user.pk == karma_owner.pk:
            return True

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

def user_get_or_create_fake_user(self, username, email, status='w'):
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
        user.set_unusable_password()
        user.save()
        user.is_fake = True
        user.status = status
        user.save()
    return user

def get_or_create_anonymous_user():
    """returns fake anonymous user"""
    username = get_name_of_anonymous_user()
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        user = User()
        user.username = username
        user.email = askbot_settings.ANONYMOUS_USER_EMAIL
        user.set_unusable_password()
        user.save()
        user.is_fake = True
        user.save()
    return user

def user_needs_moderation(self):
    if self.status not in ('a', 'm', 'd'):
        choices = ('audit', 'premoderation')
        return askbot_settings.CONTENT_MODERATION_MODE in choices
    return False

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
    return False

def user_get_notifications(self, notification_types=None, **kwargs):
    """returns query set of activity audit status objects"""
    return ActivityAuditStatus.objects.filter(
                        user=self,
                        activity__activity_type__in=notification_types,
                        **kwargs
                    )

def _assert_user_can(
        user=None,
        post=None, #related post (may be parent)
        admin_or_moderator_required=False,
        owner_can=False,
        action_display=None,
        suspended_owner_cannot=False,
        suspended_user_cannot=False,
        blocked_user_cannot=False,
        min_rep_setting=None
    ):
    """generic helper assert for use in several
    User.assert_can_XYZ() calls regarding changing content

    user is required and at least one error message

    if assertion fails, method raises exception.PermissionDenied
    with appropriate text as a payload
    """
    action_display = action_display or _('perform this action')

    from askbot.deps.django_authopenid.util import email_is_blacklisted

    if askbot_settings.READ_ONLY_MODE_ENABLED:
        error_message = _(
            'Sorry, you cannot %(perform_action)s because '
            'the site is temporarily read only'
        ) % {'perform_action': action_display}

    elif ('@' in user.email) and email_is_blacklisted(user.email) \
        and askbot_settings.BLACKLISTED_EMAIL_PATTERNS_MODE == 'strict':
        error_message = format_lazy('{} {}',
            _('Sorry, you cannot %(perform_action)s because '
              '%(domain)s emails have been blacklisted.'
            ),
            _('Please <a href="%(url)s">change your email</a>.')
        ) % {
            'perform_action': action_display,
            'domain': user.email.split('@')[1],
            'url': reverse('edit_user', args=(user.id,))
        }

    elif user.is_read_only():
        error_message = _('Sorry, but you have only read access')

    elif user.is_active == False:
        error_message = getattr(
                            django_settings,
                            'ASKBOT_INACTIVE_USER_MESSAGE',
                            _(message_keys.ACCOUNT_CANNOT_PERFORM_ACTION) % {
                                'perform_action': action_display,
                                'your_account_is': _('your account is disabled')
                            }
                        )

    elif blocked_user_cannot and user.is_blocked():
        error_message = _(message_keys.ACCOUNT_CANNOT_PERFORM_ACTION) % {
            'perform_action': action_display,
            'your_account_is': _('your account is blocked')
        }
        error_message = format_lazy('{}.</br> {}',error_message, _(message_keys.PUNISHED_USER_INFO))

    elif post and owner_can and user.pk == post.author_id:
        if user.is_suspended() and suspended_owner_cannot:
            error_message = _(message_keys.ACCOUNT_CANNOT_PERFORM_ACTION) % {
                'perform_action': action_display,
                'your_account_is': _('your account is suspended')
            }
        else:
            return

    elif suspended_user_cannot and user.is_suspended():
        error_message = _(message_keys.ACCOUNT_CANNOT_PERFORM_ACTION) % {
            'perform_action': action_display,
            'your_account_is': _('your account is suspended')
        }

    elif user.is_administrator() or user.is_moderator():
        return

    elif user.is_post_moderator(post):
        return

    elif min_rep_setting and user.reputation < min_rep_setting:
        raise askbot_exceptions.InsufficientReputation(
            _(message_keys.MIN_REP_REQUIRED_TO_PERFORM_ACTION) % {
                'perform_action': action_display,
                'min_rep': min_rep_setting
            }
        )

    elif admin_or_moderator_required:
        if min_rep_setting is None:
            #message about admins only
            error_message = _(
                'Sorry, only moderators and site administrators can %(perform_action)s'
            ) % {
                'perform_action': action_display
            }
        else:
            #message with minimum reputation
            error_message = _(
                'Sorry, only administrators, moderators '
                'or users with reputation > %(min_rep)s '
                'can %(perform_action)s'
            ) % {
                'min_rep': min_rep_setting,
                'perform_action': action_display
            }
    else:
        return

    assert(error_message is not None)
    raise django_exceptions.PermissionDenied(error_message)

def user_assert_can_approve_post_revision(self, post_revision = None):
    _assert_user_can(
        user=self,
        admin_or_moderator_required=True
    )

def user_assert_can_unaccept_best_answer(self, answer=None):
    assert getattr(answer, 'post_type', '') == 'answer'
    suspended_error_message = _(message_keys.ACCOUNT_CANNOT_PERFORM_ACTION) % {
        'perform_action': askbot_settings.WORDS_ACCEPT_OR_UNACCEPT_THE_BEST_ANSWER,
        'your_account_is': _('your account is suspended')
    }
    blocked_error_message = _(message_keys.ACCOUNT_CANNOT_PERFORM_ACTION) % {
        'perform_action': askbot_settings.WORDS_ACCEPT_OR_UNACCEPT_THE_BEST_ANSWER,
        'your_account_is': _('your account is blocked')
    }

    if self.is_blocked():
        error_message = blocked_error_message
    elif self.is_suspended():
        error_message = suspended_error_message
    elif self.pk == answer.thread._question_post().author_id:
        if self.pk == answer.author_id:
            if not self.is_administrator():
                #check rep
                _assert_user_can(
                    user=self,
                    action_display=askbot_settings.WORDS_ACCEPT_OR_UNACCEPT_OWN_ANSWER,
                    blocked_user_cannot=True,
                    suspended_owner_cannot=True,
                    min_rep_setting = askbot_settings.MIN_REP_TO_ACCEPT_OWN_ANSWER
                )
        return # success

    elif self.is_administrator() or self.is_moderator():
        return # success

    elif self.reputation >= askbot_settings.MIN_REP_TO_ACCEPT_ANY_ANSWER or \
        self.is_post_moderator(answer):

        will_be_able_at = (
            answer.added_at +
            datetime.timedelta(
                days=askbot_settings.MIN_DAYS_FOR_STAFF_TO_ACCEPT_ANSWER)
        )

        if timezone.now() < will_be_able_at:
            error_message = _(message_keys.CANNOT_PERFORM_ACTION_UNTIL) % {
                'perform_action': askbot_settings.WORDS_ACCEPT_OR_UNACCEPT_THE_BEST_ANSWER,
                'until': will_be_able_at.strftime('%d/%m/%Y')
            }
        else:
            return

    else:
        question_owner = answer.thread._question_post().author
        error_message = _(message_keys.MODERATORS_OR_AUTHOR_CAN_PEFROM_ACTION) % {
            'post_author': askbot_settings.WORDS_AUTHOR_OF_THE_QUESTION,
            'perform_action': askbot_settings.WORDS_ACCEPT_OR_UNACCEPT_THE_BEST_ANSWER,
        }

    raise django_exceptions.PermissionDenied(error_message)

def user_assert_can_accept_best_answer(self, answer=None):
    assert getattr(answer, 'post_type', '') == 'answer'
    self.assert_can_unaccept_best_answer(answer)

def user_assert_can_vote_for_post(self, post=None, direction=None):
    """raises exceptions.PermissionDenied exception
    if user can't in fact upvote

    :param:direction can be 'up' or 'down'
    :param:post can be instance of question or answer
    """
    if self.pk == post.author_id:
        raise django_exceptions.PermissionDenied(
            _('Sorry, you cannot vote for your own posts')
        )

    assert(direction in ('up', 'down'))

    if direction == 'up':
        min_rep_setting = askbot_settings.MIN_REP_TO_VOTE_UP
        action_display = _('upvote')
    else:
        min_rep_setting = askbot_settings.MIN_REP_TO_VOTE_DOWN
        action_display = _('downvote')

    _assert_user_can(
        user=self,
        action_display=action_display,
        blocked_user_cannot=True,
        suspended_user_cannot=True,
        min_rep_setting = min_rep_setting,
    )


def user_assert_can_upload_file(user):
    _assert_user_can(
        user=user,
        action_display=_('upload files'),
        blocked_user_cannot=True,
        suspended_user_cannot=True,
        min_rep_setting=askbot_settings.MIN_REP_TO_UPLOAD_FILES
    )


def user_can_upload_file(user):
    try:
        user.assert_can_upload_file()
    except Exception: #pylint: disable=broad-except
        return False
    return True


def user_can_upload_attachment(user):
    if not askbot_settings.ATTACHMENT_UPLOADS_ENABLED:
        return False

    if askbot_settings.GROUPS_ENABLED:
        groups = user.get_groups()
        if groups.filter(can_upload_attachments=True).count() == 0:
            return False

    return user.can_upload_file()


def user_can_upload_image(user):
    if not askbot_settings.IMAGE_UPLOADS_ENABLED:
        return False

    if askbot_settings.GROUPS_ENABLED:
        groups = user.get_groups()
        if groups.filter(can_upload_images=True).count() == 0:
            return False

    return user.can_upload_file()


def user_assert_can_join_or_leave_group(self):
    _assert_user_can(
        user=self,
        action_display=_('join or leave groups'),
        blocked_user_cannot=True,
        suspended_user_cannot=True
    )
User.add_to_class(
    'assert_can_join_or_leave_group',
    user_assert_can_join_or_leave_group
)


def user_assert_can_mark_tags(self):
    _assert_user_can(
        user=self,
        action_display=_('mark or unmark tags'),
        blocked_user_cannot=True,
    )


def user_assert_can_merge_questions(self):
    _assert_user_can(
        user=self,
        action_display=_('merge duplicate questions'),
        admin_or_moderator_required=True
    )


def user_assert_can_post_text(self, text):
    """Raises exceptions.PermissionDenied, if user does not have
    privilege to post given text, depending on the contents
    """
    if re.search(URL_RE, text):
        min_rep = askbot_settings.MIN_REP_TO_SUGGEST_LINK
        if self.is_authenticated and self.reputation < min_rep:
            message = _(
                'Could not post, because your karma is insufficient to publish links'
            )
            raise django_exceptions.PermissionDenied(message)


def user_assert_can_post_question(self):
    """raises exceptions.PermissionDenied with
    text that has the reason for the denial
    """
    _assert_user_can(
        user=self,
        action_display=askbot_settings.WORDS_ASK_QUESTIONS,
        blocked_user_cannot=True,
        suspended_user_cannot=True,
    )

    if not self.has_group_permission('post_questions'):
        error_message_tpl = _('Sorry, you cannot %(perform_action)s')
        error_message = error_message_tpl % {'perform_action': askbot_settings.WORDS_ASK_QUESTIONS}
        raise django_exceptions.PermissionDenied(error_message)


def user_assert_can_post_answer(self, thread=None):
    """same as user_can_post_question
    """
    limit_answers = askbot_settings.LIMIT_ONE_ANSWER_PER_USER
    if limit_answers and thread.has_answer_by_user(self):
        message = _(
            'Sorry, %(you_already_gave_an_answer)s, please edit it instead.'
        ) % {
            'you_already_gave_an_answer': askbot_settings.WORDS_YOU_ALREADY_GAVE_AN_ANSWER
        }
        raise askbot_exceptions.AnswerAlreadyGiven(message)

    _assert_user_can(
        user=self,
        action_display=askbot_settings.WORDS_POST_ANSWERS,
        blocked_user_cannot=True,
        suspended_user_cannot=True,
    )

    if not self.has_group_permission('post_answers'):
        error_message_tpl = _('Sorry, you cannot %(perform_action)s')
        error_message = error_message_tpl % {'perform_action': askbot_settings.WORDS_POST_ANSWERS}
        raise django_exceptions.PermissionDenied(error_message)


def user_assert_can_edit_comment(self, comment=None):
    """raises exceptions.PermissionDenied if user
    cannot edit comment with the reason given as message

    only owners, moderators or admins can edit comments
    """
    if self.is_administrator() or self.is_moderator():
        return

    if comment.thread and comment.thread.closed:
        if askbot_settings.COMMENTING_CLOSED_QUESTIONS_ENABLED == False:
            error_message = _('Sorry, commenting closed entries is not allowed')
            raise django_exceptions.PermissionDenied(error_message)

    if comment.author_id == self.pk:
        if askbot_settings.USE_TIME_LIMIT_TO_EDIT_COMMENT:
            now = timezone.now()
            delta_seconds = 60 * askbot_settings.MINUTES_TO_EDIT_COMMENT
            if now - comment.added_at > datetime.timedelta(0, delta_seconds):
                if comment.is_last():
                    return
                error_message = ngettext(
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

    if not (self.is_blocked() or self.is_suspended()):
        if self.reputation >= askbot_settings.MIN_REP_TO_EDIT_OTHERS_POSTS:
            return

    error_message = _(
        'Sorry, but only post owners or moderators can edit comments'
    )
    raise django_exceptions.PermissionDenied(error_message)


def user_assert_can_convert_post(self, post=None):
    """raises exceptions.PermissionDenied if user is not allowed to convert the
    post to another type (comment -> answer, answer -> comment)

    only owners, moderators or admins can convert posts
    """
    _assert_user_can(
        user=self,
        action_display=_('repost items'),
        owner_can=True,
        blocked_user_cannot=True,
    )


def user_can_post_comment(self, parent_post=None):
    """a simplified method to test ability to comment
    """
    if self.is_administrator_or_moderator():
        return True

    if parent_post and parent_post.thread and parent_post.thread.closed:
        if askbot_settings.COMMENTING_CLOSED_QUESTIONS_ENABLED == False:
            return False

    if self.is_suspended():
        if parent_post and self.pk == parent_post.author_id:
            return True
        return False

    if self.is_blocked():
        return False

    return self.has_group_permission('post_comments')

def user_assert_can_post_comment(self, parent_post=None):
    """raises exceptions.PermissionDenied if
    user cannot post comment

    the reason will be in text of exception
    """
    _assert_user_can(
        user=self,
        post=parent_post,
        action_display=_('post comments'),
        owner_can=True,
        blocked_user_cannot=True,
        suspended_user_cannot=True,
    )

    if self.is_administrator_or_moderator():
        return

    if parent_post.thread and parent_post.thread.closed:
        if askbot_settings.COMMENTING_CLOSED_QUESTIONS_ENABLED == False:
            error_message = _('Sorry, commenting closed entries is not allowed')
            raise django_exceptions.PermissionDenied(error_message)

    if not self.has_group_permission('post_comments'):
        error_message_tpl = _('Sorry, you cannot %(perform_action)s')
        error_message = error_message_tpl % {'perform_action': _('post comments')}
        raise django_exceptions.PermissionDenied(error_message)

    if parent_post.has_moderated_comment(self):
        error_message = _('Sorry, only one moderated comment per post is allowed')
        raise django_exceptions.PermissionDenied(error_message)


def user_assert_can_see_deleted_post(self, post=None):

    """attn: this assertion is independently coded in
    Question.get_answers call
    """
    try:
        _assert_user_can(
            user=self,
            post=post,
            admin_or_moderator_required=True,
            owner_can=True
        )
    except django_exceptions.PermissionDenied as e:
        #re-raise the same exception with a different message
        error_message = _(
            'This post has been deleted and can be seen only '
            'by post owners, site administrators and moderators'
        )
        raise django_exceptions.PermissionDenied(error_message)


def user_assert_can_edit_deleted_post(self, post = None):
    assert(post.deleted == True)
    try:
        self.assert_can_see_deleted_post(post)
    except django_exceptions.PermissionDenied as e:
        error_message = _(
            'Sorry, only moderators, site administrators '
            'and post owners can edit deleted posts'
        )
        raise django_exceptions.PermissionDenied(error_message)


def user_assert_can_edit_post(self, post=None):
    """assertion that raises exceptions.PermissionDenied
    when user is not authorised to edit this post
    """

    if post.deleted == True:
        self.assert_can_edit_deleted_post(post)
        return

    if post.wiki == True:
        action_display=_('edit wiki posts')
        min_rep_setting = askbot_settings.MIN_REP_TO_EDIT_WIKI
    else:
        action_display=_('edit posts')
        min_rep_setting = askbot_settings.MIN_REP_TO_EDIT_OTHERS_POSTS

    _assert_user_can(
        user=self,
        post=post,
        action_display=action_display,
        owner_can=True,
        blocked_user_cannot=True,
        suspended_user_cannot=True,
        min_rep_setting=min_rep_setting
    )

    #mods can edit posts without time limit
    if self.is_administrator() or self.is_moderator():
        return

    #question is editable without limit as long as there are no answers
    if post.is_question():
        if post.thread.answer_count == 0:
            return

    if post.is_answer():
        use_limit = askbot_settings.USE_TIME_LIMIT_TO_EDIT_ANSWER
        minutes_limit = askbot_settings.MINUTES_TO_EDIT_ANSWER
    elif post.is_question():
        use_limit = askbot_settings.USE_TIME_LIMIT_TO_EDIT_QUESTION
        minutes_limit = askbot_settings.MINUTES_TO_EDIT_QUESTION
    else:
        return

    if use_limit == False:
        return

    now = timezone.now()
    delta_seconds = 60 * minutes_limit
    if now - post.added_at > datetime.timedelta(0, delta_seconds):
        #vague message because it is hard to add
        #these phrases to askbot.conf.words as parameters
        error_message = ngettext(
            'Sorry, posts like this are editable only '
            'within %(minutes)s minute from posting',
            'Sorry, posts like this are editable only '
            'within %(minutes)s minutes from posting',
            minutes_limit
        ) % {'minutes': minutes_limit}
        raise django_exceptions.PermissionDenied(error_message)


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
    if self.is_administrator() or self.is_moderator():
        return
    if self.pk == question.author_id:
        #if there are answers by other people,

        answer_count = question.thread.all_answers().exclude(author=self).count()
        min_karma = askbot_settings.MIN_REP_TO_DELETE_OWN_QUESTIONS
        if answer_count and self.reputation < min_karma:
            msg = _('At least %d karma point is required to delete own questions') \
                                                                            % min_karma
            raise django_exceptions.PermissionDenied(msg)

        answer_count = question.thread.all_answers()\
                        .exclude(author=self).exclude(points__lte=0).count()

        if answer_count > 0:
            msg = ngettext(
                'Sorry, cannot delete this since it '
                'has an upvoted response posted by someone else',
                'Sorry, cannot delete this since it '
                'has some upvoted responses posted by someone else',
                answer_count
            )
            raise django_exceptions.PermissionDenied(msg)


def user_assert_can_delete_answer(self, answer = None):
    """intentionally use "post" word in the messages
    instead of "answer", because this logic also applies to
    assert on deleting question (in addition to some special rules)
    """
    min_rep_setting = askbot_settings.MIN_REP_TO_DELETE_OTHERS_POSTS

    _assert_user_can(
        user=self,
        post=answer,
        action_display=_('delete posts'),
        owner_can=True,
        blocked_user_cannot=True,
        suspended_user_cannot=True,
        min_rep_setting=min_rep_setting,
    )


def user_assert_can_close_question(self, question = None):
    assert(getattr(question, 'post_type', '') == 'question')
    min_rep_setting = askbot_settings.MIN_REP_TO_CLOSE_OTHERS_QUESTIONS
    _assert_user_can(
        user=self,
        post=question,
        action_display=askbot_settings.WORDS_CLOSE_QUESTIONS,
        owner_can=True,
        suspended_owner_cannot=True,
        blocked_user_cannot=True,
        suspended_user_cannot=True,
        min_rep_setting=min_rep_setting,
    )


def user_assert_can_reopen_question(self, question = None):
    assert(question.post_type == 'question')
    _assert_user_can(
        user=self,
        post=question,
        action_display=_('reopen questions'),
        suspended_owner_cannot=True,
        #for some reason rep to reopen own questions != rep to close own q's
        min_rep_setting=askbot_settings.MIN_REP_TO_CLOSE_OTHERS_QUESTIONS,
        blocked_user_cannot=True,
        suspended_user_cannot=True,
    )


def user_assert_can_flag_offensive(self, post = None):

    assert(post is not None)

    double_flagging_error_message = _(
        'You have flagged this post before and '
        'cannot do it more than once'
    )

    if self.get_flags_for_post(post).count() > 0:
        raise askbot_exceptions.DuplicateCommand(double_flagging_error_message)

    min_rep_setting = askbot_settings.MIN_REP_TO_FLAG_OFFENSIVE

    _assert_user_can(
        user = self,
        post = post,
        action_display=_('flag posts as offensive'),
        blocked_user_cannot=True,
        suspended_user_cannot=True,
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


def user_assert_can_follow_question(self, question=None):
    _assert_user_can(
        user=self,
        post=question, #related post (may be parent)
        owner_can=True,
        action_display=askbot_settings.WORDS_FOLLOW_QUESTIONS,
        blocked_user_cannot=True
    )


def user_assert_can_remove_flag_offensive(self, post=None):
    assert(post is not None)

    if self.is_administrator_or_moderator():
        return

    non_existing_flagging_error_message = _('cannot remove non-existing flag')

    if self.get_flags_for_post(post).count() < 1:
        raise django_exceptions.PermissionDenied(non_existing_flagging_error_message)

    min_rep_setting = askbot_settings.MIN_REP_TO_FLAG_OFFENSIVE
    _assert_user_can(
        user=self,
        post=post,
        action_display=_('remove flags'),
        blocked_user_cannot=True,
        suspended_user_cannot=True,
        min_rep_setting=min_rep_setting
    )


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
    if self.is_administrator() or self.is_moderator():
        return
    raise django_exceptions.PermissionDenied(permission_denied_message)


def user_assert_can_retag_question(self, question = None):

    if question.deleted == True:
        self.assert_can_edit_deleted_post(question)

    _assert_user_can(
        user=self,
        post=question,
        action_display=askbot_settings.WORDS_RETAG_QUESTIONS,
        owner_can=True,
        blocked_user_cannot=True,
        suspended_user_cannot=True,
        min_rep_setting=askbot_settings.MIN_REP_TO_RETAG_OTHERS_QUESTIONS
    )


def user_assert_can_delete_comment(self, comment = None):
    min_rep_setting = askbot_settings.MIN_REP_TO_DELETE_OTHERS_COMMENTS

    _assert_user_can(
        user = self,
        post = comment,
        action_display=_('delete comments'),
        owner_can = True,
        blocked_user_cannot=True,
        suspended_user_cannot=True,
        min_rep_setting = min_rep_setting,
    )

    if self.is_administrator_or_moderator():
        return

    if comment.author_id == self.pk:
        if askbot_settings.USE_TIME_LIMIT_TO_EDIT_COMMENT:
            now = timezone.now()
            delta_seconds = 60 * askbot_settings.MINUTES_TO_EDIT_COMMENT
            if now - comment.added_at > datetime.timedelta(0, delta_seconds):
                if not comment.is_last():
                    error_message = ngettext(
                        'Sorry, comments (except the last one) are deletable only '
                        'within %(minutes)s minute from posting',
                        'Sorry, comments (except the last one) are deletable only '
                        'within %(minutes)s minutes from posting',
                        askbot_settings.MINUTES_TO_EDIT_COMMENT
                    ) % {'minutes': askbot_settings.MINUTES_TO_EDIT_COMMENT}
                    raise django_exceptions.PermissionDenied(error_message)


def user_assert_can_revoke_old_vote(self, vote):
    """raises exceptions.PermissionDenied if old vote
    cannot be revoked due to age of the vote
    """
    if askbot_settings.MAX_DAYS_TO_CANCEL_VOTE <= 0:
        return
    if (timezone.now() - vote.voted_at).days \
        >= askbot_settings.MAX_DAYS_TO_CANCEL_VOTE:
        raise django_exceptions.PermissionDenied(
            _('sorry, but older votes cannot be revoked')
        )


def user_anonymize(self):
    """Removes personal data and disables account"""
    self.email = ''
    self.password = ''
    self.username = self.get_anonymized_name()
    self.save()
    self.askbot_profile.anonymize()
    self.askbot_profile.save()
    self.posts.update(is_anonymous=True)
    revs = PostRevision.objects.filter(author=self)
    revs.update(is_anonymous=True)
    self.clear_cached_data()
    self.notification_subscriptions.update(frequency='n')
    self.userassociation_set.all().delete()
    for prof in self.localized_askbot_profiles.all():
        prof.anonymize()
        prof.save()


def user_get_localized_profile(self):
    lang = get_language()
    key = get_localized_profile_cache_key(self, lang)
    profile = cache.get(key)
    if not profile:
        kwargs = {
            'language_code': lang,
            'auth_user': self
        }
        profile = LocalizedUserProfile.objects.get_or_create(**kwargs)[0]
        profile.update_cache()
    return profile


def user_update_localized_profile(self, **kwargs):
    profile = self.get_localized_profile()
    for key, val in list(kwargs.items()):
        setattr(profile, key, val)
    profile.update_cache()
    lp = LocalizedUserProfile.objects.filter(pk=profile.pk)
    lp.update(**kwargs)


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

@reject_forbidden_phrases
def user_post_comment(
                    self,
                    parent_post=None,
                    body_text=None,
                    timestamp=None,
                    by_email=False,
                    ip_addr=None,
                ):
    """post a comment on behalf of the user
    to parent_post
    """

    if body_text is None:
        raise ValueError('body_text is required to post comment')
    if parent_post is None:
        raise ValueError('parent_post is required to post comment')
    if timestamp is None:
        timestamp = timezone.now()

    self.assert_can_post_comment(parent_post=parent_post)

    comment = parent_post.add_comment(
                    user=self,
                    comment=body_text,
                    added_at=timestamp,
                    by_email=by_email,
                    ip_addr=ip_addr,
                )
    comment.add_to_groups([self.get_personal_group()])

    parent_post.thread.reset_cached_data()
    award_badges_signal.send(None,
                             event='post_comment',
                             actor=self,
                             context_object=comment,
                             timestamp=timestamp)
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
    is_on_read_only_group = user.get_groups().filter(read_only=True).count()
    if askbot_settings.READ_ONLY_MODE_ENABLED or is_on_read_only_group:
        user.message_set.create(message = _('Sorry, but you have only read access'))
        return

    for aq in AnonymousQuestion.objects.filter(session_key=session_key):
        aq.publish(user)
    for aa in AnonymousAnswer.objects.filter(session_key=session_key):
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
    self.assert_can_mark_tags()

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
    language_code = get_language()
    existing_tagnames = Tag.objects.filter(
                            name__in=tagnames,
                            language_code=language_code
                        ).values_list(
                            'name', flat=True
                        )
    non_existing_tagnames = set(tagnames) - set(existing_tagnames)
    #create those tags, and if tags are moderated make them suggested
    if (len(non_existing_tagnames) > 0):
        Tag.objects.create_in_bulk(
                        tag_names=tagnames,
                        user=self,
                        language_code=language_code
                    )

    #below we update normal tag selections
    marked_ts = MarkedTag.objects.filter(
                                    user = self,
                                    tag__name__in=tagnames,
                                    tag__language_code=language_code
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
            ts = Tag.objects.filter(
                            name__in=unmarked_names,
                            language_code=language_code
                        )
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

def user_merge_duplicate_questions(self, from_q, to_q):
    """merges content from the ``from_thread`` to the ``to-thread``"""
    #todo: maybe assertion will depend on which questions are merged
    self.assert_can_merge_questions()
    to_q.merge_post(from_q, user=self)
    from_thread = from_q.thread
    to_thread = to_q.thread
    #set new thread value to all posts
    posts = from_thread.posts.all()
    posts.update(thread=to_thread)

    if askbot_settings.LIMIT_ONE_ANSWER_PER_USER:
        #merge answers if only one is allowed per user
        answers = to_thread.all_answers()
        answer_map = collections.defaultdict(list)
        #compile all answers by user
        for answer in answers:
            author = answer.author
            answer_map[author].append(answer)

        for author in answer_map:
            author_answers = answer_map[author]
            if author_answers > 1:
                first_answer = author_answers.pop(0)
                for answer in author_answers:
                    first_answer.merge_post(answer, user=self)

    #from_thread.spaces.clear()
    from_thread.delete()
    to_thread.answer_count = to_thread.get_answers().count()
    to_thread.last_activity_by = self
    to_thread.last_activity_at = timezone.now()
    to_thread.save()
    to_thread.reset_cached_data()


def user_recount_badges(self):
    bronze, silver, gold = 0, 0, 0

    awards = Award.objects.filter(
                            user=self
                        ).annotate(
                            count=Count('badge')
                        )
    for award in awards:
        badge = award.badge
        if badge.is_enabled():
            level = badge.get_level()
            if level == const.BRONZE_BADGE:
                bronze += award.count
            elif level == const.SILVER_BADGE:
                silver += award.count
            elif level == const.GOLD_BADGE:
                gold += award.count

    self.bronze = bronze
    self.silver = silver
    self.gold = gold
    self.save()


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
    question.thread.reset_cached_data()
    award_badges_signal.send(None,
                             event='retag_question',
                             actor=self,
                             context_object=question,
                             timestamp=timestamp)


def user_repost_comment_as_answer(self, comment):
    """converts comment to answer under the
    parent question"""

    #todo: add assertion
    self.assert_can_convert_post(comment)

    comment.post_type = 'answer'
    old_parent = comment.parent

    comment.parent = comment.thread._question_post()
    comment.parse_and_save(author=self)

    comment.thread.update_answer_count()

    comment.parent.recount_comments()
    comment.parent.save()

    old_parent.recount_comments()
    old_parent.save()
    comment.thread.reset_cached_data()

@auto_now_timestamp
def user_accept_best_answer(
                self, answer=None,
                timestamp=None,
                cancel=False,
                force=False
            ):
    if cancel:
        return self.unaccept_best_answer(
                                answer=answer,
                                timestamp=timestamp,
                                force=force
                            )
    if force == False:
        self.assert_can_accept_best_answer(answer)
    if answer.endorsed:
        return

    #todo: optionally allow accepting >1 answer
    #but for now only one
    prev_accepted_answers = answer.thread.posts.filter(
                                        post_type='answer',
                                        endorsed=True
                                    )
    for accepted_answer in prev_accepted_answers:
        auth.onAnswerAcceptCanceled(accepted_answer, self)

    auth.onAnswerAccept(answer, self, timestamp=timestamp)
    award_badges_signal.send(None,
                             event='accept_best_answer',
                             actor=self,
                             context_object=answer,
                             timestamp=timestamp)

@auto_now_timestamp
def user_unaccept_best_answer(
                self, answer=None,
                timestamp=None,
                force=False
            ):
    if force == False:
        self.assert_can_unaccept_best_answer(answer)
    if not answer.endorsed:
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
    comment.thread.reset_cached_data()

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

    if answer.endorsed and answer.thread.accepted_answer == answer:
        #forget about the accepted answer,
        #but do not erase the "endorsement" info on
        #the answer post itself, to allow restoring
        answer.thread.accepted_answer = None

    answer.save()

    answer.thread.update_answer_count()
    answer.thread.update_last_activity_info()
    answer.thread.reset_cached_data()
    logging.debug('updated answer count to %d' % answer.thread.answer_count)

    signals.after_post_removed.send(
        sender=answer.__class__,
        instance=answer,
        deleted_by=self
    )
    award_badges_signal.send(None,
                             event='delete_post',
                             actor=self,
                             context_object=answer,
                             timestamp=timestamp)


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
        if tag.used_count <= 1:
            tag.used_count = 0
            tag.deleted = True
            tag.deleted_by = self
            tag.deleted_at = timestamp
        else:
            tag.decrement_used_count()
        tag.save()

    signals.after_post_removed.send(
        sender = question.__class__,
        instance = question,
        deleted_by = self
    )
    award_badges_signal.send(None,
                             event='delete_post',
                             actor=self,
                             context_object=question,
                             timestamp=timestamp)


def user_delete_all_content_authored_by_user(self,
                                             author,
                                             timestamp=None,
                                             mark_as_spam=False):
    """Deletes all questions, answers and comments made by the user"""
    count = 0

    #delete answers
    answers = Post.objects.get_answers().filter(author=author, deleted=False)
    timestamp = timestamp or timezone.now()
    count += answers.update(deleted_at=timestamp, deleted_by=self, deleted=True)
    post_ids = list(answers.values_list('pk', flat=True))

    #delete questions
    questions = Post.objects.get_questions().filter(author=author, deleted=False)
    count += questions.count()
    for question in questions:
        self.delete_question(question=question, timestamp=timestamp)
        post_ids.append(question.pk)

    threads = Thread.objects.filter(last_activity_by=author)
    for thread in threads:
        thread.update_last_activity_info()

    #delete threads
    thread_ids = questions.values_list('thread_id', flat=True)
    #load second time b/c threads above are not quite real
    threads = Thread.objects.filter(id__in=thread_ids)
    threads.update(deleted=True)
    for thread in threads:
        thread.reset_cached_data()

    # delete comments
    # todo: switch to marking comments as deleted
    comments = Post.objects.get_comments().filter(author=author)
    count += comments.count()
    comments.delete()

    if mark_as_spam:
        Post.objects.filter(id__in=post_ids).update(
            marked_as_spam=True,
            marked_as_spam_by=self,
            marked_as_spam_at=timestamp
        )
        signals.posts_marked_as_spam.send(post_ids=post_ids, sender=self.__class__)

    #delete all unused tags created by this user
    #tags = author.created_tags.all()
    #tag_ids = list()
    #for tag in tags:
    #    if tag.used_count == 0:
    #        tag_ids.append(tag.id)
    #Tag.objects.filter(id__in=tag_ids).delete()

    return count


@auto_now_timestamp
def user_close_question(self, question=None, reason=None, timestamp=None):
    self.assert_can_close_question(question)
    question.thread.set_closed_status(closed=True, closed_by=self, closed_at=timestamp, close_reason_text=reason)

@auto_now_timestamp
def user_reopen_question(
                    self,
                    question = None,
                    timestamp = None
                ):
    self.assert_can_reopen_question(question)
    question.thread.set_closed_status(closed=False, closed_by=self, closed_at=timestamp, close_reason_text='')

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
    post.thread.reset_cached_data()

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
        if post.post_type == 'question':
            post.thread.deleted = False
            post.thread.save()
        post.thread.reset_cached_data()
        if post.post_type == 'answer':
            if post.endorsed and post.thread.accepted_answer == None:
                post.thread.accepted_answer = post
            post.thread.update_answer_count()
            post.thread.update_last_activity_info()
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
        signals.after_post_restored.send(
            sender=post.__class__,
            instance=post,
            restored_by=self,
        )
    else:
        raise NotImplementedError()

@reject_forbidden_phrases
def user_post_question(
                    self,
                    title=None,
                    body_text='',
                    tags=None, # string of space-separated tags
                    wiki=False,
                    is_anonymous=False,
                    is_private=False,
                    group_id=None,
                    timestamp=None,
                    by_email=False,
                    email_address=None,
                    language=None,
                    ip_addr=None,
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
        timestamp = timezone.now()

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
                                    language=language,
                                    ip_addr=ip_addr
                                )
    thread.reset_cached_data()
    question = thread._question_post()
    if question.author != self:
        raise ValueError('question.author != self')
    question.author = self # HACK: Some tests require that question.author IS exactly the same object as self-user (kind of identity map which Django doesn't provide),
                           #       because they set some attributes for that instance and expect them to be changed also for question.author

    if askbot_settings.AUTO_FOLLOW_QUESTION_BY_OP:
        self.toggle_favorite_question(question)

    award_badges_signal.send(None,
                             event='post_question',
                             actor=self,
                             context_object=question,
                             timestamp=timestamp)

    return question

@auto_now_timestamp
@reject_forbidden_phrases
def user_edit_comment(
                    self,
                    comment_post=None,
                    body_text=None,
                    timestamp=None,
                    by_email=False,
                    suppress_email=False,
                    ip_addr=None,
                ):
    """apply edit to a comment, the method does not
    change the comments timestamp and no signals are sent
    todo: see how this can be merged with edit_post
    todo: add timestamp
    """
    self.assert_can_edit_comment(comment_post)
    revision = comment_post.apply_edit(
                        text=body_text,
                        edited_at=timestamp,
                        edited_by=self,
                        by_email=by_email,
                        suppress_email=suppress_email,
                        ip_addr=ip_addr,
                    )
    comment_post.thread.reset_cached_data()
    return revision

def user_edit_post(self,
                   post=None,
                   body_text=None,
                   revision_comment=None,
                   timestamp=None,
                   by_email=False,
                   is_private=False,
                   suppress_email=False,
                   ip_addr=None):
    """Edits post body.
    Todo: unify it in the style of just a generic post
    this requires refactoring of underlying functions
    because we cannot bypass the permissions checks set within."""
    if post.post_type == 'comment':
        return self.edit_comment(comment_post=post,
							body_text=body_text,
							by_email=by_email,
							suppress_email=suppress_email,
							ip_addr=ip_addr)
    elif post.post_type == 'answer':
        return self.edit_answer(
            answer=post,
            body_text=body_text,
            timestamp=timestamp,
            revision_comment=revision_comment,
            by_email=by_email,
            suppress_email=suppress_email,
            ip_addr=ip_addr
        )
    elif post.post_type == 'question':
        return self.edit_question(
            question=post,
            body_text=body_text,
            timestamp=timestamp,
            revision_comment=revision_comment,
            by_email=by_email,
            is_private=is_private,
            suppress_email=suppress_email,
            ip_addr=ip_addr
        )
    elif post.post_type == 'tag_wiki':
        return post.apply_edit(
            edited_at=timestamp,
            edited_by=self,
            text=body_text,
            #todo: summary name clash in question and question revision
            comment=revision_comment,
            wiki=True,
            by_email=False,
            ip_addr=ip_addr,
        )
    else:
        raise NotImplementedError()

@auto_now_timestamp
@reject_forbidden_phrases
def user_edit_question(
                self,
                question=None,
                title=None,
                body_text=None,
                revision_comment=None,
                tags=None, # string of space-separated tags
                wiki=False,
                edit_anonymously=False,
                is_private=False,
                timestamp=None,
                force=False,#if True - bypass the assert
                by_email=False,
                suppress_email=False,
                ip_addr=None,
            ):
    if force == False:
        self.assert_can_edit_question(question)

    ##it is important to do this before __apply_edit b/c of signals!!!
    if question.is_private() != is_private:
        if is_private:
            #todo: make private for author or for the editor?
            question.thread.make_private(question.author)
        else:
            question.thread.make_public(recursive=False)

    latest_revision = question.get_latest_revision(self)
    #a hack to allow partial edits - important for SE loader
    if title is None:
        title = question.thread.title
    if tags is None:
        tags = latest_revision.tagnames

    #revision has title and tags as well
    revision = question.apply_edit(
        edited_at=timestamp,
        edited_by=self,
        text=body_text,
        #todo: summary name clash in question and question revision
        comment=revision_comment,
        wiki=wiki,
        edit_anonymously=edit_anonymously,
        is_private=is_private,
        by_email=by_email,
        suppress_email=suppress_email,
        ip_addr=ip_addr
    )

    # Update the Question tag associations
    if latest_revision.tagnames != tags:
        question.thread.update_tags(
            tagnames=tags, user=self, timestamp=timestamp
        )

    question.thread.title = title
    question.thread.tagnames = tags
    question.thread.set_last_activity_info(
        last_activity_at=timestamp,
        last_activity_by=self
    )
    question.thread.save()
    question.thread.reset_cached_data()

    award_badges_signal.send(None,
                             event='edit_question',
                             actor=self,
                             context_object=question,
                             timestamp=timestamp)
    return revision

@auto_now_timestamp
@reject_forbidden_phrases
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
                    ip_addr=None,
                ):

    if force == False:
        self.assert_can_edit_answer(answer)

    if answer.is_private() != is_private:
        if is_private:
            answer.make_private(answer.author)
        else:
            answer.make_public()

    revision = answer.apply_edit(edited_at=timestamp,
                                 edited_by=self,
                                 text=body_text,
                                 comment=revision_comment,
                                 wiki=wiki,
                                 is_private=is_private,
                                 by_email=by_email,
                                 suppress_email=suppress_email,
                                 ip_addr=ip_addr)

    answer.thread.set_last_activity_info(
        last_activity_at=timestamp,
        last_activity_by=self
    )
    answer.thread.save()
    answer.thread.reset_cached_data()

    award_badges_signal.send(None,
                             event='edit_answer',
                             actor=self,
                             context_object=answer,
                             timestamp=timestamp)
    return revision

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
        comment = str(const.POST_STATUS['default_version'])
    )

    reason.details = details
    reason.save()
    return reason

@auto_now_timestamp
def user_edit_post_reject_reason(self, reason, title=None,
                                 details=None, timestamp=None):
    reason.title = title
    reason.save()
    return reason.details.apply_edit(edited_by=self,
                                     edited_at=timestamp,
                                     text=details)

@reject_forbidden_phrases
def user_post_answer(self,
                     question=None,
                     body_text=None,
                     follow=False,
                     wiki=False,
                     is_private=False,
                     timestamp=None,
                     by_email=False,
                     ip_addr=None):

    #todo: move this to assertion - user_assert_can_post_answer
    if self.pk == question.author_id and not self.is_administrator():

        # check date and rep required to post answer to own question

        delta = datetime.timedelta(askbot_settings.MIN_DAYS_TO_ANSWER_OWN_QUESTION)

        now = timezone.now()
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
                left = ngettext('in %(hr)d hour','in %(hr)d hours',hours) % {'hr':hours}
            else:
                left = ngettext('in %(min)d min','in %(min)d mins',minutes) % {'min':minutes}
            day = ngettext('%(days)d day','%(days)d days',askbot_settings.MIN_DAYS_TO_ANSWER_OWN_QUESTION) % {'days':askbot_settings.MIN_DAYS_TO_ANSWER_OWN_QUESTION}
            error_message = _(
                'New users must wait %(days)s to %(answer_own_questions)s. '
                ' You can post an answer %(left)s'
                ) % {
                    'days': day,
                    'left': left,
                    'answer_own_questions': askbot_settings.WORDS_ANSWER_OWN_QUESTIONS
                }
            assert(error_message is not None)
            raise django_exceptions.PermissionDenied(error_message)

    self.assert_can_post_answer(thread = question.thread)

    if getattr(question, 'post_type', '') != 'question':
        raise TypeError('question argument must be provided')
    if body_text is None:
        raise ValueError('Body text is required to post answer')

    if timestamp is None:
        timestamp = timezone.now()

    answer_post = Post.objects.create_new_answer(thread=question.thread,
                                                 author=self,
                                                 text=body_text,
                                                 added_at=timestamp,
                                                 email_notify=follow,
                                                 wiki=wiki,
                                                 is_private=is_private,
                                                 by_email=by_email,
                                                 ip_addr=ip_addr)
    #add to the answerer's group
    answer_post.add_to_groups([self.get_personal_group()])

    answer_post.thread.reset_cached_data()
    award_badges_signal.send(None,
                             event='post_answer',
                             actor=self,
                             context_object=answer_post,
                             timestamp=timestamp)
    return answer_post

def user_visit_question(self, question = None, timestamp = None):
    """create a QuestionView record
    on behalf of the user represented by the self object
    and mark it as taking place at timestamp time

    and remove pending on-screen notifications about anything in
    the post - question, answer or comments
    """
    if timestamp is None:
        timestamp = timezone.now()

    try:
        QuestionView.objects.filter(
            who=self,
            question=question
        ).update(
            when=timestamp
        )
    except QuestionView.DoesNotExist:
        QuestionView(who=self,
                     question=question,
                     when=timestamp).save()

    #filter memo objects on response activities directed to the qurrent user
    #that refer to the children of the currently
    #viewed question and clear them for the current user
    ACTIVITY_TYPES = const.RESPONSE_ACTIVITY_TYPES_FOR_DISPLAY
    ACTIVITY_TYPES += (const.TYPE_ACTIVITY_MENTION,)

    audit_records = ActivityAuditStatus.objects.filter(
                        user=self,
                        status=ActivityAuditStatus.STATUS_NEW,
                        activity__question=question
                    )

    cleared_record_count = audit_records.filter(
                                activity__activity_type__in=ACTIVITY_TYPES
                            ).update(
                                status=ActivityAuditStatus.STATUS_SEEN
                            )

    if cleared_record_count > 0:
        self.update_response_counts()

    #finally, mark admin memo objects if applicable
    #the admin response counts are not denormalized b/c they are easy to obtain
    if self.is_moderator() or self.is_administrator():
        audit_records.filter(
            activity__activity_type=const.TYPE_ACTIVITY_MARK_OFFENSIVE
        ).update(
            status=ActivityAuditStatus.STATUS_SEEN
        )


def user_is_administrator(self):
    """checks whether user in the forum site administrator
    the admin must be both superuser and staff member
    the latter is because staff membership is required
    to access the live settings"""
    return self.status == 'd'


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
    """True, if user and post have common private groups,
    the "everyone" group does not count"""
    if askbot_settings.GROUPS_ENABLED:
        group_ids = self.get_groups(private=True).values_list('id', flat=True)
        post_groups = PostToGroup.objects.filter(post=post, group__id__in=group_ids)
        return post_groups.count() > 0
    return False


def user_is_administrator_or_moderator(self):
    return self.is_administrator() or self.is_moderator()

def user_is_suspended(self):
    return (self.status == 's')

def user_is_blocked(self):
    return (self.status == 'b')

def user_is_watched(self):
    return (self.status == 'w')

def user_is_approved(self):
    return (self.status == 'a')

def user_is_terminated(self):
    return (self.status == 't')

def user_is_owner_of(self, obj):
    """True if user owns object
    False otherwise
    """
    if isinstance(obj, Post) and obj.post_type == 'question':
        return self.pk == obj.author_id
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


def user_get_anonymized_name(self):
    """Returns name that can be used for anonymized
    account"""
    anonymized_name = f'anonymous{self.pk}'
    attempt = 0

    if self.username == anonymized_name:
        return anonymized_name

    while User.objects.filter(username=anonymized_name).exists():
        seed_name = f'anonymous{self.pk}{attempt}'
        attempt += 1
    return anonymized_name


def user_assign_role_set(self, status):
    """Assigns roles specific to user `status`.
    Currently supported status values are: 'administrator' and 'moderator'.
    """
    current_roles = self.get_roles()
    desired_roles = get_role_set(status)
    for role in desired_roles - current_roles:
        try:
            Role.objects.create(user=self, role=role)
        except IntegrityError:
            # have an unlikely accident
            pass

def user_remove_role_set(self, status):
    """Symmetric method to `user_assign_role_set`"""
    role_names = get_role_set(status)
    roles = Role.objects.filter(user=self, role__in=role_names)
    roles.delete()

def user_set_status(self, new_status):
    """sets new status to user
    if new status is applied to user, then the record is
    committed to the database
    d - administrator (kept in sync with is_superuser)
    m - moderator
    s - suspended
    b - blocked
    w - watched
    a - approved (regular user)
    """
    assert(new_status in ('d', 'm', 's', 'b', 'w', 'a'))
    if new_status == self.status:
        return

    if new_status not in ('d', 'm'):
        self.remove_role_set('moderator')
        self.remove_role_set('administrator')
        self.is_superuser = False
        self.is_staff = False

    if new_status == 'm':
        self.remove_role_set('administrator')
        self.assign_role_set('moderator')
        self.is_superuser = False #cannot access /settings/
        self.is_staff = False #cannot access /admin/

    if new_status == 'd':
        self.assign_role_set('administrator')
        self.is_superuser = True
        #do not modify is_staff, staff is above admin
        #because staff has access to the /admin/ dashboard
        #you want to have tight control over access to the /admin/
        #therefore - assign this flag manually on per-user basis


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

    user.receive_reputation(reputation_change, get_language())
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
                user=user,
                comment=comment,
                #question = fake_question,
                reputed_at=timestamp,
                reputation_type=10, #todo: fix magic number
                reputation=user.reputation
            )
    if reputation_change < 0:
        repute.negative = -1 * reputation_change
    else:
        repute.positive = reputation_change
    repute.save()

def user_get_status_display(self):
    if self.is_approved():
        return _('Registered User')
    elif self.is_administrator():
        return _('Administrator')
    elif self.is_moderator():
        return _('Moderator')
    elif self.is_suspended():
        return  _('Suspended User')
    elif self.is_blocked():
        return _('Blocked User')
    elif self.is_watched():
        return _('Active User')
    elif self.is_terminated():
        return _('Account terminated')
    else:
        raise ValueError('Unknown user status %s' % self.status)


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

    language_code = get_language()

    if self.email_tag_filter_strategy == const.EXCLUDE_IGNORED:

        ignored_tags = Tag.objects.filter(
                                user_selections__reason = 'bad',
                                user_selections__user = self,
                                language_code=language_code
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
                                user_selections__user = self,
                                language_code=language_code
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


def user_set_languages(self, langs, primary=None):
    self.languages = ' '.join(langs)
    if primary:
        self.primary_language = primary

    profile_objects = LocalizedUserProfile.objects

    profiles = profile_objects.filter(auth_user=self)
    profile_langs = profiles.values_list('language_code', flat=True)

    profile_langs_set = set(profile_langs)
    langs_set = set(langs)

    if len(langs):
        profiles = profile_objects.filter(
                                    auth_user=self,
                                    language_code__in=langs,
                                )
        profiles.update(is_claimed=True)
        langs = set(profiles.values_list('language_code', flat=True))
        for lang in langs_set - profile_langs_set:
            profile_objects.create(
                            auth_user=self,
                            language_code=lang,
                            is_claimed=True
                        )

    #mark removed languages as not claimed
    removed_langs = profile_langs_set - langs_set
    if len(removed_langs):
        profiles = profile_objects.filter(
                                    auth_user=self,
                                    language_code__in=removed_langs
                                )
        profiles.update(is_claimed=False)

    profiles = profile_objects.filter(auth_user=self)
    for profile in profiles:
        profile.update_cache()


def user_get_languages(self):
    return self.languages.split()


def get_profile_link(self, text=None):
    profile_link = f'<a href="{self.get_profile_url()}">{escape(text or self.username)}</a>'

    return mark_safe(profile_link)

def user_get_groups(self, private=False):
    """returns a query set of groups to which user belongs"""
    #todo: maybe cache this query
    return Group.objects.get_for_user(self, private=private)

def user_join_default_groups(self):
    """adds user to "global" and "personal" groups"""
    #needs to be run when Askbot is added to pre-existing site
    #and Askbot groups are not populated
    #In Askbot user by default must by a member of "global" group
    #and of "personal" group - which is created for each user individually
    group = Group.objects.get_global_group()
    self.join_group(group, force=True)
    group_name = format_personal_group_name(self)
    group = Group.objects.get_or_create(name=group_name, user=self)
    self.join_group(group, force=True)

def user_get_personal_group(self):
    group_name = format_personal_group_name(self)
    try:
        #may be absent if askbot is added to pre-existing site
        return Group.objects.get(name=group_name)
    except Group.DoesNotExist:
        self.join_default_groups()
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
    if askbot_settings.GROUPS_ENABLED:
        groups = self.get_groups(private=True)
        for group in groups:
            if group.is_personal():
                continue
            return group
    return None


def user_can_post_question(self):
    """`True` if user can post questions"""
    try:
        self.assert_can_post_question()
    except django_exceptions.PermissionDenied:
        return False
    return True


def user_can_post_answer(self, thread=None):
    """`True` if user can post questions"""
    try:
        self.assert_can_post_answer(thread=thread)
    except django_exceptions.PermissionDenied:
        return False
    return True


def user_can_make_group_private_posts(self):
    """simplest implementation: user belongs to at least one group"""
    return (self.get_primary_group() != None)


def user_request_account_termination(self):
    """Notifies admins about user account termination"""
    msg_template = _('User %(username)s, id=%(id)s, %(email)s '
                  'asked to terminate the account.')
    admin_msg = msg_template % {'username': self.username,
                             'id': self.pk,
                             'email': self.email}
    email = AccountManagementRequest({'message': admin_msg,
                                      'username': self.username})
    mods = get_users_by_role('terminate_accounts')
    email.send(mods)


def user_get_data_export_dir(self):
    """Returns directory path where exported data is to be held"""
    return os.path.join(django_settings.ASKBOT_USER_DATA_EXPORT_DIR, str(self.pk))


def user_get_backup_file_names(self):
    """Returns list of user data backup file names"""
    backup_dir = self.get_data_export_dir()
    if os.path.exists(backup_dir):
        return os.listdir(backup_dir)
    return []


def user_get_todays_backup_file_name(self):
    """Returns todays backup file name or `None`"""
    backup_dir = self.get_data_export_dir()
    if not os.path.exists(backup_dir):
        return None

    today = datetime.date.today()
    for name in self.get_backup_file_names():
        if name.endswith('.zip'):
            path = os.path.join(backup_dir, name)
            file_mtime = os.path.getmtime(path)
            file_date = datetime.date.fromtimestamp(file_mtime)
            if file_date == today:
                return name
    return None


def user_delete_exported_data(self):
    """Deletes .zip files in the data export directory"""
    data_dir = os.path.join(self.get_data_export_dir())
    if not os.path.exists(data_dir):
        return

    for item in self.get_backup_file_names():
        if item.endswith('.zip'):
            os.remove(os.path.join(data_dir, item))


def user_suggest_backup_file_path(self):
    """Returns full path to the up-to date data export file"""
    date_token = datetime.date.today().strftime('%d-%m-%Y')
    file_slug = ascii_slugify(date_token + '-' +
                              self.username + '-' +
                              askbot_settings.APP_SHORT_NAME)
    file_name = file_slug + '.zip'
    return os.path.join(self.get_data_export_dir(), file_name)


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
        bit = ngettext(
                'one gold badge',
                '%(count)d gold badges',
                self.gold
            ) % {'count': self.gold}
        badge_bits.append(bit)
    if self.silver:
        bit = ngettext(
                'one silver badge',
                '%(count)d silver badges',
                self.silver
            ) % {'count': self.silver}
        badge_bits.append(bit)
    if self.bronze:
        bit = ngettext(
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
def user_toggle_favorite_question(
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
    self.assert_can_follow_question(question)

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
            timestamp = timezone.now()
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
                                 event='select_favorite_question',
                                 actor=self,
                                 context_object=question,
                                 timestamp=timestamp)
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

    post.thread.reset_cached_data()

    if post.post_type == 'question':
        #denormalize the question post score on the thread
        post.thread.points = post.points
        post.thread.save()

    if cancel:
        return None

    event = VOTES_TO_EVENTS.get((vote_type, post.post_type), None)
    if event:
        award_badges_signal.send(None,
                                 event=event,
                                 actor=user,
                                 context_object=post,
                                 timestamp=timestamp)
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
            message = ngettext(
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


def upvote(self, post, timestamp=None, cancel=False, force=False):
    #force parameter not used yet
    return _process_vote(
        self,
        post,
        timestamp=timestamp,
        cancel=cancel,
        vote_type=Vote.VOTE_UP
    )

def downvote(self, post, timestamp=None, cancel=False, force=False):
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

    post = post_revision.post

    #approval of unpublished revision
    if post_revision.revision > 0:
        post.parse_and_save(author=post_revision.author)
        post.thread.reset_cached_data()
        #todo: maybe add a notification here
    else:
        post_revision.revision = post.get_latest_revision_number() + 1

        post_revision.save()

        if post.approved == False:
            if post.is_comment():
                post.parent.recount_comments()
                post.parent.save()
            elif post.is_answer():
                post.thread.answer_count += 1
                post.thread.save()

        post.approved = True
        post.text = post_revision.text

        post_is_new = (post.revisions.count() == 1)
        parse_results = post.parse_and_save(author=post_revision.author)

        signals.post_updated.send(
            post=post,
            updated_by=post_revision.author,
            newly_mentioned_users=parse_results['newly_mentioned_users'],
            #suppress_email=suppress_email,
            timestamp=timestamp,
            created=post_is_new,
            diff=parse_results['diff'],
            sender=post.__class__
        )

        if post_revision.post.post_type == 'question':
            thread = post.thread
            thread.approved = True
            thread.save()

        post.thread.reset_cached_data()

        #send the signal of published revision
        signals.post_revision_published.send(
                                        None,
                                        revision=post_revision,
                                        was_approved=True
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

    elif cancel:
        if force == False:
            user.assert_can_remove_flag_offensive(post=post)
        auth.onUnFlaggedItem(post, user, timestamp=timestamp)

    else:
        if force == False:
            user.assert_can_flag_offensive(post=post)
        auth.onFlaggedItem(post, user, timestamp=timestamp)
        award_badges_signal.send(None,
                                 event='flag_post',
                                 actor=user,
                                 context_object=post,
                                 timestamp=timestamp)

def user_get_flags(self):
    """return flag Activity query set
    for all flags set by te user"""
    return Activity.objects.filter(
                        user=self,
                        activity_type=const.TYPE_ACTIVITY_MARK_OFFENSIVE
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

def user_create_email_key(self):
    email_key = generate_random_key()
    self.email_key = email_key #updates the profile object in the database
    return email_key

def user_get_or_create_email_key(self):
    if self.email_key:
        return self.email_key
    return self.create_email_key()

def user_update_response_counts(user):
    """Recount number of responses to the user.
    """
    ACTIVITY_TYPES = const.RESPONSE_ACTIVITY_TYPES_FOR_DISPLAY
    ACTIVITY_TYPES += (const.TYPE_ACTIVITY_MENTION,)

    user.new_response_count = ActivityAuditStatus.objects.filter(
                                    user=user,
                                    status=ActivityAuditStatus.STATUS_NEW,
                                    activity__activity_type__in=ACTIVITY_TYPES
                                ).count()
    user.seen_response_count = ActivityAuditStatus.objects.filter(
                                    user=user,
                                    status=ActivityAuditStatus.STATUS_SEEN,
                                    activity__activity_type__in=ACTIVITY_TYPES
                                ).count()
    user.save()


def user_receive_reputation(self, num_points, language_code=None):
    language_code = language_code or get_language()
    old_points = self.reputation
    new_points = old_points + num_points
    self.reputation = max(const.MIN_REPUTATION, new_points)

    #record localized user reputation - this starts with 0
    try:
        profile = LocalizedUserProfile.objects.get(
                                            auth_user=self,
                                            language_code=language_code
                                        )
    except LocalizedUserProfile.DoesNotExist:
        profile = LocalizedUserProfile(
                                    auth_user=self,
                                    language_code=language_code
                                )
    profile.reputation = max(0, profile.reputation + num_points)
    profile.save()

    signals.reputation_received.send(None, user=self, reputation_before=old_points)

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
                               action=None, force=False,
                               level=None
                            ):
    """allows one user to add another to a group
    or remove user from group.

    If when adding, the group does not exist, it will be created
    the delete function is not symmetric, the group will remain
    even if it becomes empty

    returns instance of GroupMembership (if action is "add") or None
    """
    if not force:
        self.assert_can_join_or_leave_group()

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
                level = level or GroupMembership.FULL
            elif openness == 'moderated':
                level = level or GroupMembership.PENDING
            elif openness == 'closed':
                raise django_exceptions.PermissionDenied()
        else:
            level = level or GroupMembership.FULL

        auth_group = group.group_ptr
        user.groups.add(auth_group)

        try:
            membership = GroupMembership.objects.get(user=user, group=group)
        except GroupMembership.DoesNotExist:
            membership = GroupMembership.objects.create(user=user, group=group, level=level)
        else:
            membership.level = level
            membership.save()

        return membership

    if action == 'remove':
        auth_group = group.group_ptr
        GroupMembership.objects.get(user=user, group=group).delete()
        user.groups.remove(auth_group)
        return None

    raise ValueError('invalid action')

def user_join_group(self, group, force=False, level=None):
    return self.edit_group_membership(group=group, user=self,
                                      action='add', force=force,
                                      level=level)

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
    'get_followed_question_alert_frequency',
    user_get_followed_question_alert_frequency
)
User.add_to_class(
    'get_top_answers_paginator',
    user_get_top_answers_paginator
)
User.add_to_class(
    'subscribe_for_followed_question_alerts',
    user_subscribe_for_followed_question_alerts
)
User.add_to_class('get_absolute_url', user_get_absolute_url)
User.add_to_class('get_avatar_type', user_get_avatar_type)
User.add_to_class('get_avatar_url', user_get_avatar_url)
User.add_to_class('can_terminate_account', user_can_terminate_account)
User.add_to_class('can_manage_account', user_can_manage_account)
User.add_to_class('can_upload_file', user_can_upload_file)
User.add_to_class('can_upload_attachment', user_can_upload_attachment)
User.add_to_class('can_upload_image', user_can_upload_image)
User.add_to_class('calculate_avatar_url', user_calculate_avatar_url)
User.add_to_class('clear_avatar_urls', user_clear_avatar_urls)
User.add_to_class('clear_cached_data', user_clear_cached_data)
User.add_to_class('init_avatar_urls', user_init_avatar_urls)
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
User.add_to_class('get_anonymized_name', user_get_anonymized_name)
User.add_to_class('get_social_sharing_mode', user_get_social_sharing_mode)
User.add_to_class('get_social_sharing_status', user_get_social_sharing_status)
User.add_to_class('get_localized_profile', user_get_localized_profile)
User.add_to_class('update_avatar_type', user_update_avatar_type)
User.add_to_class('update_localized_profile', user_update_localized_profile)
User.add_to_class('post_question', user_post_question)
User.add_to_class('edit_question', user_edit_question)
User.add_to_class('recount_badges', user_recount_badges)
User.add_to_class('retag_question', user_retag_question)
User.add_to_class('repost_comment_as_answer', user_repost_comment_as_answer)
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
User.add_to_class('get_unsubscribe_url', user_get_unsubscribe_url)
User.add_to_class('get_subscriptions_url', user_get_subscriptions_url)
User.add_to_class('get_or_create_email_key', user_get_or_create_email_key)
User.add_to_class('create_email_key', user_create_email_key)
User.add_to_class('get_profile_link', get_profile_link)
User.add_to_class('get_tag_filtered_questions', user_get_tag_filtered_questions)
User.add_to_class('get_messages', get_messages)
User.add_to_class('delete_messages', delete_messages)
User.add_to_class('toggle_favorite_question', user_toggle_favorite_question)
User.add_to_class('fix_html_links', user_fix_html_links)
User.add_to_class('follow_question', user_follow_question)
User.add_to_class('unfollow_question', user_unfollow_question)
User.add_to_class('is_following_question', user_is_following_question)
User.add_to_class('mark_tags', user_mark_tags)
User.add_to_class('merge_duplicate_questions', user_merge_duplicate_questions)
User.add_to_class('update_response_counts', user_update_response_counts)
User.add_to_class('can_anonymize_account', user_can_anonymize_account)
User.add_to_class('can_create_tags', user_can_create_tags)
User.add_to_class('can_have_strong_url', user_can_have_strong_url)
User.add_to_class('can_post_by_email', user_can_post_by_email)
User.add_to_class('can_post_answer', user_can_post_answer)
User.add_to_class('can_post_comment', user_can_post_comment)
User.add_to_class('can_post_question', user_can_post_question)
User.add_to_class('can_make_group_private_posts', user_can_make_group_private_posts)
User.add_to_class('is_administrator', user_is_administrator)
User.add_to_class('is_administrator_or_moderator', user_is_administrator_or_moderator)
User.add_to_class('is_admin_or_mod', user_is_administrator_or_moderator) #shorter version
User.add_to_class('edit_group_membership', user_edit_group_membership)
User.add_to_class('join_group', user_join_group)
User.add_to_class('join_default_groups', user_join_default_groups)
User.add_to_class('leave_group', user_leave_group)
User.add_to_class('is_group_member', user_is_group_member)
User.add_to_class('is_moderator', user_is_moderator)
User.add_to_class('is_post_moderator', user_is_post_moderator)
User.add_to_class('is_approved', user_is_approved)
User.add_to_class('is_watched', user_is_watched)
User.add_to_class('is_suspended', user_is_suspended)
User.add_to_class('is_blocked', user_is_blocked)
User.add_to_class('is_terminated', user_is_terminated)
User.add_to_class('is_owner_of', user_is_owner_of)
User.add_to_class('has_interesting_wildcard_tags', user_has_interesting_wildcard_tags)
User.add_to_class('has_ignored_wildcard_tags', user_has_ignored_wildcard_tags)
User.add_to_class('assign_role_set', user_assign_role_set)
User.add_to_class('remove_role_set', user_remove_role_set)
User.add_to_class('has_role', user_has_role)
User.add_to_class('get_roles', user_get_roles)
User.add_to_class('can_moderate_user', user_can_moderate_user)
User.add_to_class('can_see_karma', user_can_see_karma)
User.add_to_class('has_affinity_to_question', user_has_affinity_to_question)
User.add_to_class('has_badge', user_has_badge)
User.add_to_class('has_group_permission', user_has_group_permission)
User.add_to_class('moderate_user_reputation', user_moderate_user_reputation)
User.add_to_class('set_status', user_set_status)
User.add_to_class('get_badge_summary', user_get_badge_summary)
User.add_to_class('get_languages', user_get_languages)
User.add_to_class('set_languages', user_set_languages)
User.add_to_class('get_status_display', user_get_status_display)
User.add_to_class('get_old_vote_for_post', user_get_old_vote_for_post)
User.add_to_class('get_unused_votes_today', user_get_unused_votes_today)
User.add_to_class('delete_comment', user_delete_comment)
User.add_to_class('delete_question', user_delete_question)
User.add_to_class('delete_answer', user_delete_answer)
User.add_to_class(
    'delete_all_content_authored_by_user',
    user_delete_all_content_authored_by_user
)
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
User.add_to_class('anonymize', user_anonymize)
User.add_to_class('needs_moderation', user_needs_moderation)
User.add_to_class('notify_users', user_notify_users)
User.add_to_class('is_read_only', user_is_read_only)
User.add_to_class('get_data_export_dir', user_get_data_export_dir)
User.add_to_class('delete_exported_data', user_delete_exported_data)
User.add_to_class('suggest_backup_file_path', user_suggest_backup_file_path)
User.add_to_class('get_backup_file_names', user_get_backup_file_names)
User.add_to_class('get_todays_backup_file_name', user_get_todays_backup_file_name)
User.add_to_class('request_account_termination', user_request_account_termination)

#assertions
User.add_to_class('assert_can_vote_for_post', user_assert_can_vote_for_post)
User.add_to_class('assert_can_revoke_old_vote', user_assert_can_revoke_old_vote)
User.add_to_class('assert_can_upload_file', user_assert_can_upload_file)
User.add_to_class('assert_can_mark_tags', user_assert_can_mark_tags)
User.add_to_class('assert_can_merge_questions', user_assert_can_merge_questions)
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
User.add_to_class('assert_can_follow_question', user_assert_can_follow_question)
User.add_to_class('assert_can_remove_flag_offensive', user_assert_can_remove_flag_offensive)
User.add_to_class('assert_can_remove_all_flags_offensive', user_assert_can_remove_all_flags_offensive)
User.add_to_class('assert_can_retag_question', user_assert_can_retag_question)
#todo: do we need assert_can_delete_post
User.add_to_class('assert_can_delete_post', user_assert_can_delete_post)
User.add_to_class('assert_can_restore_post', user_assert_can_restore_post)
User.add_to_class('assert_can_delete_comment', user_assert_can_delete_comment)
User.add_to_class('assert_can_edit_comment', user_assert_can_edit_comment)
User.add_to_class('assert_can_convert_post', user_assert_can_convert_post)

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


def reset_cached_post_data(sender, instance, **kwargs):
    instance.reset_cached_data()


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


def notify_author_of_published_revision(revision=None, was_approved=False, **kwargs):
    """notifies author about approved post revision,
    assumes that we have the very first revision
    """
    #only email about first revision
    if revision.should_notify_author_about_publishing(was_approved):
        from askbot.tasks import notify_author_of_published_revision_celery_task
        defer_celery_task(
            notify_author_of_published_revision_celery_task,
            args=(revision.pk,)
        )


#todo: move to utils
def calculate_gravatar_hash(instance, **kwargs):
    """Calculates a User's gravatar hash from their email address."""
    user = instance
    if kwargs.get('raw', False):
        return
    clean_email = user.email.strip().lower().encode('utf-8')
    user.gravatar = hashlib.md5(clean_email).hexdigest()


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
    assert(timestamp != None)
    assert(updated_by != None)
    if newly_mentioned_users is None:
        newly_mentioned_users = list()

    from askbot import tasks

    mentioned_ids = [u.id for u in newly_mentioned_users]

    from askbot.models.recent_contributors import AvatarsBlockData
    AvatarsBlockData.push_user(updated_by)

    defer_celery_task(
        tasks.record_post_update_celery_task,
        kwargs = {
            'post_id': post.id,
            'newly_mentioned_user_id_list': mentioned_ids,
            'updated_by_id': updated_by.id,
            'suppress_email': suppress_email,
            'timestamp': timestamp,
            'created': created,
            'diff': diff,
        }
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

        with override(user.primary_language):
            badge = get_badge(instance.badge.slug)

            msg = _("Congratulations, you have received a badge '%(badge_name)s'. "
                    "Check out <a href=\"%(user_profile)s\">your profile</a>.") \
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

    if not created and instance.endorsed:
        activity = Activity(
                        #pretty bad: user must be actor
                        user=question.author,
                        active_at=timezone.now(),
                        #content object must be answer!
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
    prev_last_seen = user.last_seen or timezone.now()
    user.last_seen = timestamp
    consecutive_days = user.consecutive_days_visit_count
    if (user.last_seen.date() - prev_last_seen.date()).days == 1:
        user.consecutive_days_visit_count += 1
        consecutive_days = user.consecutive_days_visit_count
        award_badges_signal.send(None,
                                 event='site_visit',
                                 actor=user,
                                 context_object=user,
                                 timestamp=timestamp)
    #somehow it saves on the query as compared to user.save()
    update_data = {
        'last_seen': timestamp,
        'consecutive_days_visit_count': consecutive_days
    }
    UserProfile.objects.filter(pk=user.pk).update(**update_data)
    profile = UserProfile.objects.get(pk=user.pk)
    profile.update_cache()


def record_question_visit(request, question, **kwargs):
    if functions.not_a_robot_request(request):
        #todo: split this out into a subroutine
        #todo: merge view counts per user and per session
        #1) view count per session
        if 'question_view_times' not in request.session:
            request.session['question_view_times'] = {}

        last_seen = request.session['question_view_times'].get(question.id, None)

        if last_seen and timezone.is_naive(last_seen) \
            and getattr(django_settings, 'USE_TZ', False):
            last_seen = timezone.make_aware(last_seen, datetime.timezone.utc)

        update_view_count = False
        if question.thread.last_activity_by_id != request.user.id:
            if last_seen:
                if last_seen < question.thread.last_activity_at:
                    update_view_count = True
            else:
                update_view_count = True

        request.session['question_view_times'][question.id] = timezone.now()
        #2) run the slower jobs in a celery task
        from askbot import tasks
        defer_celery_task(
            tasks.record_question_visit,
            kwargs={
                'question_post_id': question.id,
                'user_id': request.user.id,
                'update_view_count': update_view_count,
                'language_code': get_language()
            }
        )

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
                    active_at=timezone.now(),
                    content_object=instance,
                    activity_type=const.TYPE_ACTIVITY_CANCEL_VOTE
                )
    #todo: same problem - cannot access receiving user here
    activity.save()


def delete_post_activities(instance, **kwargs):
    """Deletes items connected to instance via generic relations
    upon removal of objects from the database"""
    from askbot import tasks
    ctype = ContentType.objects.get_for_model(instance)
    aa = Activity.objects.filter(object_id=instance.pk, content_type=ctype)
    aa.delete()
    instance.delete_update_notifications(False) #don't keep activities


#todo: weird that there is no record delete answer or comment
#is this even necessary to keep track of?
def record_delete_post(instance, deleted_by, **kwargs):
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
                    user=deleted_by,
                    active_at=timezone.now(),
                    content_object=instance,
                    activity_type=activity_type,
                    question = instance.get_origin_post()
                )
    activity.save()

    #keep activity records, but delete notifications
    instance.delete_update_notifications(True)

def record_flag_offensive(instance, mark_by, **kwargs):
    """places flagged post on the moderation queue"""
    activity = Activity(
                    user=mark_by,
                    active_at=timezone.now(),
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

def record_update_tags(thread, tags, user, timestamp, **kwargs):
    """
    This function sends award badges signal on each updated tag
    the badges that respond to the 'ta
    """
    for tag in tags:
        award_badges_signal.send(None,
                                 event='update_tag',
                                 actor=user,
                                 context_object=tag,
                                 timestamp=timestamp)

    question = thread._question_post()

    activity = Activity(
                    user=user,
                    active_at=timezone.now(),
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
                        active_at=timezone.now(),
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
                    active_at=timezone.now(),
                    content_object=instance,
                    activity_type=const.TYPE_ACTIVITY_USER_FULL_UPDATED
                )
    activity.save()


def add_user_to_default_groups(sender, instance, created, **kwargs):
    """auto-joins user to his/her personal group
    ``instance`` is an instance of ``User`` class
    """
    if created:
        instance.join_default_groups()


def greet_new_user(user, **kwargs):
    """sends welcome email to the newly created user

    todo: second branch should send email with a simple
    clickable link.
    """
    if askbot_settings.NEW_USER_GREETING.strip():
        user.message_set.create(message=askbot_settings.NEW_USER_GREETING)

    import sys
    if 'test' in sys.argv:
        return

    if askbot_settings.REPLY_BY_EMAIL:#with this on we also collect signature
        reply_address = ReplyAddress.objects.create_new(
                                        user=user,
                                        reply_action='validate_email'
                                    )
        email = WelcomeEmailRespondable({
            'recipient_user': user,
            'email_code': reply_address.address,
            'reply_to_address': reply_address.as_email_address(prefix='welcome-')
        })
    else:
        email = WelcomeEmail({'user': user})

    email.send([user.email,])



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

def set_administrator_flag(sender, instance, *args, **kwargs):
    user = instance
    if user.is_superuser:
        if instance.status != 'd':
            instance.status = 'd'
            instance.assign_role_set('administrator')
    elif instance.status == 'd': # demoting the admin by setting is_superuser to false
        instance.status = 'a'
        instance.remove_role_set('administrator')
        instance.remove_role_set('moderator')


def init_avatar_type(sender, instance, *args, **kwargs):
    user = instance
    #if user is new, set avatar type
    if not user.pk:
        user.avatar_type = askbot_settings.AVATAR_TYPE_FOR_NEW_USERS


def init_avatar_urls(sender, instance, *args, **kwargs):
    instance.init_avatar_urls()

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
            for subscription in BulkTagSubscription.objects.filter(groups__in=user_groups):
                tag_list = subscription.tag_list()
                instance.mark_tags(tagnames = tag_list,
                                reason='subscribed', action='add')

def notify_punished_users(user, **kwargs):
    try:
        _assert_user_can(
                    user=user,
                    blocked_user_cannot=True,
                    suspended_user_cannot=True
                )
    except django_exceptions.PermissionDenied as e:
        user.message_set.create(message = str(e))

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
    if user.is_blocked() or user.is_suspended():
        pass
    else:
        user.post_anonymous_askbot_content(session_key)

def make_admin_if_first_user(user, **kwargs):
    """first user automatically becomes an administrator
    the function is run only once in the interpreter session

    function is run when user registers
    """
    user_count = User.objects.all().count()
    if user_count == 1:
        user.set_status('d')


def init_language_settings(user, **kwargs):
    lang = get_language()
    user.set_languages([lang,], primary=lang)
    user.askbot_profile.save()


def make_invited_moderator(user, **kwargs):
    """If user's email matches one of the values in "INVITED_MODERATORS"
    setting, change status of this user to "moderator"
    """
    from askbot.models.user import (get_invited_moderators,
                                    remove_email_from_invited_moderators)

    mods = get_invited_moderators(include_registered=True)
    invited_emails = [m.email for m in mods]
    if user.email in invited_emails:
        remove_email_from_invited_moderators(user.email)
        user.set_status('m')


def moderate_group_joining(sender, instance=None, created=False, **kwargs):
    if instance.level != GroupMembership.PENDING:
        return

    user = instance.user
    group = instance.group
    user.notify_users(
            notification_type=const.TYPE_ACTIVITY_ASK_TO_JOIN_GROUP,
            recipients=group.group.get_moderators(),
            content_object=group
        )

#this variable and the signal handler below is
#needed to work around the issue in the django admin
#where auth_user table editing affects group memberships
GROUP_MEMBERSHIP_LEVELS = dict()
def group_membership_changed(**kwargs):
    sender = kwargs['sender']
    user = kwargs['instance']
    action = kwargs['action']
    reverse = kwargs['reverse']
    model = kwargs['model']
    pk_set = kwargs['pk_set']

    if reverse:
        raise NotImplementedError()

    #store group memberships info
    #and then delete group memberships
    if action == 'pre_clear':
        #get membership info, if exists, save
        memberships = GroupMembership.objects.filter(user=user)
        for gm in memberships:
            GROUP_MEMBERSHIP_LEVELS[(user.id, gm.group.id)] = gm.level
        memberships.delete()
    elif action == 'post_add':
        group_ids = pk_set
        for group_id in group_ids:
            gm_key = (user.id, group_id)
            #mend group membership if it does not exist
            if not GroupMembership.objects.filter(user=user, group__id=group_id).exists():
                try:
                    group = Group.objects.get(id=group_id)
                except Group.DoesNotExist:
                    #this is not an Askbot group, no group profile
                    #so we don't add anything here
                    pass
                else:
                    # Restore group membership.
                    # Default level is FULL - to handle the case
                    # when group is added via admin interface.
                    level = GROUP_MEMBERSHIP_LEVELS.get(gm_key,
                                                        GroupMembership.FULL)
                    GroupMembership.objects.create(user=user,
                                                   group=group,
                                                   level=level)

            GROUP_MEMBERSHIP_LEVELS.pop(gm_key, None)


def tweet_new_post(sender, user=None, question=None, answer=None, **kwargs):
    """seends out tweets about the new post"""
    from askbot.tasks import tweet_new_post_task
    post = question or answer
    defer_celery_task(tweet_new_post_task, args=(post.id,))

def autoapprove_reputable_user(*args, user=None, reputation_before=None, **kwargs):
    """if user is 'watched' we change status to 'approved'
    if user's rep crossed the auto-approval margin"""
    margin = askbot_settings.MIN_REP_TO_AUTOAPPROVE_USER
    if user.is_watched() and reputation_before < margin <= user.reputation:
        user.set_status('a')

def record_spam_rejection(sender, spam=None, text=None, user=None, ip_addr='unknown', **kwargs): #pylint: disable=unused-argument
    """Record spam autorejection activity
    Only one record per user kept

    todo: this might be factored out into the moderation app
    and data might be tracked in some other record
    """
    now = timezone.now()
    summary = f'Found spam text: {spam}, posted from ip={ip_addr} in\n{text}'
    spam_type = const.TYPE_ACTIVITY_FORBIDDEN_PHRASE_FOUND
    act_list = Activity.objects.filter(user=user, activity_type=spam_type)
    if len(act_list) == 0:
        activity = Activity(
                        activity_type=spam_type,
                        user=user,
                        active_at=now,
                        content_object=user,
                        summary=summary
                    )
        activity.save()
    else:
        activity = act_list[0]
        activity.active_at = now
        activity.summary = summary
        activity.save()


def update_last_seen(sender, user=None, **kwargs):
    """Updates the user.askbot_profile.last_seen field
    to the current time."""
    user.askbot_profile.last_seen = timezone.now()
    user.askbot_profile.save() # this also updates cache (see UserProfile.save)


# signals for User model save changes
user_signals = [
    signals.GenericSignal(
        django_signals.post_save,
        callback=calculate_gravatar_hash,
        dispatch_uid='calculate_gravatar_hash_on_user_save',
    ),
    signals.GenericSignal(
        django_signals.post_save,
        callback=set_administrator_flag,
        dispatch_uid='set_administrator_flag_on_user_save',
    ),
    signals.GenericSignal(
        django_signals.post_save,
        callback=init_avatar_type,
        dispatch_uid='init_avatar_type_on_user_create'
    ),
    signals.GenericSignal(
        django_signals.post_save,
        callback=init_avatar_urls,
        dispatch_uid='init_avatar_urls_on_user_save',
    ),
    signals.GenericSignal(
        django_signals.post_save,
        callback=add_missing_subscriptions,
        dispatch_uid='add_missing_subscriptions_on_user_save',
    ),
    signals.GenericSignal(
        django_signals.post_save,
        callback=add_user_to_default_groups,
        dispatch_uid='add_user_to_default_groups_on_user_save',
    ),
    signals.GenericSignal(
        django_signals.post_save,
        callback=add_missing_tag_subscriptions,
        dispatch_uid='add_missing_tag_subscriptions_on_user_save',
    ),
    signals.GenericSignal(
        signals.user_updated,
        callback=record_user_full_updated,
        dispatch_uid='record_full_profile_upon_user_update',
    ),
]


for signal in user_signals:
    register_user_signal(signal)


django_signals.post_save.connect(
    record_award_event,
    sender=Award,
    dispatch_uid='record_award_event_on_user_save'
)
django_signals.post_save.connect(
    notify_award_message,
    sender=Award,
    dispatch_uid='notify_user_on_award_save'
)
django_signals.post_save.connect(
    record_answer_accepted,
    sender=Post,
    dispatch_uid='record_answer_accepted_on_answer_save'
)
django_signals.post_save.connect(
    record_vote,
    sender=Vote,
    dispatch_uid='record_vote_activity_on_vote_save'
)
django_signals.post_save.connect(
    record_favorite_question,
    sender=FavoriteQuestion,
    dispatch_uid='record_favorite_question_on_fave_save'
)
django_signals.post_save.connect(
    moderate_group_joining,
    sender=GroupMembership,
    dispatch_uid='moderate_group_joining_on_gm_save'
)
django_signals.m2m_changed.connect(
    group_membership_changed,
    sender=User.groups.through, #pylint: disable=no-member
    dispatch_uid='record_group_membership_change_on_group_change'
)

django_signals.post_delete.connect(
    record_cancel_vote,
    sender=Vote,
    dispatch_uid='record_cancel_vote_on_vote_delete'
)

django_signals.pre_delete.connect(
    delete_post_activities,
    sender=Post,
    dispatch_uid='delete_post_activities_on_post_pre_delete'
)

#change this to real m2m_changed with Django1.2
signals.after_post_removed.connect(
    record_delete_post,
    sender=Post,
    dispatch_uid='record_delete_question_on_delete_post'
)
signals.flag_offensive.connect(
    record_flag_offensive,
    sender=Post,
    dispatch_uid='record_flag_offensive_on_post_flag'
)
signals.tags_updated.connect(
    record_update_tags,
    dispatch_uid='record_tag_update'
)
signals.user_registered.connect(
    greet_new_user,
    dispatch_uid='greet_user_upon_registration'
)
signals.user_registered.connect(
    make_admin_if_first_user,
    dispatch_uid='make_amin_first_registrant'
)
signals.user_registered.connect(
    init_language_settings,
    dispatch_uid='update_language_settings_upon_registration'
)
signals.user_registered.connect(
        make_invited_moderator,
        dispatch_uid='make_invited_moderator'
)
signals.user_registered.connect(
        update_last_seen,
        dispatch_uid='update_last_seen_on_register'
)

signals.user_logged_in.connect(
        update_last_seen,
        dispatch_uid='update_last_seen_on_login'
)
signals.user_logged_in.connect(
    complete_pending_tag_subscriptions,
    dispatch_uid='complete_pending_tag_subs_on_user_login'
)#todo: add this to fake onlogin middleware
signals.user_logged_in.connect(
    notify_punished_users,
    dispatch_uid='notify_punished_users_on_login'
)
signals.user_logged_in.connect(
    post_anonymous_askbot_content,
    dispatch_uid='post_anon_content_on_login'
)
#signals.post_save.connect(
#    reset_cached_post_data,
#    sender=Thread,
#    dispatch_uid='reset_cached_post_data',
#)
signals.post_updated.connect(
    record_post_update_activity,
    dispatch_uid='record_post_update_activity'
)
signals.new_answer_posted.connect(
    tweet_new_post,
    dispatch_uid='tweet_on_new_answer'
)
signals.new_question_posted.connect(
    tweet_new_post,
    dispatch_uid='tweet_on_new_question'
)
signals.reputation_received.connect(
    autoapprove_reputable_user,
    dispatch_uid='autoapprove_reputable_user'
)
signals.spam_rejected.connect(
    record_spam_rejection,
    dispatch_uid='record_spam_rejection'
)

#probably we cannot use post-save here the point of this is
#to tell when the revision becomes publicly visible, not when it is saved
signals.post_revision_published.connect(
    notify_author_of_published_revision,
    dispatch_uid='notify_authon_of_published_revision'
)
signals.site_visited.connect(
    record_user_visit,
    dispatch_uid='record_user_visit'
)
signals.question_visited.connect(
    record_question_visit,
    dispatch_uid='record_question_visit'
)

def handle_posts_marked_as_spam(sender, post_ids, **kwargs):
    """Launches a task to submit spam posts to Akismet"""
    if not askbot_settings.SPAM_FILTER_ENABLED:
        return

    akismet_func_path = 'askbot.spam_checker.akismet_spam_checker.is_spam'
    if django_settings.ASKBOT_SPAM_CHECKER_FUNCTION != akismet_func_path:
        return

    if not askbot_settings.AKISMET_API_KEY:
        return

    from askbot.tasks import submit_spam_posts_to_akismet
    defer_celery_task(submit_spam_posts_to_akismet, kwargs={'post_ids': post_ids})

signals.posts_marked_as_spam.connect(
    handle_posts_marked_as_spam,
    dispatch_uid='handle_posts_marked_as_spam'
)

#set up a possibility for the users to follow others
#try:
#    import followit
#    followit.register(User)
#except ImportError:
#    pass


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
        'UserProfile',

        'ReplyAddress',

        'ImportRun',
        'ImportedObjectInfo',

        'get_model',
]
