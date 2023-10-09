from django.test import TestCase
from django.urls import reverse

class TestHeadRequestMiddleware(TestCase):
    def test_head_request_middleware(self):
        response = self.client.head(reverse('user_signin'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'')
        content_length = response['Content-Length']
        self.assertTrue(int(content_length) > 0)
