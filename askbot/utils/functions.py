"""Utility functions"""
import datetime
import os
import re
import random
from typing import List

import json
import textwrap
import time
import warnings
import zlib
import zipfile
import jwt
from urllib.parse import urlencode
from django.conf import settings as django_settings
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.core.validators import validate_email
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django.utils.html import escape
from django.utils.functional import lazy
from django.utils.safestring import mark_safe
from django import forms

mark_safe_lazy = lazy(mark_safe, str) #pylint: disable=invalid-name

def decode_and_loads(input_str):
    """utf-8 decodes the input, then runs json loads"""
    return json.loads(input_str.decode('utf-8'))


def decode_jwt(data_jwt):
    """Decodes the jwt with the SECRET_KEY, returns a dict"""
    return jwt.decode(data_jwt, django_settings.SECRET_KEY)


def encode_jwt(data):
    """Encodes dict as jwt with the SECRET_KEY"""
    return jwt.encode(data, django_settings.SECRET_KEY).decode('utf-8')


def is_email_valid(email):
    """Returns `True` if email is valid"""
    try:
        validate_email(email)
    except forms.ValidationError:
        return False
    return True


def get_emails(text):
    words = text.split()
    return [word for word in words if is_email_valid(word)]



def timedelta_total_seconds(time_delta):
    """returns total seconds for the timedelta object
    supports python < 2.7
    """
    if hasattr(time_delta, 'total_seconds'):
        return time_delta.total_seconds()
    # pylint: disable=line-too-long
    return (time_delta.microseconds + (time_delta.seconds + time_delta.days * 24 * 3600) * 10**6) / 10**6


def get_epoch_str(date_time):
    """returns epoch as string to datetime"""
    return str(int(time.mktime(date_time.timetuple())))


def get_from_dict_or_object(source, key):
    """Returns either object attribute or dictionary value
    by key"""
    try:
        return source[key]
    except:
        return getattr(source, key)


def enumerate_string_list(strings):
    """for a list or a tuple ('one', 'two',) return
    a list formatted as ['1) one', '2) two',]
    """
    numbered_strings = enumerate(strings, start=1)
    return ['%d) %s' % item for item in numbered_strings]


def format_setting_name(token):
    """Returns string in style in upper case
    with underscores to separate words"""
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
    if words:
        return ' ' + ' '.join(words) + ' '
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
    return [word.strip() for word in text.split(',')]

def is_iterable(thing):
    #pylint: disable=missing-docstring
    if hasattr(thing, '__iter__'):
        return True
    return isinstance(thing, str)

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
    return re.sub(r'\s+', ' ', text).strip()


def not_a_robot_request(request):
    """`True` if the best guess is that request is not a robot"""

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

