"""
:synopsis: user-centric views for askbot

This module includes all views that are specific to a given user - his or her profile,
and other views showing profile-related information.

Also this module includes the view listing all forum users.
"""
import calendar
import collections
import functools
import datetime
import logging
import operator
import urllib

from django.db.models import Count
from django.db.models import Q
from django.conf import settings as django_settings
from django.contrib.auth.decorators import login_required
from django.core import exceptions as django_exceptions
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.http import HttpResponse, HttpResponseForbidden
from django.http import HttpResponseRedirect, Http404
from django.utils.translation import get_language
from django.utils.translation import string_concat
from django.utils.translation import ugettext as _
from django.utils.translation import ungettext
from django.utils import simplejson
from django.utils.html import strip_tags as strip_all_tags
from django.views.decorators import csrf

from askbot.utils.slug import slugify
from askbot.utils.html import sanitize_html
from askbot.mail import send_mail
from askbot.utils.http import get_request_info
from askbot.utils import decorators
from askbot.utils import functions
from askbot import forms
from askbot import const
from askbot.views import context as view_context
from askbot.conf import settings as askbot_settings
from askbot import models
from askbot import exceptions
from askbot.models.badges import award_badges_signal
from askbot.models.tag import format_personal_group_name
from askbot.search.state_manager import SearchState
from askbot.utils import url_utils
from askbot.utils.loading import load_module

def owner_or_moderator_required(f):
    @functools.wraps(f)
    def wrapped_func(request, profile_owner, context):
        if profile_owner == request.user:
            pass
        elif request.user.is_authenticated():
            if request.user.can_moderate_user(profile_owner):
                pass
            else:
                #redirect to the user profile homepage
                #as this one should be accessible to all
                return HttpResponseRedirect(request.path)
        else:
            next_url = request.path + '?' + urllib.urlencode(request.REQUEST)
            params = '?next=%s' % urllib.quote(next_url)
            return HttpResponseRedirect(url_utils.get_login_url() + params)
        return f(request, profile_owner, context)
    return wrapped_func

@decorators.ajax_only
def clear_new_notifications(request):
    """clears all new notifications for logged in user"""
    user = request.user
    if user.is_anonymous():
        raise django_exceptions.PermissionDenied

    activity_types = const.RESPONSE_ACTIVITY_TYPES_FOR_DISPLAY
    activity_types += (
        const.TYPE_ACTIVITY_MENTION,
    )
    post_data = simplejson.loads(request.raw_post_data)
    memo_set = models.ActivityAuditStatus.objects.filter(
        id__in=post_data['memo_ids'],
        activity__activity_type__in=activity_types,
        user=user,
    )
    memo_set.update(status = models.ActivityAuditStatus.STATUS_SEEN)
    user.update_response_counts()

@decorators.ajax_only
def delete_notifications(request):
    post_data = simplejson.loads(request.raw_post_data)
    memo_set = models.ActivityAuditStatus.objects.filter(
        id__in=post_data['memo_ids'],
        user=request.user
    )
    memo_set.delete()
    request.user.update_response_counts()

