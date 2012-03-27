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

from django.db.models import Count, Q
from django.conf import settings as django_settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, HttpResponseForbidden
from django.http import HttpResponseRedirect, Http404
from django.utils.translation import ugettext as _
from django.utils import simplejson
from django.views.decorators import csrf

from askbot.utils.slug import slugify
from askbot.utils.html import sanitize_html
from askbot.utils.mail import send_mail
from askbot.utils.http import get_request_info
from askbot.utils import functions
from askbot import forms
from askbot import const
from askbot.conf import settings as askbot_settings
from askbot import models
from askbot import exceptions
from askbot.models.badges import award_badges_signal
from askbot.skins.loaders import render_into_skin
from askbot.templatetags import extra_tags
from askbot.search.state_manager import SearchState
from askbot.utils import url_utils

def owner_or_moderator_required(f):
    @functools.wraps(f)
    def wrapped_func(request, profile_owner, context):
        if profile_owner == request.user:
            pass
        elif request.user.is_authenticated() and request.user.can_moderate_user(profile_owner):
            pass
        else:
            params = '?next=%s' % request.path
            return HttpResponseRedirect(url_utils.get_login_url() + params)
        return f(request, profile_owner, context)
    return wrapped_func

def users(request):
    is_paginated = True
    sortby = request.GET.get('sort', 'reputation')
    suser = request.REQUEST.get('query',  "")
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1

    if suser == "":
        if sortby == "newest":
            order_by_parameter = '-date_joined'
        elif sortby == "last":
            order_by_parameter = 'date_joined'
        elif sortby == "user":
            order_by_parameter = 'username'
        else:
            # default
            order_by_parameter = '-reputation'

        objects_list = Paginator(
                            models.User.objects.all().order_by(
                                                order_by_parameter
                                            ),
                            const.USERS_PAGE_SIZE
                        )
        base_url = reverse('users') + '?sort=%s&' % sortby
    else:
        sortby = "reputation"
        objects_list = Paginator(
                            models.User.objects.filter(
                                                username__icontains = suser
                                            ).order_by(
                                                '-reputation'
                                            ),
                            const.USERS_PAGE_SIZE
                        )
        base_url = reverse('users') + '?name=%s&sort=%s&' % (suser, sortby)

    try:
        users_page = objects_list.page(page)
    except (EmptyPage, InvalidPage):
        users_page = objects_list.page(objects_list.num_pages)

    paginator_data = {
        'is_paginated' : is_paginated,
        'pages': objects_list.num_pages,
        'page': page,
        'has_previous': users_page.has_previous(),
        'has_next': users_page.has_next(),
        'previous': users_page.previous_page_number(),
        'next': users_page.next_page_number(),
        'base_url' : base_url
    }
    paginator_context = functions.setup_paginator(paginator_data) #
    data = {
        'active_tab': 'users',
        'page_class': 'users-page',
        'users' : users_page,
        'suser' : suser,
        'keywords' : suser,
        'tab_id' : sortby,
        'paginator_context' : paginator_context
    }
    return render_into_skin('users.html', data, request)

@csrf.csrf_protect
def user_moderate(request, subject, context):
    """user subview for moderation
    """
    moderator = request.user

    if moderator.is_authenticated() and not moderator.can_moderate_user(subject):
        raise Http404

    user_rep_changed = False
    user_status_changed = False
    message_sent = False
    email_error_message = None

    user_rep_form = forms.ChangeUserReputationForm()
    send_message_form = forms.SendMessageForm()
    if request.method == 'POST':
        if 'change_status' in request.POST:
            user_status_form = forms.ChangeUserStatusForm(
                                                    request.POST,
                                                    moderator = moderator,
                                                    subject = subject
                                                )
            if user_status_form.is_valid():
                subject.set_status( user_status_form.cleaned_data['user_status'] )
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
        'tab_description': _('moderate this user'),
        'page_title': _('moderate user'),
        'change_user_status_form': user_status_form,
        'change_user_reputation_form': user_rep_form,
        'send_message_form': send_message_form,
        'message_sent': message_sent,
        'email_error_message': email_error_message,
        'user_rep_changed': user_rep_changed,
        'user_status_changed': user_status_changed
    }
    context.update(data)
    return render_into_skin('user_profile/user_moderate.html', context, request)

#non-view function
def set_new_email(user, new_email, nomessage=False):
    if new_email != user.email:
        user.email = new_email
        user.email_isvalid = False
        user.save()
        #if askbot_settings.EMAIL_VALIDATION == True:
        #    send_new_email_key(user,nomessage=nomessage)

