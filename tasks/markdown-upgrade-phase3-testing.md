# Phase 3: Testing & Deployment

**Status**: ⚪ Not started
**Duration**: 1 week
**Prerequisites**: Phase 1 and Phase 2 complete
**Deliverable**: Production-ready markdown upgrade

## Overview

Comprehensive testing and migration validation to ensure existing content renders correctly with the new markdown-it implementation, followed by staged deployment to production.

## Goals

1. Create migration testing script for existing posts
2. Perform visual regression testing (old vs new HTML)
3. Validate performance benchmarks
4. Test edge cases and unusual content
5. Update documentation
6. Create rollback plan
7. Execute staged deployment
8. Monitor production metrics

## Prerequisites

Before starting Phase 3, ensure:

```bash
# Activate Python virtual environment
source env/bin/activate

# Verify Phase 1 and Phase 2 are complete
python -c "import markdown_it; print(markdown_it.__version__)"  # Should be 4.0.0
python -c "from askbot.utils.markdown_plugins.video_embed import video_embed_plugin; print('OK')"

# Navigate to askbot_site directory for running tests (this directory has manage.py)
cd askbot_site/

# Verify database is accessible
python manage.py check
```

If a clean environment is needed, the system has pyenv v2.5.5 installed,
use Python 3.11.11 for this new environment.

**Note**: All Python commands in this phase assume you have activated the virtual environment with `source env/bin/activate`.

## Task Breakdown

### Task 3.1: Create Migration Test Script

**Estimated Time**: 6 hours
**Files Created**: 1
**Location**: `askbot/management/commands/test_markdown_migration.py`

#### Subtasks
- [ ] Create Django management command
- [ ] Query all posts from database
- [ ] Re-render with new markdown-it converter
- [ ] Compare with stored HTML
- [ ] Generate diff report
- [ ] Flag problematic posts

#### Implementation

