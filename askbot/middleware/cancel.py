from django.http import HttpResponseRedirect
from askbot.utils.forms import get_next_url
class CancelActionMiddleware(object):
    def process_view(self, request, view_func, view_args, view_kwargs):
        if 'cancel' in request.REQUEST:
            #todo use session messages for the anonymous users
            try:
                msg = getattr(view_func,'CANCEL_MESSAGE')
            except AttributeError:
                msg = 'action canceled'
            request.user.message_set.create(message=unicode(msg))
            return HttpResponseRedirect(get_next_url(request))
        else:
            return None
