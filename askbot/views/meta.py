"""
:synopsis: remaining "secondary" views for askbot

This module contains a collection of views displaying all sorts of secondary and mostly static content.
"""
from django.shortcuts import render_to_response, get_object_or_404
from django.core.urlresolvers import reverse
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.shortcuts import render
from django.template import RequestContext, Template
from django.template.loader import get_template
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _
from django.views import static
from django.views.decorators import csrf
from django.db.models import Max, Count
from askbot import skins
from askbot.conf import settings as askbot_settings
from askbot.forms import FeedbackForm
from askbot.utils.url_utils import get_login_url
from askbot.utils.forms import get_next_url
from askbot.mail import mail_moderators
from askbot.models import BadgeData, Award, User, Tag
from askbot.models import badges as badge_data
from askbot.skins.loaders import render_text_into_skin
from askbot.utils.decorators import admins_only
from askbot.utils.forms import get_next_url
from askbot.utils import functions

def generic_view(request, template = None, page_class = None):
    """this may be not necessary, since it is just a rewrite of render"""
    if request is None:  # a plug for strange import errors in django startup
        return render_to_response('django_error.html')
    return render(request, template, {'page_class': page_class})

def config_variable(request, variable_name = None, mimetype = None):
    """Print value from the configuration settings
    as response content. All parameters are required.
    """
    #todo add http header-based caching here!!!
    output = getattr(askbot_settings, variable_name, '')
    return HttpResponse(output, mimetype = mimetype)

def about(request, template='about.html'):
    title = _('About %(site)s') % {'site': askbot_settings.APP_SHORT_NAME}
    data = {
        'title': title,
        'page_class': 'meta',
        'content': askbot_settings.FORUM_ABOUT
    }
    return render(request, 'static_page.html', data)

def page_not_found(request, template='404.html'):
    return generic_view(request, template)

def server_error(request, template='500.html'):
    return generic_view(request, template)

def help(request):
    data = {
        'app_name': askbot_settings.APP_SHORT_NAME,
        'page_class': 'meta'
    }
    return render(request, 'help.html', data)

def faq(request):
    if askbot_settings.FORUM_FAQ.strip() != '':
        data = {
            'title': _('FAQ'),
            'content': askbot_settings.FORUM_FAQ,
            'page_class': 'meta',
        }
        return render(request, 'static_page.html', data)
    else:
        data = {
            'gravatar_faq_url': reverse('faq') + '#gravatar',
            'ask_question_url': reverse('ask'),
            'page_class': 'meta',
        }
        return render(request, 'faq_static.html', data)

@csrf.csrf_protect
def feedback(request):
    data = {'page_class': 'meta'}
    form = None

    if askbot_settings.ALLOW_ANONYMOUS_FEEDBACK is False:
        if request.user.is_anonymous():
            message = _('Please sign in or register to send your feedback')
            request.user.message_set.create(message=message)
            redirect_url = get_login_url() + '?next=' + request.path
            return HttpResponseRedirect(redirect_url)

    if request.method == "POST":
        form = FeedbackForm(
            is_auth=request.user.is_authenticated(),
            data=request.POST
        )
        if form.is_valid():

            if not request.user.is_authenticated():
                data['email'] = form.cleaned_data.get('email', None)
            else:
                data['email'] = request.user.email

            data['message'] = form.cleaned_data['message']
            data['name'] = form.cleaned_data.get('name', None)
            template = get_template('email/feedback_email.txt')
            message = template.render(RequestContext(request, data))

            headers = {}
            if data['email']:
                headers = {'Reply-To': data['email']}

            mail_moderators(
                _('Q&A forum feedback'),
                message,
                headers=headers
            )
            msg = _('Thanks for the feedback!')
            request.user.message_set.create(message=msg)
            return HttpResponseRedirect(get_next_url(request))
    else:
        form = FeedbackForm(is_auth = request.user.is_authenticated(),
                            initial={'next':get_next_url(request)})

    data['form'] = form
    return render(request, 'feedback.html', data)
feedback.CANCEL_MESSAGE=_('We look forward to hearing your feedback! Please, give it next time :)')

def privacy(request):
    data = {
        'title': _('Privacy policy'),
        'page_class': 'meta',
        'content': askbot_settings.FORUM_PRIVACY
    }
    return render(request, 'static_page.html', data)

def badges(request):#user status/reputation system
    #todo: supplement database data with the stuff from badges.py
    if askbot_settings.BADGES_MODE != 'public':
        raise Http404
    known_badges = badge_data.BADGES.keys()
    badges = BadgeData.objects.filter(slug__in = known_badges).order_by('slug')
    my_badge_ids = list()
    if request.user.is_authenticated():
        my_badge_ids = Award.objects.filter(
                                user=request.user
                            ).values_list(
                                'badge_id', flat=True
                            ).distinct()

    data = {
        'active_tab': 'badges',
        'badges' : badges,
        'page_class': 'meta',
        'my_badge_ids' : my_badge_ids
    }
    return render(request, 'badges.html', data)

def badge(request, id):
    #todo: supplement database data with the stuff from badges.py
    badge = get_object_or_404(BadgeData, id=id)

    badge_recipients = User.objects.filter(
                            award_user__badge = badge
                        ).annotate(
                            last_awarded_at = Max('award_user__awarded_at'),
                            award_count = Count('award_user')
                        ).order_by(
                            '-last_awarded_at'
                        )

    data = {
        'active_tab': 'badges',
        'badge_recipients' : badge_recipients,
        'badge' : badge,
        'page_class': 'meta',
    }
    return render(request, 'badge.html', data)

@admins_only
def list_suggested_tags(request):
    """moderators and administrators can list tags that are
    in the moderation queue, apply suggested tag to questions
    or cancel the moderation reuest."""
    if askbot_settings.ENABLE_TAG_MODERATION == False:
        raise Http404
    tags = Tag.objects.filter(status = Tag.STATUS_SUGGESTED)
    tags = tags.order_by('-used_count', 'name')
    #paginate moderated tags
    paginator = Paginator(tags, 20)

    page_no = request.GET.get('page', '1')

    try:
        page = paginator.page(page_no)
    except (EmptyPage, InvalidPage):
        page = paginator.page(paginator.num_pages)

    paginator_context = functions.setup_paginator({
        'is_paginated' : True,
        'pages': paginator.num_pages,
        'page': page_no,
        'has_previous': page.has_previous(),
        'has_next': page.has_next(),
        'previous': page.previous_page_number(),
        'next': page.next_page_number(),
        'base_url' : request.path
    })

    data = {
        'tags': page.object_list,
        'active_tab': 'tags',
        'tab_id': 'suggested',
        'page_class': 'moderate-tags-page',
        'page_title': _('Suggested tags'),
        'paginator_context' : paginator_context,
    }
    return render(request, 'list_suggested_tags.html', data)
