"""functions in this module return body text
of email messages for various occasions
"""
import functools
import logging
import urllib
from copy import copy
from django.conf import settings as django_settings
from django.core.urlresolvers import reverse
from django.template import Context
from django.template.loader import get_template
from django.utils.encoding import force_str
from django.utils.html import mark_safe
from django.utils.translation import ugettext_lazy as _
from askbot import const
from askbot.conf import settings as askbot_settings
from askbot.utils import html as html_utils
from askbot.utils.diff import textDiff as htmldiff
from askbot.utils.html import (absolutize_urls, sanitize_html, site_link, site_url)
from askbot.utils.slug import slugify

LOG = logging.getLogger(__name__)

def get_user():
    """returns a user object"""
    from askbot.models import User
    return User.objects.all()[0]


def get_question():
    from askbot.models import Post
    return Post.objects.filter(post_type='question')[0]


class BaseEmail(object):
    """Base class for templated emails.

    Besides sending formatted emails,
    this class allows to generate
    email mockups, to help development
    of the email templates.

    Subclass must specify variables:
    * `template_path` - path to the directory which must contain
       files `subject.txt` and `body.txt`
    * `title` - a brief title for this email
    * `description` - string explaining why/when this email is sent
    * `mock_context` - optional, may be replaced with custom method
    get_mock_context(), see below

    plain text version of the email is calculated from body.html
    by stripping tags
    """

    template_path = 'path/to/email/dir' #override in subclass
    title = 'A brief title for this email'
    description = 'In subclass, explain when/why this email might be sent'
    mock_context = {}

    def __init__(self, context=None):
        self.context = context
        self._cached_context = None

    def process_context(self, context):
        """override if context requires post-processing"""
        return context

    def get_attachments(self):
        """override if attachments need to be determined from context"""
        return None

    def get_mock_context(self):
        """override if need to fetch mock context dynamically"""
        return self.mock_context

    def get_context(self):
        if self._cached_context:
            return self._cached_context
        context = self.context or self.get_mock_context() or self.mock_context or {}
        self._cached_context = self.process_context(context)
        self._cached_context['settings'] = askbot_settings
        return self._cached_context

    def get_headers(self):
        """override this method if headers need to be calculated
        from context"""
        return None

    def is_enabled(self):
        """override if necessary"""
        return True

    def render_subject(self):
        template = get_template(self.template_path + '/subject.txt')

        context = copy(self.get_context()) #copy context
        for key in context:
            if isinstance(context[key], basestring):
                context[key] = mark_safe(context[key])

        return ' '.join(template.render(Context(context)).split())

    def render_body(self):
        template = get_template(self.template_path + '/body.html')
        body = template.render(Context(self.get_context()))
        return absolutize_urls(body)

    def send(self, recipient_list, raise_on_failure=False, headers=None, attachments=None):
        if self.is_enabled():
            from askbot.mail import send_mail
            send_mail(
                subject_line=self.render_subject(),
                body_text=self.render_body(),
                from_email=None,
                recipient_list=recipient_list,
                headers=headers or self.get_headers(),
                raise_on_failure=raise_on_failure,
                attachments=attachments or self.get_attachments()
            )
        else:
            LOG.warning('Attempting to send disabled email "%s"' % self.title)

