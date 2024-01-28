"""functions that send email in askbot
these automatically catch email-related exceptions
"""
import logging
import os
import sys
from django.conf import settings as django_settings
from django.core import mail
from django.core.exceptions import PermissionDenied
from django.forms import ValidationError
from django.utils.text import format_lazy
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.utils.html import strip_tags
from askbot import exceptions
from askbot import const
from askbot.conf import settings as askbot_settings
from askbot.mail import parsing
from askbot.utils import url_utils
from askbot.utils.file_utils import store_file
from askbot.utils.html import absolutize_urls
from askbot.utils.html import get_text_from_html

DEBUG_EMAIL = django_settings.ASKBOT_DEBUG_INCOMING_EMAIL

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
    return None

def _send_mail(subject_line, body_text, sender_email, recipient_list, # pylint: disable=too-many-arguments
               headers=None, attachments=None):
    """base send_mail function, which will attach email in html format
    if html email is enabled"""
    html_enabled = askbot_settings.HTML_EMAIL_ENABLED
    if html_enabled:
        message_class = mail.EmailMultiAlternatives
    else:
        message_class = mail.EmailMessage

    from askbot.models import User # pylint: disable=import-outside-toplevel
    from askbot.models.user import InvitedModerator # pylint: disable=import-outside-toplevel
    email_list = []
    for recipient in recipient_list:
        if isinstance(recipient, (User, InvitedModerator)):
            email_list.append(recipient.email)
        else:
            email_list.append(recipient)

    msg = message_class(
                subject_line,
                get_text_from_html(body_text),
                sender_email,
                email_list,
                headers=headers,
                attachments=attachments
            )
    if html_enabled:
        msg.attach_alternative(body_text, "text/html")

    msg.send()

def send_mail( # pylint: disable=too-many-arguments
            subject_line=None,
            body_text=None,
            from_email=None,
            recipient_list=None,
            headers=None,
            raise_on_failure=False,
            attachments=None
        ):
    """
    todo: remove parameters not relevant to the function
    sends email message
    logs email sending activity
    and any errors are reported as critical
    in the main log file

    if raise_on_failure is True, exceptions.EmailNotSent is raised
    `attachments` is a tuple of triples ((filename, filedata, mimetype), ...)
    """
    from_email = from_email or askbot_settings.FROM_EMAIL
    body_text = absolutize_urls(body_text)
    try:
        have_subject = subject_line is not None
        assert have_subject
        subject_line = prefix_the_subject_line(subject_line)
        _send_mail(
            subject_line,
            body_text,
            from_email,
            recipient_list,
            headers=headers,
            attachments=attachments
        )
        logging.debug('sent update to %s' % ','.join(map(str, recipient_list)))
    except Exception as error: # pylint: disable=broad-except
        sys.stderr.write('\n' + str(error) + '\n')
        if raise_on_failure:
            raise exceptions.EmailNotSent(str(error))

INSTRUCTIONS_PREAMBLE = gettext_lazy('<p>To post by email, please:</p>')
QUESTION_TITLE_INSTRUCTION = gettext_lazy(
    '<li>Type title in the subject line</li>'
)
QUESTION_DETAILS_INSTRUCTION = gettext_lazy(
    '<li>Type details into the email body</li>'
)
OPTIONAL_TAGS_INSTRUCTION = gettext_lazy(
"""<li>The beginning of the subject line can contain tags,
<em>enclosed in the square brackets</em> like so: [Tag1; Tag2]</li>"""
)
REQUIRED_TAGS_INSTRUCTION = gettext_lazy(
"""<li>In the beginning of the subject add at least one tag
<em>enclosed in the brackets</em> like so: [Tag1; Tag2].</li>"""
)
TAGS_INSTRUCTION_FOOTNOTE = gettext_lazy(
"""<p>Note that a tag may consist of more than one word, to separate
the tags, use a semicolon or a comma, for example, [One tag; Other tag]</p>"""
)

