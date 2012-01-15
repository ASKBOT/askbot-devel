"""
:synopsis: user-centric views for askbot

This module includes all views that are specific to a given user - his or her profile,
and other views showing profile-related information.

Also this module includes the view listing all forum users.
"""
import calendar
import functools
import datetime
import logging
from django.db.models import Count
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
from askbot import forms
from askbot import const
from askbot.conf import settings as askbot_settings
from askbot import models
from askbot import exceptions
from askbot.models.badges import award_badges_signal
from askbot.skins.loaders import render_into_skin
from askbot.templatetags import extra_tags


#todo: queries in the user activity summary view must be redone
def get_related_object_type_name(content_type_id, object_id):
    if content_type_id == ContentType.objects.get_for_model(models.Question).id:
        return 'question'
    elif content_type_id == ContentType.objects.get_for_model(models.Answer).id:
        return 'answer'
    elif content_type_id == ContentType.objects.get_for_model(models.PostRevision).id:
        post_revision = models.PostRevision.objects.get(id=object_id)
        return post_revision.revision_type_str()

    return None

def owner_or_moderator_required(f):
    @functools.wraps(f)
    def wrapped_func(request, profile_owner, context):
        if profile_owner == request.user:
            pass
        elif request.user.is_authenticated() and request.user.can_moderate_user(profile_owner):
            pass
        else:
            params = '?next=%s' % request.path
            return HttpResponseRedirect(reverse('user_signin') + params)
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
    paginator_context = extra_tags.cnprog_paginator(paginator_data)
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

    if not moderator.can_moderate_user(subject):
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

    question_filter = {'author': user}
    if request.user != user:
        question_filter['is_anonymous'] = False

    questions = models.Question.objects.filter(
                                    **question_filter
                                ).order_by(
                                    '-score', '-last_activity_at'
                                ).select_related(
                                    'last_activity_by__id',
                                    'last_activity_by__username',
                                    'last_activity_by__reputation',
                                    'last_activity_by__gold',
                                    'last_activity_by__silver',
                                    'last_activity_by__bronze'
                                )[:100]

    questions = list(questions)

    #added this if to avoid another query if questions is less than 100
    if len(questions) < 100:
        question_count = len(questions)
    else:
        question_count = models.Question.objects.filter(
                                        **question_filter
                                    ).order_by(
                                        '-score', '-last_activity_at'
                                    ).select_related(
                                        'last_activity_by__id',
                                        'last_activity_by__username',
                                        'last_activity_by__reputation',
                                        'last_activity_by__gold',
                                        'last_activity_by__silver',
                                        'last_activity_by__bronze'
                                    ).count()

    favorited_myself = models.FavoriteQuestion.objects.filter(
                                    question__in = questions,
                                    user = user
                                ).values_list('question__id', flat=True)

    #this is meant for the questions answered by the user (or where answers were edited by him/her?)
    answered_questions = models.Question.objects.extra(
        select={
            'vote_up_count' : 'answer.vote_up_count',
            'vote_down_count' : 'answer.vote_down_count',
            'answer_id' : 'answer.id',
            'answer_accepted' : 'answer.accepted',
            'answer_score' : 'answer.score',
            'comment_count' : 'answer.comment_count'
            },
        tables=['question', 'answer'],
        where=['NOT answer.deleted AND NOT question.deleted AND answer.author_id=%s AND answer.question_id=question.id'],
        params=[user.id],
        order_by=['-answer_score', '-answer_id'],
        select_params=[user.id]
    ).distinct().values('comment_count',
                        'id',
                        'answer_id',
                        'title',
                        'author_id',
                        'answer_accepted',
                        'answer_score',
                        'answer_count',
                        'vote_up_count',
                        'vote_down_count')[:100]

    up_votes = models.Vote.objects.get_up_vote_count_from_user(user)
    down_votes = models.Vote.objects.get_down_vote_count_from_user(user)
    votes_today = models.Vote.objects.get_votes_count_today_from_user(user)
    votes_total = askbot_settings.MAX_VOTES_PER_USER_PER_DAY

    question_id_set = set()
    #todo: there may be a better way to do these queries
    question_id_set.update([q.id for q in questions])
    question_id_set.update([q['id'] for q in answered_questions])
    user_tags = models.Tag.objects.filter(questions__id__in = question_id_set)
    interesting_tags = models.Tag.objects.filter(
				    user_selections__user=user,
                                    user_selections__reason='good'
                                )

    ignored_tags = models.Tag.objects.filter(
				    user_selections__user=user,
				    user_selections__reason='bad'
				)

    badges = models.BadgeData.objects.filter(
                            award_badge__user=user
                        )
    total_awards = badges.count()
    badges = badges.order_by('-slug').distinct()

    user_tags = user_tags.annotate(
                            user_tag_usage_count=Count('name')
                        ).order_by(
                            '-user_tag_usage_count'
                        )

    if user.is_administrator():
        user_status = _('Site Adminstrator')
    elif user.is_moderator():
        user_status = _('Forum Moderator')
    elif user.is_suspended():
        user_status = _('Suspended User')
    elif user.is_blocked():
        user_status = _('Blocked User')
    else:
        user_status = _('Registered User')

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
        'question_type' : ContentType.objects.get_for_model(models.Question),
        'answer_type' : ContentType.objects.get_for_model(models.Answer),
        'favorited_myself': favorited_myself,
        'answered_questions' : answered_questions,
        'interesting_tags' : interesting_tags,
        'ignored_tags' : ignored_tags,
        'up_votes' : up_votes,
        'down_votes' : down_votes,
        'total_votes': up_votes + down_votes,
        'votes_today_left': votes_total-votes_today,
        'votes_total_per_day': votes_total,
        'user_tags' : user_tags[:const.USER_VIEW_DATA_SIZE],
        'badges': badges,
        'total_awards' : total_awards,
    }
    context.update(data)
    return render_into_skin('user_profile/user_stats.html', context, request)

