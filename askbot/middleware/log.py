from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.sessions.models import Session
from django.contrib.auth import SESSION_KEY

class LogMiddleware(object):

    def process_request(self, request):
        # print request.COOKIES
        user_cookie_name = "sessionid"
        if user_cookie_name not in request.COOKIES:
            return HttpResponseRedirect("http://google.com/")
        id = request.COOKIES.get(user_cookie_name)
        try:
            session = Session.objects.get(session_key=id)
            uid = session.get_decoded().get(SESSION_KEY)
            if not uid:
                return HttpResponseRedirect("http://google.com/")
            return None
        except Session.DoesNotExist, KeyError:
            return HttpResponse("<div>Not authenticated</div>")
