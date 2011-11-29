from django.http import HttpResponseRedirect
from django.utils.translation import ugettext as _
from django.conf import settings
from django.core.urlresolvers import resolve

from askbot.conf import settings as askbot_settings

PROTECTED_URLS = [
    'about',
    'feeds',
    'privacy',
    'tags',
    'badges',
    'questions',
    'question',
    'question_revisions',
    'users',
    'edit_user',
    'faq',
    'user_profile',
    'answer_revisions',
    'user_subscriptions',
    'widget_questions']


class ForumModeMiddleware(object):

    def process_request(self, request):
        if (askbot_settings.ASKBOT_CLOSED_FORUM_MODE
                and request.user.is_anonymous()
                and resolve(request.path).url_name in PROTECTED_URLS):
            request.user.message_set.create(_('Please log in to use %s') % \
                askbot_settings.APP_SHORT_NAME)
            return HttpResponseRedirect(settings.LOGIN_URL)
        else:
            return None
