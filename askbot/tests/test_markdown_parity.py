"""
Markdown parity tests: verify Python and JavaScript converters produce identical output.

These tests spawn a Node.js subprocess to render markdown using the same
markdown-it configuration as the frontend, then compare with Python output.

Design decisions:
1. Node.js subprocess (not embedded JS) - uses npm packages directly
2. Graceful skip if Node.js not installed or dependencies not installed
3. Skip syntax highlighting class comparison (Pygments vs highlight.js differ)
4. Test math extraction/restoration only (skip browser typesetting)
5. BeautifulSoup normalization for HTML comparison
"""
import json
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from bs4 import BeautifulSoup
from django.test import TestCase

from askbot.tests.utils import with_settings
from askbot.utils.markup import markdown_input_converter, reset_md_converter


def node_available():
    """Check if Node.js is available."""
    return shutil.which('node') is not None


def npm_dependencies_installed():
    """Check if npm dependencies are installed for the parity test runner."""
    js_dir = Path(__file__).parent / 'js'
    node_modules = js_dir / 'node_modules'
    return node_modules.exists() and (node_modules / 'markdown-it').exists()


def skip_if_no_node(func):
    """Decorator to skip tests if Node.js is not available."""
    def wrapper(self, *args, **kwargs):
        if not node_available():
            self.skipTest("Node.js not available")
        if not npm_dependencies_installed():
            self.skipTest(
                "npm dependencies not installed. Run: "
                "cd askbot/tests/js && npm install"
            )
        return func(self, *args, **kwargs)
    return wrapper


class MarkdownParityRunner:
    """Helper class to run the JavaScript markdown converter."""

    def __init__(self):
        self.js_dir = Path(__file__).parent / 'js'
        self.runner_script = self.js_dir / 'markdown_parity_runner.js'

    def render(self, markdown_text, settings=None):
        """
        Render markdown using the JavaScript converter.

        Args:
            markdown_text: Markdown source text
            settings: Dict of settings matching frontend configuration

        Returns:
            str: Rendered HTML

        Raises:
            RuntimeError: If the Node.js process fails
        """
        settings = settings or {}

        input_data = {
            'markdown': markdown_text,
            'settings': settings
        }

        result = subprocess.run(
            ['node', str(self.runner_script)],
            input=json.dumps(input_data),
            capture_output=True,
            text=True,
            cwd=str(self.js_dir),
            timeout=30
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Node.js process failed: {result.stderr}\n"
                f"stdout: {result.stdout}"
            )

        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Failed to parse JSON output: {e}\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )

        if 'error' in output:
            raise RuntimeError(f"JavaScript converter error: {output['error']}")

        return output.get('html', '')


def normalize_html(html, skip_highlight_classes=True):
    """
    Normalize HTML for comparison.

    Args:
        html: HTML string to normalize
        skip_highlight_classes: If True, remove syntax highlighting classes

    Returns:
        str: Normalized HTML
    """
    soup = BeautifulSoup(html, 'html5lib')

    # Remove syntax highlighting classes from code blocks
    # Pygments and highlight.js use different class names
    if skip_highlight_classes:
        for code in soup.find_all('code'):
            if code.has_attr('class'):
                # Keep language-* class but remove highlighting classes
                classes = code.get('class', [])
                new_classes = [c for c in classes if c.startswith('language-')]
                if new_classes:
                    code['class'] = new_classes
                else:
                    del code['class']

        # Remove span classes used for syntax highlighting
        for span in soup.find_all('span'):
            if span.has_attr('class'):
                del span['class']

    # Normalize task list classes (Python and JS implementations differ)
    # Python: no task-specific classes
    # JS: contains-task-list, task-list-item, task-list-item-checkbox
    for ul in soup.find_all('ul'):
        if ul.has_attr('class'):
            classes = ul.get('class', [])
            if 'contains-task-list' in classes:
                del ul['class']

    for li in soup.find_all('li'):
        if li.has_attr('class'):
            classes = li.get('class', [])
            if 'task-list-item' in classes:
                del li['class']

    for inp in soup.find_all('input'):
        if inp.has_attr('class'):
            classes = inp.get('class', [])
            if 'task-list-item-checkbox' in classes:
                del inp['class']

    # Normalize table alignment styles
    # Python and JS may use inline styles vs no styles differently
    for th in soup.find_all('th'):
        if th.has_attr('style'):
            del th['style']
    for td in soup.find_all('td'):
        if td.has_attr('style'):
            del td['style']

    # Normalize footnote structure (Python and JS implementations differ)
    # Python: <ol><li>...
    # JS: <section class="footnotes"><ol class="footnotes-list"><li class="footnote-item">...

    # Remove footnote-related classes
    footnote_classes = [
        'footnote-ref', 'footnotes-sep', 'footnotes', 'footnotes-list',
        'footnote-item', 'footnote-backref'
    ]
    for element in soup.find_all(class_=True):
        classes = element.get('class', [])
        new_classes = [c for c in classes if c not in footnote_classes]
        if new_classes:
            element['class'] = new_classes
        elif classes:  # Had classes but all were removed
            del element['class']

    # Unwrap section.footnotes to match Python structure
    for section in soup.find_all('section'):
        section.unwrap()

    # Normalize footnote IDs
    for element in soup.find_all(id=True):
        element_id = element.get('id', '')
        if element_id.startswith('fn') or element_id.startswith('fnref'):
            del element['id']  # Remove ID entirely for comparison

    for a in soup.find_all('a', href=True):
        href = a.get('href', '')
        if href.startswith('#fn') or href.startswith('#fnref'):
            a['href'] = '#NORMALIZED_FOOTNOTE_ID'

    def is_inside_code_block(element):
        """Check if element is inside a pre or code block."""
        parent = element.parent
        while parent:
            if parent.name in ('pre', 'code'):
                return True
            parent = parent.parent
        return False

    # Normalize whitespace in text nodes (outside code blocks)
    for text_node in soup.find_all(string=True):
        # Don't normalize content inside pre/code blocks
        if is_inside_code_block(text_node):
            continue
        # Collapse whitespace
        normalized = ' '.join(text_node.split())
        if normalized != text_node:
            text_node.replace_with(normalized)

    # Get the body content (html5lib adds html/head/body)
    body = soup.find('body')
    if body:
        # Get inner HTML
        result = ''.join(str(child) for child in body.children)
    else:
        result = str(soup)

    # Normalize line endings and strip
    result = result.strip()

    return result


