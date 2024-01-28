"Taken from django.middleware.locale: this is the locale selecting middleware that will look at accept headers"

from django.utils.cache import patch_vary_headers
from django.utils import translation
from askbot.conf import settings

class LocaleMiddleware:
    """
    This is a very simple middleware that parses a request
    and decides what translation object to install in the current
    thread context. This allows pages to be dynamically
    translated to the language the user desires (if the language
    is available, of course).
    """
    def __init__(self, get_response=None): # i think get_reponse is never None. If it's not another middleware it's the view, I think
        if get_response is None:
            get_response = lambda x:x
        self.get_response = get_response

    def __call__(self, request):
        self.process_request(request)
        response = self.get_response(request) # i think this simply chains all middleware
        response = self.process_response(request, response)
        return response

    def process_request(self, request):
        language = settings.ASKBOT_LANGUAGE
        translation.activate(language)
        request.LANGUAGE_CODE = translation.get_language()

    def process_response(self, request, response):
        patch_vary_headers(response, ('Accept-Language',))
        if 'Content-Language' not in response:
            response['Content-Language'] = translation.get_language()
        #translation.deactivate()
        return response
