"""functions that send email in askbot
these automatically catch email-related exceptions
"""
import smtplib
import logging
from django.core import mail
from django.conf import settings as django_settings
from askbot.conf import settings as askbot_settings
from askbot import exceptions
from askbot import const
#todo: maybe send_mail functions belong to models
#or the future API
def prefix_the_subject_line(subject):
    """prefixes the subject line with the
    EMAIL_SUBJECT_LINE_PREFIX either from
    from live settings, which take default from django
    """
    prefix = askbot_settings.EMAIL_SUBJECT_PREFIX
    if prefix != '':
        subject = prefix.strip() + ' ' + subject.strip()
    return subject

def extract_first_email_address(text):
    """extract first matching email address
    from text string
    returns ``None`` if there are no matches
    """
    match = const.EMAIL_REGEX.search(text)
    if match:
        return match.group(0)
    else:
        return None

def thread_headers(post, orig_post, update):
    suffix_id = django_settings.SERVER_EMAIL
    if update == const.TYPE_ACTIVITY_ASK_QUESTION:
       id = "NQ-%s-%s" % (post.id, suffix_id)
       headers = {'Message-ID': id}
    elif update == const.TYPE_ACTIVITY_ANSWER:
       id = "NA-%s-%s" % (post.id, suffix_id)
       orig_id = "NQ-%s-%s" % (orig_post.id, suffix_id)
       headers = {'Message-ID': id,
                  'In-Reply-To': orig_id}
    elif update == const.TYPE_ACTIVITY_UPDATE_QUESTION:
       id = "UQ-%s-%s-%s" % (post.id, post.last_edited_at, suffix_id)
       orig_id = "NQ-%s-%s" % (orig_post.id, suffix_id)
       headers = {'Message-ID': id,
                  'In-Reply-To': orig_id}
    elif update == const.TYPE_ACTIVITY_COMMENT_QUESTION:
       id = "CQ-%s-%s" % (post.id, suffix_id)
       orig_id = "NQ-%s-%s" % (orig_post.id, suffix_id)
       headers = {'Message-ID': id,
                  'In-Reply-To': orig_id}
    elif update == const.TYPE_ACTIVITY_UPDATE_ANSWER:
       id = "UA-%s-%s-%s" % (post.id, post.last_edited_at, suffix_id)
       orig_id = "NQ-%s-%s" % (orig_post.id, suffix_id)
       headers = {'Message-ID': id,
                  'In-Reply-To': orig_id}
    elif update == const.TYPE_ACTIVITY_COMMENT_ANSWER:
       id = "CA-%s-%s" % (post.id, suffix_id)
       orig_id = "NQ-%s-%s" % (orig_post.id, suffix_id)
       headers = {'Message-ID': id,
                  'In-Reply-To': orig_id}
    else:
       # Unknown type -> Can't set headers
       return {}

    return headers

def send_mail(
            subject_line = None,
            body_text = None,
            recipient_list = None,
            activity_type = None,
            related_object = None,
            headers = None,
            raise_on_failure = False,
        ):
    """
    todo: remove parameters not relevant to the function
    sends email message
    logs email sending activity
    and any errors are reported as critical
    in the main log file

    related_object is not mandatory, other arguments
    are. related_object (if given, will be saved in
    the activity record)

    if raise_on_failure is True, exceptions.EmailNotSent is raised
    """
    try:
        assert(subject_line is not None)
        subject_line = prefix_the_subject_line(subject_line)
        msg = mail.EmailMessage(
                        subject_line, 
                        body_text, 
                        django_settings.DEFAULT_FROM_EMAIL,
                        recipient_list,
                        headers = headers
                    )
        msg.content_subtype = 'html'
        msg.send()
        if related_object is not None:
            assert(activity_type is not None)
    except Exception, error:
        logging.critical(unicode(error))
        if raise_on_failure == True:
            raise exceptions.EmailNotSent(unicode(error))

def mail_moderators(
            subject_line = '',
            body_text = '',
            raise_on_failure = False):
    """sends email to forum moderators and admins
    """
    from django.db.models import Q
    from askbot.models import User
    recipient_list = User.objects.filter(
                    Q(status='m') | Q(is_superuser=True)
                ).filter(
                    is_active = True
                ).values_list('email', flat=True)
    recipient_list = set(recipient_list)

    from_email = ''
    if hasattr(django_settings, 'DEFAULT_FROM_EMAIL'):
        from_email = django_settings.DEFAULT_FROM_EMAIL

    try:
        mail.send_mail(subject_line, body_text, from_email, recipient_list)
        pass
    except smtplib.SMTPException, error:
        logging.critical(unicode(error))
        if raise_on_failure == True:
            raise exceptions.EmailNotSent(unicode(error))
