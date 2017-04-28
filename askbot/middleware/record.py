try:
    from django.utils.deprecation import MiddlewareMixin  # Django 1.10.x
except ImportError:
    MiddlewareMixin = object  # Django 1.4.x - Django 1.9.x

class LogMiddleware(MiddlewareMixin):
    def process_request(self, request):
        return None
    def process_response(self, request, response):
        print request.path
        return response
