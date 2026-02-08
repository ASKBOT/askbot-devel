"""Tests for the custom link patterns plugin."""
from bs4 import BeautifulSoup
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

        soup = BeautifulSoup(html, 'html5lib')

        # Should have exactly 2 links
        links = soup.find_all('a')
        self.assertEqual(len(links), 2)

        # Verify bug link
        bug_link = [l for l in links if 'bugs.example.com' in l['href']][0]
        self.assertEqual(bug_link['href'], 'https://bugs.example.com/456')
        self.assertEqual(bug_link.text, '#bug456')

        # Verify mention link
        mention_link = [l for l in links if 'github.com' in l['href']][0]
        self.assertEqual(mention_link['href'], 'https://github.com/alice')
        self.assertEqual(mention_link.text, '@alice')

        # Verify surrounding text preserved
        paragraph = soup.find('p')
        self.assertIn('Fixed', paragraph.text)
        self.assertIn('by', paragraph.text)

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

        soup = BeautifulSoup(html, 'html5lib')

        # Should have exactly 1 link (the one in text, not in code)
        links = soup.find_all('a')
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]['href'], 'https://bugs.example.com/123')

        # Verify code element exists and contains unlinked pattern
        code = soup.find('code')
        self.assertIsNotNone(code)
        self.assertIn('#bug456', code.text)

        # Ensure no link inside code element
        code_links = code.find_all('a')
        self.assertEqual(len(code_links), 0)

    def test_invalid_regex_ignored(self):
        # Plugin should not crash on invalid regex
        md = MarkdownIt().use(link_patterns_plugin, {
            'enabled': True,
            'patterns': r'[invalid(regex',  # Missing closing ]
            'urls': r'https://example.com',
        })

        text = "Some text"
        html = md.render(text)

        soup = BeautifulSoup(html, 'html5lib')

        # Verify text rendered properly in paragraph
        paragraph = soup.find('p')
        self.assertIsNotNone(paragraph)
        self.assertEqual(paragraph.text.strip(), 'Some text')

        # Verify no links created due to invalid regex
        links = soup.find_all('a')
        self.assertEqual(len(links), 0)

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