def show_users(request, by_group=False, group_id=None, group_slug=None):
    """Users view, including listing of users by group"""
    if askbot_settings.GROUPS_ENABLED and not by_group:
        default_group = models.Group.objects.get_global_group()
        group_slug = slugify(default_group.name)
        new_url = reverse('users_by_group',
                kwargs={'group_id': default_group.id,
                        'group_slug': group_slug})
        return HttpResponseRedirect(new_url)

    users = models.User.objects.exclude(
                                    status='b'
                                ).exclude(
                                    is_active=False
                                )
    group = None
    group_email_moderation_enabled = False
    user_acceptance_level = 'closed'
    user_membership_level = 'none'
    if by_group == True:
        if askbot_settings.GROUPS_ENABLED == False:
            raise Http404
        if group_id:
            if all((group_id, group_slug)) == False:
                return HttpResponseRedirect('groups')
            else:
                try:
                    group = models.Group.objects.get(id = group_id)
                    group_email_moderation_enabled = (
                        askbot_settings.GROUP_EMAIL_ADDRESSES_ENABLED \
                        and askbot_settings.CONTENT_MODERATION_MODE == 'premoderation'
                    )
                    user_acceptance_level = group.get_openness_level_for_user(
                                                                    request.user
                                                                )
                except models.Group.DoesNotExist:
                    raise Http404
                if group_slug == slugify(group.name):
                    #filter users by full group memberships
                    #todo: refactor as Group.get_full_members()
                    full_level = models.GroupMembership.FULL
                    memberships = models.GroupMembership.objects.filter(
                                                    group=group, level=full_level
                                                )
                    user_ids = memberships.values_list('user__id', flat=True)
                    users = users.filter(id__in=user_ids)
                    if request.user.is_authenticated():
                        membership = request.user.get_group_membership(group)
                        if membership:
                            user_membership_level = membership.get_level_display()

                else:
                    group_page_url = reverse(
                                        'users_by_group',
                                        kwargs = {
                                            'group_id': group.id,
                                            'group_slug': slugify(group.name)
                                        }
                                    )
                    return HttpResponseRedirect(group_page_url)

    is_paginated = True

    sortby = request.GET.get('sort', 'reputation')
    if askbot_settings.KARMA_MODE == 'private' and sortby == 'reputation':
        sortby = 'newest'

    page = forms.PageField().clean(request.GET.get('page'))

    search_query = request.GET.get('query',  '')
    if search_query == '':
        if sortby == 'newest':
            order_by_parameter = '-date_joined'
        elif sortby == 'last':
            order_by_parameter = 'date_joined'
        elif sortby == 'user':
            order_by_parameter = 'username'
        else:
            # default
            order_by_parameter = '-reputation'

        objects_list = Paginator(
                            users.order_by(order_by_parameter),
                            const.USERS_PAGE_SIZE
                        )
        base_url = request.path + '?sort=%s&' % sortby
    else:
        sortby = 'reputation'
        matching_users = models.get_users_by_text_query(search_query, users)
        objects_list = Paginator(
                            matching_users.order_by('-reputation'),
                            const.USERS_PAGE_SIZE
                        )
        base_url = request.path + '?name=%s&sort=%s&' % (search_query, sortby)

    try:
        users_page = objects_list.page(page)
    except (EmptyPage, InvalidPage):
        users_page = objects_list.page(objects_list.num_pages)

    paginator_data = {
        'is_paginated' : is_paginated,
        'pages': objects_list.num_pages,
        'current_page_number': page,
        'page_object': users_page,
        'base_url' : base_url
    }
    paginator_context = functions.setup_paginator(paginator_data) #

    #todo: move to contexts
    #extra context for the groups
    if askbot_settings.GROUPS_ENABLED:
        #todo: cleanup this branched code after groups are migrated to auth_group
        user_groups = models.Group.objects.exclude_personal()
        if len(user_groups) <= 1:
            assert(user_groups[0].name == askbot_settings.GLOBAL_GROUP_NAME)
            user_groups = None
        group_openness_choices = models.Group().get_openness_choices()
    else:
        user_groups = None
        group_openness_choices = None

    data = {
        'active_tab': 'users',
        'group': group,
        'group_email_moderation_enabled': group_email_moderation_enabled,
        'group_openness_choices': group_openness_choices,
        'page_class': 'users-page',
        'paginator_context' : paginator_context,
        'search_query' : search_query,
        'tab_id' : sortby,
        'user_acceptance_level': user_acceptance_level,
        'user_count': users.count(),
        'user_groups': user_groups,
        'user_membership_level': user_membership_level,
        'users' : users_page,
    }

    return render(request, 'users.html', data)

@csrf.csrf_protect
def user_moderate(request, subject, context):
    """user subview for moderation
    """
    moderator = request.user

    if moderator.is_authenticated() and not moderator.can_moderate_user(subject):
        raise Http404

    user_rep_changed = False
    user_status_changed = False
    user_status_changed_message = _('User status changed')
    message_sent = False
    email_error_message = None

    user_rep_form = forms.ChangeUserReputationForm()
    send_message_form = forms.SendMessageForm()
    if request.method == 'POST':
        if 'change_status' in request.POST or 'hard_block' in request.POST:
            user_status_form = forms.ChangeUserStatusForm(
                                                    request.POST,
                                                    moderator = moderator,
                                                    subject = subject
                                                )
            if user_status_form.is_valid():
                subject.set_status( user_status_form.cleaned_data['user_status'] )
                if user_status_form.cleaned_data['delete_content'] == True:
                    num_deleted = request.user.delete_all_content_authored_by_user(subject)
                    if num_deleted:
                        num_deleted_message = ungettext('%d post deleted', '%d posts deleted', num_deleted) % num_deleted
                        user_status_changed_message = string_concat(user_status_changed_message, ', ', num_deleted_message)
            user_status_changed = True
        elif 'send_message' in request.POST:
            send_message_form = forms.SendMessageForm(request.POST)
            if send_message_form.is_valid():
                subject_line = send_message_form.cleaned_data['subject_line']
                body_text = send_message_form.cleaned_data['body_text']

                try:
                    send_mail(
                            subject_line = subject_line,
                            body_text = body_text,
                            recipient_list = [subject.email],
                            headers={'Reply-to':moderator.email},
                            raise_on_failure = True
                        )
                    message_sent = True
                except exceptions.EmailNotSent, e:
                    email_error_message = unicode(e)
                send_message_form = forms.SendMessageForm()
        else:
            reputation_change_type = None
            if 'subtract_reputation' in request.POST:
                rep_change_type = 'subtract'
            elif 'add_reputation' in request.POST:
                rep_change_type = 'add'
            else:
                raise Http404

            user_rep_form = forms.ChangeUserReputationForm(request.POST)
            if user_rep_form.is_valid():
                rep_delta = user_rep_form.cleaned_data['user_reputation_delta']
                comment = user_rep_form.cleaned_data['comment']

                if rep_change_type == 'subtract':
                    rep_delta = -1 * rep_delta

                moderator.moderate_user_reputation(
                                    user = subject,
                                    reputation_change = rep_delta,
                                    comment = comment,
                                    timestamp = datetime.datetime.now(),
                                )
                #reset form to preclude accidentally repeating submission
                user_rep_form = forms.ChangeUserReputationForm()
                user_rep_changed = True

    #need to re-initialize the form even if it was posted, because
    #initial values will most likely be different from the previous
    user_status_form = forms.ChangeUserStatusForm(
                                        moderator = moderator,
                                        subject = subject
                                    )
    data = {
        'active_tab': 'users',
        'page_class': 'user-profile-page',
        'tab_name': 'moderation',
        'page_title': _('moderate user'),
        'change_user_status_form': user_status_form,
        'change_user_reputation_form': user_rep_form,
        'send_message_form': send_message_form,
        'message_sent': message_sent,
        'email_error_message': email_error_message,
        'user_rep_changed': user_rep_changed,
        'user_status_changed': user_status_changed,
        'user_status_changed_message': user_status_changed_message
    }
    context.update(data)
    return render(request, 'user_profile/user_moderate.html', context)