class InstantEmailAlert(BaseEmail):
    template_path = 'email/instant_notification'
    title = _('Instant email notification')
    description = _('Sent to relevant users when a post is made or edited')
    preview_error_message = _(
        'At least two users and one post are needed to generate the preview'
    )

    def is_enabled(self):
        return askbot_settings.ENABLE_EMAIL_ALERTS \
            and askbot_settings.INSTANT_EMAIL_ALERT_ENABLED

    def get_mock_context(self):
        from askbot.models import (Activity, Post, User)
        post_types = ('question', 'answer', 'comment')
        post = Post.objects.filter(post_type__in=post_types)[0]

        if post.is_question():
            activity_type = const.TYPE_ACTIVITY_ASK_QUESTION
        elif post.is_answer():
            activity_type = const.TYPE_ACTIVITY_ANSWER
        elif post.parent.is_question():
            activity_type = const.TYPE_ACTIVITY_COMMENT_QUESTION
        else:
            activity_type = const.TYPE_ACTIVITY_COMMENT_ANSWER

        activity = Activity(
                    user=post.author,
                    content_object=post,
                    activity_type=activity_type,
                    question=post.get_origin_post()
                )
        return {
            'post': post,
            'from_user': post.author,
            'to_user': User.objects.exclude(id=post.author_id)[0],
            'update_activity': activity
        }

    def get_headers(self):
        context = self.get_context()
        post = context['post']
        origin_post = context['origin_post']
        reply_address = context['reply_address']
        update_activity = context['update_activity']

        headers = self.get_thread_headers(
            post,
            origin_post,
            update_activity.activity_type
            )
        headers['Reply-To'] = reply_address
        return headers

    def get_thread_headers(self, post, orig_post, update):
        """modify headers for email messages, so
        that emails appear as threaded conversations in gmail"""
        suffix_id = django_settings.SERVER_EMAIL
        if update == const.TYPE_ACTIVITY_ASK_QUESTION:
            msg_id = "NQ-%s-%s" % (post.id, suffix_id)
            headers = {'Message-ID': msg_id}
        elif update == const.TYPE_ACTIVITY_ANSWER:
            msg_id = "NA-%s-%s" % (post.id, suffix_id)
            orig_id = "NQ-%s-%s" % (orig_post.id, suffix_id)
            headers = {'Message-ID': msg_id, 'In-Reply-To': orig_id}
        elif update == const.TYPE_ACTIVITY_UPDATE_QUESTION:
            msg_id = "UQ-%s-%s-%s" % (post.id, post.last_edited_at, suffix_id)
            orig_id = "NQ-%s-%s" % (orig_post.id, suffix_id)
            headers = {'Message-ID': msg_id, 'In-Reply-To': orig_id}
        elif update == const.TYPE_ACTIVITY_COMMENT_QUESTION:
            msg_id = "CQ-%s-%s" % (post.id, suffix_id)
            orig_id = "NQ-%s-%s" % (orig_post.id, suffix_id)
            headers = {'Message-ID': msg_id, 'In-Reply-To': orig_id}
        elif update == const.TYPE_ACTIVITY_UPDATE_ANSWER:
            msg_id = "UA-%s-%s-%s" % (post.id, post.last_edited_at, suffix_id)
            orig_id = "NQ-%s-%s" % (orig_post.id, suffix_id)
            headers = {'Message-ID': msg_id, 'In-Reply-To': orig_id}
        elif update == const.TYPE_ACTIVITY_COMMENT_ANSWER:
            msg_id = "CA-%s-%s" % (post.id, suffix_id)
            orig_id = "NQ-%s-%s" % (orig_post.id, suffix_id)
            headers = {'Message-ID': msg_id, 'In-Reply-To': orig_id}
        else:
            # Unknown type -> Can't set headers
            return {}
        return headers

    @classmethod
    def get_update_type(cls, activity):
        update_type_map = const.RESPONSE_ACTIVITY_TYPE_MAP_FOR_TEMPLATES
        return update_type_map[activity.activity_type]

    def process_context(self, context):
        to_user = context.get('to_user')
        from_user = context.get('from_user')
        post = context.get('post')
        update_activity = context.get('update_activity')
        update_type = self.get_update_type(update_activity)

        origin_post = post.get_origin_post()

        from askbot.models import Post
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
            content_preview = post.format_for_email(is_leaf_post=True, recipient=to_user)

        #add indented summaries for the parent posts
        content_preview += post.format_for_email_as_parent_thread_summary(recipient=to_user)

        #content_preview += '<p>======= Full thread summary =======</p>'
        #content_preview += post.thread.format_for_email(recipient=to_user)

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

        if to_user.is_administrator_or_moderator() and askbot_settings.SHOW_ADMINS_PRIVATE_USER_DATA:
            user_link_fmt = '<a href="%(profile_url)s">%(username)s</a> (<a href="mailto:%(email)s">%(email)s</a>)'
            user_link = user_link_fmt % {
                'profile_url': user_url,
                    'username': from_user.username,
                    'email': from_user.email
            }
        elif post.is_anonymous:
            user_link = from_user.get_name_of_anonymous_user()
        else:
            user_link = '<a href="%s">%s</a>' % (user_url, from_user.username)

        user_action = user_action % {
            'user': user_link,
            'post_link': '<a href="%s">%s</a>' % (post_url, _(post.post_type))
        }

        can_reply = to_user.can_post_by_email()
        from askbot.models import get_reply_to_addresses
        reply_address, alt_reply_address = get_reply_to_addresses(to_user, post)

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
                reply_separator += '<p>' + const.REPLY_WITH_COMMENT_TEMPLATE % data
                reply_separator += '</p>'
            else:
                reply_separator = '<p>%s</p>' % reply_separator
                reply_separator += user_action
        else:
            reply_separator = user_action

        return {
           'admin_email': askbot_settings.ADMIN_EMAIL,
           'recipient_user': to_user,
           'update_author_name': from_user.username,
           'receiving_user_name': to_user.username,
           'receiving_user_karma': to_user.reputation,
           'reply_by_email_karma_threshold': askbot_settings.MIN_REP_TO_POST_BY_EMAIL,
           'can_reply': can_reply,
           'content_preview': content_preview,
           'update_type': update_type,
           'update_activity': update_activity,
           'post': post,
           'post_url': post_url,
           'origin_post': origin_post,
           'thread_title': origin_post.thread.title,
           'reply_separator': reply_separator,
           'reply_address': reply_address,
           'is_multilingual': getattr(django_settings, 'ASKBOT_MULTILINGUAL', False)
        }


