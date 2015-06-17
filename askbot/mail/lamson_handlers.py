import functools
import re
import sys
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.urlresolvers import reverse
from django.conf import settings as django_settings
from django.template import Context
from django.template.loader import get_template
from django.utils.translation import ugettext as _
from lamson.routing import route, stateless
from lamson.server import Relay
from askbot.models import ReplyAddress, Group, Tag
from askbot import mail
from askbot.conf import settings as askbot_settings
from askbot.utils.html import site_url
from askbot.mail import DEBUG_EMAIL

#we might end up needing to use something like this
#to distinguish the reply text from the quoted original message
"""
def _strip_message_qoute(message_text):
    import re
    result = message_text
    pattern = "(?P<qoute>" + \
        "On ([a-zA-Z0-9, :/<>@\.\"\[\]]* wrote:.*)|" + \
        "From: [\w@ \.]* \[mailto:[\w\.]*@[\w\.]*\].*|" + \
        "From: [\w@ \.]*(\n|\r\n)+Sent: [\*\w@ \.,:/]*(\n|\r\n)+To:.*(\n|\r\n)+.*|" + \
        "[- ]*Forwarded by [\w@ \.,:/]*.*|" + \
        "From: [\w@ \.<>\-]*(\n|\r\n)To: [\w@ \.<>\-]*(\n|\r\n)Date: [\w@ \.<>\-:,]*\n.*|" + \
        "From: [\w@ \.<>\-]*(\n|\r\n)To: [\w@ \.<>\-]*(\n|\r\n)Sent: [\*\w@ \.,:/]*(\n|\r\n).*|" + \
        "From: [\w@ \.<>\-]*(\n|\r\n)To: [\w@ \.<>\-]*(\n|\r\n)Subject:.*|" + \
        "(-| )*Original Message(-| )*.*)"
    groups = re.search(pattern, email_text, re.IGNORECASE + re.DOTALL)
    qoute = None
    if not groups is None:
        if groups.groupdict().has_key("qoute"):
            qoute = groups.groupdict()["qoute"]
    if qoute:
        result = reslut.split(qoute)[0]
    #if the last line contains an email message remove that one too
    lines = result.splitlines(True)
    if re.search(r'[\w\.]*@[\w\.]*\].*', lines[-1]):
        result = '\n'.join(lines[:-1])
    return result
"""

def get_disposition(part):
    """return list of part's content dispositions
    or an empty list
    """
    dispositions = part.content_encoding.get('Content-Disposition', None)
    if dispositions:
        return dispositions[0]
    else:
        return list()

def get_attachment_info(part):
    return part.content_encoding['Content-Disposition'][1]

def is_attachment(part):
    """True if part content disposition is
    attachment"""
    return get_disposition(part) == 'attachment'

def is_inline_attachment(part):
    """True if part content disposition is
    inline"""
    return get_disposition(part) == 'inline'

def format_attachment(part):
    """takes message part and turns it into SimpleUploadedFile object"""
    att_info = get_attachment_info(part)
    name = att_info.get('filename', None)
    content_type = get_content_type(part)
    return SimpleUploadedFile(name, part.body, content_type)

def get_content_type(part):
    """return content type of the message part"""
    return part.content_encoding.get('Content-Type', (None,))[0]

def is_body(part):
    """True, if part is plain text and is not attachment"""
    if get_content_type(part) == 'text/plain':
        if not is_attachment(part):
            return True
    return False

def get_part_type(part):
    if is_body(part):
        return 'body'
    elif is_attachment(part):
        return 'attachment'
    elif is_inline_attachment(part):
        return 'inline'

def get_parts(message):
    """returns list of tuples (<part_type>, <formatted_part>),
    where <part-type> is one of 'body', 'attachment', 'inline'
    and <formatted-part> - will be in the directly usable form:
    * if it is 'body' - then it will be unicode text
    * for attachment - it will be django's SimpleUploadedFile instance

    There may be multiple 'body' parts as well as others
    usually the body is split when there are inline attachments present.
    """

    parts = list()

    simple_body = ''
    if message.body():
        simple_body = message.body()
        parts.append(('body', simple_body))

    for part in message.walk():
        part_type = get_part_type(part)
        if part_type == 'body':
            part_content = part.body
            if part_content == simple_body:
                continue#avoid duplication
        elif part_type in ('attachment', 'inline'):
            part_content = format_attachment(part)
        else:
            continue
        parts.append((part_type, part_content))
    return parts