**File**: `askbot/management/commands/test_markdown_migration.py`
```python
"""
Management command to test markdown migration.

Tests all existing posts by re-rendering with new markdown-it converter
and comparing output to existing HTML.

Usage:
    python manage.py test_markdown_migration --sample 1000
    python manage.py test_markdown_migration --all --report migration_report.html
"""

import difflib
import logging
from django.core.management.base import BaseCommand
from django.db.models import Q
from askbot.models import Post, PostRevision
from askbot.utils.markup import markdown_input_converter, get_md_converter
from askbot.utils.html import sanitize_html


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Test markdown migration by re-rendering all posts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sample',
            type=int,
            default=None,
            help='Test only N random posts'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Test all posts (may take a while)'
        )
        parser.add_argument(
            '--post-id',
            type=int,
            default=None,
            help='Test specific post by ID'
        )
        parser.add_argument(
            '--report',
            type=str,
            default='markdown_migration_report.html',
            help='Output report filename'
        )
        parser.add_argument(
            '--threshold',
            type=float,
            default=0.95,
            help='Similarity threshold (0-1). Default: 0.95 (95%% similar)'
        )

    def handle(self, *args, **options):
        sample_size = options.get('sample')
        test_all = options.get('all')
        post_id = options.get('post_id')
        report_file = options.get('report')
        threshold = options.get('threshold')

        if not any([sample_size, test_all, post_id]):
            self.stdout.write(self.style.ERROR(
                'Must specify --sample N, --all, or --post-id ID'
            ))
            return

        # Get posts to test
        if post_id:
            posts = Post.objects.filter(id=post_id)
        elif test_all:
            posts = Post.objects.filter(
                deleted=False,
                post_type__in=['question', 'answer']
            ).order_by('id')
        else:
            posts = Post.objects.filter(
                deleted=False,
                post_type__in=['question', 'answer']
            ).order_by('?')[:sample_size]

        total_posts = posts.count()
        self.stdout.write(f'Testing {total_posts} posts...')

        # Test each post
        results = []
        for idx, post in enumerate(posts, 1):
            if idx % 100 == 0:
                self.stdout.write(f'Progress: {idx}/{total_posts}')

            result = self.test_post(post, threshold)
            results.append(result)

        # Generate report
        self.generate_report(results, report_file, threshold)

        # Summary
        total = len(results)
        passed = sum(1 for r in results if r['passed'])
        failed = total - passed

        self.stdout.write(self.style.SUCCESS(
            f'\nResults: {passed}/{total} passed ({100*passed/total:.1f}%)'
        ))

        if failed > 0:
            self.stdout.write(self.style.WARNING(
                f'{failed} posts had differences above threshold'
            ))

        self.stdout.write(f'Report saved to: {report_file}')

    def test_post(self, post, threshold):
        """
        Test a single post by re-rendering and comparing.

        Returns dict with test results.
        """
        # Get latest revision
        try:
            revision = post.revisions.latest('revised_at')
            markdown_text = revision.text
        except PostRevision.DoesNotExist:
            return {
                'post_id': post.id,
                'post_type': post.post_type,
                'passed': False,
                'error': 'No revision found',
                'similarity': 0.0,
            }

        # Get current HTML
        current_html = post.html

        # Re-render with new converter
        try:
            new_html = markdown_input_converter(markdown_text)
        except Exception as e:
            logger.error(f'Error rendering post {post.id}: {e}')
            return {
                'post_id': post.id,
                'post_type': post.post_type,
                'passed': False,
                'error': str(e),
                'similarity': 0.0,
            }

        # Normalize HTML for comparison
        current_normalized = self.normalize_html(current_html)
        new_normalized = self.normalize_html(new_html)

        # Calculate similarity
        similarity = self.calculate_similarity(current_normalized, new_normalized)

        # Generate diff if different
        diff_html = None
        if similarity < threshold:
            diff_html = self.generate_diff_html(
                current_normalized,
                new_normalized,
                post.id
            )

        return {
            'post_id': post.id,
            'post_type': post.post_type,
            'title': post.thread.title if hasattr(post, 'thread') else '',
            'passed': similarity >= threshold,
            'similarity': similarity,
            'markdown_length': len(markdown_text),
            'current_html_length': len(current_html),
            'new_html_length': len(new_html),
            'diff_html': diff_html,
            'error': None,
        }

    def normalize_html(self, html):
        """
        Normalize HTML for comparison.

        Removes whitespace differences, attributes order, etc.
        """
        import re

        # Remove extra whitespace
        html = re.sub(r'\s+', ' ', html)

        # Remove leading/trailing whitespace
        html = html.strip()

        # Normalize quotes in attributes
        html = html.replace("'", '"')

        # Sort attributes (basic)
        # TODO: More sophisticated normalization if needed

        return html

    def calculate_similarity(self, text1, text2):
        """
        Calculate similarity ratio between two strings.

        Returns float 0-1 (1 = identical)
        """
        matcher = difflib.SequenceMatcher(None, text1, text2)
        return matcher.ratio()

    def generate_diff_html(self, old_html, new_html, post_id):
        """
        Generate HTML diff for visual comparison.
        """
        differ = difflib.HtmlDiff()
        diff_table = differ.make_table(
            old_html.splitlines(),
            new_html.splitlines(),
            fromdesc=f'Current (Post {post_id})',
            todesc='New markdown-it',
            context=True,
            numlines=3
        )
        return diff_table

    def generate_report(self, results, filename, threshold):
        """
        Generate HTML report of test results.
        """
        passed_count = sum(1 for r in results if r['passed'])
        failed_count = len(results) - passed_count

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Markdown Migration Test Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background: #f5f5f5;
        }}
        .summary {{
            background: white;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .summary h1 {{
            margin-top: 0;
        }}
        .passed {{
            color: green;
            font-weight: bold;
        }}
        .failed {{
            color: red;
            font-weight: bold;
        }}
        table {{
            width: 100%;
            background: white;
            border-collapse: collapse;
            margin-bottom: 20px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #333;
            color: white;
        }}
        tr:hover {{
            background: #f5f5f5;
        }}
        .diff-section {{
            background: white;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 5px;
        }}
        .diff-section h3 {{
            margin-top: 0;
        }}
    </style>
</head>
<body>
    <div class="summary">
        <h1>Markdown Migration Test Report</h1>
        <p>Total Posts: {len(results)}</p>
        <p class="passed">Passed: {passed_count} ({100*passed_count/len(results):.1f}%)</p>
        <p class="failed">Failed: {failed_count} ({100*failed_count/len(results):.1f}%)</p>
        <p>Similarity Threshold: {threshold*100:.0f}%</p>
    </div>

    <h2>Results</h2>
    <table>
        <thead>
            <tr>
                <th>Post ID</th>
                <th>Type</th>
                <th>Title</th>
                <th>Similarity</th>
                <th>Status</th>
                <th>Markdown Size</th>
                <th>HTML Size Δ</th>
            </tr>
        </thead>
        <tbody>
"""

        for result in results:
            status_class = 'passed' if result['passed'] else 'failed'
            status_text = '✓ Pass' if result['passed'] else '✗ Fail'

            html_size_delta = result['new_html_length'] - result['current_html_length']
            html_size_delta_str = f"{html_size_delta:+d}"

            html += f"""
            <tr class="{status_class}">
                <td><a href="#post-{result['post_id']}">#{result['post_id']}</a></td>
                <td>{result['post_type']}</td>
                <td>{result['title'][:50] if result['title'] else 'N/A'}</td>
                <td>{result['similarity']*100:.1f}%</td>
                <td>{status_text}</td>
                <td>{result['markdown_length']} chars</td>
                <td>{html_size_delta_str} chars</td>
            </tr>
"""

        html += """
        </tbody>
    </table>

    <h2>Detailed Diffs (Failed Only)</h2>
"""

        # Add detailed diffs for failed posts
        for result in results:
            if not result['passed'] and result['diff_html']:
                html += f"""
    <div class="diff-section" id="post-{result['post_id']}">
        <h3>Post #{result['post_id']}: {result['title'][:100] if result['title'] else 'N/A'}</h3>
        <p>Similarity: {result['similarity']*100:.1f}%</p>
        {result['diff_html']}
    </div>
"""

        html += """
</body>
</html>
"""

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)
```

