from askbot import startup_procedures
startup_procedures.run()

import logging
import hashlib
import datetime
import urllib
from django.core.urlresolvers import reverse, NoReverseMatch
from django.db.models import signals as django_signals
from django.template import Context
from django.utils.translation import ugettext as _
from django.utils.translation import ungettext
from django.contrib.auth.models import User
from django.utils.safestring import mark_safe
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
from askbot.models.question import QuestionView, AnonymousQuestion
from askbot.models.question import FavoriteQuestion
from askbot.models.answer import AnonymousAnswer
from askbot.models.tag import Tag, MarkedTag
from askbot.models.meta import Vote
from askbot.models.user import EmailFeedSetting, ActivityAuditStatus, Activity
from askbot.models.post import Post, PostRevision
from askbot.models.reply_by_email import ReplyAddress
from askbot.models import signals
from askbot.models.badges import award_badges_signal, get_badge, BadgeData
from askbot.models.repute import Award, Repute
from askbot import auth
from askbot.utils.decorators import auto_now_timestamp
from askbot.utils.slug import slugify
from askbot.utils.diff import textDiff as htmldiff
from askbot.utils.url_utils import strip_path
from askbot.utils import mail

def get_model(model_name):
    return models.get_model('askbot', model_name)

User.add_to_class(
            'status',
            models.CharField(
                        max_length = 2,
                        default = const.DEFAULT_USER_STATUS,
                        choices = const.USER_STATUS_CHOICES
                    )
        )

User.add_to_class('email_isvalid', models.BooleanField(default=False))
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
User.add_to_class(
    'email_tag_filter_strategy',
    models.SmallIntegerField(
        choices=const.TAG_FILTER_STRATEGY_CHOICES,
        default=const.EXCLUDE_IGNORED
    )
)
User.add_to_class(
    'display_tag_filter_strategy',
    models.SmallIntegerField(
        choices=const.TAG_FILTER_STRATEGY_CHOICES,
        default=const.INCLUDE_ALL
    )
)

User.add_to_class('new_response_count', models.IntegerField(default=0))
User.add_to_class('seen_response_count', models.IntegerField(default=0))
User.add_to_class('consecutive_days_visit_count', models.IntegerField(default = 0))

GRAVATAR_TEMPLATE = "http://www.gravatar.com/avatar/%(gravatar)s?" + \
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

def user_get_avatar_url(self, size):
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

def user_has_affinity_to_question(self, question = None, affinity_type = None):
    """returns True if number of tag overlap of the user tag
    selection with the question is 0 and False otherwise
    affinity_type can be either "like" or "dislike"
    """
    if affinity_type == 'like':
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


def user_can_have_strong_url(self):
    """True if user's homepage url can be
    followed by the search engine crawlers"""
    return (self.reputation >= askbot_settings.MIN_REP_TO_HAVE_STRONG_URL)

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
                        general_error_message = None
                    ):
    """generic helper assert for use in several
    User.assert_can_XYZ() calls regarding changing content

    user is required and at least one error message

    if assertion fails, method raises exception.PermissionDenied
    with appropriate text as a payload
    """
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

    elif self.is_administrator() or self.is_moderator():
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
        error_message = _(
            'Sorry, only moderators or original author of the question '
            ' - %(username)s - can accept or unaccept the best answer'
            ) % {'username': answer.get_owner().username}

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


def user_assert_can_post_answer(self):
    """same as user_can_post_question
    """
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
    if self.reputation >= askbot_settings.MIN_REP_TO_LEAVE_COMMENTS:
        return True
    if parent_post and self == parent_post.author:
        return True
    if self.is_administrator_or_moderator():
        return True
    return False


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
            ) % {'min_rep': askbot_settings.MIN_REP_TO_LEAVE_COMMENTS}

    blocked_message = get_i18n_message('BLOCKED_USERS_CANNOT_POST')

    try:
        _assert_user_can(
            user = self,
            post = parent_post,
            owner_can = True,
            blocked_error_message = blocked_message,
            suspended_error_message = suspended_error_message,
            min_rep_setting = askbot_settings.MIN_REP_TO_LEAVE_COMMENTS,
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
        min_rep_setting = min_rep_setting
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
                        .exclude(author=self).exclude(score__lte=0).count()

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
                'Sorry, to deleted other people\' posts, a minimum '
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
        min_rep_setting = min_rep_setting
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
        min_rep_setting = min_rep_setting
    )


