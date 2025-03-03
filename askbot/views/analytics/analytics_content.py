from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.urls import reverse
from askbot.forms import AnalyticsContentForm
from askbot.models.analytics import DailyGroupSummary, Event
from askbot.utils.functions import get_paginated_list
from askbot.views.analytics.utils import get_date_selector_url_func, filter_events_by_users_segment

CONTENT_EVENT_TYPES = [
    Event.EVENT_TYPE_ASKED,
    Event.EVENT_TYPE_ANSWERED,
    Event.EVENT_TYPE_QUESTION_COMMENTED,
    Event.EVENT_TYPE_ANSWER_COMMENTED,
]

COMMENT_EVENT_TYPES = [
    Event.EVENT_TYPE_QUESTION_COMMENTED,
    Event.EVENT_TYPE_ANSWER_COMMENTED,
]

def get_event_types(content_segment):
    if content_segment == 'questions':
        return [Event.EVENT_TYPE_ASKED]
    elif content_segment == 'answers':
        return [Event.EVENT_TYPE_ANSWERED]
    elif content_segment == 'comments':
        return COMMENT_EVENT_TYPES
    return CONTENT_EVENT_TYPES

def analytics_content(request, content_segment='all', users_segment='all', dates='all-time'):
    """analytics content page"""
    earliest_summary = DailyGroupSummary.objects.order_by('date').first() # pylint: disable=no-member
    form = AnalyticsContentForm({
        'content_segment': content_segment,
        'users_segment': users_segment,
        'dates': dates
    }, earliest_possible_date=earliest_summary.date)

    if not form.is_valid():
        return HttpResponseRedirect(reverse('analytics_content', kwargs={'content_segment': 'all', 'users_segment': 'all', 'dates': 'all-time'}))

    start_date = form.cleaned_data['dates'][0]
    end_date = form.cleaned_data['dates'][1]

    events = Event.objects.filter(timestamp__gte=start_date, timestamp__lte=end_date)
    events = events.filter(event_type__in=CONTENT_EVENT_TYPES)
    events = events.order_by('-timestamp')

    questions_count = events.filter(event_type=Event.EVENT_TYPE_ASKED).count()
    answers_count = events.filter(event_type=Event.EVENT_TYPE_ANSWERED).count()
    comments_count = events.filter(event_type__in=COMMENT_EVENT_TYPES).count()

    events = events.filter(event_type__in=get_event_types(content_segment))
    events = filter_events_by_users_segment(events, users_segment)
    events = events.select_related('session__user').prefetch_related('content_object')
    content_events, paginator_context = get_paginated_list(request, events, 20)

    data = {
        'content_events': content_events,
        'paginator_context': paginator_context,
        'questions_count': questions_count,
        'answers_count': answers_count,
        'comments_count': comments_count,
        'start_date': start_date,
        'end_date': end_date,
        'content_segment': content_segment,
        'users_segment': users_segment,
        'dates': dates,
        'date_selector_url_func': get_date_selector_url_func('analytics_content',
                                                             content_segment=content_segment,
                                                             users_segment=users_segment)
    }

    return render(request, 'analytics/analytics_content.html', data)