@login_required
@csrf.csrf_protect
def edit_user(request, id):
    """View that allows to edit user profile.
    This view is accessible to profile owners or site administrators
    """
    user = get_object_or_404(models.User, id=id)
    if not(request.user == user or request.user.is_superuser):
        raise Http404
    if request.method == "POST":
        form = forms.EditUserForm(user, request.POST)
        if form.is_valid():
            new_email = sanitize_html(form.cleaned_data['email'])

            set_new_email(user, new_email)

            if askbot_settings.EDITABLE_SCREEN_NAME:
                user.username = sanitize_html(form.cleaned_data['username'])

            user.real_name = sanitize_html(form.cleaned_data['realname'])
            user.website = sanitize_html(form.cleaned_data['website'])
            user.location = sanitize_html(form.cleaned_data['city'])
            user.date_of_birth = form.cleaned_data.get('birthday', None)
            user.about = sanitize_html(form.cleaned_data['about'])
            user.country = form.cleaned_data['country']
            user.show_country = form.cleaned_data['show_country']

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
        'support_custom_avatars': ('avatar' in django_settings.INSTALLED_APPS),
        'view_user': user,
    }
    return render_into_skin('user_profile/user_edit.html', data, request)

def user_stats(request, user, context):
    question_filter = {}
    if request.user != user:
        question_filter['is_anonymous'] = False

    #
    # Questions
    #
    questions = user.posts.get_questions().filter(**question_filter).\
                    order_by('-score', '-thread__last_activity_at').\
                    select_related('thread', 'thread__last_activity_by')[:100]

    #added this if to avoid another query if questions is less than 100
    if len(questions) < 100:
        question_count = len(questions)
    else:
        question_count = user.posts.get_questions().filter(**question_filter).count()

    #
    # Top answers
    #
    top_answers = user.posts.get_answers().filter(
        deleted=False,
        thread__posts__deleted=False,
        thread__posts__post_type='question',
    ).select_related('thread').order_by('-score', '-added_at')[:100]

    top_answer_count = len(top_answers)

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
    user_tags = models.Tag.objects.filter(threads__posts__author=user).distinct().\
                    annotate(user_tag_usage_count=Count('threads')).\
                    order_by('-user_tag_usage_count')[:const.USER_VIEW_DATA_SIZE]
    user_tags = list(user_tags) # evaluate

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

    data = {
        'active_tab':'users',
        'page_class': 'user-profile-page',
        'support_custom_avatars': ('avatar' in django_settings.INSTALLED_APPS),
        'tab_name' : 'stats',
        'tab_description' : _('user profile'),
        'page_title' : _('user profile overview'),
        'user_status_for_display': user.get_status_display(soft = True),
        'questions' : questions,
        'question_count': question_count,

        'top_answers': top_answers,
        'top_answer_count': top_answer_count,

        'up_votes' : up_votes,
        'down_votes' : down_votes,
        'total_votes': up_votes + down_votes,
        'votes_today_left': votes_total - votes_today,
        'votes_total_per_day': votes_total,

        'user_tags' : user_tags,

        'badges': badges,
        'total_badges' : len(badges),
    }
    context.update(data)

    return render_into_skin('user_profile/user_stats.html', context, request)

