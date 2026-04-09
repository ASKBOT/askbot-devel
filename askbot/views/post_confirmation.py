"""Views for first-post email confirmation."""
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.utils.translation import gettext as _

from askbot.conf import settings as askbot_settings
from askbot.models.post_confirmation import PostConfirmation


def confirm_post_view(request, key):
    """Handle post confirmation via email link."""
    try:
        confirmation = PostConfirmation.objects.select_related('post', 'user').get(key=key)
    except PostConfirmation.DoesNotExist:
        return render(request, 'post_confirmation.html', {
            'error': _('This confirmation link is not valid.')
        })

    if confirmation.is_confirmed:
        ctx = {'confirmed': True}
        if confirmation.post.approved:
            ctx['post_url'] = confirmation.post.get_absolute_url()
        else:
            ctx['pending_moderation'] = True
        return render(request, 'post_confirmation.html', ctx)

    if confirmation.is_expired:
        return render(request, 'post_confirmation.html', {
            'error': _('This confirmation link has expired.')
        })

    if request.method == 'POST':
        if not request.POST.get('confirm_checkbox'):
            return render(request, 'post_confirmation.html', {
                'error': _('Please check the confirmation checkbox.')
            })

        confirmation.confirm()
        ctx = {'confirmed': True}
        if askbot_settings.FIRST_POST_MODERATE_AFTER_CONFIRMATION:
            ctx['pending_moderation'] = True
        else:
            ctx['post_url'] = confirmation.post.get_absolute_url()
        return render(request, 'post_confirmation.html', ctx)

    post = confirmation.post
    post_html = post.html or post.text
    return render(request, 'post_confirmation.html', {
        'post_html': post_html,
        'confirmation': confirmation,
    })
