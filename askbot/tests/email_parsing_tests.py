# -*- coding: utf-8 -*-
from django.conf import settings as django_settings
from django.template import Context
from django.template.loader import get_template
from askbot import mail
from askbot import models
from askbot.tests import utils

class EmailParsingTests(utils.AskbotTestCase):

    def setUp(self):
        self.template_name = 'email/welcome_lamson_on.html'
        self.context = {'site_name': 'askbot.com',
                        'email_code': 'DwFwndQty'}
        template = get_template(self.template_name)
        self.rendered_template = template.render(Context(self.context))
        self.expected_output = 'Welcome to askbot.com!\n\nImportant: Please reply to this message, without editing it. We need this to determine your email signature and that the email address is valid and was typed correctly.\n\nUntil we receive the response from you, you will not be able ask or answer questions on askbot.com by email.\n\nSincerely,askbot.com Administrator\n\nDwFwndQty'

    def test_clean_email_body(self):
        cleaned_body = mail.clean_html_email(self.rendered_template)
        self.assertEqual(self.expected_output, cleaned_body)

    def test_gmail_rich_text_response_stripped(self):
        text = u'\n\nthis is my reply!\n\nOn Wed, Oct 31, 2012 at 1:45 AM, <kp@kp-dev.askbot.com> wrote:\n\n> **\n>            '
        self.assertEqual(mail.extract_reply(text), 'this is my reply!')

    def test_gmail_plain_text_response_stripped(self):
        text = u'\n\nthis is my another reply!\n\nOn Wed, Oct 31, 2012 at 1:45 AM, <kp@kp-dev.askbot.com> wrote:\n>\n> '
        self.assertEqual(mail.extract_reply(text), 'this is my another reply!')

    def test_yahoo_mail_response_stripped(self):
        text = u'\n\nthis is my reply!\n\n\n\n________________________________\n From: "kp@kp-dev.askbot.com" <kp@kp-dev.askbot.com>\nTo: fadeev@rocketmail.com \nSent: Wednesday, October 31, 2012 2:41 AM\nSubject: "This is my test question"\n \n\n  \n \n \n'
        self.assertEqual(mail.extract_reply(text), 'this is my reply!')

    def test_kmail_plain_text_response_stripped(self):
        text = u'On Monday 01 October 2012 21:22:44 you wrote: \n\nthis is my reply!'
        self.assertEqual(mail.extract_reply(text), 'this is my reply!')

    def test_outlook_com_with_rtf_response_stripped(self):
        text = u'outlook.com (new hotmail) with RTF on \n\nSubject: "Posting a question by email." \nFrom: kp@kp-dev.askbot.com \nTo: aj_fitoria@hotmail.com \nDate: Thu, 1 Nov 2012 16:30:27 +0000'
        self.assertEqual(
            mail.extract_reply(text),
            'outlook.com (new hotmail) with RTF on'
        )
        self.assertEqual(
            mail.extract_reply(text),
            'outlook.com (new hotmail) with RTF on'
        )

    def test_outlook_com_plain_text_response_stripped(self):
        text = u'reply from hotmail without RTF \n________________________________ \n> Subject: "test with recovered signature" \n> From: kp@kp-dev.askbot.com \n> To: aj_fitoria@hotmail.com \n> Date: Thu, 1 Nov 2012 16:44:35 +0000'
        self.assertEqual(
            mail.extract_reply(text),
            u'reply from hotmail without RTF'
        )
