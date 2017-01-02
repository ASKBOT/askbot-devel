from askbot.utils import decorators
from askbot.utils.html import sanitize_html
from askbot.utils.functions import decode_and_loads
from askbot import const
from askbot.conf import settings as askbot_settings
from askbot import models
from askbot import mail
from datetime import datetime
from django.http import Http404
from django.utils.translation import string_concat
from django.utils.translation import ungettext
from django.utils.translation import ugettext as _
from django.template.loader import get_template
from django.conf import settings as django_settings
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.utils.encoding import force_text
from django.shortcuts import render
from django.template import RequestContext
from django.views.decorators import csrf
from django.utils.encoding import force_text
from django.core import exceptions
import simplejson

#some utility functions
def get_object(memo):
    content_object = memo.activity.content_object
    if isinstance(content_object, models.PostRevision):
        return content_object.post
    else:
        return content_object


def get_revision_set(memo_set):
    """returns revisions given the memo_set"""
    rev_ids = set()
    for memo in memo_set:
        obj = memo.activity.content_object
        if isinstance(obj, models.PostRevision):
            rev_ids.add(obj.id)
    return models.PostRevision.objects.filter(id__in=rev_ids)


def expand_revision_set(revs):
    """returns lists of ips and users,
    seeded by given revisions"""
    #1) get post edits and ips from them
    ips, users = get_revision_ips_and_authors(revs)
    #2) get revs by those ips and users
    revs_filter = Q(ip_addr__in=ips) | Q(author__in=users)
    more_revs = models.PostRevision.objects.filter(revs_filter)

    #return ips and users when number of revisions loaded by
    #users and ip addresses stops growing
    diff_count = more_revs.count() - revs.count()
    if diff_count == 0:
        return revs
    elif diff_count > 0:
        return expand_revision_set(more_revs)
    else:
        raise ValueError('expanded revisions set smaller then the original')


def get_revision_ips_and_authors(revs):
    """returns sets of ips and users from revisions"""
    ips = set(revs.values_list('ip_addr', flat=True))
    user_ids = set(revs.values_list('author', flat=True))
    users = models.User.objects.filter(id__in=user_ids)
    return ips, users


def get_memos_by_revisions(revs, user):
    rev_ct = ContentType.objects.get_for_model(models.PostRevision)
    rev_ids = revs.values_list('id', flat=True)
    acts = models.Activity.objects.filter(
                            object_id__in=rev_ids,
                            content_type=rev_ct,
                            activity_type__in=get_activity_types()
                        )
    memos = models.ActivityAuditStatus.objects.filter(
                        activity__in=acts,
                        user=user
                    )
    return memos


def get_editors(memo_set):
    """returns editors corresponding to the memo set
    some memos won't yeild editors - if the related object
    is post and it has > 1 editor (in which case we don't know
    who was the editor that we want to block!!!
    this applies to flagged posts.

    todo: an inconvenience is that "offensive flags" are stored
    differently in the Activity vs. "new moderated posts" or "post edits"
    """
    editors = set()
    for memo in memo_set:
        obj = memo.activity.content_object
        if isinstance(obj, models.PostRevision):
            editors.add(obj.author)
        elif isinstance(obj, models.Post):
            rev_authors = set()
            for rev in obj.revisions.all():
                rev_authors.add(rev.author)

            #if we have > 1 author we skip, b/c don't know
            #which user we want to block
            if len(rev_authors) == 1:
                editors.update(rev_authors)
    return editors


def exclude_admins(users):
    filtered = set()
    for user in users:
        if not user.is_administrator_or_moderator():
            filtered.add(user)
    return filtered


def concat_messages(message1, message2):
    if message1:
        message = string_concat(message1, ', ')
        return string_concat(message, message2)
    else:
        return message2


def get_activity_types():
    """returns activity types for the memos"""
    activity_types = (const.TYPE_ACTIVITY_MARK_OFFENSIVE,)
    if askbot_settings.CONTENT_MODERATION_MODE in ('premoderation', 'audit'):
        activity_types += (
            const.TYPE_ACTIVITY_MODERATED_NEW_POST,
            const.TYPE_ACTIVITY_MODERATED_POST_EDIT
        )
    return activity_types