#### Usage Examples

```bash
# Activate virtual environment
source env/bin/activate

# Navigate to askbot_site directory (this directory has manage.py)
cd askbot_site/

# Test 100 random posts
python manage.py test_markdown_migration --sample 100

# Test all posts (may take hours)
python manage.py test_markdown_migration --all

# Test specific post
python manage.py test_markdown_migration --post-id 12345

# Custom threshold (98% similarity required)
python manage.py test_markdown_migration --sample 1000 --threshold 0.98
```

---

### Task 3.2: Visual Regression Testing

**Estimated Time**: 4 hours
**Tools**: Percy, BackstopJS, or Playwright

#### Subtasks
- [ ] Set up visual regression testing tool
- [ ] Capture screenshots of sample posts (before)
- [ ] Apply migration
- [ ] Capture screenshots (after)
- [ ] Compare and generate diff report

#### Option 1: Using BackstopJS

**Setup**:
```bash
npm install -g backstopjs

# Create config
backstop init
```

**Config**: `backstop.json`
```json
{
  "id": "markdown_migration",
  "viewports": [
    {
      "label": "desktop",
      "width": 1280,
      "height": 1024
    }
  ],
  "scenarios": [
    {
      "label": "Question with code",
      "url": "http://localhost:8000/questions/123/",
      "selectors": [".post-body"],
      "delay": 500
    },
    {
      "label": "Question with table",
      "url": "http://localhost:8000/questions/456/",
      "selectors": [".post-body"],
      "delay": 500
    }
    // Add more scenarios
  ]
}
```

**Commands**:
```bash
# Capture reference screenshots (before migration)
backstop reference

# After migration, test for differences
backstop test

# Approve new screenshots as baseline
backstop approve
```

#### Option 2: Using Playwright

**File**: `askbot/tests/visual_regression_test.py`
```python
"""
Visual regression testing using Playwright.
"""
import pytest
from playwright.sync_api import sync_playwright


SAMPLE_POSTS = [123, 456, 789]  # Post IDs to test


@pytest.mark.visual
def test_visual_regression(live_server):
    """
    Capture screenshots and compare.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        for post_id in SAMPLE_POSTS:
            url = f"{live_server.url}/questions/{post_id}/"
            page.goto(url)

            # Capture post body
            post_body = page.locator('.post-body').first
            screenshot = post_body.screenshot()

            # Compare with baseline
            # (Use pytest-playwright or custom comparison)

        browser.close()
```

---

### Task 3.3: Performance Benchmarking

