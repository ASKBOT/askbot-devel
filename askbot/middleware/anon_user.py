"""middleware that allows anonymous users
receive messages using the now deprecated `message_set()`
interface of the user objects.

To allow anonymous users accept messages, a special
message manager is defined here, and :meth:`__deepcopy__()` method
added to the :class:`AnonymousUser` so that user could be pickled.

Secondly, it sends greeting message to anonymous users.
"""
from askbot.user_messages import create_message, get_and_delete_messages
from askbot.conf import settings as askbot_settings

class AnonymousMessageManager(object):
    """message manager for the anonymous user"""
    def __init__(self, request):
        self.request = request

    def create(self, message=''):
        """send message to anonymous user"""
        create_message(self.request, message)  

    def get_and_delete(self):
        """returns messages sent to the anonymous user
        via session, and removes messages from the session"""
        messages = get_and_delete_messages(self.request)
        return messages

def dummy_deepcopy(*arg):
    """this is necessary to prevent deepcopy() on anonymous user object
    that now contains reference to request, which cannot be deepcopied
    """
    return None

class ConnectToSessionMessagesMiddleware(object):
    """Middleware that attaches messages to anonymous users, and
    makes sure that anonymous user greeting is shown just once.
    Middleware does not do anything if the anonymous user greeting
    is disabled.
    """
    def process_request(self, request):
        """Enables anonymous users to receive messages
        the same way as authenticated users, and sets
        the anonymous user greeting, if it should be shown"""
        if request.user.is_anonymous():
            #1) Attach the ability to receive messages
            #plug on deepcopy which may be called by django db "driver"
            request.user.__deepcopy__ = dummy_deepcopy
            #here request is linked to anon user
            request.user.message_set = AnonymousMessageManager(request)
            request.user.get_and_delete_messages = \
                            request.user.message_set.get_and_delete

            #2) set the first greeting one time per session only
            if 'greeting_set' not in request.session and \
                    'askbot_visitor' not in request.COOKIES and \
			        askbot_settings.ENABLE_GREETING_FOR_ANON_USER:
                request.session['greeting_set'] = True
                msg = askbot_settings.GREETING_FOR_ANONYMOUS_USER
                request.user.message_set.create(message=msg)

    def process_response(self, request, response):
        """Adds the ``'askbot_visitor'``key to cookie if user ever
        authenticates so that the anonymous user message won't
        be shown after the user logs out"""
        if hasattr(request, 'user') and \
                request.user.is_authenticated() and \
                'askbot_visitor' not in request.COOKIES :
            #import datetime
            #max_age = 365*24*60*60
            #expires = datetime.datetime.strftime\
            #        (datetime.datetime.utcnow() +
            #                datetime.timedelta(seconds=max_age),\
            #                        "%a, %d-%b-%Y %H:%M:%S GMT")
            response.set_cookie('askbot_visitor', False)
        return response
