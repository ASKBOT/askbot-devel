from appconf import AppConf
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
if settings.ASKBOT_TRANSLATE_URL:
    from django.utils.translation import pgettext
else:
    def pgettext(_context, value):
        return value

from askbot import const # pylint: disable=wrong-import-position


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

    ALLOWED_HTML_ELEMENTS = ('a', 'abbr', 'acronym', 'address', 'b', 'big',
        'blockquote', 'br', 'caption', 'center', 'cite', 'code', 'col',
        'colgroup', 'dd', 'del', 'dfn', 'dir', 'div', 'dl', 'dt', 'em',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'img', 'ins', 'kbd',
        'li', 'ol', 'p', 'pre', 'q', 's', 'samp', 'small', 'span', 'strike',
        'strong', 'sub', 'sup', 'table', 'tbody', 'td', 'tfoot', 'th', 'thead',
        'tr', 'tt', 'u', 'ul', 'var', 'param')

    ALLOWED_HTML_ATTRIBUTES = {
        'a': ['href', 'title'],
        'abbr': ['title'],
        'acronym': ['title'],
        'td': ['colspan', 'rowspan'],
        'th': ['colspan', 'rowspan'],
        'col': ['span'],
        'colgroup': ['span'],
        'img': ['alt', 'src'],
        'blockquote': ['cite'],
        'del': ['cite', 'datetime'],
        'ins': ['cite', 'datetime'],
        'q': ['cite'],
    }

    AUTO_INIT_BADGES = True

    ANALYTICS_EMAIL_DOMAIN_ORGANIZATIONS_ENABLED = False
    ANALYTICS_ADMINS_FILTER = None # None or a dictionary applied in the Django ORM filter
    ANALYTICS_SESSION_TIMEOUT_MINUTES = 30
    # a list of dictionaries, each dictionary has keys: name, slug, description, group_ids
    # these segments will be ordered the same way they are defined in the list
    ANALYTICS_NAMED_SEGMENTS = []
    # a dictionary with keys: name, slug, description - includes all users except
    # the users belonging to the named segments
    # this segment will be ordered after all named segments
    ANALYTICS_DEFAULT_SEGMENT = {}

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

    class Meta: # pylint: disable=too-few-public-methods
        prefix = 'askbot'
