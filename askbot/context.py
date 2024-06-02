"""Askbot template context processor that makes some parameters
from the django settings, all parameters from the askbot livesettings
and the application available for the templates
"""
import sys
import json
from django.conf import settings
from django.middleware import csrf
from django.urls import reverse
from django.utils import timezone

import askbot
from askbot import api
from askbot import models
from askbot import const
from askbot.conf import settings as askbot_settings
from askbot.search.state_manager import SearchState
from askbot.utils import url_utils
from askbot.utils.slug import slugify
from askbot.utils.html import site_url
from askbot.utils.translation import get_language

def should_show_ask_button(user): #pylint: disable=missing-docstring
    # without groups we always show the ASK button
    if not askbot_settings.GROUPS_ENABLED:
        return True

    # with groups - users must be logged in to ask
    if not user.is_authenticated:
        return False

    # get permission to ask based on the group memberships
    return user.can_post_question()

def make_group_list():
    """Returns list of dictionaries with keys 'name' and 'link'"""
    if not askbot_settings.GROUPS_ENABLED:
        return []
    # calculate context needed to list all the groups
    def _get_group_url(group):
        """calculates url to the group based on its id and name"""
        group_slug = slugify(group['name'])
        return reverse(
            'users_by_group',
            kwargs={'group_id': group['id'], 'group_slug': group_slug})

    # load id's and names of all groups
    global_group = models.Group.objects.get_global_group()
    groups = models.Group.objects.exclude_personal()
    groups = groups.exclude(id=global_group.id)
    groups_data = list(groups.values('id', 'name'))

    # sort groups_data alphanumerically, but case-insensitive
    groups_data = sorted(groups_data, key=lambda x: x['name'].lower())

    # insert data for the global group at the first position
    groups_data.insert(0, {'id': global_group.id, 'name': global_group.name})

    # build group_list for the context
    group_list = []
    for group in groups_data:
        link = _get_group_url(group)
        group_list.append({'name': group['name'], 'link': link})
    return group_list

def application_settings(request):
    """The context processor function"""
    my_settings = askbot_settings.as_dict()
    my_settings['LANGUAGE_CODE'] = getattr(request, 'LANGUAGE_CODE', settings.LANGUAGE_CODE)
    my_settings['LANGUAGE_MODE'] = askbot.get_lang_mode()
    my_settings['MULTILINGUAL'] = askbot.is_multilingual()
    my_settings['LANGUAGES_DICT'] = dict(getattr(settings, 'LANGUAGES', []))
    my_settings['ALLOWED_UPLOAD_FILE_TYPES'] = settings.ASKBOT_ALLOWED_UPLOAD_FILE_TYPES
    my_settings['ASKBOT_URL'] = settings.ASKBOT_URL
    my_settings['STATIC_URL'] = settings.STATIC_URL
    my_settings['STATIC_ROOT'] = settings.STATIC_ROOT
    my_settings['IP_MODERATION_ENABLED'] = getattr(settings, 'ASKBOT_IP_MODERATION_ENABLED', False)
    my_settings['USE_LOCAL_FONTS'] = getattr(settings, 'ASKBOT_USE_LOCAL_FONTS', False)
    my_settings['CSRF_COOKIE_NAME'] = settings.CSRF_COOKIE_NAME
    my_settings['DEBUG'] = settings.DEBUG
    my_settings['USING_RUNSERVER'] = 'runserver' in sys.argv
    my_settings['ASKBOT_VERSION'] = askbot.get_version()
    my_settings['LOGIN_URL'] = url_utils.get_login_url()
    my_settings['LOGOUT_URL'] = url_utils.get_logout_url()
    my_settings['SEARCH_FRONTEND_SRC_URL'] = settings.ASKBOT_SEARCH_FRONTEND_SRC_URL
    my_settings['SEARCH_FRONTEND_CSS_URL'] = settings.ASKBOT_SEARCH_FRONTEND_CSS_URL
    my_settings['LOGOUT_REDIRECT_URL'] = url_utils.get_logout_redirect_url()
    my_settings['FEDERATED_LOGIN_EMAIL_EDITABLE'] = settings.ASKBOT_FEDERATED_LOGIN_EMAIL_EDITABLE

    current_language = get_language()

    # for some languages we will start searching for shorter words
    if current_language == 'ja':
        # we need to open the search box and show info message about
        # the japanese lang search
        min_search_word_length = 1
    else:
        min_search_word_length = my_settings['MIN_SEARCH_WORD_LENGTH']

    need_scope_links = askbot_settings.ALL_SCOPE_ENABLED or \
        askbot_settings.UNANSWERED_SCOPE_ENABLED or \
        (request.user.is_authenticated and askbot_settings.FOLLOWED_SCOPE_ENABLED)

    context = {
        'base_url': site_url(''),
        'csrf_token': csrf.get_token(request),
        'empty_search_state': SearchState.get_empty(),
        'min_search_word_length': min_search_word_length,
        'current_language_code': current_language,
        'settings': my_settings,
        'moderation_items': api.get_info_on_moderation_items(request.user),
        'need_scope_links': need_scope_links,
        'now': timezone.now(),
        'noscript_url': const.DEPENDENCY_URLS['noscript'],
        'show_ask_button': should_show_ask_button(request.user)
    }

    use_askbot_login = 'askbot.deps.django_authopenid' in settings.INSTALLED_APPS
    my_settings['USE_ASKBOT_LOGIN_SYSTEM'] = use_askbot_login
    if use_askbot_login and request.user.is_anonymous:
        from askbot.deps.django_authopenid import context as login_context
        context.update(login_context.login_context(request))

    context['group_list'] = json.dumps(make_group_list())
    return context
