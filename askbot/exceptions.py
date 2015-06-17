from django.core import exceptions
from django.utils.translation import ugettext as _

class DeploymentError(exceptions.ImproperlyConfigured):
    """raised when there is some error with deployment"""
    pass

class LoginRequired(exceptions.PermissionDenied):
    """raised when an operation required a logged
    in user"""
    def __init__(self, msg = None):
        if msg is None:
            msg = _('Sorry, but anonymous visitors cannot access this function')
        super(LoginRequired, self).__init__(msg)

class InsufficientReputation(exceptions.PermissionDenied):
    """exception class to indicate that permission
    was denied due to insufficient reputation
    """
    pass

class AnswerAlreadyGiven(exceptions.PermissionDenied):
    """Raised when user attempts to post a second answer
    to the same question"""
    pass

class DuplicateCommand(exceptions.PermissionDenied):
    """exception class to indicate that something
    that can happen only once was attempted for the second time
    """
    pass

class EmailNotSent(exceptions.ImproperlyConfigured):
    """raised when email cannot be sent
    due to some mis-configurations on the server
    """
    pass

class QuestionHidden(exceptions.PermissionDenied):
    """raised when user cannot see deleted question
    """
    pass

class AnswerHidden(exceptions.PermissionDenied):
    """raised when user cannot see deleted answer
    """
    pass
