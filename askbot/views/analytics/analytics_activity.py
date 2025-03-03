from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.urls import reverse
from askbot.forms import AnalyticsActivityForm
from askbot.models.analytics import DailyGroupSummary, Event
from askbot.utils.functions import get_paginated_list
from askbot.views.analytics.utils import get_date_selector_url_func, filter_events_by_users_segment

def analytics_activity(request, activity_segment=None, users_segment=None, dates=None):
    """analytics activity page"""
    earliest_summary = DailyGroupSummary.objects.order_by('date').first() # pylint: disable=no-member
    form = AnalyticsActivityForm({
        'activity_segment': activity_segment,
        'users_segment': users_segment,
        'dates': dates
    }, earliest_possible_date=earliest_summary.date)

    if not form.is_valid():
        return HttpResponseRedirect(reverse('analytics_content', kwargs={'content_segment': 'all', 'users_segment': 'all', 'dates': 'all-time'}))

    event_types = form.cleaned_data['activity_segment']
    users_segment = form.cleaned_data['users_segment']
    start_date, end_date = form.cleaned_data['dates']

    events = Event.objects.filter(timestamp__gte=start_date, timestamp__lte=end_date)
    events = events.order_by('-timestamp')
    events = filter_events_by_users_segment(events, users_segment)
    events = events.filter(event_type__in=event_types)
    events, paginator_context = get_paginated_list(request, events, 20)

    data = {
        'Event': Event,
        'events': events,
        'event_types': event_types,
        'users_segment': users_segment,
        'dates': dates,
        'start_date': start_date,
        'end_date': end_date,
        'paginator_context': paginator_context,
        'date_selector_url_func': get_date_selector_url_func('analytics_activity',
                                                             activity_segment=activity_segment,
                                                             users_segment=users_segment)
    }

    return render(request, 'analytics/analytics_activity.html', data)