#non-view function
def set_new_email(user, new_email, nomessage=False):
    if new_email != user.email:
        user.email = new_email
        user.email_isvalid = False
        user.save()
        #if askbot_settings.EMAIL_VALIDATION == True:
        #    send_new_email_key(user,nomessage=nomessage)


def need_to_invalidate_post_caches(user, form):
    """a utility function for the edit user profile view"""
    new_country = (form.cleaned_data.get('country') != user.country)
    new_show_country = (form.cleaned_data.get('show_country') != user.show_country)
    new_username = (form.cleaned_data.get('username') != user.username)
    return (new_country or new_show_country or new_username)


@login_required
@csrf.csrf_protect
def edit_user(request, id):
    """View that allows to edit user profile.
    This view is accessible to profile owners or site administrators
    """
    user = get_object_or_404(models.User, id=id)
    if not(request.user.pk == user.pk or request.user.is_superuser):
        raise Http404
    if request.method == "POST":
        form = forms.EditUserForm(user, request.POST)
        if form.is_valid():
            if 'email' in form.cleaned_data and askbot_settings.EDITABLE_EMAIL:
                new_email = sanitize_html(form.cleaned_data['email'])
                set_new_email(user, new_email)

            prev_username = user.username
            if askbot_settings.EDITABLE_SCREEN_NAME:
                new_username = strip_all_tags(form.cleaned_data['username'])
                if user.username != new_username:
                    group = user.get_personal_group()
                    user.username = new_username
                    group.name = format_personal_group_name(user)
                    group.save()

            #Maybe we need to clear post caches, b/c
            #author info may need to be updated on posts and thread summaries
            if need_to_invalidate_post_caches(user, form):
                #get threads where users participated
                thread_ids = models.Post.objects.filter(
                                    Q(author=user) | Q(last_edited_by=user)
                                ).values_list(
                                    'thread__id', flat=True
                                ).distinct()
                threads = models.Thread.objects.filter(id__in=thread_ids)
                for thread in threads:
                    #for each thread invalidate cache keys for posts, etc
                    thread.clear_cached_data()

            user.real_name = strip_all_tags(form.cleaned_data['realname'])
            user.website = sanitize_html(form.cleaned_data['website'])
            user.location = sanitize_html(form.cleaned_data['city'])
            user.date_of_birth = form.cleaned_data.get('birthday', None)
            user.about = sanitize_html(form.cleaned_data['about'])
            user.country = form.cleaned_data['country']
            user.show_country = form.cleaned_data['show_country']
            user.show_marked_tags = form.cleaned_data['show_marked_tags']
            user.save()
            # send user updated signal if full fields have been updated
            award_badges_signal.send(None,
                            event = 'update_user_profile',
                            actor = user,
                            context_object = user
                        )
            return HttpResponseRedirect(user.get_profile_url())
    else:
        form = forms.EditUserForm(user)

    data = {
        'active_tab': 'users',
        'page_class': 'user-profile-edit-page',
        'form' : form,
        'marked_tags_setting': askbot_settings.MARKED_TAGS_ARE_PUBLIC_WHEN,
        'support_custom_avatars': ('avatar' in django_settings.INSTALLED_APPS),
        'view_user': user,
    }
    return render(request, 'user_profile/user_edit.html', data)

