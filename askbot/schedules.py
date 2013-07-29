"""tests on whether certain scheduled tasks need
to be performed at the moment"""
from datetime import datetime
from django.utils import timezone
import logging

def should_update_avatar_data(request):
    """True if it is time to update user's avatar data
    user is taken from the request object
    """
    user = request.user
    if user.is_authenticated():
        if (timezone.now() - user.last_login).days <= 1:
            #avatar is updated on login anyway
            return False
        updated_at = request.session.get('avatar_data_updated_at', None)
        if updated_at is None:
            return True
        else:
            if timezone.is_naive(updated_at):
                updated_at = timezone.make_aware(updated_at, timezone.get_default_timezone())
                logging.info('updated_at is not timezone aware')
            
            return (timezone.now() - updated_at).days > 0
    return False
