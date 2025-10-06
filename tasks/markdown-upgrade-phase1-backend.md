# Phase 1: Backend Implementation

**Status**: 🟡 Planning
**Duration**: 2 weeks
**Prerequisites**: None
**Blocks**: Phase 2 (Frontend Migration)

## Overview

Upgrade Python markdown backend to markdown-it-py 4.0.0 with complete feature parity to the old markdown2 implementation, plus additional askbot-specific features.

## Goals

1. Upgrade markdown-it-py from 2.2.0 → 4.0.0
2. Add required plugin dependencies
3. Implement video embedding plugin
4. Implement custom link patterns plugin
5. Configure code-friendly mode
6. Integrate Pygments syntax highlighting
7. Achieve 95%+ test coverage
8. Maintain backward compatibility with existing content

## Prerequisites

Before starting, ensure your development environment is set up:

```bash
# Clone/navigate to project root
cd /path/to/askbot-master

# Activate Python virtual environment
source env/bin/activate

# Verify you're in the correct environment
which python  # Should point to env/bin/python

# Install current dependencies
pip install -e .

# Verify installation
python -c "import askbot; print(askbot.get_version())"
```

**Note**: All commands in this phase assume you have activated the virtual environment with `source env/bin/activate`.

## Task Breakdown

### Task 1.1: Dependency Upgrades

**Estimated Time**: 2 hours
**Files Modified**: 2

#### Subtasks
- [ ] Update `askbot/__init__.py` REQUIREMENTS dict
- [ ] Update `askbot_requirements.txt`
- [ ] Remove markdown2 dependency references
- [ ] Test installation in clean virtualenv

#### Implementation Details

**File**: `askbot/__init__.py`
```python
# Find REQUIREMENTS dict and update:
REQUIREMENTS = {
    # ... other dependencies ...
    'markdown_it': 'markdown-it-py==4.0.0',
    'mdit_py_plugins': 'mdit-py-plugins==0.4.2',
    'linkify_it': 'linkify-it-py==2.0.2',
    # Remove: 'markdown2': 'markdown2>=2.4.0',
}
```

**File**: `askbot_requirements.txt`
```
# Replace markdown2>=2.4.0 with:
markdown-it-py==4.0.0
mdit-py-plugins==0.4.2
linkify-it-py==2.0.2
pygments>=2.15.0  # For syntax highlighting
```

#### Validation
```bash
# Activate virtual environment
source env/bin/activate

# Install updated dependencies
pip install -e .

# Verify versions
python -c "import markdown_it; print(markdown_it.__version__)"  # Should print 4.0.0
python -c "import mdit_py_plugins; print(mdit_py_plugins.__version__)"  # Should print 0.4.2
```

---

### Task 1.2: Pygments Integration

**Estimated Time**: 3 hours
**Files Modified**: 1
**Location**: `askbot/utils/markup.py`

#### Subtasks
- [ ] Import Pygments modules
- [ ] Write `highlight_code()` function
- [ ] Configure markdown-it highlight option
- [ ] Test with common languages (Python, JS, SQL, Bash)
- [ ] Handle unknown languages gracefully

#### Implementation

```python
# Add to askbot/utils/markup.py after imports

from pygments import highlight as pygments_highlight
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import HtmlFormatter
from pygments.util import ClassNotFound


def highlight_code(code, lang, attrs):
    """
    Syntax highlighting using Pygments.

    Args:
        code: Source code string
        lang: Language identifier (e.g., 'python', 'javascript')
        attrs: Additional attributes (unused, for markdown-it compatibility)

    Returns:
        HTML string with syntax highlighting
    """
    if not lang:
        # No language specified, return plain code block
        return f'<pre><code>{code}</code></pre>'

    try:
        lexer = get_lexer_by_name(lang, stripall=True)
        formatter = HtmlFormatter(
            cssclass='highlight',
            noclasses=False,  # Use CSS classes instead of inline styles
            linenos=False
        )
        highlighted = pygments_highlight(code, lexer, formatter)
        return highlighted
    except ClassNotFound:
        # Unknown language, try guessing
        try:
            lexer = guess_lexer(code)
            formatter = HtmlFormatter(cssclass='highlight', noclasses=False)
            return pygments_highlight(code, lexer, formatter)
        except:
            # Give up, return plain code
            return f'<pre><code class="language-{lang}">{code}</code></pre>'
    except Exception as e:
        # Log error but don't break rendering
        import logging
        logger = logging.getLogger('askbot.markdown')
        logger.warning(f"Pygments highlighting failed for lang={lang}: {e}")
        return f'<pre><code class="language-{lang}">{code}</code></pre>'
```

