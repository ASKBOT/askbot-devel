"""Askbot analytics views"""
from datetime import timedelta
from django.conf import settings as django_settings
from django.db import models
from django.shortcuts import render, HttpResponseRedirect
from django.http import HttpResponseForbidden
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.html import escape
from askbot.utils import analytics_utils
from askbot.utils.functions import get_paginated_list
from askbot.forms import AnalyticsUsersForm
from askbot.models import User, Group
from askbot.views.analytics.utils import get_date_selector_url_func
from askbot.models.analytics import (get_organizations_count,
                                     DailyGroupSummary,
                                     DailyUserSummary,
                                     Event)

def get_aggregated_group_data(summaries):
    if summaries.count() == 0:
        return {
            'num_users': 0,
            'num_users_added': 0,
            'num_questions': 0,
            'num_answers': 0,
            'num_upvotes': 0,
            'num_downvotes': 0,
            'question_views': 0,
            'time_on_site': timedelta(seconds=0),
        }

    data = summaries.aggregate(
        num_questions=models.Sum('num_questions'),
        num_answers=models.Sum('num_answers'),
        num_upvotes=models.Sum('num_upvotes'),
        num_downvotes=models.Sum('num_downvotes'),
        question_views=models.Sum('question_views'),
        time_on_site=models.Sum('time_on_site'),
        num_users_added=models.Sum('num_users_added')
    )
    return data


def get_total_users_in_groups_by_date(group_ids, date):
    """Returns total number of users in groups, specified by ids at a given date"""
    total_users = 0
    for group_id in group_ids:
        named_segment_summaries = DailyGroupSummary.objects.filter(group__id=group_id) # pylint: disable=no-member
        named_segment_summaries = named_segment_summaries.filter(date__lte=date)
        latest_segment = named_segment_summaries.order_by('-date').first()
        total_users += latest_segment.num_users if latest_segment else 0
    return total_users


def non_routed_per_segment_stats(request, data):
    """Renders the all users page"""
    default_segment_config = django_settings.ASKBOT_ANALYTICS_DEFAULT_SEGMENT
    data.update({
        'all_users_count': User.objects.exclude(askbot_profile__status='b').count(),
        'default_segment_name': default_segment_config['name'],
        'default_segment_description': default_segment_config['description'],
    })

    #1) get data for all users
    all_data = {
        'num_users': data['all_users_count'],
        'num_users_added': User.objects.filter(date_joined__gt=data['start_date'],
                                               date_joined__lte=data['end_date']).count(),
        # remaining fields will be added as sum of all segments
        # symmetrically - for the default segment
        # we will obtain the above numbers by subtraction
    }

    #2) get data for all named segments
    named_segment_configs = django_settings.ASKBOT_ANALYTICS_NAMED_SEGMENTS
    named_segments_data = []
    for segment_config in named_segment_configs:
        group_ids = segment_config['group_ids']
        named_segment_summaries = DailyGroupSummary.objects.filter(group__id__in=group_ids) # pylint: disable=no-member
        named_segment_summaries = named_segment_summaries.filter(date__lte=data['end_date'])
        named_segment_summaries = named_segment_summaries.filter(date__gt=data['start_date'])

        datum = get_aggregated_group_data(named_segment_summaries)
        datum['num_users'] = get_total_users_in_groups_by_date(group_ids, data['end_date'])
        datum['slug'] = segment_config['slug']
        datum['name'] = segment_config['name']
        named_segments_data.append(datum)


    #2) for the default segment, subtract the numbers for 2) from 1)
    named_segment_group_ids = analytics_utils.get_all_named_segment_group_ids()
    default_segment_summaries = DailyGroupSummary.objects.exclude( # pylint: disable=no-member
                                    group__id__in=named_segment_group_ids)
    default_segment_summaries = default_segment_summaries.filter(date__gt=data['start_date'],
                                                                 date__lte=data['end_date'])

    default_segment_data = get_aggregated_group_data(default_segment_summaries)
    default_segment_data['slug'] = django_settings.ASKBOT_ANALYTICS_DEFAULT_SEGMENT['slug']
    default_segment_data['name'] = django_settings.ASKBOT_ANALYTICS_DEFAULT_SEGMENT['name']
    # here goes the symmetrical calculation of the missing fields - see step 1)
    named_segments_users_added = sum(datum['num_users_added'] for datum in named_segments_data)
    default_segment_data['num_users_added'] = all_data['num_users_added']\
                                              - named_segments_users_added
    named_segments_num_users = sum(datum['num_users'] for datum in named_segments_data)
    default_segment_data['num_users'] = all_data['num_users'] - named_segments_num_users

    # finally calculate the remaining fields for the all_data
    all_data['num_questions'] = default_segment_data['num_questions'] + \
                                sum(datum['num_questions'] for datum in named_segments_data)

    all_data['num_answers'] = default_segment_data['num_answers'] + \
                              sum(datum['num_answers'] for datum in named_segments_data)

    all_data['num_upvotes'] = default_segment_data['num_upvotes'] + \
                              sum(datum['num_upvotes'] for datum in named_segments_data)

    all_data['num_downvotes'] = default_segment_data['num_downvotes'] + \
                                sum(datum['num_downvotes'] for datum in named_segments_data)

    all_data['question_views'] = default_segment_data['question_views'] + \
                                 sum(datum['question_views'] for datum in named_segments_data)

    all_data['time_on_site'] = default_segment_data['time_on_site'] + \
                               sum((datum['time_on_site'] for datum in named_segments_data),
                                   start=timedelta(seconds=0))

    data['all_data'] = all_data
    data['named_segments_data'] = named_segments_data
    data['default_segment_data'] = default_segment_data

    if django_settings.ASKBOT_ANALYTICS_EMAIL_DOMAIN_ORGANIZATIONS_ENABLED:
        data['orgs_count'] = get_organizations_count()
        data['orgs_enabled'] = True
    data['date_selector_url_func'] = get_date_selector_url_func('analytics_users',
                                                                users_segment=data['users_segment'])
    return render(request, 'analytics/per_segment_stats.html', data)


