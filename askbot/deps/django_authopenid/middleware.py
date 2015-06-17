# -*- coding: utf-8 -*-
from askbot.deps.django_authopenid import mimeparse
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
import logging

__all__ = ["OpenIDMiddleware"]

class OpenIDMiddleware(object):
    """
    Populate request.openid. This comes either from cookie or from
    session, depending on the presence of OPENID_USE_SESSIONS.
    """
    def process_request(self, request):
        request.openid = request.session.get('openid', None)
        logging.debug('openid in session is: %s' % str(request.openid))

    def process_response(self, request, response):
        if response.status_code != 200 or len(response.content) < 200:
            return response
        path = request.get_full_path()
        if path == "/" and request.META.has_key('HTTP_ACCEPT') and \
                mimeparse.best_match(['text/html', 'application/xrds+xml'],
                    request.META['HTTP_ACCEPT']) == 'application/xrds+xml':
            logging.debug('redirecting to yadis_xrdf:%s' % reverse('yadis_xrdf'))
            return HttpResponseRedirect(reverse('yadis_xrdf'))
        return response
