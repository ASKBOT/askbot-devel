from askbot.mail import messages
from askbot.mail.messages import BaseEmail
from askbot.utils.decorators import moderators_only
from django.http import Http404
from django.shortcuts import render
from django.template import Context
from django.utils.translation import ugettext_lazy as _
import logging

LOG = logging.getLogger(__name__)

REGISTRY = dict()
def autodiscover():
    if REGISTRY:
        return
    for name in dir(messages):
        item = messages.__dict__[name]
        if item == BaseEmail:
            continue
        if isinstance(item, type) and issubclass(item, BaseEmail):
            REGISTRY[name] = item

autodiscover()

@moderators_only
def list_emails(request):
    #list only enabled emails
    enabled = dict((k, v) for k, v in REGISTRY.items() if v().is_enabled())
    data = {'emails': enabled}#REGISTRY}
    return render(request, 'email/list_emails.html', Context(data))


DEFAULT_PREVIEW_ERROR_MESSAGE = _(
    'Preview failed possibly because of insufficient data '
    'or an error during the rendering'
)

@moderators_only
def preview_email(request, slug):
    if slug not in REGISTRY:
        raise Http404

    data = {
        'subject': None,
        'body': None,
        'error_message': None
    }

    email = REGISTRY[slug]()
    #if email.is_enabled() == False:
    #    raise Http404

    try:
        data['subject'] = email.render_subject()
        data['body'] = email.render_body()
    except Exception, e:
        tech_error = unicode(e)
        LOG.critical(tech_error)
        error_message = getattr(
                    email,
                    'preview_error_message',
                    DEFAULT_PREVIEW_ERROR_MESSAGE
                )
        error_message += u'</br> %s' % tech_error
        data['error_message'] = error_message

    data['email'] = email
    return render(request, 'email/preview_email.html', Context(data))
