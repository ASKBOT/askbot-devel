"""a module for patching django"""
import imp
import os
import sys
from django.utils.safestring import mark_safe
from django.utils.functional import lazy
from django.template import Node
try:
    from functools import WRAPPER_ASSIGNMENTS
except ImportError:
    from django.utils.functional import WRAPPER_ASSIGNMENTS

def module_has_submodule(package, module_name):
    """See if 'module' is in 'package'."""
    name = ".".join([package.__name__, module_name])
    if name in sys.modules:
        return True
    for finder in sys.meta_path:
        if finder.find_module(name):
            return True
    for entry in package.__path__:  # No __path__, then not a package.
        try:
            # Try the cached finder.
            finder = sys.path_importer_cache[entry]
            if finder is None:
                # Implicit import machinery should be used.
                try:
                    file_, _, _ = imp.find_module(module_name, [entry])
                    if file_:
                        file_.close()
                    return True
                except ImportError:
                    continue
            # Else see if the finder knows of a loader.
            elif finder.find_module(name):
                return True
            else:
                continue
        except KeyError:
            # No cached finder, so try and make one.
            for hook in sys.path_hooks:
                try:
                    finder = hook(entry)
                    # XXX Could cache in sys.path_importer_cache
                    if finder.find_module(name):
                        return True
                    else:
                        # Once a finder is found, stop the search.
                        break
                except ImportError:
                    # Continue the search for a finder.
                    continue
            else:
                # No finder found.
                # Try the implicit import machinery if searching a directory.
                if os.path.isdir(entry):
                    try:
                        file_, _, _ = imp.find_module(module_name, [entry])
                        if file_:
                            file_.close()
                        return True
                    except ImportError:
                        pass
                # XXX Could insert None or NullImporter
    else:
        # Exhausted the search, so the module cannot be found.
        return False

class CsrfTokenNode(Node):
    def render(self, context):
        csrf_token = context.get('csrf_token', None)
        if csrf_token:
            if csrf_token == 'NOTPROVIDED':
                return mark_safe(u"")
            else:
                return mark_safe(u"<div style='display:none'><input type='hidden' name='csrfmiddlewaretoken' value='%s' /></div>" % csrf_token)
        else:
            # It's very probable that the token is missing because of
            # misconfiguration, so we raise a warning
            from django.conf import settings
            if settings.DEBUG:
                import warnings
                warnings.warn("A {% csrf_token %} was used in a template, but the context did not provide the value.  This is usually caused by not using RequestContext.")
            return u''

def get_token(request):
    """
    Returns the the CSRF token required for a POST form.
    A side effect of calling this function is to make the the csrf_protect
    decorator and the CsrfViewMiddleware add a CSRF cookie and a 'Vary: Cookie'
    header to the outgoing response.  For this reason, you may need to use this
    function lazily, as is done by the csrf context processor.
    """
    request.META["CSRF_COOKIE_USED"] = True
    return request.META.get("CSRF_COOKIE", None)

def csrf(request):
    """
    Context processor that provides a CSRF token, or the string 'NOTPROVIDED' if
    it has not been provided by either a view decorator or the middleware
    """
    def _get_val():
        token = get_token(request)
        if token is None:
            # In order to be able to provide debugging info in the
            # case of misconfiguration, we use a sentinel value
            # instead of returning an empty dict.
            return 'NOTPROVIDED'
        else:
            return token
    _get_val = lazy(_get_val, str)
    return {'csrf_token': _get_val() }

"""
Cross Site Request Forgery Middleware.
This module provides a middleware that implements protection
against request forgeries from other sites.
"""
import itertools
import re
import random
from django.conf import settings
from django.core.urlresolvers import get_callable
from django.utils.hashcompat import md5_constructor
from django.utils.safestring import mark_safe
_POST_FORM_RE = \
    re.compile(r'(<form\W[^>]*\bmethod\s*=\s*(\'|"|)POST(\'|"|)\b[^>]*>)', re.IGNORECASE)
_HTML_TYPES = ('text/html', 'application/xhtml+xml')
# Use the system (hardware-based) random number generator if it exists.
if hasattr(random, 'SystemRandom'):
    randrange = random.SystemRandom().randrange
else:
    randrange = random.randrange
_MAX_CSRF_KEY = 18446744073709551616L     # 2 << 63
def _get_failure_view():
    """
    Returns the view to be used for CSRF rejections
    """
    return get_callable(settings.CSRF_FAILURE_VIEW)