class ReplyByEmailError(BaseEmail):
    template_path = 'email/reply_by_email_error'
    title = _('Error processing post sent by email')
    description = _('Sent to the post author when error occurs when posting by email')
    mock_context = {
        'error': _('You were replying to an email address\
             unknown to the system or you were replying from a different address from the one where you\
             received the notification.')
    }

    def is_enabled(self):
        return askbot_settings.REPLY_BY_EMAIL


class WelcomeEmail(BaseEmail):
    template_path = 'email/welcome'
    title = _('Welcome message')
    description = _('Sent to newly registered user when replying by email is disabled')
    preview_error_message = _(
        'At least one user is required generate a preview'
    )

    def is_enabled(self):
        return askbot_settings.ENABLE_EMAIL_ALERTS \
            and askbot_settings.WELCOME_EMAIL_ENABLED


    def get_mock_context(self):
        return {'user': get_user()}

    def process_context(self, context):
        context['recipient_user'] = context['user']
        return context

class WelcomeEmailRespondable(BaseEmail):
    template_path = 'email/welcome_respondable'
    title = _('Respondable "welcome" message')
    description = _('Sent to newly registered user when replying by email is enabled')
    preview_error_message = _(
        'At least one user is required generate a preview'
    )

    def is_enabled(self):
        return askbot_settings.REPLY_BY_EMAIL

    def process_context(self, context):
        user = context['recipient_user']
        extra_data = {
            'site_name': askbot_settings.APP_SHORT_NAME,
            'site_url': reverse('questions'),
            'ask_address': 'ask@' + askbot_settings.REPLY_BY_EMAIL_HOSTNAME,
            'can_post_by_email': user.can_post_by_email(),
        }
        extra_data.update(context)
        return extra_data

    def get_headers(self):
        context = self.get_context()
        return {'Reply-To': context['reply_to_address']}

    def get_mock_context(self):
        email_code = '5kxe4cyfkchv'
        return {
            'recipient_user': get_user(),
            'email_code': email_code,
            'reply_to_address': 'welcome-' + email_code + '@example.com'
        }