**Estimated Time**: 3 hours
**Files Created**: 1

#### Subtasks
- [ ] Create benchmark script
- [ ] Test rendering speed (markdown → HTML)
- [ ] Test with various content sizes
- [ ] Compare old vs new performance
- [ ] Generate performance report

#### Implementation

**File**: `askbot/tests/benchmark_markdown.py`
```python
"""
Performance benchmarks for markdown rendering.
"""
import time
import statistics
from askbot.utils.markup import get_md_converter


SAMPLE_TEXTS = {
    'short': '# Hello\n\nThis is **bold**.',
    'medium': '# Title\n\n' + ('Paragraph with *some* text.\n\n' * 50),
    'long': '# Long Document\n\n' + ('Paragraph.\n\n' * 500),
    'code_heavy': '```python\n' + ('def func():\n    pass\n' * 100) + '```',
    'table': '| Col 1 | Col 2 |\n|-------|-------|\n' + ('| A | B |\n' * 100),
}


def benchmark_render(text, iterations=100):
    """
    Benchmark markdown rendering.

    Returns average time in milliseconds.
    """
    md = get_md_converter()
    times = []

    for _ in range(iterations):
        start = time.perf_counter()
        html = md.render(text)
        end = time.perf_counter()
        times.append((end - start) * 1000)  # Convert to ms

    return {
        'mean': statistics.mean(times),
        'median': statistics.median(times),
        'stdev': statistics.stdev(times) if len(times) > 1 else 0,
        'min': min(times),
        'max': max(times),
    }


def run_benchmarks():
    """
    Run all benchmarks and print results.
    """
    print("Markdown Rendering Performance Benchmarks")
    print("=" * 60)

    for name, text in SAMPLE_TEXTS.items():
        print(f"\n{name.upper()} ({len(text)} chars)")
        stats = benchmark_render(text)

        print(f"  Mean:   {stats['mean']:.3f} ms")
        print(f"  Median: {stats['median']:.3f} ms")
        print(f"  StdDev: {stats['stdev']:.3f} ms")
        print(f"  Range:  {stats['min']:.3f} - {stats['max']:.3f} ms")


if __name__ == '__main__':
    run_benchmarks()
```

**Run**:
```bash
python askbot/tests/benchmark_markdown.py
```

**Acceptance Criteria**:
- Short text: <5ms
- Medium text: <50ms
- Long text: <200ms
- 95th percentile: <2x median

---

### Task 3.4: Edge Case Testing

**Estimated Time**: 4 hours
**Files Created**: 1

#### Subtasks
- [ ] Collect edge cases (malformed markdown, special chars, etc.)
- [ ] Test each edge case
- [ ] Document any issues
- [ ] Fix issues or document as known limitations

#### Edge Cases to Test