#### Test Cases
```python
# Test in askbot/tests/test_markup.py
def test_syntax_highlighting_python():
    md = get_md_converter()
    text = "```python\ndef hello():\n    print('world')\n```"
    html = md.render(text)
    assert 'class="highlight"' in html
    assert '<span class="k">def</span>' in html  # 'def' is a keyword

def test_syntax_highlighting_unknown_language():
    md = get_md_converter()
    text = "```unknownlang\nsome code\n```"
    html = md.render(text)
    assert 'some code' in html  # Still renders
```

---

### Task 1.3: Video Embedding Plugin

**Estimated Time**: 8 hours
**Files Created**: 1
**Location**: `askbot/utils/markdown_plugins/video_embed.py`

#### Subtasks
- [ ] Create plugin directory structure
- [ ] Write inline parser rule for `@[service](id)` syntax
- [ ] Support YouTube, Vimeo, Dailymotion
- [ ] Write render function for iframe generation
- [ ] Add plugin to get_md_converter()
- [ ] Write unit tests

#### Implementation

**Directory Structure**:
```
askbot/utils/markdown_plugins/
├── __init__.py
└── video_embed.py
```

**File**: `askbot/utils/markdown_plugins/__init__.py`
```python
"""Custom markdown-it plugins for askbot."""
```

**File**: `askbot/utils/markdown_plugins/video_embed.py`
```python
"""
Video embedding plugin for markdown-it-py.

Syntax:
    @[youtube](video_id)
    @[vimeo](video_id)
    @[dailymotion](video_id)

Renders as iframe embed for supported services.

Based on: https://github.com/CenterForOpenScience/markdown-it-video
"""

import re
from markdown_it import MarkdownIt
from markdown_it.rules_inline import StateInline


VIDEO_SERVICES = {
    'youtube': {
        'url': 'https://www.youtube.com/embed/{0}',
        'width': 640,
        'height': 390,
    },
    'vimeo': {
        'url': 'https://player.vimeo.com/video/{0}',
        'width': 640,
        'height': 360,
    },
    'dailymotion': {
        'url': 'https://www.dailymotion.com/embed/video/{0}',
        'width': 640,
        'height': 360,
    },
}


def video_embed_rule(state: StateInline, silent: bool) -> bool:
    """
    Parse video embed syntax: @[service](video_id)

    Returns True if pattern matches and token created.
    """
    pos = state.pos
    maximum = state.posMax

    # Must start with @[
    if state.src[pos:pos+2] != '@[':
        return False

    # Find closing ]
    service_start = pos + 2
    service_end = state.src.find(']', service_start)

    if service_end == -1 or service_end >= maximum:
        return False

    service = state.src[service_start:service_end].strip().lower()

    # Check if it's a supported service
    if service not in VIDEO_SERVICES:
        return False

    # Must have opening (
    if service_end + 1 >= maximum or state.src[service_end + 1] != '(':
        return False

    # Find closing )
    id_start = service_end + 2
    id_end = state.src.find(')', id_start)

    if id_end == -1 or id_end >= maximum:
        return False

    video_id = state.src[id_start:id_end].strip()

    # Validate video ID (alphanumeric, dashes, underscores)
    if not re.match(r'^[a-zA-Z0-9_-]+$', video_id):
        return False

    if not silent:
        token = state.push('video_embed', '', 0)
        token.meta = {
            'service': service,
            'id': video_id,
        }
        token.markup = state.src[pos:id_end+1]

    state.pos = id_end + 1
    return True


def render_video_embed(tokens, idx, options, env, renderer):
    """
    Render video embed token as iframe.
    """
    token = tokens[idx]
    service = token.meta['service']
    video_id = token.meta['id']

    config = VIDEO_SERVICES[service]
    url = config['url'].format(video_id)
    width = config['width']
    height = config['height']

    # Security: Only allow whitelisted domains
    # HTML escaping handled by renderer

    iframe = (
        f'<div class="video-embed video-embed-{service}">'
        f'<iframe '
        f'width="{width}" '
        f'height="{height}" '
        f'src="{url}" '
        f'frameborder="0" '
        f'allowfullscreen '
        f'loading="lazy"'
        f'></iframe>'
        f'</div>'
    )

    return iframe


def video_embed_plugin(md: MarkdownIt) -> MarkdownIt:
    """
    Plugin to enable video embedding in markdown.

    Usage:
        md = MarkdownIt()
        md.use(video_embed_plugin)
    """
    # Register inline rule before 'link' to give it priority
    md.inline.ruler.before('link', 'video_embed', video_embed_rule)

    # Register renderer
    md.add_render_rule('video_embed', render_video_embed)

    return md
```

