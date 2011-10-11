"""This module records the site visits by the authenticaded
users and heps maintain the state of the search (for all visitors).

Included here is the ViewLogMiddleware
"""
import logging
import datetime
from django.conf import settings
from django.views.static import serve
from django.views.i18n import javascript_catalog
from askbot.models import signals
from askbot.views.readers import questions as questions_view
from askbot.views.commands import vote, get_tag_list
from askbot.views.writers import delete_comment, post_comments, retag_question
from askbot.views.readers import revisions, get_question_body
from askbot.views.meta import media
from askbot.search.state_manager import ViewLog

#todo: the list is getting bigger and bigger - maybe there is a better way to
#trigger reset of sarch state?
IGNORED_VIEWS = (
    serve, vote, media, delete_comment, post_comments,
    retag_question, revisions, javascript_catalog,
    get_tag_list, get_question_body
)


class ViewLogMiddleware(object):
    """ViewLogMiddleware does two things: tracks visits of pages for the
    stateful site search and sends the site_visited signal
    """
    def process_view(self, request, view_func, view_args, view_kwargs):
        #send the site_visited signal for the authenticated users
        if request.user.is_authenticated():
            signals.site_visited.send(None, #this signal has no sender
                user = request.user,
                timestamp = datetime.datetime.now()
            )

        #remaining stuff is for the search state
        if view_func == questions_view:
            view_str = 'questions'
        elif view_func in IGNORED_VIEWS:
            return
        else:
            view_str = view_func.__name__
            if view_str == 'wrap':
                return

        if settings.DEBUG == True:
            #todo: dependency!
            try:
                from debug_toolbar.views import debug_media as debug_media_view
                if view_func == debug_media_view:
                    return
            except ImportError:
                pass

        logging.debug('user %s, view %s' % (request.user.username, view_str))
        logging.debug('next url is %s' % request.REQUEST.get('next','nothing'))

        if 'view_log' in request.session:
            view_log = request.session['view_log']
        else:
            view_log = ViewLog()

        view_log.set_current(view_str)
        request.session['view_log'] = view_log