def user_stats(request, user, context):
    question_filter = {}
    if request.user != user:
        question_filter['is_anonymous'] = False

    if askbot_settings.CONTENT_MODERATION_MODE == 'premoderation':
        question_filter['approved'] = True

    #
    # Questions
    #
    questions_qs = user.posts.get_questions(
                    user=request.user
                ).filter(
                    **question_filter
                ).order_by(
                    '-points', '-thread__last_activity_at'
                ).select_related(
                    'thread', 'thread__last_activity_by'
                )

    q_paginator = Paginator(questions_qs, const.USER_POSTS_PAGE_SIZE)
    questions = q_paginator.page(1).object_list
    question_count = q_paginator.count

    q_paginator_context = functions.setup_paginator({
                    'is_paginated' : (question_count > const.USER_POSTS_PAGE_SIZE),
                    'pages': q_paginator.num_pages,
                    'current_page_number': 1,
                    'page_object': q_paginator.page(1),
                    'base_url' : '?' #this paginator will be ajax
                })
    #
    # Top answers
    #
    a_paginator = user.get_top_answers_paginator(request.user)
    top_answers = a_paginator.page(1).object_list
    top_answer_count = a_paginator.count

    a_paginator_context = functions.setup_paginator({
                    'is_paginated' : (top_answer_count > const.USER_POSTS_PAGE_SIZE),
                    'pages': a_paginator.num_pages,
                    'current_page_number': 1,
                    'page_object': a_paginator.page(1),
                    'base_url' : '?' #this paginator will be ajax
                })
    #
    # Votes
    #
    up_votes = models.Vote.objects.get_up_vote_count_from_user(user)
    down_votes = models.Vote.objects.get_down_vote_count_from_user(user)
    votes_today = models.Vote.objects.get_votes_count_today_from_user(user)
    votes_total = askbot_settings.MAX_VOTES_PER_USER_PER_DAY

    #
    # Tags
    #
    # INFO: There's bug in Django that makes the following query kind of broken (GROUP BY clause is problematic):
    #       http://stackoverflow.com/questions/7973461/django-aggregation-does-excessive-group-by-clauses
    #       Fortunately it looks like it returns correct results for the test data
    user_tags = models.Tag.objects.filter(
                                    threads__posts__author=user,
                                    language_code=get_language()
                                ).distinct().\
                    annotate(user_tag_usage_count=Count('threads')).\
                    order_by('-user_tag_usage_count')[:const.USER_VIEW_DATA_SIZE]
    user_tags = list(user_tags) # evaluate

    when = askbot_settings.MARKED_TAGS_ARE_PUBLIC_WHEN
    if when == 'always' or \
        (when == 'when-user-wants' and user.show_marked_tags == True):
        #refactor into: user.get_marked_tag_names('good'/'bad'/'subscribed')
        interesting_tag_names = user.get_marked_tag_names('good')
        ignored_tag_names = user.get_marked_tag_names('bad')
        subscribed_tag_names = user.get_marked_tag_names('subscribed')
    else:
        interesting_tag_names = None
        ignored_tag_names = None
        subscribed_tag_names = None

#    tags = models.Post.objects.filter(author=user).values('id', 'thread', 'thread__tags')
#    post_ids = set()
#    thread_ids = set()
#    tag_ids = set()
#    for t in tags:
#        post_ids.add(t['id'])
#        thread_ids.add(t['thread'])
#        tag_ids.add(t['thread__tags'])
#        if t['thread__tags'] == 11:
#            print t['thread'], t['id']
#    import ipdb; ipdb.set_trace()

    #
    # Badges/Awards (TODO: refactor into Managers/QuerySets when a pattern emerges; Simplify when we get rid of Question&Answer models)
    #
    post_type = ContentType.objects.get_for_model(models.Post)

    user_awards = models.Award.objects.filter(user=user).select_related('badge')

    awarded_post_ids = []
    for award in user_awards:
        if award.content_type_id == post_type.id:
            awarded_post_ids.append(award.object_id)

    awarded_posts = models.Post.objects.filter(id__in=awarded_post_ids)\
                    .select_related('thread') # select related to avoid additional queries in Post.get_absolute_url()

    awarded_posts_map = {}
    for post in awarded_posts:
        awarded_posts_map[post.id] = post

    badges_dict = collections.defaultdict(list)

    for award in user_awards:
        if award.badge.is_enabled() == False:
            continue

        # Fetch content object
        if award.content_type_id == post_type.id:
            #here we go around a possibility of awards
            #losing the content objects when the content
            #objects are deleted for some reason
            awarded_post = awarded_posts_map.get(award.object_id, None)
            if awarded_post is not None:
                #protect from awards that are associated with deleted posts
                award.content_object = awarded_post
                award.content_object_is_post = True
            else:
                award.content_object_is_post = False
        else:
            award.content_object_is_post = False

        # "Assign" to its Badge
        badges_dict[award.badge].append(award)

    badges = badges_dict.items()
    badges.sort(key=operator.itemgetter(1), reverse=True)

    user_groups = models.Group.objects.get_for_user(user = user)
    user_groups = user_groups.exclude_personal()
    global_group = models.Group.objects.get_global_group()
    user_groups = user_groups.exclude(name=global_group.name)

    if request.user.pk == user.pk:
        groups_membership_info = user.get_groups_membership_info(user_groups)
    else:
        groups_membership_info = collections.defaultdict()

    data = {
        'active_tab':'users',
        'page_class': 'user-profile-page',
        'support_custom_avatars': ('avatar' in django_settings.INSTALLED_APPS),
        'tab_name' : 'stats',
        'page_title' : _('user profile overview'),
        'questions' : questions,
        'question_count': question_count,
        'q_paginator_context': q_paginator_context,

        'top_answers': top_answers,
        'top_answer_count': top_answer_count,
        'a_paginator_context': a_paginator_context,
        'page_size': const.USER_POSTS_PAGE_SIZE,

        'up_votes' : up_votes,
        'down_votes' : down_votes,
        'total_votes': up_votes + down_votes,
        'votes_today_left': votes_total - votes_today,
        'votes_total_per_day': votes_total,

        'user_tags' : user_tags,
        'user_groups': user_groups,
        'groups_membership_info': groups_membership_info,
        'interesting_tag_names': interesting_tag_names,
        'ignored_tag_names': ignored_tag_names,
        'subscribed_tag_names': subscribed_tag_names,
        'badges': badges,
        'total_badges' : len(badges),
    }
    context.update(data)

    extra_context = view_context.get_extra(
                                'ASKBOT_USER_PROFILE_PAGE_EXTRA_CONTEXT',
                                request,
                                context
                            )
    context.update(extra_context)

    return render(request, 'user_profile/user_stats.html', context)

