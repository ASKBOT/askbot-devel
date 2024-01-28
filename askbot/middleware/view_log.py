"""
This module records the site visits by the authenticated users

Included here is the ViewLogMiddleware
"""
from askbot import signals
from django.utils import timezone


class ViewLogMiddleware:
    """
    ViewLogMiddleware sends the site_visited signal

    """
    def __init__(self, get_response=None): # i think get_reponse is never None. If it's not another middleware it's the view, I think
        if get_response is None:
            get_response = lambda x:x
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request) # i think this simply chains all middleware

    def process_view(self, request, view_func, view_args, view_kwargs):
        #send the site_visited signal for the authenticated users
        if request.user.is_authenticated:
            signals.site_visited.send(None, #this signal has no sender
                user=request.user,
                timestamp=timezone.now()
            )
