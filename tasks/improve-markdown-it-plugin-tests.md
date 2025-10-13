# Improve Markdown_it Plugin Tests

NOTE: to run tests you need to:

1) activate virtual environment: `source env-md/bin/activate`
2) go into the deployment directory: `cd askbot_site`
3) then run tests from here: python manage.py test ...

Your goal in this task is to improve the test cases and demonstrate that they work.
You may not modify the application logic, only tests need to be improved.
Work gradually: improve a couple of tests, verify that they work, then continue.

Do not ask for my intervention, do not create new files, only modify tests and
test and repeat until they pass.

All this work must be done autonomously until completed.

## Overview

This document outlines improvements needed for the markdown_it plugin tests. Currently, some tests only check for text presence in HTML output rather than properly parsing and validating the HTML structure. This makes tests fragile and less thorough.

## Dependencies Available

- `bs4` (BeautifulSoup4) is already a project dependency (see `askbot/__init__.py:24`)
- `html5lib` parser is available (see `askbot/__init__.py:31`)
- Convention: Use `BeautifulSoup(html, 'html5lib')` (see examples in `test_question_views.py`, `test_db_api.py`)

## Test Improvement Patterns

### Pattern 1: Helper Methods (from test_db_api.py:740-750)
```python
def assert_no_link(self, html):
    soup = BeautifulSoup(html, 'html5lib')
    links = soup.findAll('a')
    self.assertEqual(len(links), 0)

def assert_has_link(self, html, url):
    soup = BeautifulSoup(html, 'html5lib')
    links = soup.findAll('a')
    self.assertTrue(len(links) > 0)
    self.assertEqual(links[0]['href'], url)
```

### Pattern 2: Direct Parsing (from test_question_views.py:42-44)
```python
dom = BeautifulSoup(response.content, 'html5lib')
title = dom.find('h1').text
self.assertTrue(str(const.POST_STATUS['private']) in title)
```

---

## File 1: test_markdown_integration.py

### ✅ Good Tests (No changes needed)
- `test_basic_markdown()` - Lines 16-23: Properly checks for specific HTML tags
- `test_tables()` - Lines 25-35: Validates table structure with specific tags

### ⚠️ Tests Needing Improvement

#### 1. test_footnotes() - Lines 37-41
**Current:**
```python
def test_footnotes(self):
    md = get_md_converter()
    text = "Text with footnote[^1]\n\n[^1]: Footnote content"
    html = md.render(text)
    self.assertIn('footnote', html.lower())  # Too weak!
```

**Problem:** Only checks for the word "footnote" somewhere in HTML. Doesn't validate structure.

**Improvement:**
```python
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
```

#### 2. test_task_lists() - Lines 43-47
**Current:**
```python
def test_task_lists(self):
    md = get_md_converter()
    text = "- [ ] Unchecked\n- [x] Checked"
    html = md.render(text)
    self.assertTrue('checkbox' in html.lower() or 'task' in html.lower())  # Vague!
```

**Problem:** Uses OR condition with vague text matching. Doesn't verify checkbox inputs.

**Improvement:**
```python
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
```

#### 3. test_syntax_highlighting() - Lines 49-53
**Current:**
```python
def test_syntax_highlighting(self):
    md = get_md_converter()
    text = "```python\ndef hello():\n    pass\n```"
    html = md.render(text)
    self.assertIn('highlight', html)  # Only checks for text!
```

**Problem:** Only verifies text "highlight" exists, not the code block structure.

**Improvement:**
```python
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
```

#### 4. test_video_embedding() - Lines 55-60
**Current:**
```python
def test_video_embedding(self):
    md = get_md_converter()
    text = "Check this: @[youtube](dQw4w9WgXcQ)"
    html = md.render(text)
    self.assertIn('youtube.com/embed/dQw4w9WgXcQ', html)  # Good
    self.assertIn('iframe', html)  # Weak - just text!
```

**Problem:** Second assertion just checks for text "iframe", not actual iframe element.

**Improvement:**
```python
def test_video_embedding(self):
    md = get_md_converter()
    text = "Check this: @[youtube](dQw4w9WgXcQ)"
    html = md.render(text)

    soup = BeautifulSoup(html, 'html5lib')

    # Find iframe element
    iframe = soup.find('iframe')
    self.assertIsNotNone(iframe)

    # Verify src attribute
    self.assertEqual(iframe['src'], 'https://www.youtube.com/embed/dQw4w9WgXcQ')

    # Verify iframe has proper attributes
    self.assertIn('video-embed-youtube', iframe.get('class', []))
    self.assertTrue(iframe.has_attr('allowfullscreen'))

    # Verify surrounding text
    self.assertIn('Check this:', html)
```

