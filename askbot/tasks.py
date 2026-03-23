"""Definitions of Celery tasks in Askbot
in this module there are two types of functions:

* those wrapped with a @task decorator and a ``_celery_task`` suffix - celery tasks
* those with the same base name, but without the decorator and the name suffix
  the actual work units run by the task

Celery tasks are special functions in a way that they require all the parameters
be serializable - so instead of ORM objects we pass object id's and
instead of query sets - lists of ORM object id's.

That is the reason for having two types of methods here:

* the base methods (those without the decorator and the
  ``_celery_task`` in the end of the name
  are work units that are called from the celery tasks.
* celery tasks - shells that reconstitute the necessary ORM
  objects and call the base methods
"""
import json
import logging
import os
import traceback
import uuid

from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.utils.translation import gettext as _
from django.utils.translation import activate as activate_language

from celery import shared_task
from celery.utils.log import get_task_logger

from askbot.conf import settings as askbot_settings
from askbot import const
from askbot.mail.messages import (
                        InstantEmailAlert,
                        ApprovedPostNotification,
                        ApprovedPostNotificationRespondable
                    )
from askbot.models import (
    Activity,
    ActivityAuditStatus,
    Post,
    PostRevision,
    User,
    ReplyAddress,
)
from askbot.models.user import get_invited_moderators
from askbot.models.badges import award_badges_signal
from askbot import exceptions as askbot_exceptions
from askbot.utils.twitter import Twitter
from askbot.spam_checker.akismet_spam_checker import akismet_submit_spam


logger = get_task_logger(__name__)


# TODO: Make exceptions raised inside record_post_update_celery_task() ...
#       ... propagate upwards to test runner, if only CELERY_TASK_ALWAYS_EAGER = True
#       (i.e. if Celery tasks are not deferred but executed straight away)
@shared_task(ignore_result=True)
def tweet_new_post_task(post_id):
    try:
        twitter = Twitter()
    except: # pylint: disable=bare-except
        return

    post = Post.objects.get(id=post_id)

    is_mod = post.author.is_administrator_or_moderator()
    if is_mod or post.author.reputation > askbot_settings.MIN_REP_TO_TWEET_ON_OTHERS_ACCOUNTS:
        tweeters = User.objects.filter(askbot_profile__social_sharing_mode=const.SHARE_EVERYTHING)
        tweeters = tweeters.exclude(id=post.author.id)
        access_tokens = tweeters.values_list('twitter_access_token', flat=True)
    else:
        access_tokens = []

    tweet_text = post.as_tweet()

    for raw_token in access_tokens:
        token = json.loads(raw_token)
        twitter.tweet(tweet_text, access_token=token)

    if post.author.social_sharing_mode != const.SHARE_NOTHING:
        token = json.loads(post.author.twitter_access_token)
        twitter.tweet(tweet_text, access_token=token)


@shared_task(ignore_result=True)
def submit_spam_posts_to_akismet(post_ids):
    posts = Post.objects.filter(pk__in=post_ids)
    # todo: save user agent in the revisions, using a fixed record
    # here because there is nothing better at the moment
    user_agent = 'Mozilla/5.0 (Windows NT 6.0; Win64; x64)'
    for post in posts:
        text = post.get_text_content()
        ip_addr = post.revisions.all()[0].ip_addr
        akismet_submit_spam(text,
                            ip_addr=ip_addr,
                            user_agent=user_agent,
                            username=post.author.username,
                            email=post.author.email)


@shared_task(ignore_result=True)
def export_user_data(user_id):
    """Exports user data by ID"""
    try:
        user = User.objects.get(pk=user_id)
        #1) delete older data exports
        user.delete_exported_data()
        #2) export new data
        file_path = user.suggest_backup_file_path()
        data_dir = os.path.dirname(file_path)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, 0o700)
        call_command('askbot_export_user_data', user_id=user_id, file_name=file_path)
    except User.DoesNotExist: # pylint: disable=no-member
        return


@shared_task(ignore_result=True)
def delete_update_notifications_task(rev_ids, keep_activity):
    """parameter is list of revision ids"""
    ctype = ContentType.objects.get_for_model(PostRevision)
    acts = Activity.objects.filter(content_type=ctype, object_id__in=rev_ids)
    act_ids = acts.values_list('pk', flat=True)

    # 2) Find notifications related to found activities
    notifs = ActivityAuditStatus.objects.filter(activity__pk__in=act_ids) # pylint: disable=no-member

    # 3) Find recipients of notifications
    user_ids = notifs.values_list('user', flat=True).distinct()
    users = list(User.objects.filter(pk__in=user_ids))

    # 4) Delete notifications by deleting activities
    # so that the loop below updates the counts
    if keep_activity:
        # delete only notifications
        notifs.delete()
    else:
        # delete activities and notifications
        # b/c notifications have activity as FK records
        acts.delete()

    for user in users:
        user.update_response_counts()

