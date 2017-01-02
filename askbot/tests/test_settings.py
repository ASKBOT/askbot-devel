import askbot
from askbot.tests.utils import AskbotTestCase
from askbot.conf import settings as askbot_settings
from django.conf import settings as django_settings
from django.utils import translation

class SettingsTests(AskbotTestCase):
    def setUp(self):
        self.conf = {
            'language_mode': askbot.get_lang_mode(),
            'language_code': django_settings.LANGUAGE_CODE,
            'languages': django_settings.LANGUAGES
        }
        django_settings.ASKBOT_LANGUAGE_MODE = 'url-lang'
        django_settings.LANGUAGE_CODE = 'en'
        django_settings.LANGUAGES = (('en', 'English'), ('de', 'German'))
        translation.activate('en')

    def tearDown(self):
        django_settings.ASKBOT_LANGUAGE_MODE = self.conf['language_mode']
        django_settings.LANGUAGE_CODE = self.conf['language_code']
        django_settings.LANGUAGES = self.conf['languages']
        translation.activate(django_settings.LANGUAGE_CODE)

    def assertSettingEquals(self, key, value):
        d = askbot_settings.as_dict()
        self.assertEqual(d[key], value)

    def test_localized_setting(self):
        translation.activate('de')
        askbot_settings.as_dict()#hit settings in German
        backup = askbot_settings.WORDS_ASK_YOUR_QUESTION

        translation.activate('en')
        askbot_settings.update('WORDS_ASK_YOUR_QUESTION', 'Stelle deine frage', 'de')
        self.assertSettingEquals('WORDS_ASK_YOUR_QUESTION', 'Ask Your Question')
        translation.activate('de')
        self.assertSettingEquals('WORDS_ASK_YOUR_QUESTION', 'Stelle deine frage')

        askbot_settings.update('WORDS_ASK_YOUR_QUESTION', backup, 'de')

    def test_unlocalized_setting(self):
        backup = askbot_settings.MIN_REP_TO_VOTE_UP

        askbot_settings.update('MIN_REP_TO_VOTE_UP', 500)
        self.assertSettingEquals('MIN_REP_TO_VOTE_UP', 500)
        translation.activate('de')
        self.assertSettingEquals('MIN_REP_TO_VOTE_UP', 500)

        askbot_settings.update('MIN_REP_TO_VOTE_UP', backup)