#### 5. test_link_patterns_enabled() - Lines 62-72
**Current:**
```python
@with_settings(ENABLE_AUTO_LINKING=True,
               AUTO_LINK_PATTERNS=r'#bug(\d+)',
               AUTO_LINK_URLS=r'https://bugs.example.com/\1')
def test_link_patterns_enabled(self):
    reset_md_converter()
    md = get_md_converter()
    text = "Fixed #bug123"
    html = md.render(text)

    self.assertIn('bugs.example.com/123', html)  # Only checks text!
```

**Problem:** Only checks for URL text, not anchor tag with proper href.

**Improvement:**
```python
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
```

#### 6. test_mathjax_math_delimiters_preserved() - Lines 86-102
**Current:**
```python
@with_settings(ENABLE_MATHJAX=True)
def test_mathjax_math_delimiters_preserved(self):
    """Test that math delimiters are preserved for MathJax"""
    reset_md_converter()
    md = get_md_converter()

    # Inline math
    text = "The equation $E = mc^2$ is famous"
    html = md.render(text)
    self.assertTrue('$E = mc^2$' in html or '$E = mc^2$' in html.replace('&nbsp;', ' '))  # Weak

    # Display math
    text = "$$\\int_0^1 x dx = \\frac{1}{2}$$"
    html = md.render(text)
    self.assertIn('$$', html)
    self.assertTrue('\\int_0^1' in html or r'\int_0^1' in html)  # Too permissive
```

**Problem:** Uses weak text matching with OR conditions. Doesn't verify proper structure.

**Improvement:**
```python
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
```

#### 7. test_mathjax_underscores_not_emphasis() - Lines 104-116
**Current:**
```python
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
    self.assertTrue('<em>' not in html or html.count('<em>') == 0)  # Confusing logic!
```

**Problem:** Confusing assertion logic with OR. Should use BeautifulSoup to be definitive.

**Improvement:**
```python
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
```

#### 8. test_combined_features() - Lines 118-150
**Current:** Mix of good and weak assertions
```python
def test_combined_features(self):
    """Test document using multiple features"""
    md = get_md_converter()
    text = """..."""
    html = md.render(text)

    # Check all features rendered
    self.assertIn('<h1>Title</h1>', html)  # Good
    self.assertIn('<strong>bold text</strong>', html)  # Good
    self.assertIn('youtube.com/embed/abc123', html)  # Weak - just URL text
    self.assertTrue('highlight' in html or 'class="language-python"' in html)  # Weak OR
    self.assertIn('<table>', html)  # Good
```

**Problem:** Inconsistent - some good assertions, some weak. Should be thorough throughout.

**Improvement:**
```python
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

    soup = BeautifulSoup(html, 'html5lib')

    # Verify heading
    h1 = soup.find('h1')
    self.assertIsNotNone(h1)
    self.assertEqual(h1.text.strip(), 'Title')

    # Verify bold text
    strong = soup.find('strong')
    self.assertIsNotNone(strong)
    self.assertEqual(strong.text, 'bold text')

    # Verify video iframe
    iframe = soup.find('iframe')
    self.assertIsNotNone(iframe)
    self.assertIn('abc123', iframe['src'])

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
```

---

## File 2: test_markdown_link_patterns_plugin.py

### ✅ Good Tests (No changes needed)
- `test_simple_pattern()` - Line 9-21: Properly checks exact anchor tag
- `test_disabled_plugin()` - Line 36-48: Good negative test
- `test_overlapping_matches()` - Line 50-63: Good logic
- `test_mismatched_pattern_url_count()` - Line 93-106: Good validation

### ⚠️ Tests Needing Improvement

#### 1. test_multiple_patterns() - Lines 23-34
**Current:**
```python
def test_multiple_patterns(self):
    md = MarkdownIt().use(link_patterns_plugin, {...})
    text = "Fixed #bug456 by @alice"
    html = md.render(text)

    self.assertIn('bugs.example.com/456', html)  # Just URL text!
    self.assertIn('github.com/alice', html)  # Just URL text!
```

**Problem:** Only checks for URL text presence, not anchor structure.

**Improvement:**
```python
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
```

#### 2. test_pattern_in_code_block_not_linkified() - Lines 65-79
**Current:**
```python
def test_pattern_in_code_block_not_linkified(self):
    md = MarkdownIt().use(link_patterns_plugin, {...})
    text = "Text #bug123 and `code #bug456` here"
    html = md.render(text)

    # #bug123 should be linked (in text)
    self.assertIn('bugs.example.com/123', html)

    # #bug456 should NOT be linked (in code)
    self.assertNotIn('bugs.example.com/456', html)
