import datetime
import re
import time
from coffin import template as coffin_template
from django.core import exceptions as django_exceptions
from django.utils.translation import ugettext as _
from django.contrib.humanize.templatetags import humanize
from django.template import defaultfilters
from django.core.urlresolvers import reverse, resolve
from django.http import Http404
from askbot import exceptions as askbot_exceptions
from askbot import auth
from askbot.conf import settings as askbot_settings
from askbot.skins import utils as skin_utils
from askbot.utils import functions
from askbot.utils.slug import slugify
from askbot.shims.django_shims import ResolverMatch

from django_countries import countries
from django_countries import settings as countries_settings

register = coffin_template.Library()

def absolutize_urls_func(text):
    url_re1 = re.compile(r'(?P<prefix><img[^<]+src=)"(?P<url>/[^"]+)"', re.I)
    url_re2 = re.compile(r"(?P<prefix><img[^<]+src=)'(?P<url>/[^']+)'", re.I)
    url_re3 = re.compile(r'(?P<prefix><a[^<]+href=)"(?P<url>/[^"]+)"', re.I)
    url_re4 = re.compile(r"(?P<prefix><a[^<]+href=)'(?P<url>/[^']+)'", re.I)
    replacement = '\g<prefix>"%s\g<url>"' % askbot_settings.APP_URL
    text = url_re1.sub(replacement, text)
    text = url_re2.sub(replacement, text)
    text = url_re3.sub(replacement, text)
    return url_re4.sub(replacement, text)
absolutize_urls = register.filter(absolutize_urls_func)

@register.filter
def clean_login_url(url):
    """pass through, unless user was originally on the logout page"""
    try:
        resolver_match = ResolverMatch(resolve(url))
        from askbot.views.readers import question
        if resolver_match.func == question:
            return url
    except Http404:
        pass
    return reverse('index')

@register.filter
def country_display_name(country_code):
    country_dict = dict(countries.COUNTRIES)
    return country_dict[country_code]

@register.filter
def country_flag_url(country_code):
    return countries_settings.FLAG_URL % country_code

@register.filter
def collapse(input):
    input = unicode(input)
    return ' '.join(input.split())

@register.filter
def split(string, separator):
    return string.split(separator)

@register.filter
def get_age(birthday):
    current_time = datetime.datetime(*time.localtime()[0:6])
    year = birthday.year
    month = birthday.month
    day = birthday.day
    diff = current_time - datetime.datetime(year,month,day,0,0,0)
    return diff.days / 365

@register.filter
def media(url):
    """media filter - same as media tag, but
    to be used as a filter in jinja templates
    like so {{'/some/url.gif'|media}}
    """
    if url:
        return skin_utils.get_media_url(url)
    else:
        return ''

@register.filter
def fullmedia(url):
    domain = askbot_settings.APP_URL
    #protocol = getattr(settings, "PROTOCOL", "http")
    path = media(url)
    return "%s%s" % (domain, path)

diff_date = register.filter(functions.diff_date)

setup_paginator = register.filter(functions.setup_paginator)

slugify = register.filter(slugify)

register.filter(
            name = 'intcomma',
            filter_func = humanize.intcomma,
            jinja2_only = True
        )

register.filter(
            name = 'urlencode',
            filter_func = defaultfilters.urlencode,
            jinja2_only = True
        )

register.filter(
            name = 'linebreaks',
            filter_func = defaultfilters.linebreaks,
            jinja2_only = True
        )

register.filter(
            name = 'default_if_none',
            filter_func = defaultfilters.default_if_none,
            jinja2_only = True
        )