def user_recent(request, user, context):

    def get_type_name(type_id):
        for item in const.TYPE_ACTIVITY:
            if type_id in item:
                return item[1]

    class Event(object):
        is_badge = False
        def __init__(self, time, type, title, summary, url):
            self.time = time
            self.type = get_type_name(type)
            self.type_id = type
            self.title = title
            self.summary = summary
            slug_title = slugify(title)
            self.title_link = url

    class AwardEvent(object):
        is_badge = True
        def __init__(self, time, type, content_object, badge):
            self.time = time
            self.type = get_type_name(type)
            self.content_object = content_object
            self.badge = badge

    # TODO: Don't process all activities here for the user, only a subset ([:const.USER_VIEW_DATA_SIZE])
    activity_types = (
        const.TYPE_ACTIVITY_ASK_QUESTION,
        const.TYPE_ACTIVITY_ANSWER,
        const.TYPE_ACTIVITY_COMMENT_QUESTION,
        const.TYPE_ACTIVITY_COMMENT_ANSWER,
        const.TYPE_ACTIVITY_UPDATE_QUESTION,
        const.TYPE_ACTIVITY_UPDATE_ANSWER,
        const.TYPE_ACTIVITY_MARK_ANSWER,
        const.TYPE_ACTIVITY_PRIZE
    )

    #1) get source of information about activities
    activity_objects = models.Activity.objects.filter(
                                        user=user,
                                        activity_type__in=activity_types
                                    ).order_by(
                                        '-active_at'
                                    )[:const.USER_VIEW_DATA_SIZE]

    #2) load content objects ("c.objects) for each activity
    # the return value is dictionary where activity id's are keys
    content_objects_by_activity = activity_objects.fetch_content_objects_dict()


    #a list of digest objects, suitable for display
    #the number of activities to show is not guaranteed to be
    #const.USER_VIEW_DATA_TYPE, because we don't show activity
    #for deleted content
    activities = []
    for activity in activity_objects:
        content = content_objects_by_activity.get(activity.id)

        if content is None:
            continue

        if activity.activity_type == const.TYPE_ACTIVITY_PRIZE:
            event = AwardEvent(
                time=content.awarded_at,
                type=activity.activity_type,
                content_object=content.content_object,
                badge=content.badge,
            )
        else:
            event = Event(
                time=activity.active_at,
                type=activity.activity_type,
                title=content.thread.title,
                summary=content.summary,
                url=content.get_absolute_url()
            )

        activities.append(event)

    activities.sort(key=operator.attrgetter('time'), reverse=True)

    data = {
        'active_tab': 'users',
        'page_class': 'user-profile-page',
        'tab_name' : 'recent',
        'page_title' : _('profile - recent activity'),
        'activities' : activities
    }
    context.update(data)
    return render(request, 'user_profile/user_recent.html', context)

#not a view - no direct url route here, called by `user_responses`
@csrf.csrf_protect
def show_group_join_requests(request, user, context):
    """show group join requests to admins who belong to the group"""
    if request.user.is_administrator_or_moderator() is False:
        raise Http404

    #get group to which user belongs
    groups = request.user.get_groups()
    #construct a dictionary group id --> group object
    #to avoid loading group via activity content object
    groups_dict = dict([(group.id, group) for group in groups])

    #get join requests for those groups
    group_content_type = ContentType.objects.get_for_model(models.Group)
    join_requests = models.Activity.objects.filter(
                        activity_type=const.TYPE_ACTIVITY_ASK_TO_JOIN_GROUP,
                        content_type=group_content_type,
                        object_id__in=groups_dict.keys()
                    ).order_by('-active_at')
    data = {
        'active_tab':'users',
        'inbox_section': 'group-join-requests',
        'page_class': 'user-profile-page',
        'tab_name' : 'join_requests',
        'page_title' : _('profile - moderation'),
        'groups_dict': groups_dict,
        'join_requests': join_requests
    }
    context.update(data)
    return render(request, 'user_inbox/group_join_requests.html', context)