#### Test Cases

**File**: `askbot/tests/test_markdown_video_plugin.py`
```python
import pytest
from markdown_it import MarkdownIt
from askbot.utils.markdown_plugins.video_embed import video_embed_plugin


class TestVideoEmbedPlugin:

    @pytest.fixture
    def md(self):
        return MarkdownIt().use(video_embed_plugin)

    def test_youtube_embed(self, md):
        text = "@[youtube](dQw4w9WgXcQ)"
        html = md.render(text)
        assert 'https://www.youtube.com/embed/dQw4w9WgXcQ' in html
        assert 'iframe' in html
        assert 'video-embed-youtube' in html

    def test_vimeo_embed(self, md):
        text = "@[vimeo](123456789)"
        html = md.render(text)
        assert 'https://player.vimeo.com/video/123456789' in html
        assert 'iframe' in html

    def test_dailymotion_embed(self, md):
        text = "@[dailymotion](x8abcdef)"
        html = md.render(text)
        assert 'dailymotion.com/embed/video/x8abcdef' in html

    def test_unsupported_service_ignored(self, md):
        text = "@[tiktok](12345)"
        html = md.render(text)
        # Should be treated as regular text
        assert '@[tiktok](12345)' in html
        assert 'iframe' not in html

    def test_invalid_video_id_ignored(self, md):
        # IDs with spaces or special chars should be rejected
        text = "@[youtube](invalid id!)"
        html = md.render(text)
        assert 'iframe' not in html

    def test_video_in_paragraph(self, md):
        text = "Check this out: @[youtube](dQw4w9WgXcQ) cool right?"
        html = md.render(text)
        assert 'Check this out:' in html
        assert 'youtube.com/embed' in html
        assert 'cool right?' in html

    def test_multiple_videos(self, md):
        text = "@[youtube](abc123)\n\n@[vimeo](456789)"
        html = md.render(text)
        assert 'youtube.com/embed/abc123' in html
        assert 'vimeo.com/video/456789' in html
```

---

### Task 1.4: Custom Link Patterns Plugin

**Estimated Time**: 10 hours
**Files Created**: 1
**Location**: `askbot/utils/markdown_plugins/link_patterns.py`

#### Subtasks
- [ ] Read settings from askbot.conf.markup
- [ ] Parse regex patterns and URL templates
- [ ] Write core state traversal logic
- [ ] Handle pattern matching with capture groups
- [ ] Replace text tokens with link tokens
- [ ] Add error handling for invalid regexes
- [ ] Write comprehensive unit tests

#### Implementation

