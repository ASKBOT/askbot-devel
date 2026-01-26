"""
Integration tests for complete markdown-it-py setup with all plugins.
"""
from bs4 import BeautifulSoup
from django.test import TestCase
from askbot.tests.utils import with_settings
from askbot.utils.markup import get_md_converter, reset_md_converter, markdown_input_converter


class TestMarkdownIntegration(TestCase):

    def tearDown(self):
        """Reset singleton between tests"""
        reset_md_converter()
        super().tearDown()

    def test_basic_markdown(self):
        md = get_md_converter()
        text = "# Hello\n\nThis is **bold** and *italic*."
        html = md.render(text)

        self.assertIn('<h1>Hello</h1>', html)
        self.assertIn('<strong>bold</strong>', html)
        self.assertIn('<em>italic</em>', html)

    def test_tables(self):
        md = get_md_converter()
        text = """
| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
"""
        html = md.render(text)
        self.assertIn('<table>', html)
        self.assertIn('<th>Header 1</th>', html)
        self.assertIn('<td>Cell 1</td>', html)

    def test_footnotes(self):
        md = get_md_converter()
        text = "Text with footnote[^1]\n\n[^1]: Footnote content"
        html = md.render(text)

        soup = BeautifulSoup(html, 'html5lib')

        # Check for footnote reference (superscript with link)
        footnote_refs = soup.find_all('sup', class_='footnote-ref')
        self.assertEqual(len(footnote_refs), 1)

        # Check for footnote section at bottom
        footnote_section = soup.find('section', class_='footnotes')
        self.assertIsNotNone(footnote_section)

        # Check footnote content
        footnote_list = footnote_section.find('ol')
        self.assertIsNotNone(footnote_list)
        footnote_items = footnote_list.find_all('li')
        self.assertEqual(len(footnote_items), 1)
        self.assertIn('Footnote content', footnote_items[0].text)

    def test_task_lists(self):
        md = get_md_converter()
        text = "- [ ] Unchecked\n- [x] Checked"
        html = md.render(text)

        soup = BeautifulSoup(html, 'html5lib')

        # Find all checkbox inputs
        checkboxes = soup.find_all('input', type='checkbox')
        self.assertEqual(len(checkboxes), 2)

        # Verify unchecked box
        self.assertFalse(checkboxes[0].has_attr('checked'))

        # Verify checked box
        self.assertTrue(checkboxes[1].has_attr('checked'))

        # Verify task list classes
        task_list = soup.find('ul', class_='contains-task-list')
        self.assertIsNotNone(task_list)

        task_items = soup.find_all('li', class_='task-list-item')
        self.assertEqual(len(task_items), 2)

    def test_syntax_highlighting(self):
        md = get_md_converter()
        text = "```python\ndef hello():\n    pass\n```"
        html = md.render(text)

        soup = BeautifulSoup(html, 'html5lib')

        # Check for pre > code structure
        pre_tag = soup.find('pre')
        self.assertIsNotNone(pre_tag)

        code_tag = pre_tag.find('code')
        self.assertIsNotNone(code_tag)

        # Verify language class
        self.assertTrue(
            'language-python' in code_tag.get('class', []) or
            'highlight' in code_tag.get('class', [])
        )

        # Verify code content is present
        self.assertIn('def hello():', code_tag.text)
        self.assertIn('pass', code_tag.text)

    @with_settings(ENABLE_VIDEO_EMBEDDING=True)
    def test_video_embedding(self):
        # Video embedding uses extraction/restoration pattern, so must use
        # the full markdown_input_converter pipeline (not just md.render)
        text = "Check this: @[youtube](dQw4w9WgXcQ)"
        html = markdown_input_converter(text)

        soup = BeautifulSoup(html, 'html5lib')

        # Find video link element (video embedding now uses clickable links)
        link = soup.find('a', class_='js-video-link')
        self.assertIsNotNone(link)

        # Verify data attributes
        self.assertEqual(link['data-video-service'], 'youtube')
        self.assertEqual(link['data-video-id'], 'dQw4w9WgXcQ')

        # Verify surrounding text
        self.assertIn('Check this:', html)

    @with_settings(ENABLE_AUTO_LINKING=True,
                   AUTO_LINK_PATTERNS=r'#bug(\d+)',
                   AUTO_LINK_URLS=r'https://bugs.example.com/\1')
    def test_link_patterns_enabled(self):
        reset_md_converter()

        md = get_md_converter()
        text = "Fixed #bug123"
        html = md.render(text)

        soup = BeautifulSoup(html, 'html5lib')

        # Find the link
        links = soup.find_all('a')
        self.assertEqual(len(links), 1)

        link = links[0]
        self.assertEqual(link['href'], 'https://bugs.example.com/123')
        self.assertEqual(link.text.strip(), '#bug123')

        # Verify surrounding text preserved
        paragraph = soup.find('p')
        self.assertIn('Fixed', paragraph.text)

    @with_settings(MARKUP_CODE_FRIENDLY=True)
    def test_code_friendly_mode(self):
        reset_md_converter()

        md = get_md_converter()
        text = "variable_name with underscores"
        html = md.render(text)

        # Underscores should NOT create emphasis
        self.assertNotIn('<em>', html)
        self.assertIn('variable_name', html)

    @with_settings(MARKUP_CODE_FRIENDLY=True)
    def test_code_friendly_mode_underscore_emphasis_disabled(self):
        """Code-friendly mode: underscore emphasis syntax should be disabled."""
        reset_md_converter()

        md = get_md_converter()

        # _italic_ should NOT become <em>italic</em>
        html = md.render('This is _italic_ text')
        self.assertNotIn('<em>', html)
        self.assertIn('_italic_', html)

        # __bold__ should NOT become <strong>bold</strong>
        html2 = md.render('This is __bold__ text')
        self.assertNotIn('<strong>', html2)
        self.assertIn('__bold__', html2)

    @with_settings(MARKUP_CODE_FRIENDLY=True)
    def test_code_friendly_mode_asterisk_emphasis_works(self):
        """Code-friendly mode: asterisk emphasis should still work."""
        reset_md_converter()

        md = get_md_converter()
        text = "variable_name and *emphasized* and **bold** text"
        html = md.render(text)

        # Underscores should NOT create emphasis
        self.assertNotIn('_name', html.replace('variable_name', ''))
        self.assertIn('variable_name', html)

        # Asterisks SHOULD create emphasis
        self.assertIn('<em>emphasized</em>', html)
        self.assertIn('<strong>bold</strong>', html)

    @with_settings(ENABLE_MATHJAX=True)
    def test_mathjax_math_delimiters_preserved(self):
        """Test that math delimiters are preserved for MathJax"""
        reset_md_converter()

        md = get_md_converter()

        # Inline math
        text = "The equation $E = mc^2$ is famous"
        html = md.render(text)

        soup = BeautifulSoup(html, 'html5lib')
        paragraph = soup.find('p')
        self.assertIsNotNone(paragraph)

        # Verify math delimiters are preserved (not converted to HTML)
        para_html = str(paragraph)
        self.assertIn('$E = mc^2$', para_html)
        self.assertNotIn('<em>', para_html)  # No emphasis tags in math
        self.assertIn('famous', paragraph.text)

        # Display math
        text = "$$\\int_0^1 x dx = \\frac{1}{2}$$"
        html = md.render(text)

        soup = BeautifulSoup(html, 'html5lib')

        # Display math should be in its own block
        self.assertIn('$$', html)
        # Verify LaTeX commands preserved
        self.assertIn('\\int_0^1', html)
        self.assertIn('\\frac{1}{2}', html)

    @with_settings(ENABLE_MATHJAX=True)
    def test_mathjax_underscores_not_emphasis(self):
        """Test that underscores in math don't create emphasis"""
        reset_md_converter()

        md = get_md_converter()
        text = "$a_b$ and $x_{123}$"
        html = md.render(text)

        soup = BeautifulSoup(html, 'html5lib')

        # Verify no em or sub tags created
        em_tags = soup.find_all('em')
        sub_tags = soup.find_all('sub')
        self.assertEqual(len(em_tags), 0, "Found emphasis tags in math content")
        self.assertEqual(len(sub_tags), 0, "Found subscript tags in math content")

        # Verify math delimiters preserved
        paragraph = soup.find('p')
        para_html = str(paragraph)
        self.assertIn('$a_b$', para_html)
        self.assertIn('$x_{123}$', para_html)

    @with_settings(ENABLE_VIDEO_EMBEDDING=True)
    def test_combined_features(self):
        """Test document using multiple features"""
        # Uses markdown_input_converter for full pipeline including video extraction
        text = """
# Title

Some **bold text** and a video:

@[youtube](abc123)

Code example:

```python
def example():
    return True
```

| Feature | Status |
|---------|--------|
| Tables  | ✓      |

- [x] Task done
- [ ] Task pending
"""
        html = markdown_input_converter(text)

        soup = BeautifulSoup(html, 'html5lib')

        # Verify heading
        h1 = soup.find('h1')
        self.assertIsNotNone(h1)
        self.assertEqual(h1.text.strip(), 'Title')

        # Verify bold text
        strong = soup.find('strong')
        self.assertIsNotNone(strong)
        self.assertEqual(strong.text, 'bold text')

        # Verify video link (video embedding now uses clickable links)
        link = soup.find('a', class_='js-video-link')
        self.assertIsNotNone(link)
        self.assertEqual(link['data-video-service'], 'youtube')
        self.assertEqual(link['data-video-id'], 'abc123')

        # Verify code block with language class
        pre = soup.find('pre')
        self.assertIsNotNone(pre)
        code = pre.find('code')
        self.assertIsNotNone(code)
        self.assertTrue(
            'language-python' in code.get('class', []) or
            'highlight' in str(pre)
        )
        self.assertIn('def example():', code.text)

        # Verify table structure
        table = soup.find('table')
        self.assertIsNotNone(table)
        th_cells = table.find_all('th')
        self.assertEqual(len(th_cells), 2)

        # Verify task list
        checkboxes = soup.find_all('input', type='checkbox')
        self.assertEqual(len(checkboxes), 2)
        self.assertTrue(checkboxes[0].has_attr('checked'))  # First is checked
        self.assertFalse(checkboxes[1].has_attr('checked'))  # Second unchecked

    def test_email_autolink(self):
        """Email addresses should be converted to mailto links."""
        md = get_md_converter()
        text = "Contact user@example.com for help"
        html = md.render(text)

        soup = BeautifulSoup(html, 'html5lib')
        links = soup.find_all('a')

        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]['href'], 'mailto:user@example.com')
        self.assertEqual(links[0].string, 'user@example.com')

    def test_email_autolink_at_start(self):
        """Email at beginning of text should be linked."""
        md = get_md_converter()
        text = "user@example.com is my email"
        html = md.render(text)

        soup = BeautifulSoup(html, 'html5lib')
        links = soup.find_all('a')

        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]['href'], 'mailto:user@example.com')
        self.assertEqual(links[0].string, 'user@example.com')

    def test_email_autolink_with_plus(self):
        """Email with + sign in username should be linked."""
        md = get_md_converter()
        text = "Contact user+tag@example.com for help"
        html = md.render(text)

        soup = BeautifulSoup(html, 'html5lib')
        links = soup.find_all('a')

        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]['href'], 'mailto:user+tag@example.com')
        self.assertEqual(links[0].string, 'user+tag@example.com')

    def test_email_autolink_multiple(self):
        """Multiple email addresses should all be linked."""
        md = get_md_converter()
        text = "Email alice@example.com or bob@test.org"
        html = md.render(text)

        soup = BeautifulSoup(html, 'html5lib')
        links = soup.find_all('a')

        self.assertEqual(len(links), 2)
        self.assertEqual(links[0]['href'], 'mailto:alice@example.com')
        self.assertEqual(links[1]['href'], 'mailto:bob@test.org')

    def test_linkify_with_truncation(self):
        """Test that URL auto-linkification and truncation work together."""
        md = get_md_converter()

        text = """
Check out example.com for details.

Here's a longer URL: https://github.com/executablebooks/markdown-it-py-documentation

And a markdown link: [GitHub](https://github.com/executablebooks/markdown-it-py)

Code should not be linkified: `http://example.com`
"""
        html = md.render(text)
        soup = BeautifulSoup(html, 'html5lib')

        links = soup.find_all('a')
        # Should have 3 links (fuzzy matched, long auto-linkified, markdown link)
        self.assertEqual(len(links), 3, "Should have exactly 3 links")

        # Link 1: Fuzzy matched example.com (short, no truncation)
        self.assertEqual(links[0]['href'], "http://example.com")
        self.assertEqual(links[0].string, "example.com")
        self.assertNotIn('title', links[0].attrs, "Short URL should not have title attribute")

        # Link 2: Long auto-linkified URL (truncated with title)
        long_url = "https://github.com/executablebooks/markdown-it-py-documentation"
        self.assertEqual(links[1]['href'], long_url)
        self.assertTrue(links[1].string.endswith("…"), "Long URL should be truncated with ellipsis")
        self.assertEqual(links[1]['title'], long_url, "Truncated URL should have title with full URL")
        self.assertEqual(len(links[1].string), 40, "Truncated URL should be exactly 40 chars")

        # Link 3: Markdown link (not truncated, no title from truncation)
        self.assertEqual(links[2]['href'], "https://github.com/executablebooks/markdown-it-py")
        self.assertEqual(links[2].string, "GitHub")
        self.assertNotIn('title', links[2].attrs, "Markdown link should not have title attribute")

        # Verify code block is not linkified
        code = soup.find('code')
        self.assertIsNotNone(code)
        code_links = code.find_all('a')
        self.assertEqual(len(code_links), 0, "URLs in code should not be linkified")

    def test_linkify_url_with_quotes(self):
        """URLs containing quotes should be linked with proper encoding."""
        md = get_md_converter()
        text = 'http://example.com/quotes-are-"part"'
        html = md.render(text)

        soup = BeautifulSoup(html, 'html5lib')
        links = soup.find_all('a')

        self.assertEqual(len(links), 1)
        # Quotes should be URL-encoded in href
        self.assertEqual(links[0]['href'], 'http://example.com/quotes-are-%22part%22')

    def test_linkify_unicode_domain(self):
        """Unicode domains should be linked with punycode href."""
        md = get_md_converter()
        text = '✪df.ws/1234'
        html = md.render(text)

        soup = BeautifulSoup(html, 'html5lib')
        links = soup.find_all('a')

        self.assertEqual(len(links), 1)
        # Unicode domain should be converted to punycode in href
        self.assertEqual(links[0]['href'], 'http://xn--df-oiy.ws/1234')
        # Original unicode should appear in link text
        self.assertEqual(links[0].string, '✪df.ws/1234')

    def test_linkify_bare_domain_with_trailing_slash(self):
        """Bare domain with trailing slash should be auto-linked."""
        md = get_md_converter()
        text = 'example.com/'
        html = md.render(text)

        soup = BeautifulSoup(html, 'html5lib')
        links = soup.find_all('a')

        self.assertEqual(len(links), 1)
        # Should add http:// and create a link
        self.assertEqual(links[0]['href'], 'http://example.com/')

    def test_script_in_code_block_escaped(self):
        """Script tags in code blocks should be escaped (full pipeline test)."""
        text = '''```html
<script>alert('xss')</script>
```'''
        html = markdown_input_converter(text)

        # Verify raw script tag is NOT present (would be XSS)
        self.assertNotIn('<script>', html)

        # Verify the content is escaped - angle brackets should be entity-encoded
        # Pygments may split tags across spans but < and > must still be escaped
        self.assertIn('&lt;', html, "< should be escaped as &lt;")
        self.assertIn('&gt;', html, "> should be escaped as &gt;")

    def test_script_in_inline_code_escaped(self):
        """Script tags in inline code should be escaped (full pipeline test)."""
        text = "Use `<script>alert('xss')</script>` carefully"
        html = markdown_input_converter(text)

        # Verify raw script tag is NOT present (would be XSS)
        self.assertNotIn('<script>', html)