@owner_or_moderator_required
def user_responses(request, user, context):
    """
    We list answers for question, comments, and
    answer accepted by others for this user.
    as well as mentions of the user

    user - the profile owner

    the view has two sub-views - "forum" - i.e. responses
    and "flags" - moderation items for mods only
    """

    #0) temporary, till urls are fixed: update context
    #   to contain response counts for all sub-sections
    context.update(view_context.get_for_inbox(request.user))

    #1) select activity types according to section
    section = request.GET.get('section', 'forum')

    if section == 'forum':
        activity_types = const.RESPONSE_ACTIVITY_TYPES_FOR_DISPLAY
        activity_types += (const.TYPE_ACTIVITY_MENTION,)
    elif section == 'join_requests':
        return show_group_join_requests(request, user, context)
    elif section == 'messages':
        if request.user != user:
            if askbot_settings.ADMIN_INBOX_ACCESS_ENABLED == False:
                raise Http404
            elif not(request.user.is_moderator() or request.user.is_administrator()):
                raise Http404

        from group_messaging.views import SendersList, ThreadsList
        context.update(SendersList().get_context(request))
        context.update(ThreadsList().get_context(request, user))
        data = {
            'inbox_threads_count': context['threads_count'],#a hackfor the inbox count
            'active_tab':'users',
            'page_class': 'user-profile-page',
            'tab_name' : 'inbox',
            'inbox_section': section,
            'page_title' : _('profile - messages')
        }
        context.update(data)
        if 'thread_id' in request.GET:
            from group_messaging.models import Message
            from group_messaging.views import ThreadDetails
            try:
                thread_id = request.GET['thread_id']
                context.update(ThreadDetails().get_context(request, thread_id))
                context['group_messaging_template_name'] = \
                    'group_messaging/home_thread_details.html'
            except Message.DoesNotExist:
                raise Http404
        else:
            context['group_messaging_template_name'] = 'group_messaging/home.html'
            #here we take shortcut, because we don't care about
            #all the extra context loaded below
        return render(request, 'user_inbox/messages.html', context)
    else:
        raise Http404

    #2) load the activity notifications according to activity types
    #todo: insert pagination code here
    memo_set = request.user.get_notifications(activity_types)
    memo_set = memo_set.select_related(
                    'activity',
                    'activity__content_type',
                    'activity__question__thread',
                    'activity__user',
                    'activity__user__gravatar',
                ).order_by(
                    '-activity__active_at'
                )[:const.USER_VIEW_DATA_SIZE]

    #3) "package" data for the output
    response_list = list()
    for memo in memo_set:
        obj = memo.activity.content_object
        if obj is None:
            memo.activity.delete()
            continue#a temp plug due to bug in the comment deletion

        act = memo.activity
        act_user = act.user
        act_message = act.get_activity_type_display()
        act_type = 'edit'

        response = {
            'id': memo.id,
            'timestamp': act.active_at,
            'user': act_user,
            'is_new': memo.is_new(),
            'url': act.get_absolute_url(),
            'snippet': act.get_snippet(),
            'title': act.question.thread.title,
            'message_type': act_message,
            'memo_type': act_type,
            'question_id': act.question.id,
            'followup_messages': list(),
            'content': obj.html or obj.text,
        }
        response_list.append(response)

    #4) sort by response id
    response_list.sort(lambda x,y: cmp(y['question_id'], x['question_id']))

    #5) group responses by thread (response_id is really the question post id)
    last_question_id = None #flag to know if the question id is different
    filtered_message_list = list()
    for message in response_list:
        #todo: group responses by the user as well
        if message['question_id'] == last_question_id:
            original_message = dict.copy(filtered_message_list[-1])
            original_message['followup_messages'].append(message)
            filtered_message_list[-1] = original_message
        else:
            filtered_message_list.append(message)
            last_question_id = message['question_id']

    #6) sort responses by time
    filtered_message_list.sort(lambda x,y: cmp(y['timestamp'], x['timestamp']))

    reject_reasons = models.PostFlagReason.objects.all().order_by('title')
    data = {
        'active_tab':'users',
        'page_class': 'user-profile-page',
        'tab_name' : 'inbox',
        'inbox_section': section,
        'page_title' : _('profile - responses'),
        'post_reject_reasons': reject_reasons,
        'messages' : filtered_message_list,
    }
    context.update(data)
    template = 'user_inbox/responses.html'
    return render(request, template, context)

def user_network(request, user, context):
    if 'followit' not in django_settings.INSTALLED_APPS:
        raise Http404
    data = {
        'followed_users': user.get_followed_users(),
        'followers': user.get_followers(),
        'page_title' : _('profile - network'),
        'tab_name': 'network',
    }
    context.update(data)
    return render(request, 'user_profile/user_network.html', context)

@owner_or_moderator_required
def user_votes(request, user, context):
    all_votes = list(models.Vote.objects.filter(user=user))
    votes = []
    for vote in all_votes:
        post = vote.voted_post
        if post.is_question():
            vote.title = post.thread.title
            vote.question_id = post.id
            vote.answer_id = 0
            votes.append(vote)
        elif post.is_answer():
            vote.title = post.thread.title
            vote.question_id = post.thread._question_post().id
            vote.answer_id = post.id
            votes.append(vote)

    votes.sort(key=operator.attrgetter('id'), reverse=True)

    data = {
        'active_tab':'users',
        'page_class': 'user-profile-page',
        'tab_name' : 'votes',
        'page_title' : _('profile - votes'),
        'votes' : votes[:const.USER_VIEW_DATA_SIZE]
    }
    context.update(data)
    return render(request, 'user_profile/user_votes.html', context)