**File**: `askbot/utils/markdown_plugins/link_patterns.py`
```python
"""
Custom link patterns plugin for markdown-it-py.

Automatically converts text matching regex patterns to links.

Example:
    Settings:
        AUTO_LINK_PATTERNS = "#bug(\\d+)"
        AUTO_LINK_URLS = "https://bugs.example.com/show?id=\\1"

    Text:
        "Fixed #bug123"

    Output:
        Fixed <a href="https://bugs.example.com/show?id=123">#bug123</a>

Based on askbot settings:
    - ENABLE_AUTO_LINKING (bool)
    - AUTO_LINK_PATTERNS (multiline string of regexes)
    - AUTO_LINK_URLS (multiline string of URL templates)
"""

import re
import logging
from markdown_it import MarkdownIt
from markdown_it.rules_core import StateCore


logger = logging.getLogger('askbot.markdown.link_patterns')


def parse_pattern_config(patterns_str, urls_str):
    """
    Parse pattern and URL configuration strings.

    Args:
        patterns_str: Newline-separated regex patterns
        urls_str: Newline-separated URL templates

    Returns:
        List of (compiled_regex, url_template) tuples
    """
    if not patterns_str or not urls_str:
        return []

    pattern_lines = [p.strip() for p in patterns_str.strip().split('\n') if p.strip()]
    url_lines = [u.strip() for u in urls_str.strip().split('\n') if u.strip()]

    if len(pattern_lines) != len(url_lines):
        logger.warning(
            f"Pattern count ({len(pattern_lines)}) != URL count ({len(url_lines)}). "
            f"Auto-linking disabled."
        )
        return []

    rules = []
    for idx, (pattern_str, url_template) in enumerate(zip(pattern_lines, url_lines)):
        try:
            compiled_pattern = re.compile(pattern_str)
            rules.append((compiled_pattern, url_template))
        except re.error as e:
            logger.error(
                f"Invalid regex pattern at line {idx+1}: {pattern_str}. Error: {e}"
            )
            continue

    return rules


def apply_link_patterns(state: StateCore, rules):
    """
    Traverse token tree and replace matching text with links.
    """
    if not rules:
        return

    for block_idx, block_token in enumerate(state.tokens):
        if block_token.type != 'inline' or not block_token.children:
            continue

        new_children = []

        for child_token in block_token.children:
            if child_token.type != 'text':
                new_children.append(child_token)
                continue

            text = child_token.content
            processed_tokens = process_text_with_patterns(text, rules, state)
            new_children.extend(processed_tokens)

        block_token.children = new_children


def process_text_with_patterns(text, rules, state):
    """
    Process a text string, replacing pattern matches with link tokens.

    Returns:
        List of tokens (text and link tokens)
    """
    Token = state.Token
    tokens = []

    # Track all matches across all patterns
    all_matches = []
    for pattern, url_template in rules:
        for match in pattern.finditer(text):
            all_matches.append({
                'start': match.start(),
                'end': match.end(),
                'matched_text': match.group(0),
                'url_template': url_template,
                'groups': match.groups(),
            })

    # Sort matches by start position
    all_matches.sort(key=lambda m: m['start'])

    # Merge overlapping matches (keep first)
    merged_matches = []
    for match in all_matches:
        if not merged_matches:
            merged_matches.append(match)
            continue

        last_match = merged_matches[-1]
        if match['start'] < last_match['end']:
            # Overlapping, skip this match
            continue

        merged_matches.append(match)

    # Build token list
    last_pos = 0
    for match in merged_matches:
        # Add text before match
        if match['start'] > last_pos:
            text_token = Token('text', '', 0)
            text_token.content = text[last_pos:match['start']]
            tokens.append(text_token)

        # Build URL from template
        url = match['url_template']
        for idx, group in enumerate(match['groups'], start=1):
            if group is not None:
                # Replace \1, \2, etc. with captured groups
                url = url.replace(f'\\{idx}', group)

        # Create link tokens
        link_open = Token('link_open', 'a', 1)
        link_open.attrs = {'href': url}
        link_open.markup = 'autolink'
        tokens.append(link_open)

        link_text = Token('text', '', 0)
        link_text.content = match['matched_text']
        tokens.append(link_text)

        link_close = Token('link_close', 'a', -1)
        tokens.append(link_close)

        last_pos = match['end']

    # Add remaining text
    if last_pos < len(text):
        text_token = Token('text', '', 0)
        text_token.content = text[last_pos:]
        tokens.append(text_token)

    # If no matches, return original text as single token
    if not tokens:
        text_token = Token('text', '', 0)
        text_token.content = text
        return [text_token]

    return tokens


def link_patterns_plugin(md: MarkdownIt, config: dict) -> MarkdownIt:
    """
    Plugin to auto-link text matching custom patterns.

    Args:
        config: Dictionary with keys:
            - enabled (bool): Whether plugin is active
            - patterns (str): Newline-separated regex patterns
            - urls (str): Newline-separated URL templates

    Usage:
        md = MarkdownIt()
        md.use(link_patterns_plugin, {
            'enabled': True,
            'patterns': '#bug(\\\\d+)',
            'urls': 'https://bugs.example.com/\\\\1'
        })
    """
    if not config.get('enabled', False):
        return md

    patterns_str = config.get('patterns', '')
    urls_str = config.get('urls', '')

    rules = parse_pattern_config(patterns_str, urls_str)

    if not rules:
        logger.info("No valid link pattern rules configured")
        return md

    logger.info(f"Loaded {len(rules)} link pattern rules")

    def link_patterns_core_rule(state: StateCore):
        apply_link_patterns(state, rules)

    # Run after linkify but before other core rules
    md.core.ruler.after('linkify', 'custom_link_patterns', link_patterns_core_rule)

    return md
```