**File**: `askbot/tests/test_markdown_edge_cases.py`
```python
"""
Edge case tests for markdown rendering.
"""
from django.test import TestCase
from askbot.tests.utils import with_settings
from askbot.utils.markup import get_md_converter, reset_md_converter


class TestMarkdownEdgeCases(TestCase):

    def tearDown(self):
        """Reset singleton between tests"""
        reset_md_converter()
        super().tearDown()

    def test_empty_input(self):
        md = get_md_converter()
        self.assertEqual(md.render(''), '')

    def test_only_whitespace(self):
        md = get_md_converter()
        result = md.render('   \n\n  \t  ')
        self.assertEqual(result.strip(), '')

    def test_unicode_characters(self):
        md = get_md_converter()
        text = "Unicode: 你好 мир 🚀"
        html = md.render(text)
        self.assertIn('你好', html)
        self.assertIn('мир', html)
        self.assertIn('🚀', html)

    def test_malformed_table(self):
        md = get_md_converter()
        text = "| Header |\n| Cell 1 | Cell 2 |"  # Mismatched columns
        html = md.render(text)
        # Should not crash, handle gracefully
        self.assertIsNotNone(html)

    def test_nested_emphasis(self):
        md = get_md_converter()
        text = "***bold and italic***"
        html = md.render(text)
        self.assertTrue('<strong>' in html or '<em>' in html)

    def test_html_injection_attempt(self):
        md = get_md_converter()
        text = '<script>alert("XSS")</script>'
        html = md.render(text)
        # HTML should be escaped (markdown-it has html: false)
        self.assertTrue('<script>' not in html or '&lt;script&gt;' in html)

    def test_very_deep_nesting(self):
        md = get_md_converter()
        # Deeply nested lists
        text = '\n'.join(['  ' * i + '- Item' for i in range(100)])
        html = md.render(text)
        self.assertIsNotNone(html)

    def test_extremely_long_line(self):
        md = get_md_converter()
        text = 'a' * 100000  # 100k characters
        html = md.render(text)
        self.assertIn('a', html)

    def test_mixed_line_endings(self):
        md = get_md_converter()
        text = "Line 1\nLine 2\r\nLine 3\rLine 4"
        html = md.render(text)
        self.assertIn('Line 1', html)
        self.assertIn('Line 4', html)

    @with_settings(MARKUP_CODE_FRIENDLY=True)
    def test_math_with_underscores(self):
        reset_md_converter()
        md = get_md_converter()
        # If code-friendly mode is on, underscores should not create emphasis
        text = "variable_name_with_underscores"
        html = md.render(text)
        # Should NOT have <em> tags
        self.assertNotIn('<em>', html)

    def test_link_in_heading(self):
        md = get_md_converter()
        text = "# [Link](http://example.com)"
        html = md.render(text)
        self.assertIn('<h1>', html)
        self.assertIn('<a href="http://example.com">', html)

    def test_code_block_with_backticks_inside(self):
        md = get_md_converter()
        text = "```\ncode with ` backtick\n```"
        html = md.render(text)
        self.assertIn('backtick', html)

    @with_settings(ENABLE_MATHJAX=True)
    def test_mathjax_inline_math_preserved(self):
        """Test inline math delimiters are preserved"""
        reset_md_converter()
        md = get_md_converter()

        text = "The formula $E = mc^2$ is famous"
        html = md.render(text)

        # Math delimiters must be preserved exactly
        self.assertIn('$E = mc^2$', html)
        # Should not have any emphasis tags
        self.assertNotIn('<em>', html)

    @with_settings(ENABLE_MATHJAX=True)
    def test_mathjax_display_math_preserved(self):
        """Test display math delimiters are preserved"""
        reset_md_converter()
        md = get_md_converter()

        text = "$$\\int_0^1 x dx = \\frac{1}{2}$$"
        html = md.render(text)

        # Display math delimiters must be preserved
        self.assertIn('$$', html)
        self.assertTrue('\\int' in html or r'\int' in html)

    @with_settings(ENABLE_MATHJAX=True)
    def test_mathjax_underscores_not_processed(self):
        """Test underscores in math don't trigger emphasis/subscript"""
        reset_md_converter()
        md = get_md_converter()

        text = "$a_b$ and $x_{123}$"
        html = md.render(text)

        # Math content should be verbatim
        self.assertIn('$a_b$', html)
        self.assertIn('$x_{123}$', html)
        # No HTML tags inside math
        self.assertNotIn('<sub>', html)
        self.assertNotIn('<em>', html)

    @with_settings(ENABLE_MATHJAX=True)
    def test_mathjax_complex_latex(self):
        """Test complex LaTeX expressions"""
        reset_md_converter()
        md = get_md_converter()

        text = "$$\\sum_{i=1}^{n} i^2 = \\frac{n(n+1)(2n+1)}{6}$$"
        html = md.render(text)

        # Complex LaTeX should be preserved
        self.assertTrue('\\sum_{i=1}^{n}' in html or r'\sum_{i=1}^{n}' in html)
        self.assertTrue('\\frac' in html or r'\frac' in html)
        # No subscript/superscript HTML tags
        self.assertNotIn('<sub>', html)
        self.assertNotIn('<sup>', html)

    def test_autolink_with_special_chars(self):
        md = get_md_converter()
        text = "Visit http://example.com/path?param=value&other=123"
        html = md.render(text)
        self.assertIn('example.com', html)

    def test_multiple_blank_lines(self):
        md = get_md_converter()
        text = "Para 1\n\n\n\n\nPara 2"
        html = md.render(text)
        self.assertIn('Para 1', html)
        self.assertIn('Para 2', html)