def user_assert_can_reopen_question(self, question = None):
    assert(question.post_type == 'question')

    owner_min_rep_setting =  askbot_settings.MIN_REP_TO_REOPEN_OWN_QUESTIONS

    general_error_message = _(
                        'Sorry, only administrators, moderators '
                        'or post owners with reputation > %(min_rep)s '
                        'can reopen questions.'
                    ) % {'min_rep': owner_min_rep_setting }

    owner_low_rep_error_message = _(
                        'Sorry, to reopen own question '
                        'a minimum reputation of %(min_rep)s is required'
                    ) % {'min_rep': owner_min_rep_setting}

    _assert_user_can(
        user = self,
        post = question,
        admin_or_moderator_required = True,
        owner_can = True,
        suspended_owner_cannot = True,
        owner_min_rep_setting = owner_min_rep_setting,
        owner_low_rep_error_message = owner_low_rep_error_message,
        general_error_message = general_error_message
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
        min_rep_setting = min_rep_setting
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
        min_rep_setting = min_rep_setting
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
                )
    parent_post.thread.invalidate_cached_data()
    award_badges_signal.send(None,
        event = 'post_comment',
        actor = self,
        context_object = comment,
        timestamp = timestamp
    )
    return comment

def user_post_anonymous_askbot_content(user, session_key):
    """posts any posts added just before logging in
    the posts are identified by the session key, thus the second argument

    this function is used by the signal handler with a similar name
    """
    aq_list = AnonymousQuestion.objects.filter(session_key = session_key)
    aa_list = AnonymousAnswer.objects.filter(session_key = session_key)
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
        assert(reason in ('good', 'bad'))
    if wildcards:
        cleaned_wildcards = self.update_wildcard_tag_selections(
            action = action,
            reason = reason,
            wildcards = wildcards
        )
    if tagnames is None:
        tagnames = list()

    #below we update normal tag selections
    marked_ts = MarkedTag.objects.filter(
                                    user = self,
                                    tag__name__in = tagnames
                                )
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
                    timestamp = None
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

    thread = Thread.objects.create_new(
                                    author = self,
                                    title = title,
                                    text = body_text,
                                    tagnames = tags,
                                    added_at = timestamp,
                                    wiki = wiki,
                                    is_anonymous = is_anonymous,
                                )
    question = thread._question_post()
    if question.author != self:
        raise ValueError('question.author != self')
    question.author = self # HACK: Some tests require that question.author IS exactly the same object as self-user (kind of identity map which Django doesn't provide),
                           #       because they set some attributes for that instance and expect them to be changed also for question.author
    return question

def user_edit_comment(self, comment_post=None, body_text = None):
    """apply edit to a comment, the method does not
    change the comments timestamp and no signals are sent
    todo: see how this can be merged with edit_post
    todo: add timestamp
    """
    self.assert_can_edit_comment(comment_post)
    comment_post.text = body_text
    comment_post.parse_and_save(author = self)
    comment_post.thread.invalidate_cached_data()

def user_edit_post(self,
                post = None,
                body_text = None,
                revision_comment = None,
                timestamp = None):
    """a simple method that edits post body
    todo: unify it in the style of just a generic post
    this requires refactoring of underlying functions
    because we cannot bypass the permissions checks set within
    """
    if post.post_type == 'comment':
        self.edit_comment(comment_post = post, body_text = body_text)
    elif post.post_type == 'answer':
        self.edit_answer(
            answer = post,
            body_text = body_text,
            timestamp = timestamp,
            revision_comment = revision_comment
        )
    elif post.post_type == 'question':
        self.edit_question(
            question = post,
            body_text = body_text,
            timestamp = timestamp,
            revision_comment = revision_comment
        )
    else:
        raise NotImplementedError()