def bounce_email(
    email, subject, reason = None, body_text = None, reply_to = None
):
    """sends a bounce email at address ``email``, with the subject
    line ``subject``, accepts several reasons for the bounce:
    * ``'problem_posting'``, ``unknown_user`` and ``permission_denied``
    * ``body_text`` in an optional parameter that allows to append
      extra text to the message
    """
    if reason == 'problem_posting':
        error_message = _(
            '<p>Sorry, there was an error while processing your message '
            'please contact the %(site)s administrator</p>'
        ) % {'site': askbot_settings.APP_SHORT_NAME}

        if askbot_settings.TAGS_ARE_REQUIRED:
            error_message = format_lazy('{}<ul>{}{}{}</ul>{}',
                                    INSTRUCTIONS_PREAMBLE,
                                    QUESTION_TITLE_INSTRUCTION,
                                    REQUIRED_TAGS_INSTRUCTION,
                                    QUESTION_DETAILS_INSTRUCTION,
                                    TAGS_INSTRUCTION_FOOTNOTE
                                )
        else:
            error_message = format_lazy('{}<ul>{}{}{}</ul>{}',
                                    INSTRUCTIONS_PREAMBLE,
                                    QUESTION_TITLE_INSTRUCTION,
                                    QUESTION_DETAILS_INSTRUCTION,
                                    OPTIONAL_TAGS_INSTRUCTION,
                                    TAGS_INSTRUCTION_FOOTNOTE
                                )

    elif reason == 'unknown_user':
        error_message = _(
            '<p>Sorry, in order to make posts to %(site)s '
            'by email, please <a href="%(url)s">register first</a></p>'
        ) % {
            'site': askbot_settings.APP_SHORT_NAME,
            'url': url_utils.get_login_url()
        }
    elif reason == 'permission_denied' and body_text is None:
        error_message = _(
            '<p>Sorry, your post could not be made by email '
            'due to insufficient privileges of your user account</p>'
        )
    elif body_text:
        error_message = body_text
    else:
        raise ValueError('unknown reason to bounce an email: "%s"' % reason)


    #print 'sending email'
    #print email
    #print subject
    #print error_message
    headers = {}
    if reply_to:
        headers['Reply-To'] = reply_to

    send_mail(
        recipient_list = (email,),
        subject_line = 'Re: ' + subject,
        body_text = error_message,
        headers = headers
    )

def extract_reply(text):
    """take the part above the separator
    and discard the last line above the separator
    ``text`` is the input text
    """
    return parsing.extract_reply_contents(
                                text,
                                const.REPLY_SEPARATOR_REGEX
                            )

def process_attachment(attachment):
    """will save a single
    attachment and return
    link to file in the markdown format and the
    file storage object
    """
    file_url = store_file(attachment.name, attachment)
    markdown_link = f'[{attachment.name}]({file_url}) '
    file_extension = os.path.splitext(attachment.name)[1]
    #todo: this is a hack - use content type
    if file_extension.lower() in ('.png', '.jpg', '.jpeg', '.gif'):
        markdown_link = '!' + markdown_link
    return markdown_link

def extract_user_signature(text, reply_code):
    """extracts email signature as text trailing
    the reply code"""
    stripped_text = strip_tags(text)

    signature = ''
    if reply_code in stripped_text:
        #extract the signature
        tail = []
        for line in reversed(stripped_text.splitlines()):
            #scan backwards from the end until the magic line
            if reply_code in line:
                break
            tail.insert(0, line)

        #strip off the leading quoted lines, there could be one or two
        #also strip empty lines
        while tail and (tail[0].startswith('>') or tail[0].strip() == ''):
            tail.pop(0)

        signature = '\n'.join(tail)

    #patch signature to a sentinel value if it is truly empty, because we
    #cannot allow empty signature field, which indicates no
    #signature at all and in that case we ask user to create one
    return signature or 'empty signature'


