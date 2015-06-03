from django.http import HttpResponse
from django.http import HttpResponseNotAllowed
from django.http import HttpResponseForbidden
from django.template import Context
from django.template.loader import get_template
try:
    from django.utils import simplejson
except ImportError:
    import json as simplejson

class PjaxView(object):
    """custom class-based view
    to be used for pjax use and for generation
    of content in the traditional way, where
    the only the :method:`get_context` would be used.
    """
    template_name = None #used only for the "GET" method
    http_method_names = ('GET', 'POST')

    def render_to_response(self, context, template_name=None):
        """like a django's shortcut, except will use
        template_name from self, if `template_name` is not given.
        Also, response is packaged as json with an html fragment
        for the pjax consumption
        """
        template_name = template_name or self.template_name
        template = get_template(template_name)
        html = template.render(Context(context))
        json = simplejson.dumps({'html': html, 'success': True})
        return HttpResponse(json, content_type='application/json')
            

    def get(self, request, *args, **kwargs):
        """view function for the "GET" method"""
        context = self.get_context(request, *args, **kwargs)
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        """view function for the "POST" method"""
        pass

    def dispatch(self, request, *args, **kwargs):
        """checks that the current request method is allowed
        and calls the corresponding view function"""
        if request.method not in self.http_method_names:
            return HttpResponseNotAllowed(self.http_method_names)
        view_func = getattr(self, request.method.lower())
        return view_func(request, *args, **kwargs)

    def get_context(self, request, *args, **kwargs):
        """Returns the context dictionary for the "get"
        method only"""
        return {}

    def as_view(self):
        """returns the view function - for the urls.py"""
        def view_function(request, *args, **kwargs):
            """the actual view function"""
            if request.user.is_authenticated() and request.is_ajax():
                view_method = getattr(self, request.method.lower())
                return view_method(request, *args, **kwargs)
            else:
                return HttpResponseForbidden()

        return view_function