@shared_task(ignore_result=True)
def notify_author_of_published_revision_celery_task(revision_id):
    # TODO: move this to ``askbot.mail`` module
    # for answerable email only for now, because
    # we don't yet have the template for the read-only notification

    try:
        revision = PostRevision.objects.get(pk=revision_id)
    except PostRevision.DoesNotExist: # pylint: disable=no-member
        logger.error("Unable to fetch revision with id %s", revision_id)
        return

    activate_language(revision.post.language_code)

    if not askbot_settings.REPLY_BY_EMAIL:
        email = ApprovedPostNotification({
            'post': revision.post,
            'recipient_user': revision.author
        })
        email.send([revision.author.email])
    else:
        # generate two reply codes (one for edit and one for addition)
        # to format an answerable email or not answerable email
        reply_options = {
            'user': revision.author,
            'post': revision.post,
            'reply_action': 'append_content'
        }
        append_content_address = ReplyAddress.objects.create_new(
                                                        **reply_options
                                                    ).as_email_address()
        reply_options['reply_action'] = 'replace_content'
        replace_content_address = ReplyAddress.objects.create_new(
                                                        **reply_options
                                                    ).as_email_address()

        if revision.post.post_type == 'question':
            mailto_link_subject = revision.post.thread.title
        else:
            mailto_link_subject = _('make an edit by email')

        email = ApprovedPostNotificationRespondable({
            'revision': revision,
            'mailto_link_subject': mailto_link_subject,
            'reply_code': append_content_address + ',' + replace_content_address,
            'append_content_address': append_content_address,
            'replace_content_address': replace_content_address
        })
        email.send([revision.author.email])


@shared_task(ignore_result=True)
def record_post_update_celery_task( # pylint: disable=too-many-arguments
        post_id, newly_mentioned_user_id_list=None, updated_by_id=None,
        suppress_email=False, timestamp=None, created=False, diff=None):
    # reconstitute objects from the database
    updated_by = User.objects.get(id=updated_by_id)
    post = Post.objects.get(id=post_id)
    newly_mentioned_users = User.objects.filter(
                                id__in=newly_mentioned_user_id_list
                            )
    try:
        notify_sets = post.get_notify_sets(
            mentioned_users=newly_mentioned_users,
            exclude_list=[updated_by])

        activity_type = post.get_updated_activity_type(created)
        post.issue_update_notifications(
            updated_by=updated_by,
            notify_sets=notify_sets,
            activity_type=activity_type,
            suppress_email=suppress_email,
            timestamp=timestamp,
            diff=diff)
    except Exception: # pylint: disable=broad-except
        logger.error(str(traceback.format_exc()).encode('utf-8'))


@shared_task(ignore_result=True)
def record_question_visit(
        language_code=None, question_post_id=None, update_view_count=False,
        user_id=None):
    """celery task which records question visit by a person
    updates view counter, if necessary,
    and awards the badges associated with the
    question visit
    """
    activate_language(language_code)
    # 1) maybe update the view count
    try:
        question_post = Post.objects.get(id=question_post_id)
    except Post.DoesNotExist: # pylint: disable=no-member
        logger.error("Unable to fetch post with id %s", question_post_id)
        return

    if update_view_count and question_post.thread_id:
        question_post.thread.increase_view_count()

    # we do not track visits per anon user
    if user_id is None:
        return

    user = User.objects.get(id=user_id)

    # 2) question view count per user and clear response displays
    if user.is_authenticated:
        # get response notifications
        user.visit_question(question_post)

    #3) send award badges signal for any badges
    #that are awarded for question views
    award_badges_signal.send(None,
                             event='view_question',
                             actor=user,
                             context_object=question_post)

@shared_task(ignore_result=True)
def send_instant_notifications_about_activity_in_post(
        activity_id=None, post_id=None, recipient_ids=None,
        include_invited_moderators=False):

    if recipient_ids:
        recipients = set(User.objects.filter(pk__in=recipient_ids))
    else:
        recipients = set()

    if include_invited_moderators:
        recipients.update(get_invited_moderators())

    if len(recipients) == 0:
        return

    acceptable_types = const.RESPONSE_ACTIVITY_TYPES_FOR_INSTANT_NOTIFICATIONS
    try:
        update_activity = Activity.objects\
            .filter(activity_type__in=acceptable_types)\
            .get(id=activity_id)
    except Activity.DoesNotExist: # pylint: disable=no-member
        logger.error("Unable to fetch activity with id %s", post_id)
        return

    try:
        post = Post.objects.get(id=post_id)
    except Post.DoesNotExist: # pylint: disable=no-member
        logger.error("Unable to fetch post with id %s", post_id)
        return

    if not post.is_approved():
        return

    if logger.getEffectiveLevel() <= logging.DEBUG:
        log_id = uuid.uuid1()
        logger.debug('email-alert %s, logId=%s', post.get_absolute_url(), log_id)
    else:
        log_id = None

    for user in recipients:
        if user.is_blocked():
            continue

        activate_language(post.language_code)

        email = InstantEmailAlert({
            'to_user': user,
            'from_user': update_activity.user,
            'post': post,
            'update_activity': update_activity
        })
        try:
            email.send([user.email])
        except Exception as error:
            error_tpl = 'send_instant_notifications_about_activity_in_post: failed to send email to %s, error=%s, logId=%s'
            logger.error(error_tpl, user.email, error, log_id)
        else:
            logger.debug('success %s, logId=%s', user.email, log_id)
