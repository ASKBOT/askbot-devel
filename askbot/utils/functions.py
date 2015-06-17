import datetime
import re
import random
import time
from django.utils.translation import ugettext as _
from django.utils.translation import ungettext
from django.utils.html import escape
from django.utils import six
from django.utils.functional import lazy
from django.utils.safestring import mark_safe


mark_safe_lazy = lazy(mark_safe, six.text_type)


def timedelta_total_seconds(td):
    """returns total seconds for the timedelta object
    supports python < 2.7
    """
    if hasattr(td, 'total_seconds'):
        return td.total_seconds()
    from future import __division__
    return (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6


def get_epoch_str(dt):
    """returns epoch as string to datetime"""
    return str(int(time.mktime(dt.timetuple())))


def get_from_dict_or_object(source, key):
    try:
        return source[key]
    except:
        return getattr(source, key)


def enumerate_string_list(strings):
    """for a list or a tuple ('one', 'two',) return
    a list formatted as ['1) one', '2) two',]
    """
    numbered_strings = enumerate(strings, start = 1)
    return [ '%d) %s' % item for item in numbered_strings ]


def format_setting_name(token):
    token = token.replace(' ', '_')
    token = token.replace('-', '_')
    bits = token.split('_')
    return '_'.join(bits).upper()


def pad_string(text):
    """Inserts one space between words,
    including one space before the first word
    and after the last word.
    String without words is collapsed to ''
    """
    words = text.strip().split()
    if len(words) > 0:
        return ' ' + ' '.join(words) + ' '
    else:
        return ''

def split_list(text):
    """Takes text, representing a loosely formatted
    list (comma, semicolon, empty space separated
    words) and returns a list() of words.
    """
    text = text.replace(',', ' ').replace(';', ' ')
    return text.strip().split()

def split_phrases(text):
    """splits text by semicolon (;), comma(,) and
    end of line
    """
    text = text.replace(';', ',').replace('\n', ',')
    return map(lambda v: v.strip(), text.split(','))

def is_iterable(thing):
    if hasattr(thing, '__iter__'):
        return True
    else:
        return isinstance(thing, basestring)

BOT_REGEX = re.compile(
    r'bot|http|\.com|crawl|spider|python|curl|yandex'
)
BROWSER_REGEX = re.compile(
    r'^(Mozilla.*(Gecko|KHTML|MSIE|Presto|Trident)|Opera).*$'
)
MOBILE_REGEX = re.compile(
    r'(BlackBerry|HTC|LG|MOT|Nokia|NOKIAN|PLAYSTATION|PSP|SAMSUNG|SonyEricsson)'
)


def strip_plus(text):
    """returns text with redundant spaces replaced with just one,
    and stripped leading and the trailing spaces"""
    return re.sub('\s+', ' ', text).strip()


def not_a_robot_request(request):

    if 'HTTP_ACCEPT_LANGUAGE' not in request.META:
        return False

    user_agent = request.META.get('HTTP_USER_AGENT', None)
    if user_agent is None:
        return False

    if BOT_REGEX.match(user_agent, re.IGNORECASE):
        return False

    if MOBILE_REGEX.match(user_agent):
        return True

    if BROWSER_REGEX.search(user_agent):
        return True

    return False

def diff_date(date, use_on_prefix = False):
    now = datetime.datetime.now()#datetime(*time.localtime()[0:6])#???
    diff = now - date
    days = diff.days
    hours = int(diff.seconds/3600)
    minutes = int(diff.seconds/60)

    if days > 2:
        if date.year == now.year:
            date_token = date.strftime("%b %d")
        else:
            date_token = date.strftime("%b %d '%y")
        if use_on_prefix:
            return _('on %(date)s') % { 'date': date_token }
        else:
            return date_token
    elif days == 2:
        return _('2 days ago')
    elif days == 1:
        return _('yesterday')
    elif minutes >= 60:
        return ungettext(
            '%(hr)d hour ago',
            '%(hr)d hours ago',
            hours
        ) % {'hr':hours}
    else:
        return ungettext(
            '%(min)d min ago',
            '%(min)d mins ago',
            minutes
        ) % {'min':minutes}

#todo: this function may need to be removed to simplify the paginator functionality
LEADING_PAGE_RANGE_DISPLAYED = TRAILING_PAGE_RANGE_DISPLAYED = 5
LEADING_PAGE_RANGE = TRAILING_PAGE_RANGE = 4
NUM_PAGES_OUTSIDE_RANGE = 1
ADJACENT_PAGES = 2
def setup_paginator(context):
    """
    custom paginator tag
    Inspired from http://blog.localkinegrinds.com/2007/09/06/digg-style-pagination-in-django/
    """
    if (context["is_paginated"]):
        " Initialize variables "
        in_leading_range = in_trailing_range = False
        pages_outside_leading_range = pages_outside_trailing_range = range(0)

        if (context["pages"] <= LEADING_PAGE_RANGE_DISPLAYED):
            in_leading_range = in_trailing_range = True
            page_numbers = [n for n in range(1, context["pages"] + 1) if n > 0 and n <= context["pages"]]
        elif (context["current_page_number"] <= LEADING_PAGE_RANGE):
            in_leading_range = True
            page_numbers = [n for n in range(1, LEADING_PAGE_RANGE_DISPLAYED + 1) if n > 0 and n <= context["pages"]]
            pages_outside_leading_range = [n + context["pages"] for n in range(0, -NUM_PAGES_OUTSIDE_RANGE, -1)]
        elif (context["current_page_number"] > context["pages"] - TRAILING_PAGE_RANGE):
            in_trailing_range = True
            page_numbers = [n for n in range(context["pages"] - TRAILING_PAGE_RANGE_DISPLAYED + 1, context["pages"] + 1) if n > 0 and n <= context["pages"]]
            pages_outside_trailing_range = [n + 1 for n in range(0, NUM_PAGES_OUTSIDE_RANGE)]
        else:
            page_numbers = [n for n in range(context["current_page_number"] - ADJACENT_PAGES, context["current_page_number"] + ADJACENT_PAGES + 1) if n > 0 and n <= context["pages"]]
            pages_outside_leading_range = [n + context["pages"] for n in range(0, -NUM_PAGES_OUTSIDE_RANGE, -1)]
            pages_outside_trailing_range = [n + 1 for n in range(0, NUM_PAGES_OUTSIDE_RANGE)]

        page_object = context['page_object']
        #patch for change in django 1.5
        if page_object.has_previous():
            previous_page_number = page_object.previous_page_number()
        else:
            previous_page_number = None

        if page_object.has_next():
            next_page_number = page_object.next_page_number()
        else:
            next_page_number = None

        return {
            "base_url": escape(context["base_url"]),
            "is_paginated": context["is_paginated"],
            "previous": previous_page_number,
            "has_previous": page_object.has_previous(),
            "next": next_page_number,
            "has_next": page_object.has_next(),
            "page": context["current_page_number"],
            "pages": context["pages"],
            "page_numbers": page_numbers,
            "in_leading_range" : in_leading_range,
            "in_trailing_range" : in_trailing_range,
            "pages_outside_leading_range": pages_outside_leading_range,
            "pages_outside_trailing_range": pages_outside_trailing_range,
        }

def get_admin():
    """Returns an admin users, usefull for raising flags"""
    try:
        from django.contrib.auth.models import User
        return User.objects.filter(is_superuser=True)[0]
    except:
        raise Exception('there is no admin users')

def generate_random_key(length=16):
    """return random string, length is number of characters"""
    random.seed()
    assert(isinstance(length, int))
    format_string = '%0' + str(2*length) + 'x'
    return format_string % random.getrandbits(length*8)
