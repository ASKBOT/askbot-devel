"""Copyright 2011 Askbot.org and Askbot project contributors.

Custom management command that takes questions posted
via email at the IMAP server
Expects subject line of emails to have format:
[Tag1, Tag2] Question title

Tags can be entered as multiword, but the space character
within the tag may be replaced with a dash, per live
setting EMAIL_REPLACE_SPACE_IN_TAGS
also, to make use of this command, the feature must
be enabled via ALLOW_ASKING_BY_EMAIL
and IMAP settings in the settings.py must be configured
correctly

todo: use templates for the email formatting
"""
import imaplib
import email
import quopri
import base64
from django.conf import settings as django_settings
from django.core.management.base import NoArgsCommand, CommandError
from askbot.conf import settings as askbot_settings
from askbot import mail

class CannotParseEmail(Exception):
    """This exception will bounce the email"""
    def __init__(self, email_address, subject):
        super(CannotParseEmail, self).__init__()
        mail.bounce_email(email_address, subject, reason = 'problem_posting')

def parse_message(msg):
    """returns a tuple
    (<from email address>, <subject>, <body>)
    the function will attempt to decode the email
    supported encodings are "quoted-printable" and "base64"
    not supported - emails using language - specific encodings
    """
    sender = msg.get('From')
    subject = msg.get('Subject')
    if msg.is_multipart():
        msg = msg.get_payload()
        if isinstance(msg, list):
            raise CannotParseEmail(sender, subject)

    #ctype = msg.get_content_type()#text/plain only
    raw_body = msg.get_payload()#text/plain only
    encoding = msg.get('Content-Transfer-Encoding')
    if encoding == 'base64':
        body = base64.b64decode(raw_body)
    elif encoding == 'quoted-printable':
        body = quopri.decodestring(raw_body)
    else:
        body = raw_body
    return (sender, subject, body)


class Command(NoArgsCommand):
    """the django management command class"""
    def handle_noargs(self, **options):
        """reads all emails from the INBOX of
        imap server and posts questions based on
        those emails. Badly formatted questions are
        bounced, as well as emails from unknown users

        all messages are deleted thereafter
        """
        if not askbot_settings.ALLOW_ASKING_BY_EMAIL:
            raise CommandError('Asking by email is not enabled')

        #open imap server and select the inbox
        if django_settings.IMAP_USE_TLS:
            imap_getter = imaplib.IMAP4_SSL
        else:
            imap_getter = imaplib.IMAP4
        imap = imap_getter(
            django_settings.IMAP_HOST,
            django_settings.IMAP_PORT
        )
        imap.login(
            django_settings.IMAP_HOST_USER,
            django_settings.IMAP_HOST_PASSWORD
        )
        imap.select('INBOX')

        #get message ids
        junk, ids = imap.search(None, 'ALL')

        if len(ids[0].strip()) == 0:
            #with empty inbox - close and exit
            imap.close()
            imap.logout()
            return

        #for each id - read a message, parse it and post a question
        for msg_id in ids[0].split(' '):
            junk, data = imap.fetch(msg_id, '(RFC822)')
            #message_body = data[0][1]
            msg = email.message_from_string(data[0][1])
            imap.store(msg_id, '+FLAGS', '\\Deleted')
            try:
                (sender, subject, body) = parse_message(msg)
            except CannotParseEmail:
                continue

            sender = mail.extract_first_email_address(sender)
            mail.process_emailed_question(sender, subject, body)

        imap.expunge()
        imap.close()
        imap.logout()
