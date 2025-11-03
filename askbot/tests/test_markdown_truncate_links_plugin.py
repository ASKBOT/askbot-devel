"""Tests for the truncate links plugin."""
from bs4 import BeautifulSoup
from django.test import TestCase
from markdown_it import MarkdownIt
from askbot.utils.markdown_plugins.truncate_links import truncate_links_plugin


class TestTruncateLinksPlugin(TestCase):
    """Test cases for URL linkification and truncation."""

    def setUp(self):
        """Set up markdown-it with linkify and truncate_links plugins."""
        self.md = MarkdownIt('commonmark', {'linkify': True})
        self.md.enable('linkify')
        self.md.use(truncate_links_plugin, {'trim_limit': 40})

    def test_inline_code_protection(self):
        """URLs in inline code (backticks) should NOT be linkified."""
        text = "Use `http://api.example.com/v1` endpoint"
        html = self.md.render(text)
        soup = BeautifulSoup(html, 'html5lib')

        # Find code element
        code = soup.find('code')
        self.assertIsNotNone(code, "No code element found")
        self.assertEqual(code.string, "http://api.example.com/v1")

        # Verify no link inside code
        code_links = code.find_all('a')
        self.assertEqual(len(code_links), 0, "URL in inline code was linkified")

    def test_code_block_protection(self):
        """URLs in fenced code blocks should NOT be linkified."""
        text = """```python
url = "http://example.com"
```"""
        html = self.md.render(text)
        soup = BeautifulSoup(html, 'html5lib')

        # Find code block
        code = soup.find('code')
        self.assertIsNotNone(code)

        # Verify no links in code block
        code_links = code.find_all('a')
        self.assertEqual(len(code_links), 0, "URL in code block was linkified")

        # Verify URL text is present
        self.assertIn("http://example.com", code.get_text())

    def test_plain_url_linkification(self):
        """Plain URLs with protocols should be auto-linkified."""
        text = "Visit http://example.com for details"
        html = self.md.render(text)
        soup = BeautifulSoup(html, 'html5lib')

        # Find link
        link = soup.find('a')
        self.assertIsNotNone(link, "URL was not linkified")
        self.assertEqual(link['href'], "http://example.com")
        self.assertEqual(link.string, "http://example.com")

    def test_fuzzy_link_detection(self):
        """URLs without protocol (fuzzy matching) should be linkified."""
        text = "Visit example.com for details"
        html = self.md.render(text)
        soup = BeautifulSoup(html, 'html5lib')

        # Find link
        link = soup.find('a')
        self.assertIsNotNone(link, "Fuzzy URL was not linkified")
        self.assertEqual(link['href'], "http://example.com")
        self.assertEqual(link.string, "example.com")

    def test_www_detection(self):
        """URLs starting with www. should be linkified."""
        text = "Check www.example.com"
        html = self.md.render(text)
        soup = BeautifulSoup(html, 'html5lib')

        # Find link
        link = soup.find('a')
        self.assertIsNotNone(link, "www. URL was not linkified")
        self.assertEqual(link['href'], "http://www.example.com")
        self.assertEqual(link.string, "www.example.com")

    def test_url_truncation_at_40_chars(self):
        """URLs longer than 40 chars should be truncated with ellipsis."""
        long_url = "https://github.com/executablebooks/markdown-it-py-documentation"
        text = f"See {long_url}"
        html = self.md.render(text)
        soup = BeautifulSoup(html, 'html5lib')

        # Find link
        link = soup.find('a')
        self.assertIsNotNone(link, "Long URL was not linkified")
        self.assertEqual(link['href'], long_url)

        # Verify truncation: exactly 39 chars + "…" = 40 chars total display
        display_text = link.string
        self.assertEqual(len(display_text), 40, f"Display text should be exactly 40 chars, got {len(display_text)}")
        self.assertTrue(display_text.endswith("…"), "Truncated URL should end with ellipsis")
        self.assertEqual(display_text, "https://github.com/executablebooks/mark…")

    def test_title_attribute_on_truncated_url(self):
        """Truncated URLs should have title attribute with full URL."""
        long_url = "https://github.com/executablebooks/markdown-it-py-documentation"
        text = long_url
        html = self.md.render(text)
        soup = BeautifulSoup(html, 'html5lib')

        # Find link
        link = soup.find('a')
        self.assertIsNotNone(link)

        # Verify title attribute contains full URL
        self.assertIn('title', link.attrs, "Truncated URL missing title attribute")
        self.assertEqual(link['title'], long_url)

    def test_no_title_attribute_on_short_url(self):
        """Short URLs should NOT have title attribute."""
        short_url = "http://example.com"
        text = short_url
        html = self.md.render(text)
        soup = BeautifulSoup(html, 'html5lib')

        # Find link
        link = soup.find('a')
        self.assertIsNotNone(link)

        # Verify no title attribute
        self.assertNotIn('title', link.attrs, "Short URL should not have title attribute")

    def test_markdown_links_unchanged(self):
        """Markdown-style links should NOT be truncated."""
        long_url = "https://github.com/executablebooks/markdown-it-py-documentation"
        text = f"[Click here]({long_url})"
        html = self.md.render(text)
        soup = BeautifulSoup(html, 'html5lib')

        # Find link
        link = soup.find('a')
        self.assertIsNotNone(link)
        self.assertEqual(link['href'], long_url)

        # Verify link text is NOT truncated (it's the label, not the URL)
        self.assertEqual(link.string, "Click here")

        # Verify no title attribute (this is a markdown link, not auto-linkified)
        self.assertNotIn('title', link.attrs, "Markdown link should not have title from truncation")

    def test_multiple_urls_in_text(self):
        """Multiple URLs in same text should all be linkified and truncated."""
        text = "Visit example.com and also check https://github.com/executablebooks/markdown-it-py-documentation"
        html = self.md.render(text)
        soup = BeautifulSoup(html, 'html5lib')

        # Find all links
        links = soup.find_all('a')
        self.assertEqual(len(links), 2, "Should have exactly 2 links")

        # Verify first link (short)
        self.assertEqual(links[0]['href'], "http://example.com")
        self.assertEqual(links[0].string, "example.com")
        self.assertNotIn('title', links[0].attrs)

        # Verify second link (long, truncated)
        long_url = "https://github.com/executablebooks/markdown-it-py-documentation"
        self.assertEqual(links[1]['href'], long_url)
        self.assertTrue(links[1].string.endswith("…"))
        self.assertEqual(links[1]['title'], long_url)

    def test_url_with_path_and_query(self):
        """URLs with paths and query strings should be linkified."""
        url = "https://example.com/path/to/page?foo=bar&baz=qux"
        text = f"Check {url}"
        html = self.md.render(text)
        soup = BeautifulSoup(html, 'html5lib')

        # Find link
        link = soup.find('a')
        self.assertIsNotNone(link)
        self.assertEqual(link['href'], url)

        # This URL is 48 chars, should be truncated
        self.assertTrue(link.string.endswith("…"))
        self.assertEqual(link['title'], url)

    def test_url_with_anchor(self):
        """URLs with anchors/fragments should be linkified."""
        url = "https://example.com/some_page.html#anchor"
        text = url
        html = self.md.render(text)
        soup = BeautifulSoup(html, 'html5lib')

        # Find link
        link = soup.find('a')
        self.assertIsNotNone(link)
        self.assertEqual(link['href'], url)

        # Verify truncation (45 chars > 40)
        self.assertTrue(link.string.endswith("…"))
        self.assertEqual(link['title'], url)

    def test_url_at_line_boundaries(self):
        """URLs at start/end of lines should be linkified."""
        text = """http://example.com
middle text www.example.com middle
example.com"""
        html = self.md.render(text)
        soup = BeautifulSoup(html, 'html5lib')

        # Should have 3 links
        links = soup.find_all('a')
        self.assertEqual(len(links), 3, "All 3 URLs should be linkified")

        self.assertEqual(links[0]['href'], "http://example.com")
        self.assertEqual(links[1]['href'], "http://www.example.com")
        self.assertEqual(links[2]['href'], "http://example.com")

    def test_url_with_port(self):
        """URLs with port numbers should be linkified."""
        url = "http://example.com:8080/api/v1"
        text = f"API at {url}"
        html = self.md.render(text)
        soup = BeautifulSoup(html, 'html5lib')

        # Find link
        link = soup.find('a')
        self.assertIsNotNone(link)
        self.assertEqual(link['href'], url)
        self.assertEqual(link.string, url)  # 31 chars, not truncated

    def test_https_url(self):
        """HTTPS URLs should be linkified."""
        url = "https://secure.example.com/login"
        text = f"Login at {url}"
        html = self.md.render(text)
        soup = BeautifulSoup(html, 'html5lib')

        # Find link
        link = soup.find('a')
        self.assertIsNotNone(link)
        self.assertEqual(link['href'], url)

    def test_ftp_url(self):
        """FTP URLs should be linkified."""
        url = "ftp://files.example.com/downloads/file.zip"
        text = f"Download from {url}"
        html = self.md.render(text)
        soup = BeautifulSoup(html, 'html5lib')

        # Find link
        link = soup.find('a')
        self.assertIsNotNone(link)
        self.assertEqual(link['href'], url)

        # 44 chars, should be truncated
        self.assertTrue(link.string.endswith("…"))
        self.assertEqual(link['title'], url)