#### Test Cases

**File**: `askbot/tests/test_markdown_link_patterns_plugin.py`
```python
import pytest
from markdown_it import MarkdownIt
from askbot.utils.markdown_plugins.link_patterns import link_patterns_plugin


class TestLinkPatternsPlugin:

    def test_simple_pattern(self):
        md = MarkdownIt().use(link_patterns_plugin, {
            'enabled': True,
            'patterns': r'#bug(\d+)',
            'urls': r'https://bugs.example.com/\1',
        })

        text = "Fixed #bug123 yesterday"
        html = md.render(text)

        assert '<a href="https://bugs.example.com/123">#bug123</a>' in html
        assert 'Fixed' in html
        assert 'yesterday' in html

    def test_multiple_patterns(self):
        md = MarkdownIt().use(link_patterns_plugin, {
            'enabled': True,
            'patterns': '#bug(\\d+)\n@user(\\w+)',
            'urls': 'https://bugs.example.com/\\1\nhttps://github.com/\\1',
        })

        text = "Fixed #bug456 by @alice"
        html = md.render(text)

        assert 'bugs.example.com/456' in html
        assert 'github.com/alice' in html

    def test_disabled_plugin(self):
        md = MarkdownIt().use(link_patterns_plugin, {
            'enabled': False,
            'patterns': r'#bug(\d+)',
            'urls': r'https://bugs.example.com/\1',
        })

        text = "Fixed #bug123"
        html = md.render(text)

        # Should not create links
        assert 'bugs.example.com' not in html
        assert '#bug123' in html

    def test_overlapping_matches(self):
        # Only first match should be linkified
        md = MarkdownIt().use(link_patterns_plugin, {
            'enabled': True,
            'patterns': r'bug(\d+)\n#bug(\d+)',
            'urls': r'https://example1.com/\1\nhttps://example2.com/\1',
        })

        text = "#bug123"
        html = md.render(text)

        # Should only match the second pattern since it starts earlier
        assert 'example2.com/123' in html
        assert 'example1.com' not in html

    def test_pattern_in_code_block_not_linkified(self):
        md = MarkdownIt().use(link_patterns_plugin, {
            'enabled': True,
            'patterns': r'#bug(\d+)',
            'urls': r'https://bugs.example.com/\1',
        })

        text = "Text #bug123 and `code #bug456` here"
        html = md.render(text)

        # #bug123 should be linked (in text)
        assert 'bugs.example.com/123' in html

        # #bug456 should NOT be linked (in code)
        assert 'bugs.example.com/456' not in html

    def test_invalid_regex_ignored(self):
        # Plugin should not crash on invalid regex
        md = MarkdownIt().use(link_patterns_plugin, {
            'enabled': True,
            'patterns': r'[invalid(regex',  # Missing closing ]
            'urls': r'https://example.com',
        })

        text = "Some text"
        html = md.render(text)
        assert 'Some text' in html  # Should still render

    def test_mismatched_pattern_url_count(self):
        # Should disable auto-linking if counts don't match
        md = MarkdownIt().use(link_patterns_plugin, {
            'enabled': True,
            'patterns': r'#bug(\d+)\n@user(\w+)',
            'urls': r'https://bugs.example.com/\1',  # Only one URL
        })

        text = "Fixed #bug123"
        html = md.render(text)

        # Should not create links due to mismatch
        assert 'bugs.example.com' not in html