def diff_date(date, use_on_prefix=False):
    """Gives human friendly label for difference in dates"""
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
            return _('on %(date)s') % {'date': date_token}
        return date_token
    elif days == 2:
        return _('2 days ago')
    elif days == 1:
        return _('yesterday')
    elif minutes >= 60:
        return ngettext(
            '%(hr)d hour ago',
            '%(hr)d hours ago',
            hours
        ) % {'hr':hours}
    else:
        return ngettext(
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
    """custom paginator tag
    Inspired from http://blog.localkinegrinds.com/2007/09/06/digg-style-pagination-in-django/
    """
    #pylint: disable=line-too-long
    if context["is_paginated"]:
        # initialize variables
        in_leading_range = in_trailing_range = False
        pages_outside_leading_range = pages_outside_trailing_range = list(range(0))

        if context["pages"] <= LEADING_PAGE_RANGE_DISPLAYED:
            in_leading_range = in_trailing_range = True
            page_numbers = [n for n in range(1, context["pages"] + 1) if n > 0 and n <= context["pages"]]
        elif context["current_page_number"] <= LEADING_PAGE_RANGE:
            in_leading_range = True
            page_numbers = [n for n in range(1, LEADING_PAGE_RANGE_DISPLAYED + 1) if n > 0 and n <= context["pages"]]
            pages_outside_leading_range = [n + context["pages"] for n in range(0, -NUM_PAGES_OUTSIDE_RANGE, -1)]
        elif context["current_page_number"] > context["pages"] - TRAILING_PAGE_RANGE:
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

        return {"base_url": escape(context["base_url"]),
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
                "pages_outside_trailing_range": pages_outside_trailing_range}


def get_paginated_list(request, objects, page_size, search_params=None):
    """Returns paginated objects and the paginator context"""
    paginator = Paginator(objects, page_size)
    from askbot.forms import PageField
    page_no = PageField().clean(request.GET.get('page'))

    try:
        page = paginator.page(page_no)
    except (EmptyPage, InvalidPage):
        page = paginator.page(paginator.num_pages)

    paginator_context = setup_paginator({
        'is_paginated' : paginator.num_pages > 1,
        'pages': paginator.num_pages,
        'current_page_number': page_no,
        'page_object': page,
        'base_url' : request.path + '?' + (urlencode(search_params) + '&' if search_params else '')
    })
    return page.object_list, paginator_context

def get_admin():
    """Returns an admin users, usefull for raising flags"""
    try:
        from django.contrib.auth.models import User
        return User.objects.filter(askbot_profile__status='d')[0]
    except:
        raise Exception('there is no admin users')

def generate_random_key(length=16):
    """return random string, length is number of characters"""
    random.seed()
    assert isinstance(length, int)
    format_string = '%0' + str(length) + 'x'
    return format_string % random.getrandbits(length*4)

def list_directory_files(dir_path):
    """Lists all files in the directory,
    including those located inside nested directories,
    returned file paths include the directory paths"""
    file_paths = list()
    def handler(root: str, directories: List[str], file_names: List[str]):
        for file_name in file_names:
            file_path = os.path.join(root, file_name)
            file_paths.append(file_path)
    for elem in os.walk(dir_path):
        handler(*elem)
    return file_paths

def wrap_text_for_email(text, max_line_length=70):
    """Repacks text to fit into email message body"""
    if not text:
        return text
    text = text.replace('\r\n', '\n')
    text = text.replace('\r', '\n')
    text = text.replace('\n', '\r\n')
    return textwrap.fill(text, max_line_length)

def zipzip(zip_path, *args, **kwargs): #pylint: disable=too-many-locals
    """creates or updates the zip file at `zip_path`
    with contents given by the `*args`, which can be
    paths to files and/or directories, glob definitons
    are not supported.

    If the zip file exists, new items will be added to it,
    otherwise the zip file will be newly created.

    If an item added already exists in the zipfile,
    the old item is replaced with the new one.

    If existing file is not zip, raises `ValueError` exception.
    """
    zlib.Z_DEFAULT_COMPRESSION = 9
    exclude_dirs = kwargs.get('exclude_dirs', list())
    exclude_files = kwargs.get('exclude_files', list())
    exclude_dir_types = kwargs.get('exclude_dir_types', list())
    exclude_file_types = kwargs.get('exclude_file_types', list())
    ignore_subpath = kwargs.get('ignore_subpath', '')

    if os.path.exists(zip_path):
        if not zipfile.is_zipfile(zip_path):
            raise ValueError('`zip_path` must be a zip file, if exists')

    with zipfile.ZipFile(zip_path, 'a', zipfile.ZIP_DEFLATED) as zip_file:
        for item in args:
            if os.path.isfile(item):
                if item in exclude_files:
                    continue
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore')
                    if ignore_subpath and item.startswith(ignore_subpath):
                        arcname = item[len(ignore_subpath):]
                        if arcname:
                            zip_file.write(item, arcname)
                        else:
                            zip_file.write(item)
                    else:
                        zip_file.write(item)

            elif os.path.isdir(item):
                for dir_path, _, file_names in os.walk(item):

                    def is_excluded_dir(dname): #pylint: disable=missing-docstring
                        for ex_dir in exclude_dirs:
                            if dname.startswith(ex_dir):
                                my_dl = len(dname)
                                ex_dl = len(ex_dir)
                                return my_dl == ex_dl or dname[ex_dl] == '/'
                        return False

                    if is_excluded_dir(dir_path):
                        continue

                    if any([dir_path.endswith(dirtype) for dirtype in exclude_dir_types]):
                        continue

                    for file_name in file_names:
                        if any([file_name.endswith(filetype) for filetype in exclude_file_types]):
                            continue
                        with warnings.catch_warnings():
                            warnings.simplefilter('ignore')
                            zip_file.write(os.path.join(dir_path, file_name))