def make_template_filter_from_permission_assertion(
                                assertion_name = None,
                                filter_name = None,
                                allowed_exception = None
                            ):
    """a decorator-like function that will create a True/False test from
    permission assertion
    """
    def filter_function(user, post):

        if askbot_settings.ALWAYS_SHOW_ALL_UI_FUNCTIONS:
            return True

        if user.is_anonymous():
            return False

        assertion = getattr(user, assertion_name)
        if allowed_exception:
            try:
                assertion(post)
                return True
            except allowed_exception:
                return True
            except django_exceptions.PermissionDenied:
                return False
        else:
            try:
                assertion(post)
                return True
            except django_exceptions.PermissionDenied:
                return False

    register.filter(filter_name, filter_function)
    return filter_function


@register.filter
def can_moderate_user(user, other_user):
    if user.is_authenticated() and user.can_moderate_user(other_user):
        return True
    return False

can_flag_offensive = make_template_filter_from_permission_assertion(
                        assertion_name = 'assert_can_flag_offensive',
                        filter_name = 'can_flag_offensive',
                    )

can_remove_flag_offensive = make_template_filter_from_permission_assertion(
                        assertion_name = 'assert_can_remove_flag_offensive',
                        filter_name = 'can_remove_flag_offensive',
                    )

can_remove_all_flags_offensive = make_template_filter_from_permission_assertion(
                        assertion_name = 'assert_can_remove_all_flags_offensive',
                        filter_name = 'can_remove_all_flags_offensive',
                    )

can_post_comment = make_template_filter_from_permission_assertion(
                        assertion_name = 'assert_can_post_comment',
                        filter_name = 'can_post_comment'
                    )

can_edit_comment = make_template_filter_from_permission_assertion(
                        assertion_name = 'assert_can_edit_comment',
                        filter_name = 'can_edit_comment'
                    )

can_close_question = make_template_filter_from_permission_assertion(
                        assertion_name = 'assert_can_close_question',
                        filter_name = 'can_close_question'
                    )

can_delete_comment = make_template_filter_from_permission_assertion(
                        assertion_name = 'assert_can_delete_comment',
                        filter_name = 'can_delete_comment'
                    )

#this works for questions, answers and comments
can_delete_post = make_template_filter_from_permission_assertion(
                        assertion_name = 'assert_can_delete_post',
                        filter_name = 'can_delete_post'
                    )

can_reopen_question = make_template_filter_from_permission_assertion(
                        assertion_name = 'assert_can_reopen_question',
                        filter_name = 'can_reopen_question'
                    )

can_edit_post = make_template_filter_from_permission_assertion(
                        assertion_name = 'assert_can_edit_post',
                        filter_name = 'can_edit_post'
                    )

can_retag_question = make_template_filter_from_permission_assertion(
                        assertion_name = 'assert_can_retag_question',
                        filter_name = 'can_retag_question'
                    )

can_accept_best_answer = make_template_filter_from_permission_assertion(
                        assertion_name = 'assert_can_accept_best_answer',
                        filter_name = 'can_accept_best_answer'
                    )

@register.filter
def can_see_offensive_flags(user, post):
    """Determines if a User can view offensive flag counts.
    there is no assertion like this User.assert_can...
    so all of the code is here

    user can see flags on own posts
    otherwise enough rep is required
    or being a moderator or administrator

    suspended or blocked users cannot see flags
    """
    if user.is_authenticated():
        if user == post.get_owner():
            return True
        if user.reputation >= askbot_settings.MIN_REP_TO_VIEW_OFFENSIVE_FLAGS:
            return True
        elif user.is_administrator() or user.is_moderator():
            return True
        else:
            return False
    else:
        return False

@register.filter
def cnprog_intword(number):
    try:
        if 1000 <= number < 10000:
            string = str(number)[0:1]
            return '<span class="thousand">%sk</span>' % string
        else:
            return number
    except:
        return number

@register.filter
def humanize_counter(number):
    if number == 0:
        return _('no items in counter')
    elif number >= 1000:
        number = number/1000
        s = '%.1f' % number
        if s.endswith('.0'):
            return s[:-2] + 'k'
        else:
            return s + 'k'
    else:
        return str(number)

@register.filter
def absolute_value(number):
    return abs(number)