def user_recent(request, user, context):

    def get_type_name(type_id):
        for item in const.TYPE_ACTIVITY:
            if type_id in item:
                return item[1]

    class Event(object):
        is_badge = False
        def __init__(self, time, type, title, summary, answer_id, question_id):
            self.time = time
            self.type = get_type_name(type)
            self.type_id = type
            self.title = title
            self.summary = summary
            slug_title = slugify(title)
            self.title_link = reverse(
                                'question',
                                kwargs={'id':question_id}
                            ) + u'%s' % slug_title
            if int(answer_id) > 0:
                self.title_link += '#%s' % answer_id

    class AwardEvent(object):
        is_badge = True
        def __init__(self, time, type, content_object, badge):
            self.time = time
            self.type = get_type_name(type)
            self.content_object = content_object
            self.badge = badge

    activities = []

    # TODO: Don't process all activities here for the user, only a subset ([:const.USER_VIEW_DATA_SIZE])
    for activity in models.Activity.objects.filter(user=user):

        # TODO: multi-if means that we have here a construct for which a design pattern should be used

        # ask questions
        if activity.activity_type == const.TYPE_ACTIVITY_ASK_QUESTION:
            q = activity.content_object
            if q.deleted:
                activities.append(Event(
                    time=activity.active_at,
                    type=activity.activity_type,
                    title=q.thread.title,
                    summary='', #q.summary,  # TODO: was set to '' before, but that was probably wrong
                    answer_id=0,
                    question_id=q.id
                ))

        elif activity.activity_type == const.TYPE_ACTIVITY_ANSWER:
            ans = activity.content_object
            question = ans.thread._question_post()
            if not ans.deleted and not question.deleted:
                activities.append(Event(
                    time=activity.active_at,
                    type=activity.activity_type,
                    title=ans.thread.title,
                    summary=question.summary,
                    answer_id=ans.id,
                    question_id=question.id
                ))

        elif activity.activity_type == const.TYPE_ACTIVITY_COMMENT_QUESTION:
            cm = activity.content_object
            q = cm.parent
            assert q.is_question()
            if not q.deleted:
                activities.append(Event(
                    time=cm.added_at,
                    type=activity.activity_type,
                    title=q.thread.title,
                    summary='',
                    answer_id=0,
                    question_id=q.id
                ))

        elif activity.activity_type == const.TYPE_ACTIVITY_COMMENT_ANSWER:
            cm = activity.content_object
            ans = cm.parent
            assert ans.is_answer()
            question = ans.thread._question_post()
            if not ans.deleted and not question.deleted:
                activities.append(Event(
                    time=cm.added_at,
                    type=activity.activity_type,
                    title=ans.thread.title,
                    summary='',
                    answer_id=ans.id,
                    question_id=question.id
                ))

        elif activity.activity_type == const.TYPE_ACTIVITY_UPDATE_QUESTION:
            q = activity.content_object
            if not q.deleted:
                activities.append(Event(
                    time=activity.active_at,
                    type=activity.activity_type,
                    title=q.thread.title,
                    summary=q.summary,
                    answer_id=0,
                    question_id=q.id
                ))

        elif activity.activity_type == const.TYPE_ACTIVITY_UPDATE_ANSWER:
            ans = activity.content_object
            question = ans.thread._question_post()
            if not ans.deleted and not question.deleted:
                activities.append(Event(
                    time=activity.active_at,
                    type=activity.activity_type,
                    title=ans.thread.title,
                    summary=ans.summary,
                    answer_id=ans.id,
                    question_id=question.id
                ))

        elif activity.activity_type == const.TYPE_ACTIVITY_MARK_ANSWER:
            ans = activity.content_object
            question = ans.thread._question_post()
            if not ans.deleted and not question.deleted:
                activities.append(Event(
                    time=activity.active_at,
                    type=activity.activity_type,
                    title=ans.thread.title,
                    summary='',
                    answer_id=0,
                    question_id=question.id
                ))

        elif activity.activity_type == const.TYPE_ACTIVITY_PRIZE:
            award = activity.content_object
            activities.append(AwardEvent(
                time=award.awarded_at,
                type=activity.activity_type,
                content_object=award.content_object,
                badge=award.badge,
            ))

    activities.sort(key=operator.attrgetter('time'), reverse=True)

    data = {
        'active_tab': 'users',
        'page_class': 'user-profile-page',
        'tab_name' : 'recent',
        'tab_description' : _('recent user activity'),
        'page_title' : _('profile - recent activity'),
        'activities' : activities[:const.USER_VIEW_DATA_SIZE]
    }
    context.update(data)
    return render_into_skin('user_profile/user_recent.html', context, request)

@owner_or_moderator_required
def user_responses(request, user, context):
    """
    We list answers for question, comments, and
    answer accepted by others for this user.
    as well as mentions of the user

    user - the profile owner
    """

    section = 'forum'
    if request.user.is_moderator() or request.user.is_administrator():
        if 'section' in request.GET and request.GET['section'] == 'flags':
            section = 'flags'

    if section == 'forum':
        activity_types = const.RESPONSE_ACTIVITY_TYPES_FOR_DISPLAY
        activity_types += (const.TYPE_ACTIVITY_MENTION,)
    else:
        assert(section == 'flags')
        activity_types = (const.TYPE_ACTIVITY_MARK_OFFENSIVE,)

    memo_set = models.ActivityAuditStatus.objects.filter(
                    user = request.user,
                    activity__activity_type__in = activity_types
                ).select_related(
                    'activity',
                    'activity__content_type',
                    'activity__question__thread',
                    'activity__user',
                    'activity__user__gravatar',
                ).order_by(
                    '-activity__active_at'
                )[:const.USER_VIEW_DATA_SIZE]

    #todo: insert pagination code here

    response_list = list()
    for memo in memo_set:
        response = {
            'id': memo.id,
            'timestamp': memo.activity.active_at,
            'user': memo.activity.user,
            'is_new': memo.is_new(),
            'response_url': memo.activity.get_absolute_url(),
            'response_snippet': memo.activity.get_preview(),
            'response_title': memo.activity.question.thread.title,
            'response_type': memo.activity.get_activity_type_display(),
            'response_id': memo.activity.question.id,
            'nested_responses': [],
            'response_content': memo.activity.content_object.html,
        }
        response_list.append(response)

    response_list.sort(lambda x,y: cmp(y['response_id'], x['response_id']))
    last_response_id = None #flag to know if the response id is different
    last_response_index = None #flag to know if the response index in the list is different
    filtered_response_list = list()

    for i, response in enumerate(response_list):
        #todo: agrupate users
        if response['response_id'] == last_response_id:
            original_response = dict.copy(filtered_response_list[len(filtered_response_list)-1])
            original_response['nested_responses'].append(response)
            filtered_response_list[len(filtered_response_list)-1] = original_response
        else:
            filtered_response_list.append(response)
            last_response_id = response['response_id']
            last_response_index = i

    response_list = filtered_response_list
    
    response_list.sort(lambda x,y: cmp(y['timestamp'], x['timestamp']))
    filtered_response_list = list()

    data = {
        'active_tab':'users',
        'page_class': 'user-profile-page',
        'tab_name' : 'inbox',
        'inbox_section':section,
        'tab_description' : _('comments and answers to others questions'),
        'page_title' : _('profile - responses'),
        'responses' : response_list,
    }
    context.update(data)
    return render_into_skin('user_profile/user_inbox.html', context, request)