@login_required
def moderation_queue(request):
    """Lists moderation queue items"""
    if not request.user.is_administrator_or_moderator():
        raise Http404

    activity_types = get_activity_types()

    #2) load the activity notifications according to activity types
    #todo: insert pagination code here
    memo_set = request.user.get_notifications(activity_types)
    memo_set = memo_set.select_related(
                    'activity',
                    'activity__content_type',
                    'activity__object_id',
                    'activity__question__thread',
                    'activity__user'
                ).order_by(
                    '-activity__active_at'
                )[:const.USER_VIEW_DATA_SIZE]

    #3) "package" data for the output
    queue = list()
    for memo in memo_set:
        obj = memo.activity.content_object
        if obj is None:
            memo.activity.delete()
            continue#a temp plug due to bug in the comment deletion

        act = memo.activity
        if act.activity_type == const.TYPE_ACTIVITY_MARK_OFFENSIVE:
            #todo: two issues here - flags are stored differently
            #from activity of new posts and edits
            #second issue: on posts with many edits we don't know whom to block
            act_user = act.content_object.author
            act_message = _('post was flagged as offensive')
            act_type = 'flag'
            ip_addr = None
        else:
            act_user = act.user
            act_message = act.get_activity_type_display()
            act_type = 'edit'
            ip_addr = act.content_object.ip_addr

        item = {
            'id': memo.id,
            'timestamp': act.active_at,
            'user': act_user,
            'ip_addr': ip_addr,
            'is_new': memo.is_new(),
            'url': act.get_absolute_url(),
            'snippet': act.get_snippet(),
            'title': act.question.thread.title,
            'message_type': act_message,
            'memo_type': act_type,
            'question_id': act.question.id,
            'content': sanitize_html(obj.html or obj.text),
        }
        queue.append(item)

    queue.sort(lambda x,y: cmp(y['timestamp'], x['timestamp']))
    reject_reasons = models.PostFlagReason.objects.all().order_by('title')
    data = {
        'active_tab': 'users',
        'page_class': 'moderation-queue-page',
        'post_reject_reasons': reject_reasons,
        'messages' : queue,
    }
    template = 'moderation/queue.html'
    return render(request, template, data)


