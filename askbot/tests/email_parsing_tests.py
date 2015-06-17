# -*- coding: utf-8 -*-
from django.conf import settings as django_settings
from django.template import Context
from django.template.loader import get_template
from askbot import mail
from askbot.mail.messages import WelcomeEmailRespondable
from askbot import models
from askbot.tests import utils
from askbot.utils.html import get_text_from_html

class EmailParsingTests(utils.AskbotTestCase):

    def setUp(self):
        data = {
            'site_name': 'askbot.com',
            'email_code': 'DwFwndQty',
            'recipient_user': self.create_user()
        }
        email = WelcomeEmailRespondable(data)
        self.rendered_template = email.render_body()
        self.expected_output = 'Welcome to askbot.com!\n\nImportant: Please reply to this message, without editing it. We need this to determine your email signature and that the email address is valid and was typed correctly.\n\nUntil we receive the response from you, you will not be able ask or answer questions on askbot.com by email.\n\nSincerely,askbot.com Administrator\n\nDwFwndQty'

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

    def test_outlook_desktop1(self):
        text = """some real text

-----Original Message-----
From: forum@example.com [mailto:forum@example.com]
Sent: Wednesday, August 07, 2013 11:00 AM
To: Jane Doe
Subject: "One more test question from email."

"""
        self.assertEqual(mail.extract_reply(text), "some real text")

    def test_some_other(self):
        text = """some real text

-------- Original message --------
From: forum@example.com [mailto:forum@example.com]
Sent: Wednesday, August 07, 2013 11:00 AM
To: Jane Doe
Subject: "One more test question from email."

"""
        self.assertEqual(mail.extract_reply(text), "some real text")

    def test_some_other1(self):
        text = 'some text here\n\n\n-------- Original message --------\nFrom: forum@example.com\nDate:12/15/2013 2:35 AM (GMT-05:00)\nTo: Some One\nSubject: some subject\n\n\n\n'
        self.assertEqual(mail.extract_reply(text), 'some text here')

    def test_blackberry(self):

        text = """Lorem ipsum lorem ipsum
blah blah blah

some more text here

Joe

________________________________________
From: forum@ask.askbot.com
Sent: Thursday, August 15, 2013 1:58:21 AM
To: Mister Joe
Subject: Our forum: "some text in the subject line"
"""
        expected = """Lorem ipsum lorem ipsum
blah blah blah

some more text here

Joe"""
        self.assertEqual(mail.extract_reply(text), expected)
