import datetime
import pytz
import re
import time
import urllib
from coffin import template as coffin_template
from bs4 import BeautifulSoup
from django.core import exceptions as django_exceptions
from django.utils.translation import ugettext as _
from django.utils.translation import get_language as django_get_language
from django.contrib.humanize.templatetags import humanize
from django.template import defaultfilters
from django.core.urlresolvers import reverse, resolve
from django.http import Http404
from django.utils import simplejson
from django.utils.text import Truncator
from askbot import exceptions as askbot_exceptions
from askbot.conf import settings as askbot_settings
from django.conf import settings as django_settings
from askbot.skins import utils as skin_utils
from askbot.utils.html import absolutize_urls, site_link
from askbot.utils.html import site_url as site_url_func
from askbot.utils import functions
from askbot.utils import url_utils
from askbot.utils.slug import slugify
from askbot.utils.pluralization import py_pluralize as _py_pluralize
from askbot.shims.django_shims import ResolverMatch

from django_countries import countries
from django_countries import settings as countries_settings

register = coffin_template.Library()

absolutize_urls = register.filter(absolutize_urls)

TIMEZONE_STR = pytz.timezone(
                    django_settings.TIME_ZONE
                ).localize(
                    datetime.datetime.now()
                ).strftime('%z')

@register.filter
def add_tz_offset(datetime_object):
    return str(datetime_object) + ' ' + TIMEZONE_STR

@register.filter
def as_js_bool(some_object):
    if bool(some_object):
        return 'true'
    return 'false'

@register.filter
def as_json(data):
    return simplejson.dumps(data)

@register.filter
def is_current_language(lang):
    return lang == django_get_language()

@register.filter
def is_empty_editor_value(value):
    if value == None:
        return True
    if str(value).strip() == '':
        return True
    #tinymce uses a weird sentinel placeholder
    if askbot_settings.EDITOR_TYPE == 'tinymce':
        soup = BeautifulSoup(value, 'html5lib')
        return soup.getText().strip() == ''
    return False

@register.filter
def to_int(value):
    return int(value)

@register.filter
def safe_urlquote(text, quote_plus = False):
    if quote_plus:
        return urllib.quote_plus(text.encode('utf8'))
    else:
        return urllib.quote(text.encode('utf8'))

@register.filter
def show_block_to(block_name, user):
    block = getattr(askbot_settings, block_name)
    if block:
        flag_name = block_name + '_ANON_ONLY'
        require_anon = getattr(askbot_settings, flag_name, False)
        return (require_anon is False) or user.is_anonymous()
    return False

@register.filter
def strip_path(url):
    """removes path part of the url"""
    return url_utils.strip_path(url)

@register.filter
def can_see_private_user_data(viewer, target):
    if viewer.is_authenticated() and viewer.is_administrator_or_moderator():
        #todo: take into account intersection of viewer and target user groups
        return askbot_settings.SHOW_ADMINS_PRIVATE_USER_DATA 
    return False

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
def transurl(url):
    """translate url, when appropriate and percent-
    escape it, that's important, othervise it won't match
    the urlconf"""
    try:
        url.decode('ascii')
    except UnicodeError:
        raise ValueError(
            u'string %s is not good for url - must be ascii' % url
        )
    if getattr(django_settings, 'ASKBOT_TRANSLATE_URL', False):
        return urllib.quote(_(url).encode('utf-8'))
    return url

@register.filter
def truncate_html_post(post_html):
    """truncates html if it is longer than 100 words"""
    post_html = Truncator(post_html).words(5, truncate=' ...', html=True)
    post_html = '<div class="truncated-post">' + post_html
    post_html += '<span class="expander">(<a>' + _('more') + '</a>)</span>'
    post_html += '<div class="clearfix"></div></div>'
    return post_html

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
    return site_url_func(media(url))

@register.filter
def site_url(url):
    return site_url_func(url)

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
                        allowed_exception = askbot_exceptions.DuplicateCommand
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
# Manual Jinja filter registration this leaves can_see_offensive_flags() untouched (unwrapped by decorator),
# which is needed by some tests
register.filter('can_see_offensive_flags', can_see_offensive_flags)

@register.filter
def humanize_counter(number):
    if number == 0:
        return _('no')
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
def py_pluralize(source, count):
    plural_forms = source.strip().split('\n')
    return _py_pluralize(plural_forms, count)

@register.filter
def absolute_value(number):
    return abs(number)

@register.filter
def get_empty_search_state(unused):
    from askbot.search.state_manager import SearchState
    return SearchState.get_empty()

@register.filter
def sub_vars(text, user=None):
    """replaces placeholders {{ USER_NAME }}
    {{ SITE_NAME }}, {{ SITE_LINK }} with relevant values"""
    sitename_re = re.compile(r'\{\{\s*SITE_NAME\s*\}\}')
    sitelink_re = re.compile(r'\{\{\s*SITE_LINK\s*\}\}')

    if user:
        username_re = re.compile(r'\{\{\s*USER_NAME\s*\}\}')
        text = username_re.sub(user.username, text)

    site_name = askbot_settings.APP_SHORT_NAME
    text = sitename_re.sub(site_name, text)
    text = sitelink_re.sub(site_link('index', site_name), text)
    return text
