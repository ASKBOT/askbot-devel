"""Email alerts for new posts.

Sends an email to POST_ALERT_EMAIL (Django setting) whenever a
question, answer, or comment is posted. Useful for low-traffic sites
or during initial rollout monitoring.

Disable by removing POST_ALERT_EMAIL from settings.py.
"""
import logging
from django.conf import settings as django_settings
from askbot import signals
from askbot.conf import settings as askbot_settings

logger = logging.getLogger(__name__)


def _get_site_url():
    """Get the site base URL from Django's sites framework."""
    try:
        from django.contrib.sites.models import Site
        site = Site.objects.get_current()
        return f"https://{site.domain}"
    except Exception:
        return ''


def _send_post_alert(post_type, post, user):
    """Send a notification email about a new post."""
    alert_email = getattr(django_settings, 'POST_ALERT_EMAIL', None)
    if not alert_email:
        return

    try:
        from askbot.mail import send_mail

        site_url = _get_site_url()
        url = post.get_absolute_url() if hasattr(post, 'get_absolute_url') else ''
        full_url = f"{site_url}{url}" if url else ''
        preview = post.text[:500] if hasattr(post, 'text') else ''

        url_link = f'<a href="{full_url}">{full_url}</a>' if full_url else ''
        preview_html = f'<p>{preview}</p>' if preview else ''

        if post_type == 'question':
            title = post.thread.title if hasattr(post, 'thread') else str(post)
            body = (f"<p>New question by <b>{user.username}</b> ({user.email})</p>"
                    f"<p>Title: {title}<br>URL: {url_link}</p>"
                    f"{preview_html}")
        elif post_type == 'answer':
            question = post.thread.title if hasattr(post, 'thread') else ''
            body = (f"<p>New answer by <b>{user.username}</b> ({user.email})</p>"
                    f"<p>Question: {question}<br>URL: {url_link}</p>"
                    f"{preview_html}")
        elif post_type == 'comment':
            body = (f"<p>New comment by <b>{user.username}</b> ({user.email})</p>"
                    f"<p>URL: {url_link}</p>"
                    f"{preview_html}")
        else:
            body = f"<p>New {post_type} by {user.username}</p>"

        subject = f"New {post_type} by {user.username}"

        send_mail(
            subject_line=subject,
            body_text=body,
            recipient_list=[alert_email],
        )

    except Exception as e:
        logger.error(f"Failed to send post alert: {e}")


def on_new_question(sender, question, user, **kwargs):
    _send_post_alert('question', question, user)


def on_new_answer(sender, answer, user, **kwargs):
    _send_post_alert('answer', answer, user)


def on_new_comment(sender, comment, user, **kwargs):
    _send_post_alert('comment', comment, user)


def connect():
    """Connect signal handlers. Call from AppConfig.ready()."""
    signals.new_question_posted.connect(on_new_question)
    signals.new_answer_posted.connect(on_new_answer)
    signals.new_comment_posted.connect(on_new_comment)
