from django.test import override_settings
from askbot.tests.utils import AskbotTestCase, with_settings
from askbot.spam_checker import is_spam
import responses
from urllib.parse import parse_qsl

AKISMET_CLASSIFIER = 'askbot.spam_checker.akismet_spam_checker.is_spam'
TEXT = 'hello foobar'
API_KEY = 'foobar'
CHECK_SPAM_URL = f'https://{API_KEY}.rest.akismet.com/1.1/comment-check'
SUBMIT_SPAM_URL = f'https://{API_KEY}.rest.akismet.com/1.1/submit-spam'
VERIFY_KEY_URL = 'https://rest.akismet.com/1.1/verify-key'
USER_AGENT = 'user_agent_string'
USER_IP = '0.0.0.0'
COMMENT_AUTHOR = 'bob'
COMMENT_AUTHOR_EMAIL = 'bob@example.com'


class User:
    def __init__(self, anon=False, username=COMMENT_AUTHOR, email=COMMENT_AUTHOR_EMAIL):
        self.anon = anon
        if anon:
            self.username = ''
        else:
            self.username = username
            self.email = email

    @property
    def is_authenticated(self):
        return not self.anon

    @property
    def is_anonymous(self):
        return self.anon


class AuthRequest:
    environ = {'HTTP_USER_AGENT': USER_AGENT}
    META = {'REMOTE_ADDR': USER_IP}
    def __init__(self, anon=False, username=COMMENT_AUTHOR, email=COMMENT_AUTHOR_EMAIL):
        self.user = User(anon, username, email)


def check_spam_callback(request):
    return (200, {}, 'false')

def verify_key_callback(request):
    return (200, {}, 'valid')

def mock_akismet():
    responses.add_callback(responses.POST,
                           CHECK_SPAM_URL,
                           callback=check_spam_callback)
    responses.add_callback(responses.POST,
                           VERIFY_KEY_URL,
                           callback=verify_key_callback)

def get_request_params(idx):
    """Returns dictionary of api call request parameters,
    as we made it.
    `idx` is the request order number, e.g
    """
    return dict(parse_qsl(responses.calls[idx].request.body))

class AkismetApiTests(AskbotTestCase):

    @responses.activate
    @override_settings(ASKBOT_SPAM_CHECKER_FUNCTION=AKISMET_CLASSIFIER)
    @with_settings(SPAM_FILTER_ENABLED=True, AKISMET_API_KEY=API_KEY, APP_URL='http://askbot.com/')
    def test_anon_user_no_author(self):
        mock_akismet()
        is_spam(TEXT, ip_addr=USER_IP, user_agent=USER_AGENT)
        params = get_request_params(1)
        self.assertEqual(params['comment_content'], TEXT)
        self.assertEqual(params['user_ip'], USER_IP)
        self.assertEqual(params['user_agent'], USER_AGENT)
        self.assertEqual(params['blog'], 'http://askbot.com/questions/')
        self.assertTrue('comment_author' not in params)
        self.assertTrue('comment_author_email' not in params)

    @responses.activate
    @override_settings(ASKBOT_SPAM_CHECKER_FUNCTION=AKISMET_CLASSIFIER)
    @with_settings(SPAM_FILTER_ENABLED=True, AKISMET_API_KEY=API_KEY, APP_URL='http://askbot.com/')
    def test_anon_user_with_author(self):
        mock_akismet()
        is_spam(TEXT, ip_addr=USER_IP, user_agent=USER_AGENT)
        params = get_request_params(1)
        self.assertEqual(params['comment_content'], TEXT)
        self.assertEqual(params['user_ip'], USER_IP)
        self.assertEqual(params['user_agent'], USER_AGENT)
        self.assertEqual(params['blog'], 'http://askbot.com/questions/')
        self.assertNotIn('comment_author', params)
        self.assertNotIn('comment_author_email', params)

    @responses.activate
    @override_settings(ASKBOT_SPAM_CHECKER_FUNCTION=AKISMET_CLASSIFIER)
    @with_settings(SPAM_FILTER_ENABLED=True, AKISMET_API_KEY=API_KEY, APP_URL='http://askbot.com/')
    def test_auth_user_no_author(self):
        mock_akismet()
        is_spam(TEXT, username='Request User', email='request@example.com', ip_addr=USER_IP, user_agent=USER_AGENT)
        params = get_request_params(1)
        self.assertEqual(params['comment_content'], TEXT)
        self.assertEqual(params['user_ip'], USER_IP)
        self.assertEqual(params['user_agent'], USER_AGENT)
        self.assertEqual(params['blog'], 'http://askbot.com/questions/')
        self.assertEqual(params['comment_author'], 'Request User')
        self.assertEqual(params['comment_author_email'], 'request@example.com')

    @responses.activate
    @override_settings(ASKBOT_SPAM_CHECKER_FUNCTION=AKISMET_CLASSIFIER)
    @with_settings(SPAM_FILTER_ENABLED=True, AKISMET_API_KEY=API_KEY, APP_URL='http://askbot.com/')
    def test_auth_user_with_author(self):
        mock_akismet()
        request = AuthRequest(username='Request User', email='request@example.com')
        from askbot import spam_checker
        spam_checker_params = spam_checker.get_params_from_request(request)
        spam_checker_params['ip_addr'] = USER_IP
        spam_checker_params['user_agent'] = USER_AGENT
        is_spam(TEXT, **spam_checker_params)
        params = get_request_params(1)
        self.assertEqual(params['comment_content'], TEXT)
        self.assertEqual(params['user_ip'], USER_IP)
        self.assertEqual(params['user_agent'], USER_AGENT)
        self.assertEqual(params['blog'], 'http://askbot.com/questions/')
        self.assertEqual(params['comment_author'], 'Request User')
        self.assertEqual(params['comment_author_email'], 'request@example.com')

    @responses.activate
    @override_settings(ASKBOT_SPAM_CHECKER_FUNCTION=AKISMET_CLASSIFIER)
    @with_settings(SPAM_FILTER_ENABLED=True, AKISMET_API_KEY=API_KEY, APP_URL='http://askbot.com/')
    def test_submit_spam_on_delete_spammer_content(self):
        mock_akismet()
        user = self.create_user()
        question = user.post_question(title='question title', body_text='body text', tags='tag1 tag2')
        user.delete_all_content_authored_by_user(user, mark_as_spam=True)
        params = get_request_params(1)
        self.assertEqual(params['comment_content'], question.get_text_content())
        self.assertEqual(params['user_ip'], question.revisions.all()[0].ip_addr)
        self.assertEqual(params['blog'], 'http://askbot.com/questions/')
        self.assertEqual(params['comment_author'], user.username)
        self.assertEqual(params['comment_author_email'], user.email)
        self.assertEqual(responses.calls[1].request.url, SUBMIT_SPAM_URL)