```

---

### Task 1.5: Update get_md_converter()

**Estimated Time**: 4 hours
**Files Modified**: 1
**Location**: `askbot/utils/markup.py:30-47`

#### Subtasks
- [ ] Import all required modules
- [ ] Import custom plugins
- [ ] Configure Pygments highlighting
- [ ] Enable standard plugins (footnotes, tasklists)
- [ ] Add video embedding plugin
- [ ] Add link patterns plugin with settings
- [ ] **Implement math delimiter protection (for MathJax)**
- [ ] Implement code-friendly mode
- [ ] Test complete integration

#### Implementation

```python
# askbot/utils/markup.py

from markdown_it import MarkdownIt
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin

from askbot.conf import settings as askbot_settings
from askbot.utils.markdown_plugins.video_embed import video_embed_plugin
from askbot.utils.markdown_plugins.link_patterns import link_patterns_plugin

# Pygments imports (from Task 1.2)
from pygments import highlight as pygments_highlight
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import HtmlFormatter
from pygments.util import ClassNotFound


def highlight_code(code, lang, attrs):
    """Syntax highlighting using Pygments (see Task 1.2)"""
    # ... (implementation from Task 1.2)
    pass


# Singleton pattern - create converter once
_MD_CONVERTER = None

def get_md_converter():
    """
    Returns a configured instance of MarkdownIt.

    Converts markdown with extra features:
    * Tables (GFM-like preset)
    * Footnotes
    * Task lists
    * Syntax highlighting (Pygments)
    * Video embedding (@[youtube](id))
    * Custom link patterns (#bug123 -> links)
    * Code-friendly mode (disable underscore emphasis)
    * Linkify URLs

    Uses singleton pattern for performance.
    """
    global _MD_CONVERTER

    if _MD_CONVERTER is not None:
        return _MD_CONVERTER

    # Create markdown-it instance with GFM-like preset
    # Includes: tables, strikethrough, linkify
    md = MarkdownIt('gfm-like')

    # Configure syntax highlighting
    md.options['highlight'] = highlight_code

    # Enable standard plugins
    md.use(footnote_plugin)
    md.use(tasklists_plugin)

    # Enable video embedding
    md.use(video_embed_plugin)

    # Enable custom link patterns
    md.use(link_patterns_plugin, {
        'enabled': askbot_settings.ENABLE_AUTO_LINKING,
        'patterns': askbot_settings.AUTO_LINK_PATTERNS,
        'urls': askbot_settings.AUTO_LINK_URLS,
    })

    # Code-friendly mode: disable underscore emphasis for MathJax compatibility
    # and programming discussions
    if askbot_settings.MARKUP_CODE_FRIENDLY or askbot_settings.ENABLE_MATHJAX:
        # Disable emphasis (handles both * and _)
        # Re-enable just * by adding custom rule
        md.disable('emphasis')
        # TODO: Add custom rule to re-enable * only if needed

    # Math delimiter protection for MathJax support
    # Protect $...$ (inline) and $$...$$ (display) from markdown processing
    if askbot_settings.ENABLE_MATHJAX:
        # Add plugin to treat math blocks as verbatim text
        # This prevents markdown from processing content inside math delimiters
        # Example: $a_b$ should NOT become $a<sub>b</sub>$
        # TODO: Implement math delimiter protection plugin
        pass

    _MD_CONVERTER = md
    return _MD_CONVERTER