def user_reputation(request, user, context):
    reputes = models.Repute.objects.filter(user=user).select_related('question', 'question__thread', 'user').order_by('-reputed_at')

    # prepare data for the graph - last values go in first
    rep_list = ['[%s,%s]' % (calendar.timegm(datetime.datetime.now().timetuple()) * 1000, user.reputation)]
    for rep in reputes:
        rep_list.append('[%s,%s]' % (calendar.timegm(rep.reputed_at.timetuple()) * 1000, rep.reputation))
    reps = ','.join(rep_list)
    reps = '[%s]' % reps

    data = {
        'active_tab':'users',
        'page_class': 'user-profile-page',
        'tab_name': 'reputation',
        'page_title': _("Profile - User's Karma"),
        'reputation': reputes,
        'reps': reps
    }
    context.update(data)
    return render(request, 'user_profile/user_reputation.html', context)


def user_favorites(request, user, context):
    favorite_threads = user.user_favorite_questions.values_list('thread', flat=True)
    questions_qs = models.Post.objects.filter(
                                post_type='question',
                                thread__in=favorite_threads
                            ).select_related(
                                'thread', 'thread__last_activity_by'
                            ).order_by(
                                '-points', '-thread__last_activity_at'
                            )[:const.USER_VIEW_DATA_SIZE]

    q_paginator = Paginator(questions_qs, const.USER_POSTS_PAGE_SIZE)

    page = forms.PageField().clean(request.GET.get('page'))
    questions = q_paginator.page(page).object_list
    question_count = q_paginator.count

    q_paginator_context = functions.setup_paginator({
                    'is_paginated' : (question_count > const.USER_POSTS_PAGE_SIZE),
                    'pages': q_paginator.num_pages,
                    'current_page_number': page,
                    'page_object': q_paginator.page(page),
                    'base_url' : request.path + '?sort=favorites&' #this paginator will be ajax
                })

    data = {
        'active_tab':'users',
        'page_class': 'user-profile-page',
        'tab_name' : 'favorites',
        'page_title' : _('profile - favorites'),
        'questions' : questions,
        'q_paginator_context': q_paginator_context,
        'question_count': question_count,
        'page_size': const.USER_POSTS_PAGE_SIZE
    }
    context.update(data)
    return render(request, 'user_profile/user_favorites.html', context)


@csrf.csrf_protect
@decorators.ajax_only
@decorators.post_only
def user_set_primary_language(request):
    if request.user.is_anonymous():
        raise django_exceptions.PermissionDenied

    form = forms.LanguageForm(request.POST)
    if form.is_valid():
        request.user.set_primary_language(form.cleaned_data['language'])
        request.user.save()


@csrf.csrf_protect
def user_select_languages(request, id=None, slug=None):
    if request.method != 'POST':
        raise django_exceptions.PermissionDenied

    user = get_object_or_404(models.User, id=id)
    if not(request.user.id == user.id or request.user.is_administrator()):
        raise django_exceptions.PermissionDenied

    form = forms.LanguagePrefsForm(request.POST)
    if form.is_valid():
        user.set_languages(form.cleaned_data['languages'])
        user.set_primary_language(form.cleaned_data['primary_language'])
        user.save()

    redirect_url = reverse(
        'user_subscriptions',
        kwargs={'id': user.id, 'slug': slugify(user.username)}
    )
    return HttpResponseRedirect(redirect_url)


@owner_or_moderator_required
@csrf.csrf_protect
def user_email_subscriptions(request, user, context):

    logging.debug(get_request_info(request))
    if request.method == 'POST':
        email_feeds_form = forms.EditUserEmailFeedsForm(request.POST)
        tag_filter_form = forms.TagFilterSelectionForm(request.POST, instance=user)
        if email_feeds_form.is_valid() and tag_filter_form.is_valid():

            action_status = None
            tag_filter_saved = tag_filter_form.save()
            if tag_filter_saved:
                action_status = _('changes saved')
            if 'save' in request.POST:
                feeds_saved = email_feeds_form.save(user)
                if feeds_saved:
                    action_status = _('changes saved')
            elif 'stop_email' in request.POST:
                email_stopped = email_feeds_form.reset().save(user)
                initial_values = forms.EditUserEmailFeedsForm.NO_EMAIL_INITIAL
                email_feeds_form = forms.EditUserEmailFeedsForm(initial=initial_values)
                if email_stopped:
                    action_status = _('email updates canceled')
    else:
        #user may have been created by some app that does not know
        #about the email subscriptions, in that case the call below
        #will add any subscription settings that are missing
        #using the default frequencies
        user.add_missing_askbot_subscriptions()

        #initialize the form
        email_feeds_form = forms.EditUserEmailFeedsForm()
        email_feeds_form.set_initial_values(user)
        tag_filter_form = forms.TagFilterSelectionForm(instance=user)
        action_status = None

    data = {
        'active_tab': 'users',
        'subscribed_tag_names': user.get_marked_tag_names('subscribed'),
        'page_class': 'user-profile-page',
        'tab_name': 'email_subscriptions',
        'page_title': _('profile - email subscriptions'),
        'email_feeds_form': email_feeds_form,
        'tag_filter_selection_form': tag_filter_form,
        'action_status': action_status,
        'user_languages': user.languages.split()
    }
    context.update(data)
    #todo: really need only if subscribed tags are enabled
    context.update(view_context.get_for_tag_editor())
    return render(
        request,
        'user_profile/user_email_subscriptions.html',
        context
    )

