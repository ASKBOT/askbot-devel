"""Tests for the custom link patterns plugin."""
from django.test import TestCase
from markdown_it import MarkdownIt
from askbot.utils.markdown_plugins.link_patterns import link_patterns_plugin


class TestLinkPatternsPlugin(TestCase):

    def test_simple_pattern(self):
        md = MarkdownIt().use(link_patterns_plugin, {
            'enabled': True,
            'patterns': r'#bug(\d+)',
            'urls': r'https://bugs.example.com/\1',
        })

        text = "Fixed #bug123 yesterday"
        html = md.render(text)

        self.assertIn('<a href="https://bugs.example.com/123">#bug123</a>', html)
        self.assertIn('Fixed', html)
        self.assertIn('yesterday', html)

    def test_multiple_patterns(self):
        md = MarkdownIt().use(link_patterns_plugin, {
            'enabled': True,
            'patterns': '#bug(\\d+)\n@(\\w+)',
            'urls': 'https://bugs.example.com/\\1\nhttps://github.com/\\1',
        })

        text = "Fixed #bug456 by @alice"
        html = md.render(text)

        self.assertIn('bugs.example.com/456', html)
        self.assertIn('github.com/alice', html)

    def test_disabled_plugin(self):
        md = MarkdownIt().use(link_patterns_plugin, {
            'enabled': False,
            'patterns': r'#bug(\d+)',
            'urls': r'https://bugs.example.com/\1',
        })

        text = "Fixed #bug123"
        html = md.render(text)

        # Should not create links
        self.assertNotIn('bugs.example.com', html)
        self.assertIn('#bug123', html)

    def test_overlapping_matches(self):
        # Only first match should be linkified
        md = MarkdownIt().use(link_patterns_plugin, {
            'enabled': True,
            'patterns': 'bug(\\d+)\n#bug(\\d+)',  # Use actual newline, not raw string
            'urls': 'https://example1.com/\\1\nhttps://example2.com/\\1',
        })

        text = "#bug123"
        html = md.render(text)

        # Should only match the second pattern since it starts earlier
        self.assertIn('example2.com/123', html)
        self.assertNotIn('example1.com', html)

    def test_pattern_in_code_block_not_linkified(self):
        md = MarkdownIt().use(link_patterns_plugin, {
            'enabled': True,
            'patterns': r'#bug(\d+)',
            'urls': r'https://bugs.example.com/\1',
        })

        text = "Text #bug123 and `code #bug456` here"
        html = md.render(text)

        # #bug123 should be linked (in text)
        self.assertIn('bugs.example.com/123', html)

        # #bug456 should NOT be linked (in code)
        self.assertNotIn('bugs.example.com/456', html)

    def test_invalid_regex_ignored(self):
        # Plugin should not crash on invalid regex
        md = MarkdownIt().use(link_patterns_plugin, {
            'enabled': True,
            'patterns': r'[invalid(regex',  # Missing closing ]
            'urls': r'https://example.com',
        })

        text = "Some text"
        html = md.render(text)
        self.assertIn('Some text', html)  # Should still render

    def test_mismatched_pattern_url_count(self):
        # Should disable auto-linking if counts don't match
        md = MarkdownIt().use(link_patterns_plugin, {
            'enabled': True,
            'patterns': r'#bug(\d+)\n@(\w+)',
            'urls': r'https://bugs.example.com/\1',  # Only one URL
        })

        text = "Fixed #bug123"
        html = md.render(text)

        # Should not create links due to mismatch
        self.assertNotIn('bugs.example.com', html)