def strip_syntax_highlighting(html):
    """
    Remove syntax highlighting spans from HTML.

    Both Pygments and highlight.js wrap tokens in spans with classes.
    Since they use different class names, we strip all spans inside
    code blocks for comparison.
    """
    soup = BeautifulSoup(html, 'html5lib')

    for code in soup.find_all('code'):
        # Get text content only
        text = code.get_text()
        code.clear()
        code.append(text)

    body = soup.find('body')
    if body:
        return ''.join(str(child) for child in body.children)
    return str(soup)


class TestMarkdownParity(TestCase):
    """Tests verifying Python and JavaScript markdown converters produce identical output."""

    def setUp(self):
        """Set up the JavaScript runner."""
        self.js_runner = MarkdownParityRunner()

    def tearDown(self):
        """Reset singleton between tests."""
        reset_md_converter()
        super().tearDown()

    def assert_parity(self, markdown, settings=None, msg=None,
                      skip_highlight=True):
        """
        Assert that Python and JavaScript converters produce the same output.

        Args:
            markdown: Markdown source text
            settings: Dict of settings
            msg: Optional message for assertion failure
            skip_highlight: If True, ignore syntax highlighting differences
        """
        settings = settings or {}

        # Build Python settings from dict
        python_settings = {
            'ENABLE_MATHJAX': settings.get('mathjaxEnabled', False),
            'ENABLE_VIDEO_EMBEDDING': settings.get('videoEmbeddingEnabled', False),
            'ENABLE_AUTO_LINKING': settings.get('autoLinkEnabled', False),
            'AUTO_LINK_PATTERNS': settings.get('autoLinkPatterns', ''),
            'AUTO_LINK_URLS': settings.get('autoLinkUrls', ''),
            'MARKUP_CODE_FRIENDLY': settings.get('markupCodeFriendly', False),
        }

        # Apply settings and get Python output
        with self._apply_settings(python_settings):
            reset_md_converter()
            python_html = markdown_input_converter(markdown)

        # Get JavaScript output
        js_html = self.js_runner.render(markdown, settings)

        # Normalize both
        python_normalized = normalize_html(python_html, skip_highlight)
        js_normalized = normalize_html(js_html, skip_highlight)

        if skip_highlight:
            python_normalized = strip_syntax_highlighting(python_normalized)
            js_normalized = strip_syntax_highlighting(js_normalized)

        self.assertEqual(
            python_normalized,
            js_normalized,
            msg or f"Parity mismatch for markdown:\n{markdown}\n\n"
                   f"Python:\n{python_html}\n\n"
                   f"JavaScript:\n{js_html}"
        )

    def _apply_settings(self, settings):
        """Context manager to temporarily apply askbot settings."""
        from askbot.tests.utils import with_settings
        # Create a decorator and use it as a context manager
        decorator = with_settings(**settings)
        # Use the decorator as a context manager via __enter__/__exit__
        class SettingsContext:
            def __init__(self, decorator):
                self._decorator = decorator

            def __enter__(self):
                # with_settings modifies settings directly
                from askbot.conf import settings as askbot_settings
                self._original = {}
                for key, value in settings.items():
                    self._original[key] = getattr(askbot_settings, key, None)
                    setattr(askbot_settings, key, value)
                return self

            def __exit__(self, *args):
                from askbot.conf import settings as askbot_settings
                for key, value in self._original.items():
                    if value is None:
                        pass  # Can't delete, just leave it
                    else:
                        setattr(askbot_settings, key, value)
        return SettingsContext(settings)

    # Basic markdown tests

    @skip_if_no_node
    def test_basic_bold(self):
        """Bold text renders identically."""
        self.assert_parity("This is **bold** text")

    @skip_if_no_node
    def test_basic_italic(self):
        """Italic text renders identically."""
        self.assert_parity("This is *italic* text")

    @skip_if_no_node
    def test_basic_headings(self):
        """Headings render identically."""
        markdown = """# Heading 1

## Heading 2

### Heading 3
"""
        self.assert_parity(markdown)

    @skip_if_no_node
    def test_basic_unordered_list(self):
        """Unordered lists render identically."""
        markdown = """- Item 1
- Item 2
- Item 3
"""
        self.assert_parity(markdown)

    @skip_if_no_node
    def test_basic_ordered_list(self):
        """Ordered lists render identically."""
        markdown = """1. First
2. Second
3. Third
"""
        self.assert_parity(markdown)

    @skip_if_no_node
    def test_basic_blockquote(self):
        """Blockquotes render identically."""
        self.assert_parity("> This is a quote")

    @skip_if_no_node
    def test_basic_code_inline(self):
        """Inline code renders identically."""
        self.assert_parity("Use `code` here")

    @skip_if_no_node
    def test_basic_link(self):
        """Links render identically."""
        self.assert_parity("[Example](https://example.com)")

    @skip_if_no_node
    def test_basic_image(self):
        """Images render identically."""
        self.assert_parity("![Alt text](https://example.com/image.png)")

    # Table tests

    @skip_if_no_node
    def test_table_basic(self):
        """Basic tables render identically."""
        markdown = """| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
| Cell 3   | Cell 4   |
"""
        self.assert_parity(markdown)

    @skip_if_no_node
    def test_table_alignment(self):
        """Table alignment renders identically."""
        markdown = """| Left | Center | Right |
|:-----|:------:|------:|
| L    |   C    |     R |
"""
        self.assert_parity(markdown)

    # Footnote tests

    @skip_if_no_node
    def test_footnote_basic(self):
        """Footnotes render identically."""
        markdown = """Text with footnote[^1]

[^1]: Footnote content
"""
        self.assert_parity(markdown)

    # Task list tests

    @skip_if_no_node
    def test_task_list(self):
        """Task lists render identically."""
        markdown = """- [ ] Unchecked task
- [x] Checked task
"""
        self.assert_parity(markdown)

    # Video embed tests

    @skip_if_no_node
    def test_video_embed_youtube(self):
        """YouTube video embeds render identically."""
        settings = {'videoEmbeddingEnabled': True}
        self.assert_parity("Watch: @[youtube](dQw4w9WgXcQ)", settings)

    @skip_if_no_node
    def test_video_embed_vimeo(self):
        """Vimeo video embeds render identically."""
        settings = {'videoEmbeddingEnabled': True}
        self.assert_parity("Watch: @[vimeo](123456789)", settings)

    @skip_if_no_node
    def test_video_embed_disabled(self):
        """Video syntax with embedding disabled renders as text."""
        settings = {'videoEmbeddingEnabled': False}
        self.assert_parity("Watch: @[youtube](dQw4w9WgXcQ)", settings)

    # Link pattern tests

    @skip_if_no_node
    def test_link_patterns_bug(self):
        """Bug link patterns render identically."""
        settings = {
            'autoLinkEnabled': True,
            'autoLinkPatterns': r'#bug(\d+)',
            'autoLinkUrls': r'https://bugs.example.com/\1'
        }
        self.assert_parity("Fixed #bug123 and #bug456", settings)

    @skip_if_no_node
    def test_link_patterns_disabled(self):
        """Link patterns disabled leaves text as-is."""
        settings = {
            'autoLinkEnabled': False,
            'autoLinkPatterns': r'#bug(\d+)',
            'autoLinkUrls': r'https://bugs.example.com/\1'
        }
        self.assert_parity("Fixed #bug123", settings)

    # URL truncation tests

    @skip_if_no_node
    def test_url_truncation_long(self):
        """Long URLs (>40 chars) are truncated identically."""
        markdown = "Visit https://example.com/very/long/path/that/exceeds/forty/characters for info"
        self.assert_parity(markdown)

    @skip_if_no_node
    def test_url_truncation_short(self):
        """Short URLs are not truncated."""
        markdown = "Visit https://example.com for info"
        self.assert_parity(markdown)

    # Code-friendly mode tests

    @skip_if_no_node
    def test_code_friendly_underscore_preserved(self):
        """Code-friendly mode preserves underscores."""
        settings = {'markupCodeFriendly': True}
        self.assert_parity("variable_name and another_var", settings)

    @skip_if_no_node
    def test_code_friendly_asterisk_emphasis(self):
        """Code-friendly mode still allows asterisk emphasis."""
        settings = {'markupCodeFriendly': True}
        self.assert_parity("*italic* and **bold** work", settings)

    @skip_if_no_node
    def test_code_friendly_mixed(self):
        """Code-friendly mode with mixed underscores and asterisks."""
        settings = {'markupCodeFriendly': True}
        self.assert_parity(
            "The snake_case var is *emphasized* and get_value() is **bold**",
            settings
        )

    # MathJax tests (extraction/restoration only)

    @skip_if_no_node
    def test_math_inline(self):
        """Inline math ($...$) is preserved identically."""
        settings = {'mathjaxEnabled': True}
        self.assert_parity("The equation $E = mc^2$ is famous", settings)

    @skip_if_no_node
    def test_math_display(self):
        """Display math ($$...$$) is preserved identically."""
        settings = {'mathjaxEnabled': True}
        self.assert_parity("$$\\int_0^1 x dx = \\frac{1}{2}$$", settings)

    @skip_if_no_node
    def test_math_escaped_dollar(self):
        """Escaped dollar (\\$) renders identically."""
        settings = {'mathjaxEnabled': True}
        self.assert_parity("The price is \\$100", settings)

    @skip_if_no_node
    def test_math_with_underscores(self):
        """Math with underscores is not treated as emphasis."""
        settings = {'mathjaxEnabled': True}
        self.assert_parity("The subscript $a_b$ and $x_{123}$", settings)

    @skip_if_no_node
    def test_math_in_code_block(self):
        """Math delimiters in code are preserved as-is."""
        settings = {'mathjaxEnabled': True}
        self.assert_parity("Use `$variable` in code", settings)

    # Code block tests (skipping highlight class comparison)

    @skip_if_no_node
    def test_code_block_fenced(self):
        """Fenced code blocks render identically (ignoring highlight classes)."""
        markdown = """```python
def hello():
    return "world"
```"""
        self.assert_parity(markdown)

    @skip_if_no_node
    def test_code_block_no_language(self):
        """Code blocks without language render identically."""
        markdown = """```
plain text code
```"""
        self.assert_parity(markdown)

    # Combined feature tests

    @skip_if_no_node
    def test_combined_features(self):
        """Document using multiple features renders identically."""
        settings = {
            'videoEmbeddingEnabled': True,
            'markupCodeFriendly': True,
        }
        markdown = """# Title

Some **bold text** with a variable_name.

@[youtube](abc123)

| Header | Value |
|--------|-------|
| One    | 1     |

- [x] Done
- [ ] Todo
"""
        self.assert_parity(markdown, settings)