```

---

### Task 3.5: Update Documentation

**Estimated Time**: 4 hours
**Files Modified**: Multiple

#### Subtasks
- [ ] Update README with markdown-it info
- [ ] Document supported markdown syntax
- [ ] Update admin documentation
- [ ] Create migration guide for existing installations
- [ ] Update CHANGELOG

#### Files to Update

**CHANGELOG.md** (or create if doesn't exist):
```markdown
# Changelog

## [Unreleased]

### Changed
- **BREAKING**: Migrated from markdown2 to markdown-it-py (backend) and markdown-it.js (frontend)
- Markdown rendering is now 100% CommonMark compliant
- Backend and frontend now render identically
- Improved syntax highlighting using Pygments

### Added
- Video embedding support: `@[youtube](video_id)` syntax
- Custom link patterns for auto-linking (configurable in admin)
- Code-friendly mode for MathJax compatibility
- Footnotes support
- Task lists support

### Removed
- Deprecated markdown2 dependency
- Deprecated Showdown.js library

### Migration Notes
See UPGRADE.md for migration guide.
```

**docs/MARKDOWN_SYNTAX.md** (new file):
```markdown
# Markdown Syntax Guide

Askbot supports CommonMark-compliant markdown with extensions.

## Basic Syntax

### Headings
```markdown
# H1
## H2
### H3
```

### Emphasis
```markdown
**bold**
*italic*
~~strikethrough~~
```

### Lists
```markdown
- Unordered item
- Another item

1. Ordered item
2. Another item
```

### Links
```markdown
[Link text](https://example.com)
```

### Images
```markdown
![Alt text](https://example.com/image.png)
```

## Extended Syntax

### Tables
```markdown
| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
```

### Code Blocks
````markdown
```python
def hello():
    print("world")
```
````

### Video Embedding
```markdown
@[youtube](video_id)
@[vimeo](video_id)
```

### Footnotes
```markdown
Text with footnote[^1]

[^1]: Footnote content
```

### Task Lists
```markdown
- [ ] Incomplete task
- [x] Complete task
```

## Settings

