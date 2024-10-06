"""Middleware for the analytics session.
Maintains sessions only for the authenticated users.
If necessary, creates a new session for the user,
otherwise updates the existing session.
"""

from django.utils import timezone
from askbot.models.analytics import Session

class AnalyticsSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        if request.user.is_authenticated:
            session = Session.objects.get_active_session(request.user)
            if not session:
                session = Session.objects.create_session(
                    user=request.user,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT')
                )
            else:
                session.touch()
        return self.get_response(request)