@csrf.csrf_protect
@decorators.post_only
@decorators.ajax_only
def moderate_post_edits(request):
    if request.user.is_anonymous():
        raise exceptions.PermissionDenied()
    if not request.user.is_administrator_or_moderator():
        raise exceptions.PermissionDenied()

    post_data = decode_and_loads(request.body)
    #{'action': 'decline-with-reason', 'items': ['posts'], 'reason': 1, 'edit_ids': [827]}

    memo_set = models.ActivityAuditStatus.objects.filter(id__in=post_data['edit_ids'])
    result = {
        'message': '',
        'memo_ids': set()
    }

    #if we are approving or declining users we need to expand the memo_set
    #to all of their edits of those users
    if post_data['action'] in ('block', 'approve') and 'users' in post_data['items']:
        editors = exclude_admins(get_editors(memo_set))
        items = models.Activity.objects.filter(
                                activity_type__in=const.MODERATED_EDIT_ACTIVITY_TYPES,
                                user__in=editors
                            )
        memo_filter = Q(user=request.user, activity__in=items)
        memo_set |= models.ActivityAuditStatus.objects.filter(memo_filter)

    memo_set.select_related('activity')

    if post_data['action'] == 'approve':
        num_posts = 0
        if 'posts' in post_data['items']:
            for memo in memo_set:
                if memo.activity.activity_type == const.TYPE_ACTIVITY_MARK_OFFENSIVE:
                    #unflag the post
                    content_object = memo.activity.content_object
                    request.user.flag_post(content_object, cancel_all=True, force=True)
                    num_posts += 1
                else:
                    revision = memo.activity.content_object
                    if isinstance(revision, models.PostRevision):
                        request.user.approve_post_revision(revision)
                        num_posts += 1

            if num_posts > 0:
                posts_message = ungettext('%d post approved', '%d posts approved', num_posts) % num_posts
                result['message'] = concat_messages(result['message'], posts_message)

        if 'users' in post_data['items']:
            editors = exclude_admins(get_editors(memo_set))
            assert(request.user not in editors)
            for editor in editors:
                editor.set_status('a')

            num_users = len(editors)
            if num_users:
                users_message = ungettext('%d user approved', '%d users approved', num_users) % num_users
                result['message'] = concat_messages(result['message'], users_message)

    elif post_data['action'] == 'decline-with-reason':
        #todo: bunch notifications - one per recipient
        num_posts = 0
        for memo in memo_set:
            post = get_object(memo)
            request.user.delete_post(post)
            reject_reason = models.PostFlagReason.objects.get(id=post_data['reason'])

            from askbot.mail.messages import RejectedPost
            email = RejectedPost({
                        'post': post.html,
                        'reject_reason': reject_reason.details.html
                    })
            email.send([post.author.email,])
            num_posts += 1

        #message to moderator
        if num_posts:
            posts_message = ungettext('%d post deleted', '%d posts deleted', num_posts) % num_posts
            result['message'] = concat_messages(result['message'], posts_message)

    elif post_data['action'] == 'block':

        num_users = 0
        num_posts = 0
        num_ips = 0

        moderate_ips = getattr(django_settings, 'ASKBOT_IP_MODERATION_ENABLED', False)
        # If we block by IPs we always block users and posts
        # so we use a "spider" algorithm to find posts, users and IPs to block.
        # once we find users, posts and IPs, we block all of them summarily.
        if moderate_ips and 'ips' in post_data['items']:
            assert('users' in post_data['items'])
            assert('posts' in post_data['items'])
            assert(len(post_data['items']) == 3)

            revs = get_revision_set(memo_set)
            revs = expand_revision_set(revs)
            ips, users = get_revision_ips_and_authors(revs)
            #important: evaluate the query here b/c some memos related to
            #comments will be lost when blocking users
            memo_set = set(get_memos_by_revisions(revs, request.user))

            #to make sure to not block the admin and
            #in case REMOTE_ADDR is a proxy server - not
            #block access to the site
            good_ips = set(getattr(django_settings, 'ASKBOT_WHITELISTED_IPS', ()))
            good_ips.add(request.META['REMOTE_ADDR'])
            ips = ips - good_ips

            #block IPs
            from stopforumspam.models import Cache
            already_blocked = Cache.objects.filter(ip__in=ips)
            already_blocked.update(permanent=True)
            already_blocked_ips = already_blocked.values_list('ip', flat=True)
            ips = ips - set(already_blocked_ips)
            for ip in ips:
                cache = Cache(ip=ip, permanent=True)
                cache.save()

            #block users and all their content
            users = exclude_admins(users)
            num_users = 0
            for user in users:
                if user.status != 'b':
                    user.set_status('b')
                    num_users += 1
                #delete all content by the user
                num_posts += request.user.delete_all_content_authored_by_user(user)

            num_ips = len(ips)

        elif 'users' in post_data['items']:
            memo_set = set(memo_set)#evaluate memo_set before deleting content
            editors = exclude_admins(get_editors(memo_set))
            assert(request.user not in editors)
            num_users = 0
            for editor in editors:
                #block user
                if editor.status != 'b':
                    editor.set_status('b')
                    num_users += 1
                #delete all content by the user
                num_posts += request.user.delete_all_content_authored_by_user(editor)

        if num_ips:
            ips_message = ungettext('%d ip blocked', '%d ips blocked', num_ips) % num_ips
            result['message'] = concat_messages(result['message'], ips_message)

        if num_users:
            users_message = ungettext('%d user blocked', '%d users blocked', num_users) % num_users
            result['message'] = concat_messages(result['message'], users_message)

        if num_posts:
            posts_message = ungettext('%d post deleted', '%d posts deleted', num_posts) % num_posts
            result['message'] = concat_messages(result['message'], posts_message)

    result['memo_ids'] = [memo.id for memo in memo_set]
    result['message'] = force_text(result['message'])

    #delete items from the moderation queue
    act_ids = [memo.activity_id for memo in memo_set]
    acts = models.Activity.objects.filter(id__in=act_ids)

    memos = models.ActivityAuditStatus.objects.filter(activity__id__in=act_ids)
    memos.delete()

    acts.delete()

    request.user.update_response_counts()
    result['memo_count'] = request.user.get_notifications(const.MODERATED_ACTIVITY_TYPES).count()
    return result
