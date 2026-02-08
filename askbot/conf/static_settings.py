from django.conf import settings
from django.utils import timezone
from appconf import AppConf
import os
from askbot import const

if settings.ASKBOT_TRANSLATE_URL:
    from django.utils.translation import pgettext
else:
    pgettext = lambda context, value: value

def default_user_can_manage_admin_tags(user):
    """True, if user can manage admin tags"""
    try:
        if user.is_anonymous:
            return False
        if user.is_administrator_or_moderator():
            return True
    except AttributeError:
        return False

    return False

class AskbotStaticSettings(AppConf):
    ALLOWED_UPLOAD_FILE_TYPES = ('.jpg', '.jpeg', '.gif',
                                '.bmp', '.png', '.tiff')

    AUTO_INIT_BADGES = True
    CAS_USER_FILTER = None
    CAS_USER_FILTER_DENIED_MSG = None
    CAS_GET_USERNAME = None # python path to function
    CAS_GET_EMAIL = None # python path to function
    CUSTOM_BADGES = None # python path to module with badges
    CUSTOM_USER_PROFILE_TAB = None # dict(NAME, SLUG, CONTEXT_GENERATOR
                                   # the latter is path to func with
                                   # variables (request, user)
    DEBUG_INCOMING_EMAIL = False
    EXTRA_SKINS_DIR = None #None or path to directory with skins
    IP_MODERATION_ENABLED = False
    LANGUAGE_MODE = 'single-lang' # 'single-lang', 'url-lang' or 'user-lang'
    MAIN_PAGE_BASE_URL = pgettext('urls', 'questions') + '/'
    MAX_UPLOAD_FILE_SIZE = 1024 * 1024 #result in bytes
    NEW_ANSWER_FORM = None # path to custom form class
    POST_RENDERERS = { # generators of html from source content
            'plain-text': 'askbot.utils.markup.plain_text_input_converter',
            'markdown': 'askbot.utils.markup.markdown_input_converter',
        }

    # only report on updates after this date, useful when
    # enabling delayed email alerts on a site with a lot of content
    # in order to prevent sending too many outdated alerts
    DELAYED_EMAIL_ALERTS_CUTOFF_TIMESTAMP = timezone.datetime.fromtimestamp(0)
    QUESTION_PAGE_BASE_URL = pgettext('urls', 'question') + '/'
    SERVICE_URL_PREFIX = 's/' # prefix for non-UI urls
    SELF_TEST = True # if true - run startup self-test
    SPAM_CHECKER_FUNCTION = 'askbot.spam_checker.akismet_spam_checker.is_spam'
    SPAM_CHECKER_API_KEY = None
    SPAM_CHECKER_API_URL = None
    SPAM_CHECKER_TIMEOUT_SECONDS = 1
    TRANSLATE_URL = True # set true to localize urls
    USER_CAN_MANAGE_ADMIN_TAGS_FUNCTION = default_user_can_manage_admin_tags
    USER_DATA_EXPORT_DIR = const.DEFAULT_USER_DATA_EXPORT_DIR
    USE_LOCAL_FONTS = False
    SEARCH_FRONTEND_SRC_URL = None
    SEARCH_FRONTEND_CSS_URL = None
    WHITELISTED_IPS = tuple() # a tuple of whitelisted ips for moderation
    FEDERATED_LOGIN_EMAIL_EDITABLE = True

    class Meta:
        prefix = 'askbot'