@auto_now_timestamp
def user_edit_question(
                    self,
                    question = None,
                    title = None,
                    body_text = None,
                    revision_comment = None,
                    tags = None,
                    wiki = False,
                    edit_anonymously = False,
                    timestamp = None,
                    force = False,#if True - bypass the assert
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
                    answer = None,
                    body_text = None,
                    revision_comment = None,
                    wiki = False,
                    timestamp = None,
                    force = False#if True - bypass the assert
                ):
    if force == False:
        self.assert_can_edit_answer(answer)
    answer.apply_edit(
        edited_at = timestamp,
        edited_by = self,
        text = body_text,
        comment = revision_comment,
        wiki = wiki,
    )
    answer.thread.invalidate_cached_data()
    award_badges_signal.send(None,
        event = 'edit_answer',
        actor = self,
        context_object = answer,
        timestamp = timestamp
    )

def user_post_answer(
                    self,
                    question = None,
                    body_text = None,
                    follow = False,
                    wiki = False,
                    timestamp = None
                ):

    #todo: move this to assertion - user_assert_can_post_answer
    if self == question.author and not self.is_administrator():

        # check date and rep required to post answer to own question

        delta = datetime.timedelta(askbot_settings.MIN_DAYS_TO_ANSWER_OWN_QUESTION)

        now = datetime.datetime.now()
        asked = question.added_at
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

    self.assert_can_post_answer()

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
        wiki = wiki
    )
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
                    )
    elif self.email_tag_filter_strategy == const.INCLUDE_INTERESTING:
        selected_tags = Tag.objects.filter(
                                user_selections__reason = 'good',
                                user_selections__user = self
                            )

        wk = self.interesting_tags.strip().split()
        selected_by_wildcards = Tag.objects.get_by_wildcards(wk)

        tag_filter = models.Q(thread__tags__in = list(selected_tags)) \
                    | models.Q(thread__tags__in = list(selected_by_wildcards))

        return questions.filter( tag_filter )
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
def get_profile_url(self):
    """Returns the URL for this User's profile."""
    return reverse(
                'user_profile',
                kwargs={'id':self.id, 'slug':slugify(self.username)}
            )

def user_get_absolute_url(self):
    return self.get_profile_url()

def get_profile_link(self):
    profile_link = u'<a href="%s">%s</a>' \
        % (self.get_profile_url(),self.username)

    return mark_safe(profile_link)

def user_get_karma_summary(self):
    """returns human readable sentence about
    status of user's karma"""
    return _("%(username)s karma is %(reputation)s") % \
            {'username': self.username, 'reputation': self.reputation}

