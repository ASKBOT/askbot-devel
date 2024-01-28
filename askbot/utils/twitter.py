import urllib.request, urllib.parse, urllib.error
from askbot.deps.django_authopenid.util import OAuthConnection

class Twitter(OAuthConnection):

    def __new__(cls):
        return super().__new__(cls, 'twitter')

    def __init__(self):
        super().__init__('twitter')
        self.tweet_url = 'https://api.twitter.com/1.1/statuses/update.json'

    def tweet(self, text, access_token=None):
        client = self.get_client(access_token)
        params = {'status': text}
        return self.send_request(client, self.tweet_url, 'POST', params=params)
