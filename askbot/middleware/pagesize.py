import logging
import traceback
import sys
from django.http import HttpResponse, Http404
from django.template import RequestContext
from django.conf import settings
from askbot import utils

# used in questions
QUESTIONS_PAGE_SIZE = 10
class QuestionsPageSizeMiddleware(object):
    def process_request(self, request):
        # Set flag to False by default. If it is True, then need to be saved.
        page_size_changed = False
        # get page_size from session, if failed then get default value
        user_page_size = request.session.get("page_size", QUESTIONS_PAGE_SIZE)
        # set page_size equal to logon user specified value in database
        if request.user.is_authenticated() \
            and request.user.questions_per_page > 0:
            user_page_size = request.user.questions_per_page

        try:
            # get new page_size from UI selection
            page_size = int(request.GET.get('page_size', user_page_size))
            if page_size != user_page_size:
                page_size_changed = True

        except ValueError:
            page_size  = user_page_size
        
        # save this page_size to user database
        if page_size_changed:
            if request.user.is_authenticated():
                user = request.user
                user.questions_per_page = page_size
                user.save()
        # put page_size into session
        request.session["page_size"] = page_size
        
class ErrorExceptionMiddleware(object):

    def process_exception(self, request, exception):
        #todo: move this to separate middleware
        exc_type, exc_value, exc_traceback = sys.exc_info()
        logging.critical(''.join(traceback.format_tb(exc_traceback)))
        logging.critical(exc_type)
        logging.critical(exc_value)
        if exc_type == Http404:
            return None
        if getattr(settings, 'DEBUG', False) == True:
            return None
        else:
            #todo - we have a strange requirement - maybe remove 
            #500.html needs RequestContext, while handler500 only receives Context
            #need to log some more details about the request
            logging.critical(utils.http.get_request_info(request))
            from askbot.skins.loaders import get_template
            template = get_template('500.jinja.html', request)
            return HttpResponse(template.render(RequestContext(request)))
