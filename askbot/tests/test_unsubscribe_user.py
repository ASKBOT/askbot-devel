from urllib.parse import urlparse
from django.urls import reverse
import django.core.mail
from bs4 import BeautifulSoup
from askbot.tests.utils import AskbotTestCase, patch_jinja2
from askbot.models import User

patch_jinja2()

class UnsubscribeUserTests(AskbotTestCase):
    def test_unsubscribe_url_for_missing_user(self):
        user = User.objects.create_user('user', email='user@example.com')
        unsub_url = user.get_unsubscribe_url()
        user.delete()
        response = self.client.get(unsub_url)
        self.assertEqual(response.status_code, 200)

    def test_unsubscribe_user(self):
        user = User.objects.create_user('user', email='user@example.com')
        self.assertTrue(user.notification_subscriptions.exclude(frequency='n').exists())
        unsub_url = user.get_unsubscribe_url()

        #load the unsubscribe page
        response = self.client.get(unsub_url)
        soup = BeautifulSoup(response.content, 'html5lib')
        form = soup.find('form', attrs={'action': reverse('user_unsubscribe')})
        #collect the unsubscribe parameters from the page
        csrftoken = form.find('input', attrs={'name': 'csrfmiddlewaretoken'})['value']
        email = form.find('input', attrs={'name': 'email'})['value']
        key = form.find('input', attrs={'name': 'key'})['value']

        #post the unsubscribe form
        post_data = {
            'csrfmiddlewaretoken': csrftoken,
            'email': email,
            'key': key,
        }
        response = self.client.post(reverse('user_unsubscribe'), data=post_data)
        user = User.objects.get(email='user@example.com')
        self.assertFalse(user.notification_subscriptions.exclude(frequency='n').exists())

    def test_invalid_url(self):
        response = self.client.get(reverse('user_unsubscribe'))
        form = response.context['unsubscribe_form']
        form_errors = set(form.errors.keys())
        self.assertEqual(form_errors, {'email', 'key'})


    def test_invalid_key(self):
        user = User.objects.create_user('user', email='user@example.com')
        unsub_url = user.get_unsubscribe_url()
        user.email_key = ''
        response = self.client.get(unsub_url)
        self.assertEqual(response.context['result'], 'bad_key')
        soup = BeautifulSoup(response.content, 'html5lib')
        form = soup.find('form', attrs={'action': reverse('user_unsubscribe')})
        #collect the unsubscribe parameters from the page
        csrftoken = form.find('input', attrs={'name': 'csrfmiddlewaretoken'})['value']
        email = form.find('input', attrs={'name': 'email'})['value']
        key = form.find('input', attrs={'name': 'key'})['value']
        resend_key_btn = form.find('input', attrs={'name': 'resend_key'})

        post_data = {
            'csrfmiddlewaretoken': csrftoken,
            'email': email,
            'key': key,
            'resend_key': resend_key_btn['value'],
        }
        response = self.client.post(reverse('user_unsubscribe'), data=post_data)
        self.assertEqual(response.context['result'], 'key_resent')
        email = django.core.mail.outbox[0]
        email_html = email.alternatives[0][0]

        soup = BeautifulSoup(email_html, 'html5lib')
        link = soup.find('a')
        new_unsub_url = link['href']
        parsed_url = urlparse(new_unsub_url)
        new_unsub_url = parsed_url.path + '?' + parsed_url.query
        self.assertFalse(new_unsub_url == unsub_url)

        response = self.client.get(new_unsub_url)
        self.assertEqual(response.context['result'], 'ready')

        soup = BeautifulSoup(response.content, 'html5lib')
        form = soup.find('form', attrs={'action': reverse('user_unsubscribe')})
        #collect the unsubscribe parameters from the page
        csrftoken = form.find('input', attrs={'name': 'csrfmiddlewaretoken'})['value']
        email = form.find('input', attrs={'name': 'email'})['value']
        key = form.find('input', attrs={'name': 'key'})['value']

        self.assertTrue(key in new_unsub_url)
        self.assertTrue(email in new_unsub_url)
        self.assertTrue(csrftoken != '')
        # no point testing the form submission, it's done in test_unsubscribe_user