# Add function to reset singleton (useful for tests)
def reset_md_converter():
    """Reset the singleton converter (used in tests when settings change)"""
    global _MD_CONVERTER
    _MD_CONVERTER = None
```

---

### Task 1.6: Integration Testing

**Estimated Time**: 6 hours
**Files Modified**: 1
**Files Created**: 1

#### Subtasks
- [ ] Create comprehensive test file
- [ ] Test all features together
- [ ] Test settings combinations
- [ ] Test edge cases
- [ ] Test backward compatibility
- [ ] Measure code coverage

#### Implementation

**File**: `askbot/tests/test_markdown_integration.py`
```python
"""
Integration tests for complete markdown-it-py setup with all plugins.
"""
from django.test import TestCase
from askbot.tests.utils import AskbotTestCase, with_settings
from askbot.utils.markup import get_md_converter, reset_md_converter
from askbot.conf import settings as askbot_settings


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
```

---

### Task 1.7: Update Tests

**Estimated Time**: 4 hours
**Files Modified**: Multiple in `askbot/tests/`

#### Subtasks
- [ ] Find existing markdown tests
- [ ] Update for markdown-it-py syntax
- [ ] Add new test cases for plugins
- [ ] Fix any broken tests
- [ ] Achieve 95%+ coverage

#### Commands
```bash
# Activate virtual environment
source env/bin/activate

# Find existing markdown-related tests
cd testproject/
python manage.py test askbot.tests.test_utils -v 2
python manage.py test askbot.tests -k markdown -v 2

# Run with coverage
coverage run --rcfile ../.coveragerc manage.py test askbot.tests.test_markdown* --parallel 4
coverage report --include="askbot/utils/markup.py,askbot/utils/markdown_plugins/*"
```

---

## Phase 1 Deliverables

### Code Deliverables
- [ ] Updated dependencies (askbot/__init__.py, askbot_requirements.txt)
- [ ] Pygments integration in markup.py
- [ ] Video embedding plugin (askbot/utils/markdown_plugins/video_embed.py)
- [ ] Link patterns plugin (askbot/utils/markdown_plugins/link_patterns.py)
- [ ] Updated get_md_converter() function
- [ ] Comprehensive test suite (>95% coverage)

### Documentation Deliverables
- [ ] Docstrings for all new functions
- [ ] README for markdown_plugins module
- [ ] Migration notes for developers

### Validation Checklist
- [ ] All unit tests passing
- [ ] Integration tests passing
- [ ] Test coverage ≥95% for new code
- [ ] No regressions in existing tests
- [ ] Manual testing of all features
- [ ] Code review completed
- [ ] Documentation reviewed

## Phase 1 Exit Criteria

**Must Complete Before Phase 2:**

1. ✅ All tests passing (0 failures)
2. ✅ Code coverage ≥95% for:
   - `askbot/utils/markup.py`
   - `askbot/utils/markdown_plugins/*.py`
3. ✅ Manual validation of features:
   - Tables render correctly
   - Syntax highlighting works
   - Videos embed properly
   - Link patterns auto-link
   - Code-friendly mode works
4. ✅ No performance regression (benchmark tests)
5. ✅ Code review approved
6. ✅ Documentation complete

**Phase 1 Gate Review Questions:**
1. Do all existing markdown2 features work in markdown-it-py?
2. Are custom plugins robust enough for production?
3. Is test coverage sufficient?
4. Are there any edge cases we missed?
5. Is performance acceptable?

**Sign-off Required:** Technical Lead

---

## Risk Mitigation

**Risk**: Custom plugins have bugs
**Mitigation**: Extensive unit tests, fuzzing, production data testing

**Risk**: Performance regression
**Mitigation**: Benchmark testing, caching strategy

**Risk**: Edge cases not covered
**Mitigation**: Test with real production content before Phase 2

---

## Next Steps After Phase 1

Once Phase 1 gate criteria are met:
1. Deploy to staging environment
2. Test with copy of production database
3. Monitor for errors/performance issues
4. Gather feedback
5. **Only then** proceed to Phase 2 (Frontend Migration)

See: [Phase 2: Frontend Migration](markdown-upgrade-phase2-frontend.md)
