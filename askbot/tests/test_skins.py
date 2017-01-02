import os
import shutil
import tempfile
from django.test import TestCase
from django.core.files.uploadedfile import UploadedFile
from django.conf import settings as django_settings
from askbot.conf import settings as askbot_settings
from askbot.skins import utils as skin_utils
from askbot.utils.path import mkdir_p
import askbot

class SkinTests(TestCase):

    def setUp(self):
        #create dummy skin
        self.temp_dir = tempfile.mkdtemp()
        self.skins_dir_backup = getattr(django_settings, 'ASKBOT_EXTRA_SKINS_DIR', None)
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
                            'logo.gif'
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
        if self.skins_dir_backup is None:
            del(django_settings.ASKBOT_EXTRA_SKINS_DIR)
        else:
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

    def test_uploaded_logo(self):
        logo_src = os.path.join(
                            askbot.get_install_directory(),
                            'tests',
                            'images',
                            'logo.gif'
                        )
        logo_file = open(logo_src, 'r')
        new_logo = UploadedFile(file = logo_file)
        askbot_settings.update('SITE_LOGO_URL', new_logo)
        logo_url = askbot_settings.SITE_LOGO_URL
        self.assertTrue(logo_url.startswith(django_settings.MEDIA_URL))
        response = self.client.get(logo_url, follow=True)
        self.assertTrue(response.status_code == 200)