def user_get_badge_summary(self):
    """returns human readable sentence about
    number of badges of different levels earned
    by the user. It is assumed that user has some badges"""
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
                self.gold
            ) % {'count': self.silver}
        badge_bits.append(bit)
    if self.silver:
        bit = ungettext(
                'one bronze badge',
                '%(count)d bronze badges',
                self.gold
            ) % {'count': self.bronze}
        badge_bits.append(bit)

    if len(badge_bits) == 1:
        badge_str = badge_bits[0]
    elif len(badge_bits) > 1:
        last_bit = badge_bits.pop()
        badge_str = ', '.join(badge_bits)
        badge_str = _('%(item1)s and %(item2)s') % \
                    {'item1': badge_str, 'item2': last_bit}
    else:
        raise ValueError('user must have badges to call this function')
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
    """
    try:
        fave = FavoriteQuestion.objects.get(thread=question.thread, user=self)
        fave.delete()
        result = False
        question.thread.update_favorite_count()
    except FavoriteQuestion.DoesNotExist:
        if timestamp is None:
            timestamp = datetime.datetime.now()
        fave = FavoriteQuestion(
            thread = question.thread,
            user = self,
            added_at = timestamp,
        )
        fave.save()
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
        post.thread.score = post.score
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
def flag_post(user, post, timestamp=None, cancel=False, cancel_all = False, force = False):
    if cancel_all:
        # remove all flags
        if force == False:
            user.assert_can_remove_all_flags_offensive(post = post)
        post_content_type = ContentType.objects.get_for_model(post)
        all_flags = Activity.objects.filter(
                        activity_type = const.TYPE_ACTIVITY_MARK_OFFENSIVE,
                        content_type = post_content_type, object_id=post.id
                    )
        for flag in all_flags:
            auth.onUnFlaggedItem(post, flag.user, timestamp=timestamp)            

    elif cancel:#todo: can't unflag?
        if force == False:
            user.assert_can_remove_flag_offensive(post = post)
        auth.onUnFlaggedItem(post, user, timestamp=timestamp)        

    else:
        if force == False:
            user.assert_can_flag_offensive(post = post)
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
    new_tags = set(wildcards)
    interesting = set(self.interesting_tags.split())
    ignored = set(self.ignored_tags.split())

    target_set = interesting
    other_set = ignored
    if reason == 'good':
        pass
    elif reason == 'bad':
        target_set = ignored
        other_set = interesting
    else:
        assert(action == 'remove')

    if action == 'add':
        target_set.update(new_tags)
        other_set.difference_update(new_tags)
    else:
        target_set.difference_update(new_tags)
        other_set.difference_update(new_tags)

    self.interesting_tags = ' '.join(interesting)
    self.ignored_tags = ' '.join(ignored)
    self.save()
    return new_tags


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
User.add_to_class('get_anonymous_name', user_get_anonymous_name)
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
User.add_to_class('delete_post', user_delete_post)
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
User.add_to_class('get_profile_url', get_profile_url)
User.add_to_class('get_profile_link', get_profile_link)
User.add_to_class('get_tag_filtered_questions', user_get_tag_filtered_questions)
User.add_to_class('get_messages', get_messages)
User.add_to_class('delete_messages', delete_messages)
User.add_to_class('toggle_favorite_question', toggle_favorite_question)
User.add_to_class('follow_question', user_follow_question)
User.add_to_class('unfollow_question', user_unfollow_question)
User.add_to_class('is_following_question', user_is_following_question)
User.add_to_class('mark_tags', user_mark_tags)
User.add_to_class('update_response_counts', user_update_response_counts)
User.add_to_class('can_have_strong_url', user_can_have_strong_url)
User.add_to_class('can_post_comment', user_can_post_comment)
User.add_to_class('is_administrator', user_is_administrator)
User.add_to_class('is_administrator_or_moderator', user_is_administrator_or_moderator)
User.add_to_class('set_admin_status', user_set_admin_status)
User.add_to_class('remove_admin_status', user_remove_admin_status)
User.add_to_class('is_moderator', user_is_moderator)
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

#assertions
User.add_to_class('assert_can_vote_for_post', user_assert_can_vote_for_post)
User.add_to_class('assert_can_revoke_old_vote', user_assert_can_revoke_old_vote)
User.add_to_class('assert_can_upload_file', user_assert_can_upload_file)
User.add_to_class('assert_can_post_question', user_assert_can_post_question)
User.add_to_class('assert_can_post_answer', user_assert_can_post_answer)
User.add_to_class('assert_can_post_comment', user_assert_can_post_comment)
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

#todo: move this to askbot/utils ??
def format_instant_notification_email(
                                        to_user = None,
                                        from_user = None,
                                        post = None,
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

    site_url = askbot_settings.APP_URL
    origin_post = post.get_origin_post()
    #todo: create a better method to access "sub-urls" in user views
    user_subscriptions_url = site_url + \
                                reverse(
                                    'user_subscriptions',
                                    kwargs = {
                                        'id': to_user.id,
                                        'slug': slugify(to_user.username)
                                    }
                                )

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
    else:
        raise ValueError('unexpected update_type %s' % update_type)

    if update_type.endswith('update'):
        assert('comment' not in update_type)
        revisions = post.revisions.all()[:2]
        assert(len(revisions) == 2)
        content_preview = htmldiff(
                            revisions[1].as_html(),
                            revisions[0].as_html(),
                            ins_start = '<b><u style="background-color:#cfc">',
                            ins_end = '</u></b>',
                            del_start = '<del style="color:#600;background-color:#fcc">',
                            del_end = '</del>'
                        )
        #todo: remove hardcoded style
    else:
        from askbot.templatetags.extra_filters_jinja import absolutize_urls_func
        content_preview = absolutize_urls_func(post.html)
        tag_style = "white-space: nowrap; " \
                    + "font-size: 11px; color: #333;" \
                    + "background-color: #EEE;" \
                    + "border-left: 3px solid #777;" \
                    + "border-top: 1px solid #EEE;" \
                    + "border-bottom: 1px solid #CCC;" \
                    + "border-right: 1px solid #CCC;" \
                    + "padding: 1px 8px 1px 8px;" \
                    + "margin-right:3px;"
        if post.post_type == 'question':#add tags to the question
            content_preview += '<div>'
            for tag_name in post.get_tag_names():
                content_preview += '<span style="%s">%s</span>' % (tag_style, tag_name)
            content_preview += '</div>'

    update_data = {
        'update_author_name': from_user.username,
        'receiving_user_name': to_user.username,
        'receiving_user_karma': to_user.reputation,
        'reply_by_email_karma_threshold': askbot_settings.MIN_REP_TO_POST_BY_EMAIL,
        'can_reply': to_user.reputation > askbot_settings.MIN_REP_TO_POST_BY_EMAIL,
        'content_preview': content_preview,#post.get_snippet()
        'update_type': update_type,
        'post_url': strip_path(site_url) + post.get_absolute_url(),
        'origin_post_title': origin_post.thread.title,
        'user_subscriptions_url': user_subscriptions_url,
    }
    subject_line = _('"%(title)s"') % {'title': origin_post.thread.title}
    return subject_line, template.render(Context(update_data))

#todo: action
def send_instant_notifications_about_activity_in_post(
                                                update_activity = None,
                                                post = None,
                                                recipients = None,
                                            ):
    """
    function called when posts are updated
    newly mentioned users are carried through to reduce
    database hits
    """

    if recipients is None:
        return

    acceptable_types = const.RESPONSE_ACTIVITY_TYPES_FOR_INSTANT_NOTIFICATIONS

    if update_activity.activity_type not in acceptable_types:
        return

    from askbot.skins.loaders import get_template
    template = get_template('instant_notification.html')

    update_type_map = const.RESPONSE_ACTIVITY_TYPE_MAP_FOR_TEMPLATES
    update_type = update_type_map[update_activity.activity_type]

    origin_post = post.get_origin_post()
    for user in recipients:

        if askbot_settings.REPLY_BY_EMAIL:
            template = get_template('instant_notification_reply_by_email.html')
      
        subject_line, body_text = format_instant_notification_email(
                            to_user = user,
                            from_user = update_activity.user,
                            post = post,
                            update_type = update_type,
                            template = template,
                        )
      
        #todo: this could be packaged as an "action" - a bundle
        #of executive function with the activity log recording
        #TODO check user reputation
        headers = mail.thread_headers(post, origin_post, update_activity.activity_type)
        if askbot_settings.REPLY_BY_EMAIL:
            reply_address = "noreply"
            if user.reputation >= askbot_settings.MIN_REP_TO_POST_BY_EMAIL:
                reply_address = ReplyAddress.objects.create_new(post, user).address
            reply_to = 'reply-%s@%s' % (reply_address, askbot_settings.REPLY_BY_EMAIL_HOSTNAME)
            headers.update({'Reply-To': reply_to})
        else:
            reply_to = django_settings.DEFAULT_FROM_EMAIL
        mail.send_mail(
            subject_line = subject_line,
            body_text = body_text,
            recipient_list = [user.email],
            related_object = origin_post,
            activity_type = const.TYPE_ACTIVITY_EMAIL_UPDATE_SENT,
            headers = headers
        )




#todo: move to utils
def calculate_gravatar_hash(instance, **kwargs):
    """Calculates a User's gravatar hash from their email address."""
    if kwargs.get('raw', False):
        return
    clean_email = instance.email.strip().lower()
    instance.gravatar = hashlib.md5(clean_email).hexdigest()