def _get_new_csrf_key():
    return md5_constructor("%s%s"
                % (randrange(0, _MAX_CSRF_KEY), settings.SECRET_KEY)).hexdigest()

def _make_legacy_session_token(session_id):
    return md5_constructor(settings.SECRET_KEY + session_id).hexdigest()

class CsrfViewMiddleware(object):
    """
    Middleware that requires a present and correct csrfmiddlewaretoken
    for POST requests that have a CSRF cookie, and sets an outgoing
    CSRF cookie.
    This middleware should be used in conjunction with the csrf_token template
    tag.
    """
    def process_view(self, request, callback, callback_args, callback_kwargs):
        if getattr(callback, 'csrf_exempt', False):
            return None
        if getattr(request, 'csrf_processing_done', False):
            return None
        reject = lambda s: _get_failure_view()(request, reason=s)
        def accept():
            # Avoid checking the request twice by adding a custom attribute to
            # request.  This will be relevant when both decorator and middleware
            # are used.
            request.csrf_processing_done = True
            return None
        # If the user doesn't have a CSRF cookie, generate one and store it in the
        # request, so it's available to the view.  We'll store it in a cookie when
        # we reach the response.
        try:
            request.META["CSRF_COOKIE"] = request.COOKIES[settings.CSRF_COOKIE_NAME]
            cookie_is_new = False
        except KeyError:
            # No cookie, so create one.  This will be sent with the next
            # response.
            request.META["CSRF_COOKIE"] = _get_new_csrf_key()
            # Set a flag to allow us to fall back and allow the session id in
            # place of a CSRF cookie for this request only.
            cookie_is_new = True
        if request.method == 'POST':
            if getattr(request, '_dont_enforce_csrf_checks', False):
                # Mechanism to turn off CSRF checks for test suite.  It comes after
                # the creation of CSRF cookies, so that everything else continues to
                # work exactly the same (e.g. cookies are sent etc), but before the
                # any branches that call reject()
                return accept()
            if request.is_ajax():
                # .is_ajax() is based on the presence of X-Requested-With.  In
                # the context of a browser, this can only be sent if using
                # XmlHttpRequest.  Browsers implement careful policies for
                # XmlHttpRequest:
                #
                #  * Normally, only same-domain requests are allowed.
                #
                #  * Some browsers (e.g. Firefox 3.5 and later) relax this
                #    carefully:
                #
                #    * if it is a 'simple' GET or POST request (which can
                #      include no custom headers), it is allowed to be cross
                #      domain.  These requests will not be recognized as AJAX.
                #
                #    * if a 'preflight' check with the server confirms that the
                #      server is expecting and allows the request, cross domain
                #      requests even with custom headers are allowed. These
                #      requests will be recognized as AJAX, but can only get
                #      through when the developer has specifically opted in to
                #      allowing the cross-domain POST request.
                #
                # So in all cases, it is safe to allow these requests through.
                return accept()
            if request.is_secure():
                # Strict referer checking for HTTPS
                referer = request.META.get('HTTP_REFERER')
                if referer is None:
                    return reject("Referer checking failed - no Referer.")
                # The following check ensures that the referer is HTTPS,
                # the domains match and the ports match.  This might be too strict.
                good_referer = 'https://%s/' % request.get_host()
                if not referer.startswith(good_referer):
                    return reject("Referer checking failed - %s does not match %s." %
                                  (referer, good_referer))
            # If the user didn't already have a CSRF cookie, then fall back to
            # the Django 1.1 method (hash of session ID), so a request is not
            # rejected if the form was sent to the user before upgrading to the
            # Django 1.2 method (session independent nonce)
            if cookie_is_new:
                try:
                    session_id = request.COOKIES[settings.SESSION_COOKIE_NAME]
                    csrf_token = _make_legacy_session_token(session_id)
                except KeyError:
                    # No CSRF cookie and no session cookie. For POST requests,
                    # we insist on a CSRF cookie, and in this way we can avoid
                    # all CSRF attacks, including login CSRF.
                    return reject("No CSRF or session cookie.")
            else:
                csrf_token = request.META["CSRF_COOKIE"]
            # check incoming token
            request_csrf_token = request.POST.get('csrfmiddlewaretoken', None)
            if request_csrf_token != csrf_token:
                if cookie_is_new:
                    # probably a problem setting the CSRF cookie
                    return reject("CSRF cookie not set.")
                else:
                    return reject("CSRF token missing or incorrect.")
        return accept()
    def process_response(self, request, response):
        if getattr(response, 'csrf_processing_done', False):
            return response
        # If CSRF_COOKIE is unset, then CsrfViewMiddleware.process_view was
        # never called, probaby because a request middleware returned a response
        # (for example, contrib.auth redirecting to a login page).
        if request.META.get("CSRF_COOKIE") is None:
            return response
        if not request.META.get("CSRF_COOKIE_USED", False):
            return response
        # Set the CSRF cookie even if it's already set, so we renew the expiry timer.
        response.set_cookie(settings.CSRF_COOKIE_NAME,
                request.META["CSRF_COOKIE"], max_age = 60 * 60 * 24 * 7 * 52,
                domain=settings.CSRF_COOKIE_DOMAIN)
        # Content varies with the CSRF cookie, so set the Vary header.
        from django.utils.cache import patch_vary_headers
        patch_vary_headers(response, ('Cookie',))
        response.csrf_processing_done = True
        return response