def non_routed_per_group_in_segment_stats(request, data):
    """Renders the non vip users page -- a.k.a. customers"""
    named_segment_group_ids = analytics_utils.get_all_named_segment_group_ids()
    named_segment_groups = Group.objects.filter(group_ptr__id__in=named_segment_group_ids)
    all_customer_summaries = DailyGroupSummary.objects.exclude(group__id__in=named_segment_groups) # pylint: disable=no-member

    if data['query']:
        all_customer_summaries = all_customer_summaries.filter(group__name__icontains=data['query'])

    start_date = data['start_date']
    end_date = data['end_date']
    customer_summaries = all_customer_summaries.filter(date__gt=start_date, date__lte=end_date) # pylint: disable=no-member
    data['groups'] = []
    data['default_segment_name'] = django_settings.ASKBOT_ANALYTICS_DEFAULT_SEGMENT['name']
    data['default_segment_slug'] = django_settings.ASKBOT_ANALYTICS_DEFAULT_SEGMENT['slug']

    customer_summaries = customer_summaries.values('group_id')
    customer_summaries = customer_summaries.annotate(
        num_users_added=models.Sum('num_users_added'),
        num_questions=models.Sum('num_questions'),
        num_answers=models.Sum('num_answers'),
        num_upvotes=models.Sum('num_upvotes'),
        num_downvotes=models.Sum('num_downvotes'),
        question_views=models.Sum('question_views'),
        time_on_site=models.Sum('time_on_site'),
        orgname=models.F('group__name')
    )

    customer_summaries = customer_summaries.order_by(data['order_by'])

    query_params = {}
    if data['query']:
        query_params['query'] = data['query']

    query_params['sort_by'] = data['sort_by']
    query_params['sort_order'] = data['sort_order']
    customer_summaries, paginator_context = get_paginated_list(request,
                                                               customer_summaries,
                                                               20,
                                                               query_params or None)
    data['paginator_context'] = paginator_context

    for summary in customer_summaries:
        group = Group.objects.get(id=summary['group_id'])
        summary['group'] = group
        summary['num_users'] = all_customer_summaries.filter(group_id=group.id,
                                                             date__lte=end_date) \
                                                            .order_by('date') \
                                                            .last() \
                                                            .num_users
        data['groups'].append(summary)

    data['date_selector_url_func'] = get_date_selector_url_func('analytics_users',
                                                                users_segment=data['users_segment'])
    return render(request, 'analytics/per_group_in_segment_stats.html', data)