def user_network(request, user, context):
    if 'followit' not in django_settings.INSTALLED_APPS:
        raise Http404
    data = {
        'tab_name': 'network',
        'followed_users': user.get_followed_users(),
        'followers': user.get_followers(),
    }
    context.update(data)
    return render_into_skin('user_profile/user_network.html', context, request)

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
        'tab_description' : _('user vote record'),
        'page_title' : _('profile - votes'),
        'votes' : votes[:const.USER_VIEW_DATA_SIZE]
    }
    context.update(data)
    return render_into_skin('user_profile/user_votes.html', context, request)


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
        'tab_description': _('user karma'),
        'page_title': _("Profile - User's Karma"),
        'reputation': reputes,
        'reps': reps
    }
    context.update(data)
    return render_into_skin('user_profile/user_reputation.html', context, request)


def user_favorites(request, user, context):
    favorite_threads = user.user_favorite_questions.values_list('thread', flat=True)
    questions = models.Post.objects.filter(post_type='question', thread__in=favorite_threads)\
                    .select_related('thread', 'thread__last_activity_by')\
                    .order_by('-score', '-thread__last_activity_at')[:const.USER_VIEW_DATA_SIZE]

    data = {
        'active_tab':'users',
        'page_class': 'user-profile-page',
        'tab_name' : 'favorites',
        'tab_description' : _('users favorite questions'),
        'page_title' : _('profile - favorite questions'),
        'questions' : questions,
    }
    context.update(data)
    return render_into_skin('user_profile/user_favorites.html', context, request)


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
        'page_class': 'user-profile-page',
        'tab_name': 'email_subscriptions',
        'tab_description': _('email subscription settings'),
        'page_title': _('profile - email subscriptions'),
        'email_feeds_form': email_feeds_form,
        'tag_filter_selection_form': tag_filter_form,
        'action_status': action_status,
    }
    context.update(data)
    return render_into_skin(
        'user_profile/user_email_subscriptions.html',
        context,
        request
    )

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
#todo: rename this function - variable named user is everywhere
def user(request, id, slug=None, tab_name=None):
    """Main user view function that works as a switchboard

    id - id of the profile owner

    todo: decide what to do with slug - it is not used
    in the code in any way
    """
    profile_owner = get_object_or_404(models.User, id = id)

    if not tab_name:
        tab_name = request.GET.get('sort', 'stats')

    user_view_func = USER_VIEW_CALL_TABLE.get(tab_name, user_stats)

    search_state = SearchState( # Non-default SearchState with user data set
        scope=None,
        sort=None,
        query=None,
        tags=None,
        author=profile_owner.id,
        page=None,
        user_logged_in=profile_owner.is_authenticated(),
    )

    context = {
        'view_user': profile_owner,
        'search_state': search_state,
        'user_follow_feature_on': ('followit' in django_settings.INSTALLED_APPS),
    }
    return user_view_func(request, profile_owner, context)

@csrf.csrf_exempt
def update_has_custom_avatar(request):
    """updates current avatar type data for the user
    """
    if request.is_ajax() and request.user.is_authenticated():
        if request.user.avatar_type in ('n', 'g'):
            request.user.update_avatar_type()
            request.session['avatar_data_updated_at'] = datetime.datetime.now()
            return HttpResponse(simplejson.dumps({'status':'ok'}), mimetype='application/json')
    return HttpResponseForbidden()