```

**Problem:** Doesn't verify code element structure or that text link is proper anchor.

**Improvement:**
```python
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
```

#### 3. test_invalid_regex_ignored() - Lines 81-91
**Current:**
```python
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
```

**Problem:** Minimal validation. Should verify proper paragraph structure.

**Improvement:**
```python
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
```

---

## File 3: test_markdown_video_plugin.py

### ✅ Partially Good Tests
All tests in this file check for iframe and URL text, but could be more thorough with attributes.

### ⚠️ Tests Needing Improvement

#### 1. test_youtube_embed() - Lines 12-17
**Current:**
```python
def test_youtube_embed(self):
    text = "@[youtube](dQw4w9WgXcQ)"
    html = self.md.render(text)
    self.assertIn('https://www.youtube.com/embed/dQw4w9WgXcQ', html)  # URL text
    self.assertIn('iframe', html)  # Just text!
    self.assertIn('video-embed-youtube', html)  # Just text!
```

**Problem:** Checks for text "iframe" and "video-embed-youtube", not actual elements/attributes.

**Improvement:**
```python
def test_youtube_embed(self):
    text = "@[youtube](dQw4w9WgXcQ)"
    html = self.md.render(text)

    soup = BeautifulSoup(html, 'html5lib')

    # Find iframe element
    iframe = soup.find('iframe')
    self.assertIsNotNone(iframe, "No iframe element found")

    # Verify src attribute
    self.assertEqual(iframe['src'], 'https://www.youtube.com/embed/dQw4w9WgXcQ')

    # Verify class attribute
    self.assertIn('video-embed-youtube', iframe.get('class', []))

    # Verify iframe has allowfullscreen
    self.assertTrue(iframe.has_attr('allowfullscreen'))

    # Verify typical iframe dimensions (if plugin sets them)
    # self.assertEqual(iframe.get('width'), '560')
    # self.assertEqual(iframe.get('height'), '315')
```

#### 2. test_vimeo_embed() - Lines 19-23
**Current:**
```python
def test_vimeo_embed(self):
    text = "@[vimeo](123456789)"
    html = self.md.render(text)
    self.assertIn('https://player.vimeo.com/video/123456789', html)
    self.assertIn('iframe', html)
```

**Improvement:**
```python
def test_vimeo_embed(self):
    text = "@[vimeo](123456789)"
    html = self.md.render(text)

    soup = BeautifulSoup(html, 'html5lib')

    iframe = soup.find('iframe')
    self.assertIsNotNone(iframe)
    self.assertEqual(iframe['src'], 'https://player.vimeo.com/video/123456789')
    self.assertIn('video-embed-vimeo', iframe.get('class', []))
    self.assertTrue(iframe.has_attr('allowfullscreen'))
```

#### 3. test_dailymotion_embed() - Lines 25-28
**Current:**
```python
def test_dailymotion_embed(self):
    text = "@[dailymotion](x8abcdef)"
    html = self.md.render(text)
    self.assertIn('dailymotion.com/embed/video/x8abcdef', html)
```

**Improvement:**
```python
def test_dailymotion_embed(self):
    text = "@[dailymotion](x8abcdef)"
    html = self.md.render(text)

    soup = BeautifulSoup(html, 'html5lib')

    iframe = soup.find('iframe')
    self.assertIsNotNone(iframe)
    self.assertIn('dailymotion.com/embed/video/x8abcdef', iframe['src'])
    self.assertIn('video-embed-dailymotion', iframe.get('class', []))
```

#### 4. test_unsupported_service_ignored() - Lines 30-36
**Current:** Actually pretty good as a negative test
```python
def test_unsupported_service_ignored(self):
    text = "@[tiktok](12345)"
    html = self.md.render(text)
    # Unsupported service - no iframe should be created
    # Note: markdown-it will parse [tiktok](12345) as a regular link
    self.assertNotIn('iframe', html)
    self.assertNotIn('video-embed', html)
```

**Minor Improvement:**
```python
def test_unsupported_service_ignored(self):
    text = "@[tiktok](12345)"
    html = self.md.render(text)

    soup = BeautifulSoup(html, 'html5lib')

    # Unsupported service - no iframe should be created
    iframe = soup.find('iframe')
    self.assertIsNone(iframe, "Iframe created for unsupported service")

    # Should not have video-embed classes
    video_embeds = soup.find_all(class_=lambda x: x and 'video-embed' in x)
    self.assertEqual(len(video_embeds), 0)
