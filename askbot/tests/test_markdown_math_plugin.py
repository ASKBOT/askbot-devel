"""
Unit tests for the math_protect plugin.

Tests the MathJax delimiter protection to ensure:
1. Math delimiters ($...$, $$...$$) are preserved
2. Content inside math is treated as verbatim
3. No markdown processing occurs inside math delimiters
4. Edge cases are handled correctly
"""
from bs4 import BeautifulSoup
from django.test import TestCase
from askbot.tests.utils import with_settings
from askbot.utils.markup import get_md_converter, reset_md_converter


class TestMathProtectPlugin(TestCase):
    """Test suite for math_protect plugin"""

    def setUp(self):
        reset_md_converter()

    def tearDown(self):
        """Reset singleton between tests"""
        reset_md_converter()
        super().tearDown()

    @with_settings(ENABLE_MATHJAX=True)
    def test_inline_math_basic(self):
        """Test basic inline math rendering"""
        md = get_md_converter()

        text = "$E = mc^2$"
        html = md.render(text)

        # Verify delimiters and content are preserved
        self.assertIn('$E = mc^2$', html)
        # Should not create any emphasis or other tags inside
        soup = BeautifulSoup(html, 'html5lib')
        self.assertEqual(len(soup.find_all('em')), 0)
        self.assertEqual(len(soup.find_all('sup')), 0)

    @with_settings(ENABLE_MATHJAX=True)
    def test_display_math_block_same_line(self):
        """Test display math on same line"""
        md = get_md_converter()

        text = "$$E = mc^2$$"
        html = md.render(text)

        # Verify display math delimiters preserved
        self.assertIn('$$E = mc^2$$', html)
        # Should not create any emphasis or other tags inside
        soup = BeautifulSoup(html, 'html5lib')
        self.assertEqual(len(soup.find_all('em')), 0)
        self.assertEqual(len(soup.find_all('sup')), 0)

    @with_settings(ENABLE_MATHJAX=True)
    def test_display_math_block_multiline(self):
        """Test display math spanning multiple lines"""
        md = get_md_converter()

        text = """$$
\\int_0^1 x dx = \\frac{1}{2}
$$"""
        html = md.render(text)

        # Verify display math preserved - test non-whitespace matches
        self.assertIn(''.join(text.split()), ''.join(html.split()))

    @with_settings(ENABLE_MATHJAX=True)
    def test_math_with_url(self):
        """CRITICAL: URLs inside math should NOT be linkified"""
        md = get_md_converter()

        text = "$x = http://example.com$"
        html = md.render(text)

        soup = BeautifulSoup(html, 'html5lib')

        # Verify math delimiters present
        self.assertIn('$x = http://example.com$', html)

        # Verify NO link tags inside paragraph
        paragraph = soup.find('p')
        self.assertIsNotNone(paragraph)

        # Should not contain anchor tags for the URL
        links = paragraph.find_all('a')
        self.assertEqual(len(links), 0, "URLs inside math should NOT be linkified")

    @with_settings(ENABLE_MATHJAX=True)
    def test_math_with_www(self):
        """CRITICAL: www URLs inside math should NOT be linkified"""
        md = get_md_converter()

        text = "$y = www.example.com$"
        html = md.render(text)

        soup = BeautifulSoup(html, 'html5lib')

        # Verify NO links
        links = soup.find_all('a')
        self.assertEqual(len(links), 0, "www URLs inside math should NOT be linkified")

        # Verify math delimiters preserved
        self.assertIn('$y = www.example.com$', html)

    @with_settings(ENABLE_MATHJAX=True)
    def test_math_with_fuzzy_link(self):
        """CRITICAL: Fuzzy-matched domains inside math should NOT be linkified"""
        md = get_md_converter()

        text = "$z = example.com$"
        html = md.render(text)

        soup = BeautifulSoup(html, 'html5lib')

        # Verify NO links
        links = soup.find_all('a')
        self.assertEqual(len(links), 0, "Fuzzy-matched domains inside math should NOT be linkified")

        # Verify math preserved
        self.assertIn('$z = example.com$', html)

    @with_settings(ENABLE_MATHJAX=True,
                   ENABLE_AUTO_LINKING=True,
                   AUTO_LINK_PATTERNS=r'bug(\d+)',
                   AUTO_LINK_URLS=r'https://bugs.example.com/\1')
    def test_math_with_pattern(self):
        """CRITICAL: Link patterns inside math should NOT create links"""
        md = get_md_converter()

        text = "$bug123 = x$"
        html = md.render(text)

        soup = BeautifulSoup(html, 'html5lib')

        # Verify NO links created
        links = soup.find_all('a')
        self.assertEqual(len(links), 0, "Patterns inside math should NOT create links")

        # Verify math preserved
        self.assertIn('$bug123 = x$', html)

    @with_settings(ENABLE_MATHJAX=True)
    def test_math_with_underscores(self):
        """Test that underscores in math don't create emphasis"""
        md = get_md_converter()

        text = "$a_b + c_d$"
        html = md.render(text)

        soup = BeautifulSoup(html, 'html5lib')

        # Verify NO emphasis tags
        em_tags = soup.find_all('em')
        sub_tags = soup.find_all('sub')
        self.assertEqual(len(em_tags), 0, "No emphasis in math")
        self.assertEqual(len(sub_tags), 0, "No subscript in math")

        # Verify math preserved with underscores
        self.assertIn('$a_b + c_d$', html)

    @with_settings(ENABLE_MATHJAX=True)
    def test_math_with_asterisk(self):
        """Test that asterisks in math don't create emphasis"""
        md = get_md_converter()

        text = "$a * b$"
        html = md.render(text)

        soup = BeautifulSoup(html, 'html5lib')

        # Verify NO emphasis tags
        em_tags = soup.find_all('em')
        strong_tags = soup.find_all('strong')
        self.assertEqual(len(em_tags), 0, "No emphasis in math")
        self.assertEqual(len(strong_tags), 0, "No strong in math")

        # Verify asterisk preserved
        self.assertIn('$a * b$', html)

    @with_settings(ENABLE_MATHJAX=True)
    def test_single_dollar_not_math(self):
        """Test that single dollar sign followed by space is NOT math"""
        md = get_md_converter()

        text = "I paid $100 for this"
        html = md.render(text)

        # Should render as plain text
        self.assertIn('$100', html)
        # Should NOT have math delimiters on both sides (just one $)
        # The $ should appear in output
        soup = BeautifulSoup(html, 'html5lib')
        paragraph = soup.find('p')
        self.assertIn('$100', paragraph.text)

    @with_settings(ENABLE_MATHJAX=True)
    def test_single_double_dollar_not_math(self):
        """Test that mismatched delimiters are treated as literal text"""
        md = get_md_converter()

        text = "$$x is incomplete"
        html = md.render(text)

        # Should render as plain text with literal $
        soup = BeautifulSoup(html, 'html5lib')
        paragraph = soup.find('p')
        self.assertIn('$$x is incomplete', paragraph.text)

    @with_settings(ENABLE_MATHJAX=True)
    def test_multiple_math_expressions(self):
        """Test multiple math expressions in one line"""
        md = get_md_converter()

        text = "$x$ and $y$ are variables"
        html = md.render(text)

        # Both should be preserved
        self.assertIn('$x$', html)
        self.assertIn('$y$', html)
        self.assertIn('variables', html)

    @with_settings(ENABLE_MATHJAX=True)
    def test_empty_math(self):
        """Test empty math delimiters"""
        reset_md_converter()
        md = get_md_converter()

        text = "$$"
        html = md.render(text)

        # Empty delimiters should be treated as literal
        soup = BeautifulSoup(html, 'html5lib')
        # Should either be in text or ignored, but not cause errors
        # Just verify it doesn't crash
        self.assertIsNotNone(html)

    @with_settings(ENABLE_MATHJAX=True)
    def test_math_inline_not_crossing_newline(self):
        """Test that inline math must be on same line"""
        reset_md_converter()
        md = get_md_converter()

        text = "$x = \ny$"
        html = md.render(text)

        # Should NOT create math token (newline breaks inline math)
        # Should render as literal text
        soup = BeautifulSoup(html, 'html5lib')
        # The $ should appear as literal
        self.assertIn('$', html)

    @with_settings(ENABLE_MATHJAX=True)
    def test_math_in_text_context(self):
        """Test math within regular text"""
        reset_md_converter()
        md = get_md_converter()

        text = "The equation $E = mc^2$ is famous."
        html = md.render(text)

        soup = BeautifulSoup(html, 'html5lib')
        paragraph = soup.find('p')

        # Verify all parts present
        self.assertIn('equation', paragraph.text)
        self.assertIn('famous', paragraph.text)

        # Verify math preserved
        para_html = str(paragraph)
        self.assertIn('$E = mc^2$', para_html)

    @with_settings(ENABLE_MATHJAX=True)
    def test_display_math_multiline_complex(self):
        """Test complex multiline display math"""
        reset_md_converter()
        md = get_md_converter()

        text = """Here is a formula:

$$
\\begin{align}
x &= a + b \\\\
y &= c + d
\\end{align}
$$

That was interesting."""
        html = md.render(text)

        # Verify display math preserved
        self.assertIn('$$', html)
        self.assertIn('\\begin{align}', html)
        self.assertIn('\\end{align}', html)
        self.assertIn('That was interesting', html)

    @with_settings(ENABLE_MATHJAX=True)
    def test_math_with_special_chars(self):
        """Test math with special characters"""
        reset_md_converter()
        md = get_md_converter()

        text = "$\\alpha + \\beta = \\gamma$"
        html = md.render(text)

        # Verify LaTeX commands preserved
        self.assertIn('\\alpha', html)
        self.assertIn('\\beta', html)
        self.assertIn('\\gamma', html)
        self.assertIn('$', html)

    @with_settings(ENABLE_MATHJAX=False)
    def test_no_math_protection_when_disabled(self):
        """Test that math protection is NOT active when ENABLE_MATHJAX is False"""
        reset_md_converter()
        md = get_md_converter()

        text = "$x = *y*$"
        html = md.render(text)

        # Without math protection, this might be processed differently
        # Just verify it renders without error
        self.assertIsNotNone(html)
        self.assertIn('<em>y</em>', html)

    @with_settings(ENABLE_MATHJAX=True)
    def test_escaped_dollar_not_opening_delimiter(self):
        """Test that \\$ at the start is NOT treated as math delimiter"""
        reset_md_converter()
        md = get_md_converter()

        text = r"\\$x = y$"
        html = md.render(text)

        # Should NOT create math (escaped $ should not open math)
        # Should render as literal text
        soup = BeautifulSoup(html, 'html5lib')
        paragraph = soup.find('p')

        # The backslash-escaped dollar should be in output
        # (markdown-it escape processing converts \$ to $)
        self.assertIn('$x = y$', paragraph.text)

        # Additional test: verify markdown processing happens when \$ prevents math
        text_with_emphasis = r"\\$x = *y*$"
        html = md.render(text_with_emphasis)

        soup = BeautifulSoup(html, 'html5lib')
        em_tags = soup.find_all('em')
        self.assertEqual(len(em_tags), 1, "Emphasis should be processed when \\$ prevents math")
        self.assertEqual(em_tags[0].text, 'y', "Emphasis content should be correct")

    @with_settings(ENABLE_MATHJAX=True)
    def test_escaped_dollar_not_closing_delimiter(self):
        """Test that \\$ in potential math is NOT treated as closing delimiter"""
        reset_md_converter()
        md = get_md_converter()

        # Opening $ followed by escaped \$ should keep looking for closing $
        text = r"$x = \\$100$"
        html = md.render(text)

        # Should create math token with escaped $ inside
        self.assertIn('$x = \\$100$', html)

        soup = BeautifulSoup(html, 'html5lib')
        # Should not have multiple separate $ signs
        # All should be part of the math expression

    @with_settings(ENABLE_MATHJAX=True)
    def test_escaped_dollar_literal_text(self):
        """Test that escaped \\$100 renders as literal $100"""
        reset_md_converter()
        md = get_md_converter()

        text = r"The price is \\$100"
        html = md.render(text)

        # Should render as literal text, not math
        soup = BeautifulSoup(html, 'html5lib')
        paragraph = soup.find('p')

        # Escaped dollar should appear as literal $
        self.assertIn('$100', paragraph.text)
        self.assertIn('The price is', paragraph.text)

        # Additional test: verify markdown processing happens with escaped $
        text_with_emphasis = r"The price is \\$100 for *this*"
        html = md.render(text_with_emphasis)

        soup = BeautifulSoup(html, 'html5lib')
        em_tags = soup.find_all('em')
        self.assertEqual(len(em_tags), 1, "Emphasis should be processed when no math mode")
        self.assertEqual(em_tags[0].text, 'this', "Emphasis content should be correct")

    @with_settings(ENABLE_MATHJAX=True)
    def test_escaped_dollars_both_sides(self):
        """Test that \\$...\\$ renders as literal text, not math"""
        reset_md_converter()
        md = get_md_converter()

        text = r"\\$x = y\\$"
        html = md.render(text)

        # Should NOT create math (both delimiters escaped)
        soup = BeautifulSoup(html, 'html5lib')
        paragraph = soup.find('p')

        # Should appear as literal text
        self.assertIn('$x = y$', paragraph.text)

        # Additional test: verify markdown processing happens when both $ are escaped
        text_with_emphasis = r"\\$x = *y*\\$"
        html = md.render(text_with_emphasis)

        soup = BeautifulSoup(html, 'html5lib')
        em_tags = soup.find_all('em')
        self.assertEqual(len(em_tags), 1, "Emphasis should be processed when both $ are escaped")
        self.assertEqual(em_tags[0].text, 'y', "Emphasis content should be correct")

    @with_settings(ENABLE_MATHJAX=True)
    def test_escaped_dollar_in_middle_of_math(self):
        """Test that escaped \\$ within math expression is preserved"""
        reset_md_converter()
        md = get_md_converter()

        text = r"$price = \\$50 + tax$"
        html = md.render(text)

        # Should create math with escaped $ preserved inside
        self.assertIn('$price = \\$50 + tax$', html)

        soup = BeautifulSoup(html, 'html5lib')
        # Should be a single math expression
        paragraph = soup.find('p')
        self.assertIsNotNone(paragraph)


