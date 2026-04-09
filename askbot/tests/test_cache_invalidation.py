"""Tests for template cache invalidation."""
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key

from askbot.tests.utils import AskbotTestCase


class TemplateCacheInvalidationTests(AskbotTestCase):
    """Tests that thread cache invalidation clears template fragment cache."""

    def setUp(self):
        self.user = self.create_user('cacheuser')
        self.question = self.post_question(user=self.user)
        self.thread = self.question.thread

    def tearDown(self):
        cache.clear()

    def test_invalidate_clears_template_cache(self):
        """invalidate_cached_thread_content_html() should delete the
        template fragment cache for the thread."""
        key = make_template_fragment_key('thread-content-html', [self.thread.id])
        cache.set(key, '<html>cached</html>')
        self.assertIsNotNone(cache.get(key))

        self.thread.invalidate_cached_thread_content_html()
        self.assertIsNone(cache.get(key))

    def test_clear_cached_data_includes_template_cache(self):
        """clear_cached_data() should also clear the template fragment cache."""
        key = make_template_fragment_key('thread-content-html', [self.thread.id])
        cache.set(key, '<html>cached</html>')
        self.assertIsNotNone(cache.get(key))

        self.thread.clear_cached_data()
        self.assertIsNone(cache.get(key))

    def test_reset_cached_data_includes_template_cache(self):
        """reset_cached_data() should also clear the template fragment cache."""
        key = make_template_fragment_key('thread-content-html', [self.thread.id])
        cache.set(key, '<html>cached</html>')

        self.thread.reset_cached_data()
        self.assertIsNone(cache.get(key))