class ReWelcomeEmail(BaseEmail):
    template_path = 'email/re_welcome'
    title = _('Reply to the user response to the "welcome" message')
    description = _('Sent to newly registered user who replied to the welcome message')
    preview_error_message = _(
        'At least one user on the site is necessary to generate the preview'
    )

    def is_enabled(self):
        return askbot_settings.REPLY_BY_EMAIL

    def get_mock_context(self):
        return {
            'recipient_user': get_user(),
            'can_post_by_email': True
        }

    def process_context(self, context):
        user = context['recipient_user']
        extra_data = {
            'ask_address': 'ask@' + askbot_settings.REPLY_BY_EMAIL_HOSTNAME,
            'can_post_by_email': user.can_post_by_email(),
            'site_name': askbot_settings.APP_SHORT_NAME,
            'site_url': site_url(reverse('questions')),
        }
        extra_data.update(context)
        return extra_data


class AskForSignature(BaseEmail):
    template_path = 'email/ask_for_signature'
    title = _('Request to reply to get a sample of email the signature')
    description = _(
        'Sent when the system does not have a record of email signature '
        'for the user'
    )
    preview_error_message = _(
        'At least one user on the site is necessary to generate the preview'
    )

    def is_enabled(self):
        return askbot_settings.REPLY_BY_EMAIL

    def process_context(self, context):
        user = context['user']
        footer_code = context['footer_code']
        return {
            'footer_code': footer_code,
            'recipient_user': user,
            'site_name': askbot_settings.APP_SHORT_NAME,
            'username': user.username,
        }

    def get_mock_context(self):
        return {'user': get_user(), 'footer_code': 'koeunt35keaxx'}


class InsufficientReputation(BaseEmail):
    template_path = 'email/insufficient_reputation'
    title = _('Insufficient karma to post by email')
    description = _(
        'Sent when user does not have enough '
        'karma upon posting by email'
    )
    preview_error_message = _(
        'At least one user on the site is necessary to generate the preview'
    )

    def is_enabled(self):
        return askbot_settings.REPLY_BY_EMAIL

    def get_mock_context(self):
        return {'user': get_user()}

    def process_context(self, context):
        user = context['user']
        min_rep = askbot_settings.MIN_REP_TO_POST_BY_EMAIL
        min_upvotes = 1 + \
                      (min_rep/askbot_settings.REP_GAIN_FOR_RECEIVING_UPVOTE)
        return {
            'username': user.username,
            'recipient_user': user,
            'site_name': askbot_settings.APP_SHORT_NAME,
            'site_link': site_link('ask', askbot_settings.APP_SHORT_NAME),
            'min_upvotes': min_upvotes
        }


class RejectedPost(BaseEmail):
    template_path = 'email/rejected_post'
    title = _('Post was rejected')
    description = _(
        'Sent when post was rejected by a moderator with a reason given'
    )
    mock_context = {
        'post': 'How to substitute sugar with aspartame in the cupcakes',
        'reject_reason': 'Questions must be on the subject of gardening'
    }

    def is_enabled(self):
        return askbot_settings.CONTENT_MODERATION_MODE == 'premoderation' \
            and askbot_settings.REJECTED_POST_EMAIL_ENABLED

    def process_context(self, context):
        context.setdefault('recipient_user', None)
        return context


class ModerationQueueNotification(BaseEmail):
    template_path = 'email/moderation_queue_notification'
    title = _('Moderation queue has items')
    description = _(
        'Sent to moderators when the moderation queue is not empty'
    )
    preview_error_message = _(
        'At least one user on the site is necessary to generate the preview'
    )

    def is_enabled(self):
        return askbot_settings.CONTENT_MODERATION_MODE == 'premoderation' \
            and askbot_settings.MODERATION_QUEUE_NOTIFICATION_ENABLED

    def process_context(self, context):
        user = context['user']
        context.update({
            'recipient_user': user,
            'site': askbot_settings.APP_SHORT_NAME,
        })
        return context

    def get_mock_context(self):
        return {'user': get_user()}