@csrf.csrf_protect
def user_custom_tab(request, user, context):
    """works only if `ASKBOT_CUSTOM_USER_PROFILE_TAB`
    setting in the ``settings.py`` is properly configured"""
    tab_settings = django_settings.ASKBOT_CUSTOM_USER_PROFILE_TAB
    module_path = tab_settings['CONTENT_GENERATOR']
    content_generator = load_module(module_path)

    page_title = _('profile - %(section)s') % \
        {'section': tab_settings['NAME']}

    context.update({
        'custom_tab_content': content_generator(request, user),
        'tab_name': tab_settings['SLUG'],
        'page_title': page_title
    })
    return render(request, 'user_profile/custom_tab.html', context)

USER_VIEW_CALL_TABLE = {
    'stats': user_stats,
    'recent': user_recent,
    'inbox': user_responses,
    'network': user_network,
    'reputation': user_reputation,
    'favorites': user_favorites,
    'votes': user_votes,
    'email_subscriptions': user_email_subscriptions,
    'moderation': user_moderate,
}

CUSTOM_TAB = getattr(django_settings, 'ASKBOT_CUSTOM_USER_PROFILE_TAB', None)
if CUSTOM_TAB:
    CUSTOM_SLUG = CUSTOM_TAB['SLUG']
    USER_VIEW_CALL_TABLE[CUSTOM_SLUG] = user_custom_tab

#todo: rename this function - variable named user is everywhere
def user(request, id, slug=None, tab_name=None):
    """Main user view function that works as a switchboard

    id - id of the profile owner

    todo: decide what to do with slug - it is not used
    in the code in any way
    """
    profile_owner = get_object_or_404(models.User, id = id)

    if slugify(profile_owner.username) != slug:
        view_url = profile_owner.get_profile_url() + '?' \
                                + urllib.urlencode(request.REQUEST)
        return HttpResponseRedirect(view_url)

    if not tab_name:
        tab_name = request.GET.get('sort', 'stats')

    if askbot_settings.KARMA_MODE == 'public':
        can_show_karma = True
    elif askbot_settings.KARMA_MODE == 'hidden':
        can_show_karma = False
    else:
        if request.user.is_anonymous():
            can_show_karma = False
        elif request.user.is_administrator_or_moderator():
            can_show_karma = True
        elif request.user.pk == profile_owner.pk:
            can_show_karma = True
        else:
            can_show_karma = False

    if can_show_karma == False and tab_name == 'reputation':
        raise Http404

    user_view_func = USER_VIEW_CALL_TABLE.get(tab_name, user_stats)

    search_state = SearchState(
        scope=None,
        sort=None,
        query=None,
        tags=None,
        author=None,
        page=None,
        page_size=const.USER_POSTS_PAGE_SIZE,
        user_logged_in=profile_owner.is_authenticated(),
    )

    context = {
        'view_user': profile_owner,
        'can_show_karma': can_show_karma,
        'search_state': search_state,
        'user_follow_feature_on': ('followit' in django_settings.INSTALLED_APPS),
    }
    if CUSTOM_TAB:
        context['custom_tab_name'] = CUSTOM_TAB['NAME']
        context['custom_tab_slug'] = CUSTOM_TAB['SLUG']
    return user_view_func(request, profile_owner, context)

def groups(request, id = None, slug = None):
    """output groups page
    """
    if askbot_settings.GROUPS_ENABLED == False:
        raise Http404

    #6 lines of input cleaning code
    if request.user.is_authenticated():
        scope = request.GET.get('sort', 'all-groups')
        if scope not in ('all-groups', 'my-groups'):
            scope = 'all-groups'
    else:
        scope = 'all-groups'

    if scope == 'all-groups':
        groups = models.Group.objects.all()
    else:
        groups = models.Group.objects.get_for_user(
                                        user=request.user
                                    )

    groups = groups.exclude_personal()
    groups = groups.annotate(users_count=Count('user'))

    user_can_add_groups = request.user.is_authenticated() and \
            request.user.is_administrator_or_moderator()

    groups_membership_info = collections.defaultdict()
    if request.user.is_authenticated():
        #collect group memberhship information
        groups_membership_info = request.user.get_groups_membership_info(groups)

    data = {
        'groups': groups,
        'groups_membership_info': groups_membership_info,
        'user_can_add_groups': user_can_add_groups,
        'active_tab': 'groups',#todo vars active_tab and tab_name are too similar
        'tab_name': scope,
        'page_class': 'groups-page'
    }
    return render(request, 'groups.html', data)
