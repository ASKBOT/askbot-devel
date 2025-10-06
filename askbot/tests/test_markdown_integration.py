"""
Integration tests for complete markdown-it-py setup with all plugins.
"""
from django.test import TestCase
from askbot.tests.utils import with_settings
from askbot.utils.markup import get_md_converter, reset_md_converter


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
        self.assertIn('footnote', html.lower())

    def test_task_lists(self):
        md = get_md_converter()
        text = "- [ ] Unchecked\n- [x] Checked"
        html = md.render(text)
        self.assertTrue('checkbox' in html.lower() or 'task' in html.lower())

    def test_syntax_highlighting(self):
        md = get_md_converter()
        text = "```python\ndef hello():\n    pass\n```"
        html = md.render(text)
        self.assertIn('highlight', html)

    def test_video_embedding(self):
        md = get_md_converter()
        text = "Check this: @[youtube](dQw4w9WgXcQ)"
        html = md.render(text)
        self.assertIn('youtube.com/embed/dQw4w9WgXcQ', html)
        self.assertIn('iframe', html)

    @with_settings(ENABLE_AUTO_LINKING=True,
                   AUTO_LINK_PATTERNS=r'#bug(\d+)',
                   AUTO_LINK_URLS=r'https://bugs.example.com/\1')
    def test_link_patterns_enabled(self):
        reset_md_converter()

        md = get_md_converter()
        text = "Fixed #bug123"
        html = md.render(text)

        self.assertIn('bugs.example.com/123', html)

    @with_settings(MARKUP_CODE_FRIENDLY=True)
    def test_code_friendly_mode(self):
        reset_md_converter()

        md = get_md_converter()
        text = "variable_name with underscores"
        html = md.render(text)

        # Underscores should NOT create emphasis
        self.assertNotIn('<em>', html)
        self.assertIn('variable_name', html)

    @with_settings(ENABLE_MATHJAX=True)
    def test_mathjax_math_delimiters_preserved(self):
        """Test that math delimiters are preserved for MathJax"""
        reset_md_converter()

        md = get_md_converter()

        # Inline math
        text = "The equation $E = mc^2$ is famous"
        html = md.render(text)
        self.assertTrue('$E = mc^2$' in html or '$E = mc^2$' in html.replace('&nbsp;', ' '))

        # Display math
        text = "$$\\int_0^1 x dx = \\frac{1}{2}$$"
        html = md.render(text)
        self.assertIn('$$', html)
        self.assertTrue('\\int_0^1' in html or r'\int_0^1' in html)

    @with_settings(ENABLE_MATHJAX=True)
    def test_mathjax_underscores_not_emphasis(self):
        """Test that underscores in math don't create emphasis"""
        reset_md_converter()

        md = get_md_converter()
        text = "$a_b$ and $x_{123}$"
        html = md.render(text)

        # Should NOT have <em> or <sub> tags inside math
        # Math content should be preserved verbatim
        self.assertTrue('$a_b$' in html or '$a_b$' in html.replace('&nbsp;', ' '))
        self.assertTrue('<em>' not in html or html.count('<em>') == 0)

    def test_combined_features(self):
        """Test document using multiple features"""
        md = get_md_converter()
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
        html = md.render(text)

        # Check all features rendered
        self.assertIn('<h1>Title</h1>', html)
        self.assertIn('<strong>bold text</strong>', html)
        self.assertIn('youtube.com/embed/abc123', html)
        self.assertTrue('highlight' in html or 'class="language-python"' in html)
        self.assertIn('<table>', html)
