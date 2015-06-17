from askbot.deps.django_authopenid.protocols.oauth1 import OAuth1Provider
from askbot.conf import settings as askbot_settings
import jwt

class Provider(OAuth1Provider):
    def __init__(self):
        """returns mediawiki user id given the access token"""
        self.name = 'mediawiki'
        self.display_name = 'MediaWiki'
        self.request_token_url = 'https://www.mediawiki.org/w/index.php?title=Special:OAuth/initiate'
        self.access_token_url = 'https://www.mediawiki.org/w/index.php?title=Special:OAuth/token'
        self.authorize_url = 'https://www.mediawiki.org/w/index.php?title=Special:OAuth/authorize'
        self.authenticate_url = 'https://www.mediawiki.org/w/index.php?title=Special:OAuth/authorize'
        self.identify_url = 'https://www.mediawiki.org/w/index.php?title=Special:OAuth/identify'
        self.consumer_key = askbot_settings.MEDIAWIKI_KEY
        self.consumer_secret = askbot_settings.MEDIAWIKI_SECRET
        self.icon_media_path = askbot_settings.MEDIAWIKI_SITE_ICON
        self.one_click_registration = askbot_settings.MEDIAWIKI_ONE_CLICK_REGISTRATION_ENABLED
        self.callback_is_oob = True
        self.mediawiki_data = None

    def obtain_mediawiki_data(self):
        if not self.mediawiki_data:
            client = self.get_client(self.access_token)
            url, body = self.normalize_url_and_params(self.identify_url, {})
            response, content = client.request(url, 'POST', body=body)
            self.mediawiki_data = jwt.decode(
                        content,
                        self.consumer_secret,
                        audience=self.consumer_key
                    )

    def get_user_id(self):
        self.obtain_mediawiki_data()
        return self.mediawiki_data['sub']

    def get_username(self):
        self.obtain_mediawiki_data()
        return self.mediawiki_data['username']
