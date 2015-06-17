"""
Lightweight session-based messaging system.

Time-stamp: <2009-03-10 19:22:29 carljm __init__.py>

"""
VERSION = (0, 1, 'pre')

def create_message (request, message):
    """
    Create a message in the current session.

    """
    assert hasattr(request, 'session'), "django-session-messages requires session middleware to be installed. Edit your MIDDLEWARE_CLASSES setting to insert 'django.contrib.sessions.middleware.SessionMiddleware'."

    try:
        request.session['messages'].append(message)
    except KeyError:
        request.session['messages'] = [message]

def get_and_delete_messages (request, include_auth=False):
    """
    Get and delete all messages for current session.

    Optionally also fetches user messages from django.contrib.auth.

    """
    assert hasattr(request, 'session'), "django-session-messages requires session middleware to be installed. Edit your MIDDLEWARE_CLASSES setting to insert 'django.contrib.sessions.middleware.SessionMiddleware'."

    messages = request.session.pop('messages', [])

    if include_auth and request.user.is_authenticated():
        messages.extend(request.user.get_and_delete_messages())

    return messages
