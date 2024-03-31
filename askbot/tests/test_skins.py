import os
import shutil
import tempfile
from django.test import TestCase
from django.conf import settings as django_settings
from django.core.files.uploadedfile import UploadedFile
from askbot.conf import settings as askbot_settings
from askbot.skins import utils as skin_utils
from askbot.tests.utils import skip
from askbot.utils.path import mkdir_p
import askbot

class SkinTests(TestCase):

    def setUp(self):
        #create dummy skin
        self.temp_dir = tempfile.mkdtemp()
        self.skins_dir_backup = django_settings.ASKBOT_EXTRA_SKINS_DIR
        setattr(django_settings, 'ASKBOT_EXTRA_SKINS_DIR', self.temp_dir)
        skin_image_dir = os.path.join(
                            self.temp_dir,
                            'test_skin',
                            'media',
                            'images'
                        )
        mkdir_p(skin_image_dir)
        test_image_file = os.path.join(
                            askbot.get_install_directory(),
                            'tests',
                            'images',
                            'askbot-logo.svg'
                        )
        shutil.copy(test_image_file, skin_image_dir)

    def tearDown(self):
        #delete the dummy skin
        test_skin_dir = os.path.join(
                            self.temp_dir,
                            'test_skin'
                        )
        shutil.rmtree(self.temp_dir)
        askbot_settings.update('ASKBOT_DEFAULT_SKIN', 'default')
        django_settings.ASKBOT_EXTRA_SKINS_DIR = self.skins_dir_backup

    def assert_default_logo_in_skin(self, skin_name):
        url = skin_utils.get_media_url(askbot_settings.SITE_LOGO_URL)
        self.assertTrue('/' + skin_name + '/' in url)

    def test_default_skin_logo(self):
        """make sure that default logo is where it is expected"""
        self.assert_default_logo_in_skin('default')

    def test_switch_to_custom_skin_logo(self):
        askbot_settings.update('ASKBOT_DEFAULT_SKIN', 'test_skin')
        self.assert_default_logo_in_skin('test_skin')

    @skip
    def test_uploaded_logo(self):
        logo_src = os.path.join(
                            askbot.get_install_directory(),
                            'tests',
                            'images',
                            'askbot-logo.svg'
                        )
        logo_file = open(logo_src, 'rb')
        uploaded_file = UploadedFile(file=logo_file)
        askbot_settings.update('SITE_LOGO_URL', uploaded_file)
        logo_url = askbot_settings.SITE_LOGO_URL
        self.assertTrue(logo_url.startswith(django_settings.MEDIA_URL))
        response = self.client.get(logo_url, follow=True)
        self.assertTrue(response.status_code == 200)
