"""Askbot analytics views"""
from datetime import timedelta
from django.conf import settings as django_settings
from django.db import models
from django.shortcuts import render, HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.html import escape
from askbot.forms import AnalyticsDatesForm
from askbot.models import User, Group
from askbot.models.analytics import (get_non_admins_count,
                                     get_organizations_count,
                                     Event,
                                     DailyGroupSummary)

def analytics_index(request):
    """analytics home page"""
    return render(request, 'analytics/index.html')


def analytics_users(request, dates='all-time'):
    """User analytics page"""
    non_admins_slice = django_settings.ASKBOT_ANALYTICS_NON_ADMINS_SLICE_DESCRIPTION
    data = {'all_users_count': User.objects.exclude(askbot_profile__status='b').count(),
            'non_admins_count': get_non_admins_count(),
            'non_admins_slice_name': django_settings.ASKBOT_ANALYTICS_NON_ADMINS_SLICE_NAME,
            'non_admins_slice_description': non_admins_slice}

    vip_groups = Group.objects.filter(group_ptr__id__in=django_settings.ASKBOT_ANALYTICS_VIP_GROUP_IDS)
    vip_summaries = DailyGroupSummary.objects.filter(group__in=vip_groups) # pylint: disable=no-member
    vip_summaries = vip_summaries.order_by('-date')
    earliest_summary = vip_summaries.last()

    dates_form = AnalyticsDatesForm({'dates': dates}, earliest_possible_date=earliest_summary.date)
    if not dates_form.is_valid():
        escaped_range = escape(dates)
        request.user.message_set.create(message=_('Date range {range} is invalid.').format(range=escaped_range))
        return HttpResponseRedirect(reverse('analytics_users', kwargs={'dates': 'all-time'}))

    start_date, end_date = dates_form.cleaned_data['dates']

    vip_summaries = vip_summaries.filter(date__gt=start_date, date__lte=end_date)
    customer_summaries = DailyGroupSummary.objects.filter(date__gt=start_date, date__lte=end_date) # pylint: disable=no-member
    customer_summaries = customer_summaries.exclude(id__in=vip_summaries.values_list('id', flat=True))

    def get_aggregated_data(summaries):
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
        first_summary = summaries.order_by('date').first()
        data['num_users'] = first_summary.num_users if first_summary else 0
        return data

    data['vip_data'] = get_aggregated_data(vip_summaries)
    data['customer_data'] = get_aggregated_data(customer_summaries)
    data['start_date'] = start_date
    data['end_date'] = end_date
    data['dates_url_param'] = dates

    if django_settings.ASKBOT_ANALYTICS_EMAIL_DOMAIN_ORGANIZATIONS_ENABLED:
        data['orgs_count'] = get_organizations_count()
        data['orgs_enabled'] = True
    return render(request, 'analytics/users.html', data)
