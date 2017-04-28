from django.conf import settings

if getattr(settings, 'ASKBOT_TRANSLATE_URL', False):
    from django.utils.translation import pgettext
else:
    pgettext = lambda context, value: value
from appconf import AppConf
import os

class AskbotStaticSettings(AppConf):
    ALLOWED_UPLOAD_FILE_TYPES = ('.jpg', '.jpeg', '.gif',
                                '.bmp', '.png', '.tiff')
    CAS_USER_FILTER = None
    CAS_USER_FILTER_DENIED_MSG = None
    CAS_GET_USERNAME = None # python path to function
    CAS_GET_EMAIL = None # python path to function
    CUSTOM_BADGES = None # python path to module with badges
    CUSTOM_USER_PROFILE_TAB = None # dict(NAME, SLUG, CONTENT_GENERATOR
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
            'tinymce': 'askbot.utils.markup.tinymce_input_converter',
        }

    QUESTION_PAGE_BASE_URL = pgettext('urls', 'question') + '/'
    SERVICE_URL_PREFIX = 's/' # prefix for non-UI urls
    SELF_TEST = True # if true - run startup self-test
    TRANSLATE_URL = getattr(settings, 'ASKBOT_TRANSLATE_URL', False) # set true to localize urls
    WHITELISTED_IPS = tuple() # a tuple of whitelisted ips for moderation

    class Meta:
        prefix = 'askbot'


class TinyMCESettings(AppConf):
    COMPRESSOR = True
    SPELLCHECKER = False
    JS_ROOT = os.path.join(settings.STATIC_ROOT, 'default/media/tinymce/')
    JS_URL = settings.STATIC_URL + 'default/media/tinymce/tiny_mce.js'
    DEFAULT_CONFIG = {
        'plugins': 'askbot_imageuploader,askbot_attachment',
        'convert_urls': False,
        'theme': 'advanced',
        'content_css': settings.STATIC_URL + \
                    'default/media/style/tinymce/content.css',
        'force_br_newlines': True,
        'force_p_newlines': False,
        'forced_root_block': '',
        'mode' : 'textareas',
        'oninit': 'TinyMCE.onInitHook',
        'onchange_callback': 'TinyMCE.onChangeHook',
        'plugins': 'askbot_imageuploader,askbot_attachment',
        'theme_advanced_toolbar_location' : 'top',
        'theme_advanced_toolbar_align': 'left',
        'theme_advanced_buttons1': 'bold,italic,underline,|,bullist,numlist,|,undo,redo,|,link,unlink,askbot_imageuploader,askbot_attachment',
        'theme_advanced_buttons2': '',
        'theme_advanced_buttons3' : '',
        'theme_advanced_path': False,
        'theme_advanced_resizing': True,
        'theme_advanced_resize_horizontal': False,
        'theme_advanced_statusbar_location': 'bottom',
        'editor_deselector': 'mceNoEditor',
        'width': '100%',
        'height': '250'
    }


    class Meta:
        prefix = 'tinymce'
