from akismet import Akismet, APIKeyError, AkismetError
from askbot.conf import settings as askbot_settings
from askbot import get_version
from django.core.exceptions import ImproperlyConfigured
from django.utils.encoding import smart_str
from askbot.utils.html import site_url
from django.core.urlresolvers import reverse
import logging

def akismet_check_spam(text, request):
    """Returns True if spam found, false if not,
    May raise exceptions if something is not right with
    the Akismet account/service/setup"""
    if not askbot_settings.USE_AKISMET:
        return False
    try:
        if askbot_settings.USE_AKISMET and askbot_settings.AKISMET_API_KEY == "":
            raise ImproperlyConfigured('You have not set AKISMET_API_KEY')
        data = {'user_ip': request.META.get('REMOTE_ADDR'),
                'user_agent': request.environ['HTTP_USER_AGENT'],
                'comment_author': smart_str(request.user.username)
                }
        if request.user.is_authenticated():
            data.update({'comment_author_email': request.user.email})

        api = Akismet(
            askbot_settings.AKISMET_API_KEY,
            smart_str(site_url(reverse('questions'))),
            "Askbot/%s" % get_version()
        )
        return api.comment_check(text, data, build_data=False)
    except APIKeyError:
        logging.critical('Akismet Key is missing')
    except AkismetError:
        logging.critical('Akismet error: Invalid Akismet key or Akismet account issue!')
    except Exception, e:
        logging.critical((u'Akismet error: %s' % unicode(e)).encode('utf-8'))
    return False