def non_routed_per_user_in_group_stats(request,
                              data,
                              group_ids=None,
                              segment_slug=None,
                              segment_name=None,
                              is_named_segment=False):
    """Renders the group users page"""
    users = User.objects.filter(groups__id__in=group_ids)
    users_data = []

    daily_user_summaries = DailyUserSummary.objects.filter(user__in=users) # pylint: disable=no-member
    daily_user_summaries = daily_user_summaries.filter(date__gt=data['start_date'],
                                                       date__lte=data['end_date']) # pylint: disable=no-member

    if data['query']:
        daily_user_summaries = daily_user_summaries.filter(user__username__icontains=data['query'])

    daily_user_summaries = daily_user_summaries.values('user_id')
    daily_user_summaries = daily_user_summaries.annotate(
        username=models.F('user__username'),
        num_questions=models.Sum('num_questions'),
        num_answers=models.Sum('num_answers'),
        num_upvotes=models.Sum('num_upvotes'),
        num_downvotes=models.Sum('num_downvotes'),
        question_views=models.Sum('question_views'),
        time_on_site=models.Sum('time_on_site'),
    )

    daily_user_summaries = daily_user_summaries.order_by(data['order_by'])
    search_params = {}
    if data['query']:
        search_params['query'] = data['query']

    search_params['sort_by'] = data['sort_by']
    search_params['sort_order'] = data['sort_order']
    users_data, paginator_context = get_paginated_list(request,
                                                       daily_user_summaries,
                                                       20,
                                                       search_params or None)

    data['users'] = users_data
    data['paginator_context'] = paginator_context
    data['segment_slug'] = segment_slug
    data['segment_name'] = segment_name
    data['is_named_segment'] = is_named_segment
    if is_named_segment:
        data['group_name'] = segment_name
    else:
        assert len(group_ids) == 1
        group = Group.objects.get(id=group_ids[0])
        data['group_name'] = group.name
        data['org_id'] = group.id

    data['date_selector_url_func'] = get_date_selector_url_func('analytics_users',
                                                                users_segment=data['users_segment'])

    return render(request, 'analytics/per_user_in_group_stats.html', data)


def analytics_users(request, dates='all-time', users_segment='all-users'):
    """User analytics page"""

    if not request.user.is_authenticated or not request.user.is_admin_or_mod():
        return HttpResponseForbidden()

    earliest_summary = DailyGroupSummary.objects.order_by('date').first() # pylint: disable=no-member
    query_data = request.GET.copy()
    query_data.update({'dates': dates, 'users_segment': users_segment})
    users_form = AnalyticsUsersForm(query_data, earliest_possible_date=earliest_summary.date)

    if not users_form.is_valid():
        escaped_range = escape(dates)
        message = _('Date range {range} is invalid.').format(range=escaped_range)
        request.user.message_set.create(message=message)
        return HttpResponseRedirect(reverse('analytics_users',
                                            kwargs={'dates': 'all-time',
                                                    'users_segment': 'all-users'}))

    start_date, end_date = users_form.cleaned_data['dates']
    users_segment = users_form.cleaned_data['users_segment']
    data = {
        'start_date': start_date,
        'end_date': end_date,
        'users_segment': users_segment,
        'dates_url_param': dates,
        'query': users_form.cleaned_data['query'],
        'order_by': users_form.cleaned_data['order_by'],
        'sort_by': users_form.cleaned_data['sort_by'],
        'sort_order': users_form.cleaned_data['sort_order']
    }
    if users_segment == 'all-users':
        return non_routed_per_segment_stats(request, data)

    if analytics_utils.is_named_segment(users_segment):
        segment_config = analytics_utils.get_named_segment_config_by_slug(users_segment)
        return non_routed_per_user_in_group_stats(
            request,
            data,
            group_ids=segment_config['group_ids'],
            segment_slug=users_segment,
            segment_name=segment_config['name'],
            is_named_segment=True
        )

    if users_segment == django_settings.ASKBOT_ANALYTICS_DEFAULT_SEGMENT['slug']:
        return non_routed_per_group_in_segment_stats(request, data)

    if users_segment.startswith('group:'):
        group_id = int(users_segment.split(':')[1])
        default_segment_config = django_settings.ASKBOT_ANALYTICS_DEFAULT_SEGMENT
        return non_routed_per_user_in_group_stats(
            request,
            data,
            group_ids=[group_id],
            segment_slug=default_segment_config['slug'],
            segment_name=default_segment_config['name']
        )

    raise ValueError(f"Invalid users segment: {users_segment}")
