"""
Context processor for lightweight session messages.

Time-stamp: <2008-07-19 23:16:19 carljm context_processors.py>

"""
from django.conf import settings as django_settings
from django.utils.encoding import StrAndUnicode

from askbot.user_messages import get_and_delete_messages

def user_messages (request):
    """
    Returns session messages for the current session.

    """
    if not request.path.startswith('/' + django_settings.ASKBOT_URL):
        #todo: a hack, for real we need to remove this middleware
        #and switch to the new-style session messages
        return {}
    messages = request.user.get_and_delete_messages()
    #if request.user.is_authenticated():
    #else:
    #    messages = LazyMessages(request)
    #import inspect
    #print inspect.stack()[1]
    #print messages
    return { 'user_messages': messages }

class LazyMessages (StrAndUnicode):
    """
    Lazy message container, so messages aren't actually retrieved from
    session and deleted until the template asks for them.

    """
    def __init__(self, request):
        self.request = request

    def __iter__(self):
        return iter(self.messages)

    def __len__(self):
        return len(self.messages)

    def __nonzero__(self):
        return bool(self.messages)

    def __unicode__(self):
        return unicode(self.messages)

    def __getitem__(self, *args, **kwargs):
        return self.messages.__getitem__(*args, **kwargs)

    def _get_messages(self):
        if hasattr(self, '_messages'):
            return self._messages
        self._messages = get_and_delete_messages(self.request)
        return self._messages
    messages = property(_get_messages)
