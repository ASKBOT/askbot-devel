"""functions in this module return body text
of email messages for various occasions
"""
import askbot
import logging
import urllib.request, urllib.parse, urllib.error
from copy import copy
from django.conf import settings as django_settings
from django.urls import reverse
from django.template import Context
from django.template.loader import get_template
from django.utils.encoding import force_str
from django.utils.html import mark_safe
from django.utils.translation import gettext_lazy as _
from askbot import const
from askbot.conf import settings as askbot_settings
from askbot.utils.html import (absolutize_urls, site_link, site_url)

LOG = logging.getLogger(__name__)

def get_user():
    """returns a user object"""
    from askbot.models import User
    return User.objects.all()[0]


def get_question():
    from askbot.models import Post
    return Post.objects.filter(post_type='question')[0]


class BaseEmail:
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
    * `mock_contexts` - optional, may be replaced with custom methods
    like get_mock_context1, etc.

    plain text version of the email is calculated from body.html
    by stripping tags
    """

    template_path = 'path/to/email/dir' #override in subclass
    title = 'A brief title for this email'
    description = 'In subclass, explain when/why this email might be sent'
    mock_contexts = ({},)

    def __init__(self, context=None):
        self.context = context
        self._context_cache = dict()

    @classmethod
    def get_cache_key(cls, key):
        return str(id(key))

    def get_cached_context(self, key):
        key = self.get_cache_key(key)
        return self._context_cache.get(key)

    def set_cached_context(self, key, val):
        key = self.get_cache_key(key)
        self._context_cache[key] = val

    def process_context(self, context):
        """override if context requires post-processing"""
        return context

    def get_attachments(self):
        """override if attachments need to be determined from context"""
        return None

    def get_mock_contexts(self):
        """Do not override this method.
        Add methods to subclass either called get_mock_context() and/or
        get_mock_context_<xyz> to generate mock contexts programmatically
        """
        contexts = list()
        for c in self.mock_contexts:
            if c:
                contexts.append(c)

        for attr in dir(self):
            if attr == 'get_mock_contexts':
                continue
            elif attr.startswith('get_mock_context'):
                func = getattr(self, attr)
                c = func()
                if c:
                    contexts.append(c)
        return contexts

    def get_context(self, pre_context=None):
        cached_context = self.get_cached_context(pre_context)
        if cached_context:
            return cached_context

        context = copy(pre_context or self.context or {})
        context = self.process_context(context)
        context['settings'] = askbot_settings
        self.set_cached_context(pre_context, context)
        return context

    def get_headers(self):
        """override this method if headers need to be calculated
        from context"""
        return None

    def is_enabled(self):
        """override if necessary"""
        return True

    def render_subject(self, context=None):
        template = get_template(self.template_path + '/subject.txt')

        context = copy(self.get_context(context)) #copy context
        for key in context:
            if isinstance(context[key], str):
                context[key] = mark_safe(context[key])

        return ' '.join(template.render(Context(context)).split())

    def render_body(self, context=None):
        template = get_template(self.template_path + '/body.html')
        body = template.render(Context(self.get_context(context)))
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
            LOG.warning(
                'Attempting to send disabled email "%s"',
                force_str(self.title)
            )


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

    def get_mock_context_sample1(self):
        """New question alert"""
        from askbot.models import (Activity, Post, User)
        posts = Post.objects.filter(post_type='question')
        if posts.count() == 0:
            return None
        post = posts[0]

        to_users = User.objects.exclude(id=post.author_id)
        if to_users.count() == 0:
            return None
        to_user = to_users[0]

        activity = Activity(
                    user=post.author,
                    content_object=post,
                    activity_type=const.TYPE_ACTIVITY_ASK_QUESTION,
                    question=post
                )
        return {
            'post': post,
            'from_user': post.author,
            'to_user': to_user,
            'update_activity': activity
        }

    def get_mock_context_sample2(self):
        """answer edit alert"""
        #get edited answer
        from django.db.models import Count
        from askbot.models import (Activity, Post, User)
        posts = Post.objects.annotate(
                        edit_count=Count('revisions')
                    ).filter(post_type='answer', edit_count__gt=1)

        try:
            post = posts[0]
        except IndexError:
            return None

        to_users = User.objects.exclude(id=post.author_id)
        if to_users.count() == 0:
            return None
        to_user = to_users[0]

        activity = Activity(
                    user=post.author,
                    content_object=post,
                    activity_type=const.TYPE_ACTIVITY_UPDATE_ANSWER,
                    question=post.get_origin_post()
                )
        return {
            'post': post,
            'from_user': post.author,
            'to_user': to_user,
            'update_activity': activity
        }

    def get_mock_context_sample3(self):
        """question edit alert"""
        #get edited answer
        from django.db.models import Count
        from askbot.models import (Activity, Post, User)
        posts = Post.objects.annotate(
                        edit_count=Count('revisions')
                    ).filter(post_type='question', edit_count__gt=1)

        try:
            post = posts[0]
        except IndexError:
            return None

        to_users = User.objects.exclude(id=post.author_id)
        if to_users.count() == 0:
            return None
        to_user = to_users[0]

        activity = Activity(
                    user=post.author,
                    content_object=post,
                    activity_type=const.TYPE_ACTIVITY_UPDATE_QUESTION,
                    question=post
                )
        return {
            'post': post,
            'from_user': post.author,
            'to_user': to_user,
            'update_activity': activity
        }

    def get_mock_context_sample4(self):
        """New question alert"""
        from askbot.models import (Activity, Post, User)
        posts = Post.objects.filter(
                                    parent__post_type='answer',
                                    post_type='comment'
                                   )
        if posts.count() == 0:
            return None
        post = posts[0]

        to_users = User.objects.exclude(id=post.author_id)
        if to_users.count() == 0:
            return None
        to_user = to_users[0]

        activity = Activity(
                    user=post.author,
                    content_object=post,
                    activity_type=const.TYPE_ACTIVITY_COMMENT_ANSWER,
                    question=post
                )
        return {
            'post': post,
            'from_user': post.author,
            'to_user': to_user,
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
            msg_id = "<NQ-%s-%s>" % (post.id, suffix_id)
            headers = {'Message-ID': msg_id}
        elif update == const.TYPE_ACTIVITY_ANSWER:
            msg_id = "<NA-%s-%s>" % (post.id, suffix_id)
            orig_id = "<NQ-%s-%s>" % (orig_post.id, suffix_id)
            headers = {'Message-ID': msg_id, 'In-Reply-To': orig_id}
        elif update == const.TYPE_ACTIVITY_UPDATE_QUESTION:
            msg_id = "<UQ-%s-%s-%s>" % (post.id, post.last_edited_at, suffix_id)
            orig_id = "<NQ-%s-%s>" % (orig_post.id, suffix_id)
            headers = {'Message-ID': msg_id, 'In-Reply-To': orig_id}
        elif update == const.TYPE_ACTIVITY_COMMENT_QUESTION:
            msg_id = "<CQ-%s-%s>" % (post.id, suffix_id)
            orig_id = "<NQ-%s-%s>" % (orig_post.id, suffix_id)
            headers = {'Message-ID': msg_id, 'In-Reply-To': orig_id}
        elif update == const.TYPE_ACTIVITY_UPDATE_ANSWER:
            msg_id = "<UA-%s-%s-%s>" % (post.id, post.last_edited_at, suffix_id)
            orig_id = "<NQ-%s-%s>" % (orig_post.id, suffix_id)
            headers = {'Message-ID': msg_id, 'In-Reply-To': orig_id}
        elif update == const.TYPE_ACTIVITY_COMMENT_ANSWER:
            msg_id = "<CA-%s-%s>" % (post.id, suffix_id)
            orig_id = "<NQ-%s-%s>" % (orig_post.id, suffix_id)
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

        #unhandled update_type 'post_shared'
        #user_action = _('%(user)s shared a %(post_link)s.')

        origin_post = post.get_origin_post()
        post_url = site_url(post.get_absolute_url())

        can_reply = to_user.can_post_by_email()
        from askbot.models import get_reply_to_addresses
        reply_address, alt_reply_address = get_reply_to_addresses(to_user, post)
        alt_reply_subject = urllib.parse.quote(('Re: ' + post.thread.title).encode('utf-8'))

        return {
           'admin_email': askbot_settings.ADMIN_EMAIL,
           'recipient_user': to_user,
           'update_author_name': from_user.username,
           'receiving_user_name': to_user.username,
           'receiving_user_karma': to_user.reputation,
           'reply_by_email_karma_threshold': askbot_settings.MIN_REP_TO_POST_BY_EMAIL,
           'can_reply': can_reply,
           'update_type': update_type,
           'update_activity': update_activity,
           'post': post,
           'post_url': post_url,
           'origin_post': origin_post,
           'thread_title': origin_post.thread.title,
           'reply_address': reply_address,
           'alt_reply_address': alt_reply_address,
           'alt_reply_subject': alt_reply_subject,
           'is_multilingual': askbot.is_multilingual(),
           'reply_sep_tpl': const.SIMPLE_REPLY_SEPARATOR_TEMPLATE
        }


class ReplyByEmailError(BaseEmail):
    template_path = 'email/reply_by_email_error'
    title = _('Error processing post sent by email')
    description = _('Sent to the post author when error occurs when posting by email')
    mock_contexts = ({
        'error': _('You were replying to an email address\
             unknown to the system or you were replying from a different address from the one where you\
             received the notification.')
    },)

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
        return {
            'user': get_user(),
            'site_name': askbot_settings.APP_SHORT_NAME or 'our community'
        }

    def process_context(self, context):
        context['recipient_user'] = context['user']
        context['site_name'] = askbot_settings.APP_SHORT_NAME
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
            'reply_to_address': 'welcome-' + email_code + '@example.com',
            'site_name': askbot_settings.APP_SHORT_NAME or 'our community'
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
    mock_contexts = ({
        'post': 'How to substitute sugar with aspartame in the cupcakes',
        'reject_reason': 'Questions must be on the subject of gardening'
    },)

    def is_enabled(self):
        return askbot_settings.CONTENT_MODERATION_MODE == 'premoderation' \
            and askbot_settings.REJECTED_POST_EMAIL_ENABLED

    def process_context(self, context):
        context.setdefault('recipient_user', None)
        return context


class AccountManagementRequest(BaseEmail):
    template_path = 'email/account_management_request'
    title = _('Account management request')
    description = _('Sent when user wants to cancel account or download data')
    mock_contexts = ({'message': 'User Bob, id=52 asked to export personal data.',
                      'username': 'Bob'},)


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
            'is_multilingual': askbot.is_multilingual()
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


class AccountActivation(BaseEmail):
    template_path = 'authopenid/account_activation'
    title = _('Account activation')
    description = _('Sent when user creates account, contains email validation link')
    mock_contexts = ({'key': 'a4umkaeuaousthsth'},)

    def process_context(self, context):
        context.update({
            'site_name': askbot_settings.APP_SHORT_NAME,
            'recipient_user': None,#needed for the Django template
            'validation_link': site_url(reverse('verify_email_and_register')) + \
                                '?validation_code=' + context['key']
        })
        return context


class AccountRecovery(BaseEmail):
    template_path = 'authopenid/account_recovery'
    title = _('Account recovery')
    description = _('Sent when user needs to recover login')
    mock_contexts = ({'key': 'a4umkaeuaousthsth'},)

    def process_context(self, context):
        context.update({
            'site_name': askbot_settings.APP_SHORT_NAME,
            'recipient_user': None,#needed for the Django template
            'validation_link': site_url(reverse('user_account_recover')) + \
                                '?validation_code=' + context['key']
        })
        return context


class UnsubscribeLink(BaseEmail):
    template_path = 'email/unsubscribe_link'
    title = _('Unsubscribe link')
    description = _('Sent when email key expired, but user is identified')

    def get_mock_context(self):
        return {
            'key': 'au7153Eioeaia',
            'email': 'user@example.com',
            'site_name': 'example.com'
        }


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


#class GroupMessagingEmailAlert(BaseEmail):
#    template_path = 'group_messaging/email_alert'
#    title = _('Private message notification')
#    description = _('Sent when a private message is sent to the user')
#    preview_error_message = _(
#        'At least one user and one personal message are required to '
#        'generate a preview'
#    )
#
#    def is_enabled(self):
#        from askbot.deps.group_messaging.models import Message
#        if Message.objects.count() == 0:
#            return False
#        return askbot_settings.ENABLE_EMAIL_ALERTS \
#            and askbot_settings.GROUP_MESSAGING_EMAIL_ALERT_ENABLED
#
#    def get_mock_context(self):
#        from askbot.deps.group_messaging.models import Message
#        messages = Message.objects.all().order_by('-id')
#        if messages.count() == 0:
#            return None
#        message = messages[0]
#        return {
#            'messages': message.get_timeline(),
#            'message': message,
#            'recipient_user': get_user()
#        }

class FeedbackEmail(BaseEmail):
    template_path = 'email/feedback'
    title = _('Feedback email')
    description = _('Sent when user submits feedback form')

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