def record_post_update_activity(
        post,
        newly_mentioned_users = None,
        updated_by = None,
        timestamp = None,
        created = False,
        diff = None,
        **kwargs
    ):
    """called upon signal askbot.models.signals.post_updated
    which is sent at the end of save() method in posts
    """
    assert(timestamp != None)
    assert(updated_by != None)
    if newly_mentioned_users is None:
        newly_mentioned_users = list()

    from askbot import tasks

    tasks.record_post_update_celery_task.delay(
        post_id = post.id,
        post_content_type_id = ContentType.objects.get_for_model(post).id,
        newly_mentioned_user_id_list = [u.id for u in newly_mentioned_users],
        updated_by_id = updated_by.id,
        timestamp = timestamp,
        created = created,
        diff = diff,
    )
    #non-celery version
    #tasks.record_post_update(
    #    post = post,
    #    newly_mentioned_users = newly_mentioned_users,
    #    updated_by = updated_by,
    #    timestamp = timestamp,
    #    created = created,
    #)


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
    if (user.last_seen - prev_last_seen).days == 1:
        user.consecutive_days_visit_count += 1
        award_badges_signal.send(None,
            event = 'site_visit',
            actor = user,
            context_object = user,
            timestamp = timestamp
        )
    #somehow it saves on the query as compared to user.save()
    User.objects.filter(id = user.id).update(last_seen = timestamp)


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
    recipients = User.objects.filter(
                    models.Q(is_superuser=True) | models.Q(status='m')
                )
    activity.add_recipients(recipients)

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