def process_parts(parts, reply_code=None, from_address=None):
    """Uploads the attachments and parses out the
    body, if body is multipart.
    Links to attachments will be added to the body of the question.
    Returns ready to post body of the message and the list
    of uploaded files.
    """
    body_text = ''
    attachments_markdown = ''

    if DEBUG_EMAIL:
        sys.stderr.write('--- MESSAGE PARTS:\n\n')

    for (part_type, content) in parts:
        if part_type == 'attachment':
            if DEBUG_EMAIL:
                sys.stderr.write('REGULAR ATTACHMENT:\n')
            markdown = process_attachment(content)
            attachments_markdown += '\n\n' + markdown
        elif part_type == 'body':
            if DEBUG_EMAIL:
                sys.stderr.write('BODY:\n')
                sys.stderr.write(content.encode('utf-8'))
                sys.stderr.write('\n')
            body_text += '\n\n' + content.strip('\n\t ')
        elif part_type == 'inline':
            if DEBUG_EMAIL:
                sys.stderr.write('INLINE ATTACHMENT:\n')
            markdown = process_attachment(content)
            body_text += markdown

    if DEBUG_EMAIL:
        sys.stderr.write('--- THE END\n')

    body_text = body_text.replace('\r\n', '\n') #dos2unix

    #if the response separator is present -
    #split the body with it, and discard the "so and so wrote:" part
    if reply_code:
        #todo: maybe move this part out
        signature = extract_user_signature(body_text, reply_code)
        body_text = extract_reply(body_text)
    else:
        signature = None

    attachments_markdown = attachments_markdown.replace('\r\n', '\n') #dos2unix
    body_text += attachments_markdown

    if from_address:
        body_text = parsing.strip_trailing_sender_references(
                                                        body_text,
                                                        from_address
                                                    )

    body_text = body_text.strip()
    return body_text, signature


def process_emailed_question(
    from_address, subject, body_text,
    tags=None, group_id=None
):
    """posts question received by email or bounces the message"""
    #a bunch of imports here, to avoid potential circular import issues
    from askbot.forms import AskByEmailForm # pylint: disable=import-outside-toplevel
    from askbot.models import ReplyAddress, User # pylint: disable=import-outside-toplevel
    from askbot.mail.messages import ( # pylint: disable=import-outside-toplevel
                            AskForSignature,
                            InsufficientReputation
                        )

    reply_to = None
    try:
        #todo: delete uploaded files when posting by email fails!!!
        data = {
            'sender': from_address,
            'subject': subject,
            'body_text': body_text
        }
        user = User.objects.get(email__iexact=from_address)
        form = AskByEmailForm(data, user=user)
        if form.is_valid():
            email_address = form.cleaned_data['email']

            if user.can_post_by_email() is False:
                email = InsufficientReputation({'user': user})
                raise PermissionDenied(email.render_body())

            body_text = form.cleaned_data['body_text']
            stripped_body_text = user.strip_email_signature(body_text)

            #note that signature '' means it is unset and 'empty signature' is a sentinel
            #because there is no other way to indicate unset signature without adding
            #another field to the user model
            signature_changed = (
                stripped_body_text == body_text and
                user.email_signature != 'empty signature'
            )

            need_new_signature = (
                user.email_isvalid is False or
                user.email_signature == '' or
                signature_changed
            )

            #ask for signature response if user's email has not been
            #validated yet or if email signature could not be found
            if need_new_signature:
                footer_code = ReplyAddress.objects.create_new(
                    user=user,
                    reply_action='validate_email'
                ).as_email_address(prefix='welcome-')

                email = AskForSignature({
                                'user': user,
                                'footer_code': footer_code
                            })
                raise PermissionDenied(email.render_body())

            tagnames = form.cleaned_data['tagnames']
            title = form.cleaned_data['title']

            #defect - here we might get "too many tags" issue
            if tags:
                tagnames += ' ' + ' '.join(tags)

            user.post_question(
                title=title,
                tags=tagnames.strip(),
                body_text=stripped_body_text,
                by_email=True,
                email_address=from_address,
                group_id=group_id
            )
        else:
            raise ValidationError('unable to post question by email')

    except User.DoesNotExist: # pylint: disable=no-member
        bounce_email(email_address, subject, reason = 'unknown_user')
    except User.MultipleObjectsReturned: # pylint: disable=no-member
        bounce_email(email_address, subject, reason = 'problem_posting')
    except PermissionDenied as error:
        bounce_email(
            email_address,
            subject,
            reason='permission_denied',
            body_text=str(error),
            reply_to=reply_to
        )
    except ValidationError:
        if from_address:
            bounce_email(
                from_address,
                subject,
                reason='problem_posting'
            )