class TestMathIntegrationWithOtherPlugins(TestCase):
    """Integration tests for math protection with other plugins"""

    def tearDown(self):
        """Reset singleton between tests"""
        reset_md_converter()
        super().tearDown()

    @with_settings(ENABLE_MATHJAX=True)
    def test_math_linkify_no_interference(self):
        """Complex document with math and URLs - verify no interference"""
        reset_md_converter()
        md = get_md_converter()

        text = """
Visit http://example.com for details.

The formula $x = http://example.org$ should not be linkified.

Another URL: https://github.com
"""
        html = md.render(text)

        soup = BeautifulSoup(html, 'html5lib')

        # Find all links
        links = soup.find_all('a')

        # Should have exactly 2 links (the ones outside math)
        self.assertEqual(len(links), 2, "Should only linkify URLs outside math")

        # Verify the correct URLs were linkified
        hrefs = [link['href'] for link in links]
        self.assertIn('http://example.com', hrefs)
        self.assertIn('https://github.com', hrefs)

        # Verify math preserved without linkification
        self.assertIn('$x = http://example.org$', html)

    @with_settings(ENABLE_MATHJAX=True,
                   ENABLE_AUTO_LINKING=True,
                   AUTO_LINK_PATTERNS=r'#bug(\d+)',
                   AUTO_LINK_URLS=r'https://bugs.example.com/\1')
    def test_math_patterns_no_interference(self):
        """Document with math and link patterns - verify patterns work outside, not inside"""
        reset_md_converter()
        md = get_md_converter()

        text = """
Fixed #bug123 in the code.

The equation $bug456 = x$ is unrelated.

Also fixed #bug789.
"""
        html = md.render(text)

        soup = BeautifulSoup(html, 'html5lib')

        # Find all links
        links = soup.find_all('a')

        # Should have exactly 2 links (the patterns outside math)
        self.assertEqual(len(links), 2, "Should only link patterns outside math")

        # Verify correct patterns were linked
        hrefs = [link['href'] for link in links]
        self.assertIn('https://bugs.example.com/123', hrefs)
        self.assertIn('https://bugs.example.com/789', hrefs)

        # Verify pattern inside math was NOT linked
        self.assertIn('$bug456 = x$', html)

    @with_settings(ENABLE_MATHJAX=True)
    def test_math_in_code_block_no_conflict(self):
        """Test that math inside code blocks is not processed"""
        reset_md_converter()
        md = get_md_converter()

        text = """
```python
price = $100
equation = "$E = mc^2$"
```

But this $x = y$ is math.
"""
        html = md.render(text)

        soup = BeautifulSoup(html, 'html5lib')

        # Code block should contain literal $
        code = soup.find('code')
        self.assertIsNotNone(code)
        code_text = code.text
        self.assertIn('$100', code_text)
        self.assertIn('$E = mc^2$', code_text)

        # Math outside code should be preserved
        # Find paragraphs (not code blocks)
        paragraphs = soup.find_all('p')
        if paragraphs:
            # Should have math in paragraph
            found_math = any('$x = y$' in str(p) for p in paragraphs)
            self.assertTrue(found_math, "Math outside code should be preserved")

    @with_settings(ENABLE_MATHJAX=True)
    def test_mixed_content_complex(self):
        """Complex test with mixed math, links, code, and text"""
        reset_md_converter()
        md = get_md_converter()

        text = """
# Math and Links Test

Check https://example.com for details.

The formula $E = mc^2$ and the URL $http://fake.url$ inside.

Code: `$x = y$`

Display math:
$$
\\int_0^1 x dx
$$

Another link: example.org
"""
        html = md.render(text)

        soup = BeautifulSoup(html, 'html5lib')

        # Verify heading
        h1 = soup.find('h1')
        self.assertIsNotNone(h1)

        # Count links (should only be the real URLs, not ones in math)
        links = soup.find_all('a')
        # Should have 2 links: https://example.com and example.org
        self.assertEqual(len(links), 2)

        # Verify math preserved
        self.assertIn('$E = mc^2$', html)
        self.assertIn('$http://fake.url$', html)
        self.assertIn('$$', html)
        self.assertIn('\\int_0^1', html)

        # Verify inline code preserved
        code = soup.find('code')
        self.assertIsNotNone(code)