```

#### 5. test_invalid_video_id_ignored() - Lines 38-42
**Current:**
```python
def test_invalid_video_id_ignored(self):
    # IDs with spaces or special chars should be rejected
    text = "@[youtube](invalid id!)"
    html = self.md.render(text)
    self.assertNotIn('iframe', html)
```

**Improvement:**
```python
def test_invalid_video_id_ignored(self):
    # IDs with spaces or special chars should be rejected
    text = "@[youtube](invalid id!)"
    html = self.md.render(text)

    soup = BeautifulSoup(html, 'html5lib')

    iframe = soup.find('iframe')
    self.assertIsNone(iframe, "Iframe created for invalid video ID")

    # Text should still be rendered (perhaps as paragraph)
    paragraph = soup.find('p')
    self.assertIsNotNone(paragraph)
```

#### 6. test_video_in_paragraph() - Lines 44-49
**Current:**
```python
def test_video_in_paragraph(self):
    text = "Check this out: @[youtube](dQw4w9WgXcQ) cool right?"
    html = self.md.render(text)
    self.assertIn('Check this out:', html)
    self.assertIn('youtube.com/embed', html)
    self.assertIn('cool right?', html)
```

**Problem:** Only checks text presence, doesn't verify structure relationship.

**Improvement:**
```python
def test_video_in_paragraph(self):
    text = "Check this out: @[youtube](dQw4w9WgXcQ) cool right?"
    html = self.md.render(text)

    soup = BeautifulSoup(html, 'html5lib')

    # Verify iframe exists with correct src
    iframe = soup.find('iframe')
    self.assertIsNotNone(iframe)
    self.assertIn('dQw4w9WgXcQ', iframe['src'])

    # Verify surrounding text in same paragraph or adjacent
    # (depends on how plugin handles inline vs block)
    all_text = soup.get_text()
    self.assertIn('Check this out:', all_text)
    self.assertIn('cool right?', all_text)
```

#### 7. test_multiple_videos() - Lines 51-55
**Current:**
```python
def test_multiple_videos(self):
    text = "@[youtube](abc123)\n\n@[vimeo](456789)"
    html = self.md.render(text)
    self.assertIn('youtube.com/embed/abc123', html)
    self.assertIn('vimeo.com/video/456789', html)
```

**Problem:** Only checks URL text, doesn't verify separate iframes.

**Improvement:**
```python
def test_multiple_videos(self):
    text = "@[youtube](abc123)\n\n@[vimeo](456789)"
    html = self.md.render(text)

    soup = BeautifulSoup(html, 'html5lib')

    # Should have exactly 2 iframes
    iframes = soup.find_all('iframe')
    self.assertEqual(len(iframes), 2)

    # Verify youtube iframe
    youtube_iframe = [i for i in iframes if 'youtube.com' in i['src']][0]
    self.assertIn('abc123', youtube_iframe['src'])
    self.assertIn('video-embed-youtube', youtube_iframe.get('class', []))

    # Verify vimeo iframe
    vimeo_iframe = [i for i in iframes if 'vimeo.com' in i['src']][0]
    self.assertIn('456789', vimeo_iframe['src'])
    self.assertIn('video-embed-vimeo', vimeo_iframe.get('class', []))
```

---

## Summary Statistics

**Total Tests Analyzed:** 17
**Tests Needing Improvement:** 17
**Tests Already Good:** 4 (in test_markdown_integration.py and test_markdown_link_patterns_plugin.py)

### Breakdown by File:
- **test_markdown_integration.py:** 8 of 10 tests need improvement (80%)
- **test_markdown_link_patterns_plugin.py:** 3 of 7 tests need improvement (43%)
- **test_markdown_video_plugin.py:** 6 of 7 tests need improvement (86%)

## Implementation Priority

1. **High Priority:** Video plugin tests - these are the weakest, almost entirely text-based assertions
2. **Medium Priority:** Integration tests - mix of good and weak, need consistency
3. **Low Priority:** Link patterns tests - already has some good examples, fewer issues

## Benefits of These Improvements

1. **Robustness:** Tests will catch actual structure problems, not just missing text
2. **Maintainability:** Clear what HTML structure is expected
3. **Debugging:** When tests fail, BeautifulSoup parsing makes it obvious what's wrong
4. **Consistency:** Follows existing patterns in codebase (test_db_api.py, test_question_views.py)
5. **Completeness:** Validates attributes, classes, nesting - not just text presence

## Implementation Notes

1. Add `from bs4 import BeautifulSoup` to each test file
2. Use `'html5lib'` parser consistently (project standard)
3. Consider adding helper methods to test classes for common assertions
4. Run tests after each improvement to ensure they still pass
5. May need to adjust expectations based on actual plugin output
