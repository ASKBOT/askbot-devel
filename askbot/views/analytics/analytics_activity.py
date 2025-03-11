from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from askbot.forms import (
    AnalyticsActivityForm,
    AnalyticsActivityField,
    AnalyticsContentField
)
from askbot.models import User, Group
from askbot.models.analytics import DailyGroupSummary, Event
from askbot.utils.functions import get_paginated_list
from askbot.utils.analytics_utils import get_named_segment_config_by_group_id, get_segment_name
from askbot.views.analytics.utils import (
    get_date_selector_url_func,
    filter_events_by_users_segment,
    filter_events_by_content_segment
)


def get_activity_segment_breadcrumb(activity_segment, dates):
    """get breadcrumb for activity segment"""
    return {
        'url': reverse('analytics_activity', kwargs={'activity_segment': activity_segment, 'content_segment': 'all-content', 'users_segment': 'all-users', 'dates': dates}),
        'name': AnalyticsActivityField.get_field_display(activity_segment)
    }


def get_content_segment_breadcrumb(activity_segment, content_segment, dates):
    """get breadcrumb for content segment"""
    return {
        'url': reverse('analytics_activity', kwargs={'activity_segment': activity_segment, 'content_segment': content_segment, 'users_segment': 'all-users', 'dates': dates}),
        'name': AnalyticsContentField.get_field_display(content_segment)
    }


def get_users_segment_name(users_segment):
    """get name for users segment"""
    if users_segment == 'all-users':
        return _('All Users')
    return get_segment_name(users_segment)


def get_named_segment_breadcrumb(named_segment_config, dates):
    """get breadcrumb for named segment"""
    return {
        'url': reverse('analytics_activity',
                    kwargs={'activity_segment': 'all-activity',
                            'content_segment': 'all-content',
                            'users_segment': named_segment_config['slug'],
                            'dates': dates}),
        'name': named_segment_config['name']
    }


def get_user_breadcrumb(user, dates):
    """get breadcrumb for user"""
    return {
        'url': reverse('analytics_activity',
                        kwargs={'activity_segment': 'all-activity',
                                'content_segment': 'all-content',
                                'users_segment': 'user:' + str(user.id),
                                'dates': dates}),
        'name': user.username
    }

def get_group_breadcrumb(group, dates):
    """get breadcrumb for group"""
    return {
        'url': reverse('analytics_activity',
                        kwargs={'activity_segment': 'all-activity',
                                'content_segment': 'all-content',
                                'users_segment': 'group:' + str(group.id),
                                'dates': dates}),
        'name': group.name
    }


def get_default_segment_breadcrumb(dates):   
    """get breadcrumb for default segment"""
    return {
        'url': reverse('analytics_activity',
                        kwargs={'activity_segment': 'all-activity',
                                'content_segment': 'all-content',
                                'users_segment': 'all-users',
                                'dates': dates}),
        'name': _('All Users')
    }


def get_users_segment_breadcrumbs(activity_segment, content_segment, users_segment, dates):
    """get breadcrumbs for users segment"""
    url = reverse('analytics_activity',
                  kwargs={'activity_segment': activity_segment,
                          'content_segment': content_segment,
                          'users_segment': users_segment,
                          'dates': dates})

    users_segment_name = None
    if users_segment == 'all-users':
        users_segment_name = _('All Users')
    else:
        users_segment_name = get_segment_name(users_segment)

    if users_segment_name:
        return [{'url': url, 'name': users_segment_name}]

    if users_segment.startswith('user:'):
        # get first analytics group to which this user belongs
        user = User.objects.get(id=users_segment.split(':')[1])
        group = user.get_groups(used_for_analytics=True).first()

        if not group:
            return [{'url': url, 'name': user.username}]

        named_segment_config = get_named_segment_config_by_group_id(group.id)
        if named_segment_config:
            return [
                get_named_segment_breadcrumb(named_segment_config, dates),
                get_user_breadcrumb(user, dates)
            ]

        return [
            get_default_segment_breadcrumb(dates),
            get_group_breadcrumb(group, dates),
            get_user_breadcrumb(user, dates)
        ]

    if users_segment.startswith('group:'):
        group = Group.objects.get(id=users_segment.split(':')[1])
        named_segment_config = get_named_segment_config_by_group_id(group.id)
        if named_segment_config:
            return [get_named_segment_breadcrumb(named_segment_config, dates)]

        return [
            get_default_segment_breadcrumb(dates),
            get_group_breadcrumb(group, dates)
        ]
                
    return []

def get_breadcrumbs(activity_segment, content_segment, users_segment, dates):
    """get breadcrumbs for analytics activity page
    """
    breadcrumbs = [
        {
            'url': reverse('analytics_index'),
            'name': _('Analytics')
        },
        get_activity_segment_breadcrumb(activity_segment, dates),
        get_content_segment_breadcrumb(activity_segment, content_segment, dates),
    ]
    breadcrumbs.extend(get_users_segment_breadcrumbs(activity_segment, content_segment, users_segment, dates))
    return breadcrumbs


def analytics_activity(request, activity_segment=None, content_segment=None, users_segment=None, dates=None):
    """analytics activity page"""
    earliest_summary = DailyGroupSummary.objects.order_by('date').first() # pylint: disable=no-member
    form = AnalyticsActivityForm({
        'activity_segment': activity_segment,
        'content_segment': content_segment,
        'users_segment': users_segment,
        'dates': dates
    }, earliest_possible_date=earliest_summary.date)

    if not form.is_valid():
        default_params = {
            'activity_segment': 'all-activity',
            'content_segment': 'all-content',
            'users_segment': 'all-users',
            'dates': 'all-time'
        }
        return HttpResponseRedirect(reverse('analytics_activity', kwargs=default_params))

    event_types = form.cleaned_data['activity_segment']
    users_url_segment = form.cleaned_data['users_segment']
    start_date, end_date = form.cleaned_data['dates']

    events = Event.objects.filter(timestamp__gte=start_date, timestamp__lte=end_date)
    events = events.order_by('-timestamp')
    events = filter_events_by_content_segment(events, content_segment)
    events = filter_events_by_users_segment(events, users_segment)
    events = events.filter(event_type__in=event_types)
    events, paginator_context = get_paginated_list(request, events, 20)

    data = {
        'Event': Event,
        'events': events,
        'event_types': event_types,
        'users_url_segment': users_url_segment,
        'dates': dates,
        'start_date': start_date,
        'end_date': end_date,
        'paginator_context': paginator_context,
        'breadcrumbs': get_breadcrumbs(activity_segment,
                                       content_segment,
                                       users_url_segment,
                                       dates),
        'date_selector_url_func': get_date_selector_url_func('analytics_activity',
                                                             content_segment=content_segment,
                                                             activity_segment=activity_segment,
                                                             users_segment=users_url_segment)
    }

    return render(request, 'analytics/analytics_activity.html', data)