from django.utils.decorators import decorator_from_middleware
from functools import wraps

csrf_protect = decorator_from_middleware(CsrfViewMiddleware)
csrf_protect.__name__ = "csrf_protect"
csrf_protect.__doc__ = """
This decorator adds CSRF protection in exactly the same way as
CsrfViewMiddleware, but it can be used on a per view basis.  Using both, or
using the decorator multiple times, is harmless and efficient.
"""

def add_import_library_function():

    #this definition is copy/pasted from django 1.2 source code
    #it is necessary to make Coffin library happy
    from django.utils.importlib import import_module
    class InvalidTemplateLibrary(Exception):
        pass

    def import_library(taglib_module):
        """Load a template tag library module.
        Verifies that the library contains a 'register' attribute, and
        returns that attribute as the representation of the library
        """
        app_path, taglib = taglib_module.rsplit('.',1)
        app_module = import_module(app_path)
        try:
            mod = import_module(taglib_module)
        except ImportError, e:
            # If the ImportError is because the taglib submodule does not exist, that's not
            # an error that should be raised. If the submodule exists and raised an ImportError
            # on the attempt to load it, that we want to raise.
            if not module_has_submodule(app_module, taglib):
                return None
            else:
                raise InvalidTemplateLibrary("ImportError raised loading %s: %s" % (taglib_module, e))
        try:
            return mod.register
        except AttributeError:
            raise InvalidTemplateLibrary("Template library %s does not have a variable named 'register'" % taglib_module)

    import django.template
    django.template.import_library = import_library

def add_csrf_protection():
    """adds csrf_token template tag to django
    Must be used if version of django is < 1.2

    Also adds csrf function to the context processor
    and the csrf_protect decorator for the views
    """
    import django.template.defaulttags
    def csrf_token(parser, token):
        return CsrfTokenNode()
    django.template.defaulttags.CsrfTokenNode = CsrfTokenNode
    django.template.defaulttags.register.tag(csrf_token)

    #add csrf context processor
    import django.core.context_processors
    django.core.context_processors.csrf = csrf

    #add csrf_protect decorator
    import django.views.decorators
    django.views.decorators.csrf = imp.new_module('csrf')
    django.views.decorators.csrf.csrf_protect = csrf_protect

def add_available_attrs_decorator():
    def available_attrs(fn):
        """
        Return the list of functools-wrappable attributes on a callable.
        This is required as a workaround for http://bugs.python.org/issue3445.
        """
        return tuple(a for a in WRAPPER_ASSIGNMENTS if hasattr(fn, a))
    import django.utils.decorators
    django.utils.decorators.available_attrs = available_attrs

def add_render_shortcut():
    """adds `render` shortcut, introduced with django 1.3"""
    try:
        from django.shortcuts import render
    except ImportError:
        def render(request, template, data=None):
            from django.shortcuts import render_to_response
            from django.template import RequestContext
            return render_to_response(template, RequestContext(request, data))

        import django.shortcuts
        django.shortcuts.render = render


from django.utils import six
from django.utils.functional import Promise
import django.utils.html

def fix_lazy_double_escape():
    """
    Wrap django.utils.html.escape to fix the double escape issue visible at
    least with field labels with localization
    """
    django.utils.html.escape = wrap_escape(django.utils.html.escape)


def wrap_escape(func):
    """
    Decorator adapted from https://github.com/django/django/pull/1007
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        for arg in list(args) + list(six.itervalues(kwargs)):
            if isinstance(arg, Promise):
                break
        else:
            return func(*args, **kwargs)
        return lazy(func, six.text_type)(*args, **kwargs)
    @wraps(wrapper)
    def wrapped(*args, **kwargs):
        return mark_safe(func(*args, **kwargs))
    return wrapped