class BatchEmailAlert(BaseEmail):
    template_path = 'email/batch_email_alert'
    title = _('Batch email alert')
    description = _('Contains daily of weekly batches of email updates')
    preview_error_message = _(
        'At least one user on the site and two questions are '
        'necessary to generate the preview'
    )

    def is_enabled(self):
        return askbot_settings.ENABLE_EMAIL_ALERTS \
            and askbot_settings.BATCH_EMAIL_ALERT_ENABLED

    def process_context(self, context):
        user = context['user']
        context.update({
            'name': user.username,
            'question_count': len(context['questions']),
            'recipient_user': user,
            'admin_email': askbot_settings.ADMIN_EMAIL,
            'site_name': askbot_settings.APP_SHORT_NAME,
            'is_multilingual': getattr(django_settings, 'ASKBOT_MULTILINGUAL', False)
        })
        return context

    def get_mock_context(self):
        from askbot.models import Post, Thread
        from askbot.management.commands.send_email_alerts import format_action_count

        qdata = list()
        qq = Post.objects.filter(post_type='question')[:2]

        act_list = list()
        act_list.append(force_str(_('new question')))
        format_action_count('%(num)d rev', 3, act_list)
        format_action_count('%(num)d ans', 2, act_list)
        qdata.append({
            'url': qq[0].get_absolute_url(),
            'info': ', '.join(act_list),
            'title': qq[0].thread.title
        })

        act_list = list()
        format_action_count('%(num)d rev', 1, act_list)
        format_action_count('%(num)d ans rev', 4, act_list)
        qdata.append({
            'url': qq[1].get_absolute_url(),
            'info': ', '.join(act_list),
            'title': qq[1].thread.title
        })

        threads = (qq[0].thread, qq[1].thread)
        tag_summary = Thread.objects.get_tag_summary_from_threads(threads)
        return {
            'user': get_user(),
            'questions': qdata,
            'tag_summary': tag_summary
        }


class AcceptAnswersReminder(BaseEmail):
    template_path = 'email/accept_answers_reminder'
    title = _('Accept answers reminder')
    description = _('Sent to author of questions without accepted answers')
    preview_error_message = _(
        'At least one user and one question are required to '
        'generate a preview'
    )

    def get_mock_context(self):
        from askbot.models import Post
        return {
            'recipient_user': get_user(),
            'questions': Post.objects.filter(post_type='question')[:7]
        }


class UnansweredQuestionsReminder(BaseEmail):
    template_path = 'email/unanswered_questions_reminder'
    title = _('Unanswered questions reminder')
    description = _('Sent to users when there are unanswered questions')
    preview_error_message = _(
        'At least one user and one question are required to '
        'generate a preview'
    )

    def process_context(self, context):
        count = len(context['questions'])
        context['question_count'] = count
        if count == 1:
            phrase = askbot_settings.WORDS_UNANSWERED_QUESTION_SINGULAR
        else:
            phrase = askbot_settings.WORDS_UNANSWERED_QUESTION_PLURAL
        context['unanswered_questions_phrase'] = phrase
        return context

    def get_mock_context(self):
        from askbot.models import Post, Thread
        questions = Post.objects.filter(post_type='question')[:7]
        threads = [q.thread for q in questions]
        tag_summary = Thread.objects.get_tag_summary_from_threads(threads)
        return {
            'recipient_user': get_user(),
            'questions': questions,
            'tag_summary': tag_summary
        }