def process_reply(func):
    @functools.wraps(func)
    def wrapped(message, host = None, address = None):
        """processes forwarding rules, and run the handler
        in the case of error, send a bounce email
        """

        try:
            for rule in django_settings.LAMSON_FORWARD:
                if re.match(rule['pattern'], message.base['to']):
                    relay = Relay(host=rule['host'],
                               port=rule['port'], debug=1)
                    relay.deliver(message)
                    return
        except AttributeError:
            pass

        error = None

        try:
            reply_address = ReplyAddress.objects.get(
                                            address = address,
                                            allowed_from_email = message.From
                                        )

            #here is the business part of this function
            parts = get_parts(message)
            func(
                from_address = message.From,
                subject_line = message['Subject'],
                parts = parts,
                reply_address_object = reply_address
            )

        except ReplyAddress.DoesNotExist:
            error = _("You were replying to an email address\
             unknown to the system or you were replying from a different address from the one where you\
             received the notification.")
        except Exception, e:
            import sys
            sys.stderr.write(unicode(e).encode('utf-8'))
            import traceback
            sys.stderr.write(unicode(traceback.format_exc()).encode('utf-8'))

        if error is not None:
            from askbot.mail.messages import ReplyByEmailError
            email = ReplyByEmailError({'error': error})
            email.send([message.From])

    return wrapped

@route('(addr)@(host)', addr = '.+')
@stateless
def ASK(message, host = None, addr = None):
    """lamson handler for asking by email,
    to the forum in general and to a specific group"""

    #we need to exclude some other emails by prefix
    if addr.startswith('reply-'):
        return
    if addr.startswith('welcome-'):
        return

    parts = get_parts(message)
    from_address = message.From

    if DEBUG_EMAIL:
        sys.stderr.write(
            (u'Received email from %s\n' % from_address).encode('utf-8')
        )


    #why lamson does not give it normally?
    subject = message['Subject'].strip('\n\t ')
    body_text, stored_files, unused = mail.process_parts(parts)
    if addr == 'ask':
        mail.process_emailed_question(
            from_address, subject, body_text, stored_files
        )
    else:
        #this is the Ask the group branch
        if askbot_settings.GROUP_EMAIL_ADDRESSES_ENABLED == False:
            return
        try:
            group = Group.objects.get(name__iexact=addr)
            mail.process_emailed_question(
                from_address, subject, body_text, stored_files,
                group_id = group.id
            )
        except Group.DoesNotExist:
            #do nothing because this handler will match all emails
            return
        except Tag.MultipleObjectsReturned:
            return

@route('welcome-(address)@(host)', address='.+')
@stateless
@process_reply
def VALIDATE_EMAIL(
    parts = None,
    reply_address_object = None,
    from_address = None,
    **kwargs
):
    """process the validation email and save
    the email signature
    todo: go a step further and
    """
    reply_code = reply_address_object.address

    if DEBUG_EMAIL:
        msg = u'Received email validation from %s\n' % from_address
        sys.stderr.write(msg.encode('utf-8'))

    try:
        content, stored_files, signature = mail.process_parts(parts, reply_code)

        user = reply_address_object.user

        if signature != user.email_signature:
            user.email_signature = signature

        user.email_isvalid = True
        user.save()

        from askbot.mail.messages import ReWelcomeEmail
        email = ReWelcomeEmail({'recipient_user': user})
        email.send([from_address,])

    except ValueError:
        raise ValueError(
            _(
                'Please reply to the welcome email '
                'without editing it'
            )
        )

@route('reply-(address)@(host)', address='.+')
@stateless
@process_reply
def PROCESS(
    parts = None,
    reply_address_object = None,
    subject_line = None,
    from_address = None,
    **kwargs
):
    """handler to process the emailed message
    and make a post to askbot based on the contents of
    the email, including the text body and the file attachments"""
    if DEBUG_EMAIL:
        sys.stderr.write(
            (u'Received reply from %s\n' % from_address).encode('utf-8')
        )
    #1) get actual email content
    #   todo: factor this out into the process_reply decorator
    reply_code = reply_address_object.address
    body_text, stored_files, signature = mail.process_parts(parts, reply_code, from_address)

    #2) process body text and email signature
    user = reply_address_object.user

    if signature != user.email_signature:
        user.email_signature = signature

    #3) validate email address and save user along with maybe new signature
    user.email_isvalid = True
    user.save()#todo: actually, saving is not necessary, if nothing changed

    #here we might be in danger of chomping off some of the
    #message is body text ends with a legitimate text coinciding with
    #the user's email signature
    body_text = user.strip_email_signature(body_text)

    #4) actually make an edit in the forum
    robj = reply_address_object
    add_post_actions = ('post_comment', 'post_answer', 'auto_answer_or_comment')
    if robj.reply_action == 'replace_content':
        robj.edit_post(body_text, title = subject_line)
    elif robj.reply_action == 'append_content':
        robj.edit_post(body_text)#in this case we don't touch the title
    elif robj.reply_action in add_post_actions:
        if robj.was_used:
            robj.edit_post(body_text, edit_response = True)
        else:
            robj.create_reply(body_text)
    elif robj.reply_action == 'validate_email':
        #todo: this is copy-paste - factor it out to askbot.mail.messages
        from askbot.mail.messages import ReWelcomeEmail
        email = ReWelcomeEmail({'recipient_user': robj.user})
        email.send([from_address,])

        if DEBUG_EMAIL:
            msg = u'Sending welcome mail to %s\n' % from_address
            sys.stderr.write(msg.encode('utf-8'))