def complete_pending_tag_subscriptions(sender, request, *args, **kwargs):
    """save pending tag subscriptions saved in the session"""
    if 'subscribe_for_tags' in request.session:
        (pure_tag_names, wildcards) = request.session.pop('subscribe_for_tags')
        request.user.mark_tags(
                    pure_tag_names,
                    wildcards,
                    reason = 'good',
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

#signal for User model save changes
django_signals.pre_save.connect(make_admin_if_first_user, sender=User)
django_signals.pre_save.connect(calculate_gravatar_hash, sender=User)
django_signals.post_save.connect(add_missing_subscriptions, sender=User)
django_signals.post_save.connect(record_award_event, sender=Award)
django_signals.post_save.connect(notify_award_message, sender=Award)
django_signals.post_save.connect(record_answer_accepted, sender=Post)
django_signals.post_save.connect(record_vote, sender=Vote)
django_signals.post_save.connect(record_favorite_question, sender=FavoriteQuestion)

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
signals.user_updated.connect(record_user_full_updated, sender=User)
signals.user_logged_in.connect(complete_pending_tag_subscriptions)#todo: add this to fake onlogin middleware
signals.user_logged_in.connect(post_anonymous_askbot_content)
signals.post_updated.connect(record_post_update_activity)
signals.site_visited.connect(record_user_visit)

#set up a possibility for the users to follow others
try:
    import followit
    followit.register(User)
except ImportError:
    pass

__all__ = [
        'signals',

        'Thread',

        'QuestionView',
        'FavoriteQuestion',
        'AnonymousQuestion',

        'AnonymousAnswer',

        'Post',
        'PostRevision',

        'Tag',
        'Vote',
        'MarkedTag',

        'BadgeData',
        'Award',
        'Repute',

        'Activity',
        'ActivityAuditStatus',
        'EmailFeedSetting',

        'User',

        'ReplyAddress',

        'get_model'
]