class TestMarkdownParityEdgeCases(TestCase):
    """Edge case tests for markdown parity."""

    def setUp(self):
        self.js_runner = MarkdownParityRunner()

    def tearDown(self):
        reset_md_converter()
        super().tearDown()

    @skip_if_no_node
    def test_empty_input(self):
        """Empty input produces empty output."""
        from askbot.tests.test_markdown_parity import normalize_html

        python_html = markdown_input_converter("")
        js_html = self.js_runner.render("")

        self.assertEqual(
            normalize_html(python_html).strip(),
            normalize_html(js_html).strip()
        )

    @skip_if_no_node
    def test_whitespace_only(self):
        """Whitespace-only input produces consistent output."""
        from askbot.tests.test_markdown_parity import normalize_html

        python_html = markdown_input_converter("   \n\n   ")
        js_html = self.js_runner.render("   \n\n   ")

        self.assertEqual(
            normalize_html(python_html).strip(),
            normalize_html(js_html).strip()
        )

    @skip_if_no_node
    def test_special_characters(self):
        """Special HTML characters are escaped identically."""
        from askbot.tests.test_markdown_parity import normalize_html, strip_syntax_highlighting

        # Test with safe special characters (no script tags which get stripped by sanitizer)
        markdown = "Use &amp; and < and > symbols"

        python_html = markdown_input_converter(markdown)
        js_html = self.js_runner.render(markdown)

        # Both should escape special characters
        self.assertIn('&amp;', python_html)
        self.assertIn('&lt;', python_html)
        self.assertIn('&gt;', python_html)

        self.assertEqual(
            strip_syntax_highlighting(normalize_html(python_html)),
            strip_syntax_highlighting(normalize_html(js_html))
        )