Administrators can configure:
- Auto-linking patterns (e.g., #bug123 → links)
- Code-friendly mode (disable underscore emphasis)
- Syntax highlighting themes
```

---

### Task 3.6: Create Rollback Plan

**Estimated Time**: 2 hours
**Files Created**: 1

#### Subtasks
- [ ] Document rollback procedure
- [ ] Test rollback process
- [ ] Create feature flag for gradual rollout
- [ ] Document monitoring metrics

#### Rollback Strategy

**Option 1: Feature Flag**

Add to `settings.py`:
```python
# Feature flag for markdown backend
MARKDOWN_BACKEND = env('MARKDOWN_BACKEND', default='markdown_it')
# Options: 'markdown_it', 'markdown2'
```

Update `askbot/utils/markup.py`:
```python
def markdown_input_converter(text):
    """
    Convert markdown to HTML using configured backend.
    """
    from django.conf import settings

    backend = getattr(settings, 'MARKDOWN_BACKEND', 'markdown_it')

    if backend == 'markdown2':
        # Old implementation (keep as fallback)
        return markdown2_converter(text)
    else:
        # New implementation
        md = get_md_converter()
        return md.render(text)
```

**Rollback Steps**:
1. Set environment variable: `MARKDOWN_BACKEND=markdown2`
2. Restart application servers
3. Monitor for errors
4. Investigation and fix

**Option 2: Git Revert**

If feature flag not used:
```bash
# Identify commit hash
git log --oneline | grep "markdown-it"

# Revert
git revert <commit-hash>

# Deploy
git push origin master
```

---

### Task 3.7: Staged Deployment

**Estimated Time**: Variable (depends on organization)
**Files Created**: 0

#### Deployment Phases

**Phase 3.7.1: Internal Testing (Week 1)**
- Deploy to internal testing environment
- All developers test with real usage
- Collect feedback
- Fix any critical issues

**Phase 3.7.2: Staging (Week 2)**
- Deploy to staging with production data copy
- Run migration test script on all posts
- Performance testing under load
- Visual regression tests
- Sign-off from QA

**Phase 3.7.3: Canary Deployment (Week 3)**
- Deploy to 5% of production servers
- Monitor metrics:
  - Error rates
  - Response times
  - User complaints
- If stable after 48 hours, expand to 25%

**Phase 3.7.4: Full Rollout (Week 4)**
- Deploy to remaining servers
- Monitor closely for 1 week
- Collect user feedback
- Address any issues

#### Monitoring Metrics

Monitor these during rollout:
- Markdown rendering errors (log count)
- Average render time
- User reports of "weird rendering"
- JavaScript console errors (frontend)
- Server error rates
- Database query performance

**Acceptance Criteria**:
- Error rate <0.1%
- Render time <100ms (95th percentile)
- <10 user complaints per 1000 active users
- No critical bugs

---

## Phase 3 Deliverables

### Code Deliverables
- [ ] Migration test script (management command)
- [ ] Visual regression tests
- [ ] Performance benchmarks
- [ ] Edge case tests
- [ ] Feature flag for rollback

### Documentation Deliverables
- [ ] Updated CHANGELOG
- [ ] Markdown syntax guide
- [ ] Migration guide for admins
- [ ] Rollback procedure
- [ ] Deployment runbook

### Test Reports
- [ ] Migration test report (all posts tested)
- [ ] Visual regression report
- [ ] Performance benchmark results
- [ ] Edge case test results

### Validation Checklist
- [ ] 99%+ posts render identically
- [ ] Performance benchmarks met
- [ ] All edge cases handled
- [ ] Documentation complete
- [ ] Rollback tested
- [ ] Deployment plan approved

## Phase 3 Exit Criteria

**Production Deployment Approved When:**

1. ✅ Migration test script shows 99%+ similarity
2. ✅ Visual regression tests show <1% differences
3. ✅ Performance benchmarks met
4. ✅ All edge case tests passing
5. ✅ Documentation complete and reviewed
6. ✅ Rollback procedure tested
7. ✅ Staging environment stable for 1 week
8. ✅ Sign-off from:
   - Technical Lead
   - QA Lead
   - Product Owner
   - DevOps Lead

**Gate Review Questions:**
1. Are we confident existing content will render correctly?
2. Do we have a tested rollback plan?
3. Is performance acceptable under load?
4. Is monitoring in place to detect issues?
5. Are users adequately informed?

---

## Post-Deployment Monitoring

**Week 1 After Deployment**:
- Daily review of error logs
- Daily review of user feedback
- Performance monitoring
- Be ready for emergency rollback

**Week 2-4**:
- Weekly review of metrics
- Address non-critical issues
- Collect user feedback
- Plan improvements

**Month 2+**:
- Standard monitoring
- Remove old markdown2 code (if stable)
- Plan future enhancements

---

## Success Metrics

**Technical Success**:
- ✅ Error rate <0.1%
- ✅ Render time <100ms (p95)
- ✅ Zero data loss incidents
- ✅ Zero security incidents

**User Success**:
- ✅ <1% user complaints
- ✅ Positive feedback on preview accuracy
- ✅ No significant support ticket increase

**Business Success**:
- ✅ Zero downtime during migration
- ✅ Improved codebase maintainability
- ✅ Modern, actively-maintained dependencies

---

## Known Issues and Limitations

Document any known issues discovered during testing:

1. **Minor HTML differences**: Some whitespace differences in output (cosmetic only)
2. **Legacy content**: Very old posts (pre-2015) may have slight rendering differences
3. **Performance**: Complex tables with 100+ rows render ~20% slower (still <200ms)

These are acceptable tradeoffs for the benefits of the upgrade.

---

## Lessons Learned

(To be filled in after deployment)

**What went well:**
-

**What could be improved:**
-

**Recommendations for future migrations:**
-

---

## Final Sign-off

**Migration Complete**: ☐

**Date**: _________________

**Signatures**:
- Technical Lead: _________________
- QA Lead: _________________
- Product Owner: _________________
- DevOps Lead: _________________

---

## Project Complete

Congratulations on completing the markdown upgrade project! 🎉

The migration to markdown-it provides:
- ✅ Modern, actively-maintained markdown parser
- ✅ 100% CommonMark compliance
- ✅ Frontend/backend consistency
- ✅ Better plugin ecosystem
- ✅ Improved security
- ✅ Better performance (in most cases)

See: [Project Overview](markdown-upgrade-overview.md) for full context.