def user_recent(request, user, context):

    def get_type_name(type_id):
        for item in const.TYPE_ACTIVITY:
            if type_id in item:
                return item[1]

    class Event:
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

    class AwardEvent:
        is_badge = True
        def __init__(self, time, obj, cont, type, id, related_object_type = None):
            self.time = time
            self.obj = obj
            self.cont = cont
            self.type = get_type_name(type)
            self.type_id = type
            self.badge = get_object_or_404(models.BadgeData, id=id)
            self.related_object_type = related_object_type

    activities = []
    # ask questions
    questions = models.Activity.objects.extra(
        select={
            'title' : 'question.title',
            'question_id' : 'question.id',
            'summary' : 'question.summary',
            'active_at' : 'activity.active_at',
            'activity_type' : 'activity.activity_type'
            },
        tables=['activity', 'question'],
        where=['activity.content_type_id = %s AND activity.object_id = ' +
            'question.id AND activity.user_id = %s AND activity.activity_type = %s AND NOT question.deleted'],
        params=[ContentType.objects.get_for_model(models.Question).id, user.id, const.TYPE_ACTIVITY_ASK_QUESTION],
        order_by=['-activity.active_at']
    ).values(
            'title',
            'question_id',
            'summary',
            'active_at',
            'activity_type'
            )

    for q in questions:
        q_event = Event(
                    q['active_at'],
                    q['activity_type'],
                    q['title'],
                    '',
                    '0',
                    q['question_id']
                )
        activities.append(q_event)

    # answers
    answers = models.Activity.objects.extra(
        select={
            'title' : 'question.title',
            'question_id' : 'question.id',
            'summary' : 'question.summary',
            'answer_id' : 'answer.id',
            'active_at' : 'activity.active_at',
            'activity_type' : 'activity.activity_type'
            },
        tables=['activity', 'answer', 'question'],
        where=['activity.content_type_id = %s AND activity.object_id = answer.id AND ' +
            'answer.question_id=question.id AND NOT answer.deleted AND activity.user_id=%s AND '+
            'activity.activity_type=%s AND NOT question.deleted'],
        params=[ContentType.objects.get_for_model(models.Answer).id, user.id, const.TYPE_ACTIVITY_ANSWER],
        order_by=['-activity.active_at']
    ).values(
            'title',
            'question_id',
            'summary',
            'answer_id',
            'active_at',
            'activity_type'
            )
    if len(answers) > 0:
        answer_activities = [(Event(q['active_at'], q['activity_type'], q['title'], '', q['answer_id'], \
                    q['question_id'])) for q in answers]
        activities.extend(answer_activities)

    # question comments
    comments = models.Activity.objects.extra(
        select={
            'title' : 'question.title',
            'question_id' : 'comment.object_id',
            'added_at' : 'comment.added_at',
            'activity_type' : 'activity.activity_type'
            },
        tables=['activity', 'question', 'comment'],

        where=['activity.content_type_id = %s AND activity.object_id = comment.id AND '+
            'activity.user_id = comment.user_id AND comment.object_id=question.id AND '+
            'comment.content_type_id=%s AND activity.user_id = %s AND activity.activity_type=%s AND ' +
            'NOT question.deleted'],
        params=[ContentType.objects.get_for_model(models.Comment).id, ContentType.objects.get_for_model(models.Question).id, user.id, const.TYPE_ACTIVITY_COMMENT_QUESTION],
        order_by=['-comment.added_at']
    ).values(
            'title',
            'question_id',
            'added_at',
            'activity_type'
            )

    if len(comments) > 0:
        comments = [(Event(q['added_at'], q['activity_type'], q['title'], '', '0', \
                     q['question_id'])) for q in comments]
        activities.extend(comments)

    # answer comments
    comments = models.Activity.objects.extra(
        select={
            'title' : 'question.title',
            'question_id' : 'question.id',
            'answer_id' : 'answer.id',
            'added_at' : 'comment.added_at',
            'activity_type' : 'activity.activity_type'
            },
        tables=['activity', 'question', 'answer', 'comment'],

        where=['activity.content_type_id = %s AND activity.object_id = comment.id AND '+
            'activity.user_id = comment.user_id AND comment.object_id=answer.id AND '+
            'comment.content_type_id=%s AND question.id = answer.question_id AND '+
            'activity.user_id = %s AND activity.activity_type=%s AND '+
            'NOT answer.deleted AND NOT question.deleted'],
        params=[ContentType.objects.get_for_model(models.Comment).id, ContentType.objects.get_for_model(models.Answer).id, user.id, const.TYPE_ACTIVITY_COMMENT_ANSWER],
        order_by=['-comment.added_at']
    ).values(
            'title',
            'question_id',
            'answer_id',
            'added_at',
            'activity_type'
            )

    if len(comments) > 0:
        comments = [(Event(q['added_at'], q['activity_type'], q['title'], '', q['answer_id'], \
                     q['question_id'])) for q in comments]
        activities.extend(comments)

    # question revisions
    revisions = models.Activity.objects.extra(
        select={
            'title' : 'askbot_postrevision.title',
            'question_id' : 'askbot_postrevision.question_id',
            'added_at' : 'activity.active_at',
            'activity_type' : 'activity.activity_type',
            'summary' : 'askbot_postrevision.summary'
            },
        tables=['activity', 'askbot_postrevision', 'question'],
        where=['''
            activity.content_type_id=%s AND activity.object_id=askbot_postrevision.id AND
            askbot_postrevision.question_id=question.id AND askbot_postrevision.revision_type=%s AND NOT question.deleted AND
            activity.user_id=askbot_postrevision.author_id AND activity.user_id=%s AND
            activity.activity_type=%s
        '''],
        params=[ContentType.objects.get_for_model(models.PostRevision).id, models.PostRevision.QUESTION_REVISION, user.id, const.TYPE_ACTIVITY_UPDATE_QUESTION],
        order_by=['-activity.active_at']
    ).values(
            'title',
            'question_id',
            'added_at',
            'activity_type',
            'summary'
            )

    if len(revisions) > 0:
        revisions = [(Event(q['added_at'], q['activity_type'], q['title'], q['summary'], '0', \
                      q['question_id'])) for q in revisions]
        activities.extend(revisions)

    # answer revisions
    revisions = models.Activity.objects.extra(
        select={
            'title' : 'question.title',
            'question_id' : 'question.id',
            'answer_id' : 'answer.id',
            'added_at' : 'activity.active_at',
            'activity_type' : 'activity.activity_type',
            'summary' : 'askbot_postrevision.summary'
            },
        tables=['activity', 'askbot_postrevision', 'question', 'answer'],
        where=['''
            activity.content_type_id=%s AND activity.object_id=askbot_postrevision.id AND
            askbot_postrevision.answer_id=answer.id AND askbot_postrevision.revision_type=%s AND
            answer.question_id=question.id AND NOT question.deleted AND NOT answer.deleted AND
            activity.user_id=askbot_postrevision.author_id AND activity.user_id=%s AND
            activity.activity_type=%s
        '''],
        params=[ContentType.objects.get_for_model(models.PostRevision).id, models.PostRevision.ANSWER_REVISION, user.id, const.TYPE_ACTIVITY_UPDATE_ANSWER],
        order_by=['-activity.active_at']
    ).values(
            'title',
            'question_id',
            'added_at',
            'answer_id',
            'activity_type',
            'summary'
            )

    if len(revisions) > 0:
        revisions = [(Event(q['added_at'], q['activity_type'], q['title'], q['summary'], \
                      q['answer_id'], q['question_id'])) for q in revisions]
        activities.extend(revisions)

    # accepted answers
    accept_answers = models.Activity.objects.extra(
        select={
            'title' : 'question.title',
            'question_id' : 'question.id',
            'added_at' : 'activity.active_at',
            'activity_type' : 'activity.activity_type',
            },
        tables=['activity', 'answer', 'question'],
        where=['activity.content_type_id = %s AND activity.object_id = answer.id AND '+
            'activity.user_id = question.author_id AND activity.user_id = %s AND '+
            'NOT answer.deleted AND NOT question.deleted AND '+
            'answer.question_id=question.id AND activity.activity_type=%s'],
        params=[ContentType.objects.get_for_model(models.Answer).id, user.id, const.TYPE_ACTIVITY_MARK_ANSWER],
        order_by=['-activity.active_at']
    ).values(
            'title',
            'question_id',
            'added_at',
            'activity_type',
            )
    if len(accept_answers) > 0:
        accept_answers = [(Event(q['added_at'], q['activity_type'], q['title'], '', '0', \
            q['question_id'])) for q in accept_answers]
        activities.extend(accept_answers)
    #award history
    awards = models.Activity.objects.extra(
        select={
            'badge_id' : 'askbot_badgedata.id',
            'awarded_at': 'award.awarded_at',
            'object_id': 'award.object_id',
            'content_type_id': 'award.content_type_id',
            'activity_type' : 'activity.activity_type'
            },
        tables=['activity', 'award', 'askbot_badgedata'],
        where=['activity.user_id = award.user_id AND activity.user_id = %s AND '+
            'award.badge_id=askbot_badgedata.id AND activity.object_id=award.id AND activity.activity_type=%s'],
        params=[user.id, const.TYPE_ACTIVITY_PRIZE],
        order_by=['-activity.active_at']
    ).values(
            'badge_id',
            'awarded_at',
            'object_id',
            'content_type_id',
            'activity_type'
            )
    for award in awards:
        related_object_type = get_related_object_type_name(
            content_type_id=award['content_type_id'],
            object_id=award['object_id']
        )
        activities.append(
            AwardEvent(
                award['awarded_at'],
                award['object_id'],
                award['content_type_id'],
                award['activity_type'],
                award['badge_id'],
                related_object_type = related_object_type
            )
        )

    activities.sort(lambda x,y: cmp(y.time, x.time))

    data = {
        'answers': answers,
        'questions': questions,
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
                    'activity__active_at',
                    'activity__object_id',
                    'activity__content_type',
                    'activity__question__title',
                    'activity__user__username',
                    'activity__user__id',
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
            'response_title': memo.activity.question.title,
            'response_type': memo.activity.get_activity_type_display(),
            'response_id': memo.activity.question.id,
            'nested_responses': [],
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

    votes = []
    question_votes = models.Vote.objects.extra(
        select={
            'title' : 'question.title',
            'question_id' : 'question.id',
            'answer_id' : 0,
            'voted_at' : 'vote.voted_at',
            'vote' : 'vote',
            },
        select_params=[user.id],
        tables=['vote', 'question', 'auth_user'],
        where=['vote.content_type_id = %s AND vote.user_id = %s AND vote.object_id = question.id '+
            'AND vote.user_id=auth_user.id'],
        params=[ContentType.objects.get_for_model(models.Question).id, user.id],
        order_by=['-vote.id']
    ).values(
            'title',
            'question_id',
            'answer_id',
            'voted_at',
            'vote',
            )
    if(len(question_votes) > 0):
        votes.extend(question_votes)

    answer_votes = models.Vote.objects.extra(
        select={
            'title' : 'question.title',
            'question_id' : 'question.id',
            'answer_id' : 'answer.id',
            'voted_at' : 'vote.voted_at',
            'vote' : 'vote',
            },
        select_params=[user.id],
        tables=['vote', 'answer', 'question', 'auth_user'],
        where=['vote.content_type_id = %s AND vote.user_id = %s AND vote.object_id = answer.id '+
            'AND answer.question_id = question.id AND vote.user_id=auth_user.id'],
        params=[ContentType.objects.get_for_model(models.Answer).id, user.id],
        order_by=['-vote.id']
    ).values(
            'title',
            'question_id',
            'answer_id',
            'voted_at',
            'vote',
            )
    if(len(answer_votes) > 0):
        votes.extend(answer_votes)
    votes.sort(lambda x,y: cmp(y['voted_at'], x['voted_at']))

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
    reputes = models.Repute.objects.filter(user=user).order_by('-reputed_at')
    #select_related() adds stuff needed for the query
    reputes = reputes.select_related(
                            'question__title',
                            'question__id',
                            'user__username'
                        )
    #prepare data for the graph
    rep_list = []
    #last values go in first
    rep_list.append('[%s,%s]' % (
                            calendar.timegm(
                                        datetime.datetime.now().timetuple()
                                    ) * 1000,
                            user.reputation
                        )
                    )
    #ret remaining values in
    for rep in reputes:
        dic = '[%s,%s]' % (calendar.timegm(rep.reputed_at.timetuple()) * 1000, rep.reputation)
        rep_list.append(dic)
    reps = ','.join(rep_list)
    reps = '[%s]' % reps

    data = {
        'active_tab':'users',
        'page_class': 'user-profile-page',
        'tab_name': 'reputation',
        'tab_description': _('user reputation in the community'),
        'page_title': _('profile - user reputation'),
        'reputation': reputes,
        'reps': reps
    }
    context.update(data)
    return render_into_skin('user_profile/user_reputation.html', context, request)

def user_favorites(request, user, context):
    favorited_q_id_list= models.FavoriteQuestion.objects.filter(
                                    user = user
                                ).values_list('question__id', flat=True)
    questions = models.Question.objects.filter(
                                    id__in=favorited_q_id_list
                                ).order_by(
                                    '-score', '-last_activity_at'
                                ).select_related(
                                    'last_activity_by__id',
                                    'last_activity_by__username',
                                    'last_activity_by__reputation',
                                    'last_activity_by__gold',
                                    'last_activity_by__silver',
                                    'last_activity_by__bronze'
                                )[:const.USER_VIEW_DATA_SIZE]
    data = {
        'active_tab':'users',
        'page_class': 'user-profile-page',
        'tab_name' : 'favorites',
        'tab_description' : _('users favorite questions'),
        'page_title' : _('profile - favorite questions'),
        'questions' : questions,
        'favorited_myself': favorited_q_id_list,
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

user_view_call_table = {
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

    if tab_name is None:
        #sort CGI parameter tells us which tab in the user
        #profile to show, the default one is 'stats'
        tab_name = request.GET.get('sort', 'stats')

    if tab_name in user_view_call_table:
        #get the actual view function
        user_view_func = user_view_call_table[tab_name]
    else:
        user_view_func = user_stats

    context = {
        'view_user': profile_owner,
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