class EmailValidation(BaseEmail):
    template_path = 'authopenid/email_validation'
    title = _('Email validation')
    description = _('Sent when user validates email or recovers account')
    mock_context = {
        'key': 'a4umkaeuaousthsth',
        'handler_url_name': 'user_account_recover',
    }

    def process_context(self, context):
        url_name = context['handler_url_name']
        context.update({
            'site_name': askbot_settings.APP_SHORT_NAME,
            'recipient_user': None,#needed for the Django template
            'validation_link': site_url(reverse(url_name)) + \
                                '?validation_code=' + context['key']
        })
        return context


class ApprovedPostNotification(BaseEmail):
    template_path = 'email/approved_post_notification'
    title = _('Approved post notification')
    description = _('Sent when post revision is approved by the moderator')
    preview_error_message = _(
        'At least one user and one question are required to '
        'generate a preview'
    )

    def is_enabled(self):
        return askbot_settings.CONTENT_MODERATION_MODE == 'premoderation' \
            and askbot_settings.APPROVED_POST_NOTIFICATION_ENABLED

    def get_mock_context(self):
        question = get_question()
        return {
            'recipient_user': question.author,
            'post': question
        }

    def process_context(self, context):
        context['site_name'] = askbot_settings.APP_SHORT_NAME
        return context


class ApprovedPostNotificationRespondable(BaseEmail):
    template_path = 'email/approved_post_notification_respondable'
    title = _('Respondable approved post notification')
    description = _('Sent when post revision is approved by the moderator')
    preview_error_message = _(
        'At least one user and one question are required to '
        'generate a preview'
    )

    def is_enabled(self):
        return askbot_settings.CONTENT_MODERATION_MODE == 'premoderation' \
            and askbot_settings.REPLY_BY_EMAIL

    def get_mock_context(self):
        question = get_question()
        hostname = askbot_settings.REPLY_BY_EMAIL_HOSTNAME
        replace_content_address = 'reply-kot1jxx4@' + hostname
        append_content_address = 'reply-kot1jxx4@' + hostname
        return {
            'revision': question.current_revision,
            'mailto_link_subject': question.thread.title,
            'reply_code': append_content_address + ',' + replace_content_address,
            'append_content_address': append_content_address,
            'replace_content_address': replace_content_address
        }

    def get_headers(self):
        context = self.get_context()
        #todo: possibly add more mailto thread headers to organize messages
        return {'Reply-To': context['append_content_address']}

    def process_context(self, context):
        revision = context['revision']
        prompt = force_str(_('To add to your post EDIT ABOVE THIS LINE'))
        context.update({
            'site_name': askbot_settings.APP_SHORT_NAME,
            'post': revision.post,
            'recipient_user': revision.author,
            'author_email_signature': revision.author.email_signature,
            'reply_separator_line': const.SIMPLE_REPLY_SEPARATOR_TEMPLATE % prompt,
        })
        return context


class GroupMessagingEmailAlert(BaseEmail):
    template_path = 'group_messaging/email_alert'
    title = _('Private message notification')
    description = _('Sent when a private message is sent to the user')
    preview_error_message = _(
        'At least one user and one personal message are required to '
        'generate a preview'
    )

    def is_enabled(self):
        return askbot_settings.ENABLE_EMAIL_ALERTS \
            and askbot_settings.GROUP_MESSAGING_EMAIL_ALERT_ENABLED

    def get_mock_context(self):
        from askbot.deps.group_messaging.models import Message
        message = Message.objects.all().order_by('-id')[0]
        return {
            'messages': message.get_timeline(),
            'message': message,
            'recipient_user': get_user()
        }

class FeedbackEmail(BaseEmail):
    template_path = 'email/feedback'
    title = _('Feedback email')
    description = _('Sent when users submits feedback form')

    def process_context(self, context):
        context['site_name'] = askbot_settings.APP_SHORT_NAME
        return context

    def get_mock_context(self):
        return {
            'name': 'Joe',
            'email': 'joe@example.com',
            'message': 'Your site is pretty good.\n\nThank you',
            'ip_addr': '127.0.0.1'
        }

    def get_headers(self):
        context = self.get_context()
        if 'email' in context:
            return {'Reply-To': context['email']}
        return {}
