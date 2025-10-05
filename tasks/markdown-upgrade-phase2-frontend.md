# Phase 2: Frontend Migration

**Status**: ⚪ Not started
**Duration**: 2 weeks
**Prerequisites**: Phase 1 complete (backend tests passing)
**Blocks**: Phase 3 (Testing & Deployment)

## Overview

Replace the outdated Showdown markdown library (~2011) with modern markdown-it.js to match the Python backend implementation, ensuring consistent rendering between server and client.

## Goals

1. Remove Showdown/WMD dependencies
2. Install markdown-it.js and required plugins
3. Rewrite `askbot_converter.js` for markdown-it
4. Update templates to load new libraries
5. Ensure live preview matches backend rendering exactly
6. Maintain MathJax integration
7. Preserve existing WMD editor functionality

## Current Frontend Stack

**Files to Replace/Update:**
- `askbot/media/wmd/showdown-min.js` - OLD Showdown library
- `askbot/media/wmd/Markdown.Converter.js` - OLD Showdown converter
- `askbot/media/wmd/askbot_converter.js` - Askbot wrapper (needs rewrite)
- `askbot/jinja2/meta/markdown_javascript.html` - Script includes

**Files to Preserve:**
- `askbot/media/wmd/wmd.js` - WMD editor (still useful)
- `askbot/media/wmd/Markdown.Sanitizer.js` - HTML sanitization

## Task Breakdown

### Task 2.1: Install markdown-it.js Libraries

**Estimated Time**: 3 hours
**Files Created**: Multiple in `askbot/media/markdown_it/`

#### Subtasks
- [ ] Download markdown-it.js core library
- [ ] Download markdown-it-footnote plugin
- [ ] Download markdown-it-task-lists plugin
- [ ] Download markdown-it-video plugin (if available)
- [ ] Create custom link patterns JS plugin
- [ ] Verify file integrity

#### Implementation Strategy

**Option A: CDN Links (Recommended for Development)**
```html
<!-- Fast, cached, always up-to-date -->
<script src="https://cdn.jsdelivr.net/npm/markdown-it@14/dist/markdown-it.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/markdown-it-footnote@4/dist/markdown-it-footnote.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/markdown-it-task-lists@2/dist/markdown-it-task-lists.min.js"></script>
```

**Option B: Vendor Files (Recommended for Production)**
```bash
# Create directory
mkdir -p askbot/media/markdown_it/

# Download core library (v14.x)
curl -o askbot/media/markdown_it/markdown-it.min.js \
  https://cdn.jsdelivr.net/npm/markdown-it@14/dist/markdown-it.min.js

# Download plugins
curl -o askbot/media/markdown_it/markdown-it-footnote.min.js \
  https://cdn.jsdelivr.net/npm/markdown-it-footnote@4/dist/markdown-it-footnote.min.js

curl -o askbot/media/markdown_it/markdown-it-task-lists.min.js \
  https://cdn.jsdelivr.net/npm/markdown-it-task-lists@2/dist/markdown-it-task-lists.min.js

# Verify downloads
ls -lh askbot/media/markdown_it/
```

**Option C: npm + Build (Most Robust)**
```bash
cd askbot/media/
npm init -y
npm install markdown-it markdown-it-footnote markdown-it-task-lists --save
npm install webpack webpack-cli --save-dev

# Create webpack config to bundle
# Then: npm run build
```

**Decision**: Use **Option B (Vendor Files)** for Phase 2.

#### File Structure
```
askbot/media/markdown_it/
├── markdown-it.min.js              (core library)
├── markdown-it-footnote.min.js     (footnotes plugin)
├── markdown-it-task-lists.min.js   (task lists plugin)
├── markdown-it-video.js            (custom video plugin, see Task 2.3)
└── markdown-it-link-patterns.js    (custom link patterns, see Task 2.4)
```

---

### Task 2.2: Rewrite askbot_converter.js

**Estimated Time**: 8 hours
**Files Modified**: 1
**Location**: `askbot/media/wmd/askbot_converter.js`

#### Subtasks
- [ ] Study existing `askbot_converter.js` API
- [ ] Create new AskbotMarkdownConverter class
- [ ] Configure markdown-it with same plugins as backend
- [ ] Implement `makeHtml()` method
- [ ] Preserve MathJax integration
- [ ] Handle settings (code-friendly mode, etc.)
- [ ] Test preview pane updates

#### Current Implementation Analysis

**File**: `askbot/media/wmd/askbot_converter.js` (existing)
```javascript
// Current API surface:
var converter = new AskbotMarkdownConverter();
converter.makeHtml(text);  // Returns HTML string
converter.scheduleMathJaxRendering();  // Queues MathJax re-render
```

#### New Implementation

**File**: `askbot/media/wmd/askbot_converter.js` (rewrite)
```javascript
/**
 * Askbot Markdown Converter
 * Wraps markdown-it.js with askbot-specific configuration
 *
 * Matches Python backend configuration in askbot/utils/markup.py
 */

(function(window) {
    'use strict';

    /**
     * AskbotMarkdownConverter constructor
     * Creates a configured markdown-it instance with all plugins
     */
    function AskbotMarkdownConverter() {
        // Check dependencies
        if (typeof window.markdownit === 'undefined') {
            throw new Error('markdown-it library not loaded');
        }

        // Initialize markdown-it with GFM-like preset
        // Matches Python: MarkdownIt('gfm-like')
        this._md = window.markdownit({
            html: false,        // Disable raw HTML (security)
            xhtmlOut: true,     // Use XHTML-style tags
            breaks: false,      // Don't convert \n to <br>
            linkify: true,      // Auto-convert URLs to links
            typographer: false, // Don't replace quotes/dashes
            highlight: this._highlightCode.bind(this)
        });

        // Enable GFM extensions (tables, strikethrough)
        this._md.enable(['table', 'strikethrough']);

        // Load standard plugins
        this._loadPlugins();

        // Configure for askbot settings
        this._configureSettings();

        // MathJax rendering queue
        this._mathJaxTimeout = null;
    }

    /**
     * Load markdown-it plugins to match Python backend
     */
    AskbotMarkdownConverter.prototype._loadPlugins = function() {
        // Footnotes plugin
        if (typeof window.markdownitFootnote !== 'undefined') {
            this._md.use(window.markdownitFootnote);
        }

        // Task lists plugin
        if (typeof window.markdownitTaskLists !== 'undefined') {
            this._md.use(window.markdownitTaskLists);
        }

        // Video embedding plugin (custom)
        if (typeof window.markdownitVideo !== 'undefined') {
            this._md.use(window.markdownitVideo);
        }

        // Custom link patterns plugin
        if (typeof window.markdownitLinkPatterns !== 'undefined') {
            var linkPatterns = window.askbot.settings.autoLinkPatterns || {};
            this._md.use(window.markdownitLinkPatterns, linkPatterns);
        }
    };

    /**
     * Configure based on askbot settings
     */
    AskbotMarkdownConverter.prototype._configureSettings = function() {
        var settings = window.askbot.settings || {};

        // Code-friendly mode: disable underscore emphasis
        if (settings.markupCodeFriendly || settings.mathjaxEnabled) {
            // Disable emphasis rule (both * and _)
            this._md.disable('emphasis');
            // TODO: Re-enable just asterisk if needed
        }
    };

    /**
     * Syntax highlighting function
     * Matches Python Pygments output if possible
     */
    AskbotMarkdownConverter.prototype._highlightCode = function(code, lang) {
        if (!lang) {
            return ''; // Use default rendering
        }

        // If highlight.js is available, use it
        if (typeof window.hljs !== 'undefined') {
            if (hljs.getLanguage(lang)) {
                try {
                    return hljs.highlight(code, {
                        language: lang,
                        ignoreIllegals: true
                    }).value;
                } catch (err) {
                    console.warn('Highlight.js error:', err);
                }
            }
        }

        // Fallback: return empty to use default
        return '';
    };

    /**
     * Convert markdown text to HTML
     * Main API method - matches old Showdown API
     *
     * @param {string} text - Markdown source text
     * @returns {string} HTML output
     */
    AskbotMarkdownConverter.prototype.makeHtml = function(text) {
        if (!text || typeof text !== 'string') {
            return '';
        }

        // Render markdown to HTML
        var html = this._md.render(text);

        // Handle MathJax if enabled
        if (window.askbot.settings.mathjaxEnabled) {
            this.scheduleMathJaxRendering();
        }

        return html;
    };

    /**
     * Schedule MathJax re-rendering
     * Debounced to avoid excessive re-renders during typing
     */
    AskbotMarkdownConverter.prototype.scheduleMathJaxRendering = function() {
        if (typeof MathJax === 'undefined') {
            return;
        }

        // Clear existing timeout
        if (this._mathJaxTimeout) {
            clearTimeout(this._mathJaxTimeout);
        }

        // Schedule re-render after 300ms of inactivity
        this._mathJaxTimeout = setTimeout(function() {
            if (MathJax.Hub) {
                // MathJax v2
                MathJax.Hub.Queue(['Typeset', MathJax.Hub, 'wmd-preview']);
            } else if (MathJax.typesetPromise) {
                // MathJax v3
                MathJax.typesetPromise([document.getElementById('wmd-preview')])
                    .catch(function(err) {
                        console.error('MathJax typeset error:', err);
                    });
            }
        }, 300);
    };

    /**
     * Get the underlying markdown-it instance
     * Useful for advanced customization
     */
    AskbotMarkdownConverter.prototype.getMarkdownIt = function() {
        return this._md;
    };

    // Export to global scope
    window.AskbotMarkdownConverter = AskbotMarkdownConverter;

})(window);
```

#### Backward Compatibility

The new implementation maintains the same API:
```javascript
// Old Showdown code (still works):
var converter = new AskbotMarkdownConverter();
var html = converter.makeHtml(markdownText);

// New markdown-it code (also works):
var converter = new AskbotMarkdownConverter();
var html = converter.makeHtml(markdownText);
```

---

### Task 2.3: Write Video Embedding Plugin (JavaScript)

**Estimated Time**: 4 hours
**Files Created**: 1
**Location**: `askbot/media/markdown_it/markdown-it-video.js`

#### Subtasks
- [ ] Port Python video plugin logic to JavaScript
- [ ] Support same services (YouTube, Vimeo, Dailymotion)
- [ ] Match Python output HTML exactly
- [ ] Test with various video IDs

#### Implementation

**File**: `askbot/media/markdown_it/markdown-it-video.js`
```javascript
/**
 * markdown-it-video plugin
 * Embeds videos from YouTube, Vimeo, Dailymotion
 *
 * Syntax: @[youtube](video_id)
 *
 * Matches Python implementation in:
 * askbot/utils/markdown_plugins/video_embed.py
 */

(function(window) {
    'use strict';

    var VIDEO_SERVICES = {
        youtube: {
            url: 'https://www.youtube.com/embed/{0}',
            width: 640,
            height: 390
        },
        vimeo: {
            url: 'https://player.vimeo.com/video/{0}',
            width: 640,
            height: 360
        },
        dailymotion: {
            url: 'https://www.dailymotion.com/embed/video/{0}',
            width: 640,
            height: 360
        }
    };

    /**
     * Parse video embed syntax
     */
    function videoEmbedRule(state, silent) {
        var pos = state.pos;
        var max = state.posMax;

        // Check for @[
        if (state.src.charCodeAt(pos) !== 0x40 /* @ */ ||
            state.src.charCodeAt(pos + 1) !== 0x5B /* [ */) {
            return false;
        }

        // Find service name
        var serviceStart = pos + 2;
        var serviceEnd = state.src.indexOf(']', serviceStart);

        if (serviceEnd === -1 || serviceEnd >= max) {
            return false;
        }

        var service = state.src.slice(serviceStart, serviceEnd).trim().toLowerCase();

        // Check if supported
        if (!VIDEO_SERVICES.hasOwnProperty(service)) {
            return false;
        }

        // Check for (
        if (serviceEnd + 1 >= max || state.src.charCodeAt(serviceEnd + 1) !== 0x28 /* ( */) {
            return false;
        }

        // Find video ID
        var idStart = serviceEnd + 2;
        var idEnd = state.src.indexOf(')', idStart);

        if (idEnd === -1 || idEnd >= max) {
            return false;
        }

        var videoId = state.src.slice(idStart, idEnd).trim();

        // Validate video ID (alphanumeric, dashes, underscores)
        if (!/^[a-zA-Z0-9_-]+$/.test(videoId)) {
            return false;
        }

        if (!silent) {
            var token = state.push('video_embed', '', 0);
            token.meta = {
                service: service,
                id: videoId
            };
            token.markup = state.src.slice(pos, idEnd + 1);
        }

        state.pos = idEnd + 1;
        return true;
    }

    /**
     * Render video embed as iframe
     */
    function renderVideoEmbed(tokens, idx, options, env, renderer) {
        var token = tokens[idx];
        var service = token.meta.service;
        var videoId = token.meta.id;

        var config = VIDEO_SERVICES[service];
        var url = config.url.replace('{0}', videoId);

        // Match Python HTML output exactly
        return '<div class="video-embed video-embed-' + service + '">' +
               '<iframe ' +
               'width="' + config.width + '" ' +
               'height="' + config.height + '" ' +
               'src="' + url + '" ' +
               'frameborder="0" ' +
               'allowfullscreen ' +
               'loading="lazy">' +
               '</iframe>' +
               '</div>';
    }

    /**
     * Plugin initialization
     */
    function videoEmbedPlugin(md) {
        md.inline.ruler.before('link', 'video_embed', videoEmbedRule);
        md.renderer.rules.video_embed = renderVideoEmbed;
        return md;
    }

    // Export
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = videoEmbedPlugin;
    } else {
        window.markdownitVideo = videoEmbedPlugin;
    }

})(typeof window !== 'undefined' ? window : this);
```

---

### Task 2.4: Write Link Patterns Plugin (JavaScript)

**Estimated Time**: 6 hours
**Files Created**: 1
**Location**: `askbot/media/markdown_it/markdown-it-link-patterns.js`

#### Subtasks
- [ ] Port Python link patterns logic to JavaScript
- [ ] Parse regex patterns from config
- [ ] Handle capture groups (\1, \2, etc.)
- [ ] Match Python output exactly
- [ ] Test overlapping matches

#### Implementation

**File**: `askbot/media/markdown_it/markdown-it-link-patterns.js`
```javascript
/**
 * markdown-it-link-patterns plugin
 * Auto-links text matching custom regex patterns
 *
 * Example:
 *   Pattern: #bug(\d+)
 *   URL: https://bugs.example.com/\1
 *   Input: "Fixed #bug123"
 *   Output: Fixed <a href="https://bugs.example.com/123">#bug123</a>
 *
 * Matches Python implementation in:
 * askbot/utils/markdown_plugins/link_patterns.py
 */

(function(window) {
    'use strict';

    /**
     * Parse pattern configuration
     */
    function parsePatternConfig(config) {
        if (!config || !config.enabled) {
            return [];
        }

        var patternsStr = config.patterns || '';
        var urlsStr = config.urls || '';

        var patternLines = patternsStr.split('\n').map(function(s) { return s.trim(); }).filter(Boolean);
        var urlLines = urlsStr.split('\n').map(function(s) { return s.trim(); }).filter(Boolean);

        if (patternLines.length !== urlLines.length) {
            console.warn('Link patterns: pattern count != URL count');
            return [];
        }

        var rules = [];
        for (var i = 0; i < patternLines.length; i++) {
            try {
                var regex = new RegExp(patternLines[i], 'g');
                rules.push({
                    pattern: regex,
                    urlTemplate: urlLines[i]
                });
            } catch (e) {
                console.error('Invalid regex pattern:', patternLines[i], e);
            }
        }

        return rules;
    }

    /**
     * Apply link patterns to text tokens
     */
    function applyLinkPatterns(state, rules) {
        if (!rules || rules.length === 0) {
            return;
        }

        for (var i = 0; i < state.tokens.length; i++) {
            var blockToken = state.tokens[i];

            if (blockToken.type !== 'inline' || !blockToken.children) {
                continue;
            }

            var newChildren = [];

            for (var j = 0; j < blockToken.children.length; j++) {
                var child = blockToken.children[j];

                if (child.type !== 'text') {
                    newChildren.push(child);
                    continue;
                }

                var processed = processTextWithPatterns(child.content, rules, state);
                newChildren = newChildren.concat(processed);
            }

            blockToken.children = newChildren;
        }
    }

    /**
     * Process text, replacing matches with link tokens
     */
    function processTextWithPatterns(text, rules, state) {
        var Token = state.Token;
        var allMatches = [];

        // Find all matches
        rules.forEach(function(rule) {
            var pattern = new RegExp(rule.pattern.source, 'g');
            var match;

            while ((match = pattern.exec(text)) !== null) {
                allMatches.push({
                    start: match.index,
                    end: match.index + match[0].length,
                    matchedText: match[0],
                    urlTemplate: rule.urlTemplate,
                    groups: match.slice(1) // Capture groups
                });
            }
        });

        // Sort by start position
        allMatches.sort(function(a, b) {
            return a.start - b.start;
        });

        // Remove overlapping matches (keep first)
        var mergedMatches = [];
        allMatches.forEach(function(match) {
            if (mergedMatches.length === 0) {
                mergedMatches.push(match);
                return;
            }

            var lastMatch = mergedMatches[mergedMatches.length - 1];
            if (match.start >= lastMatch.end) {
                mergedMatches.push(match);
            }
        });

        // Build token list
        var tokens = [];
        var lastPos = 0;

        mergedMatches.forEach(function(match) {
            // Text before match
            if (match.start > lastPos) {
                var textToken = new Token('text', '', 0);
                textToken.content = text.slice(lastPos, match.start);
                tokens.push(textToken);
            }

            // Build URL from template
            var url = match.urlTemplate;
            match.groups.forEach(function(group, idx) {
                if (group !== undefined) {
                    url = url.replace('\\' + (idx + 1), group);
                }
            });

            // Create link tokens
            var linkOpen = new Token('link_open', 'a', 1);
            linkOpen.attrs = [['href', url]];
            linkOpen.markup = 'autolink';
            tokens.push(linkOpen);

            var linkText = new Token('text', '', 0);
            linkText.content = match.matchedText;
            tokens.push(linkText);

            var linkClose = new Token('link_close', 'a', -1);
            tokens.push(linkClose);

            lastPos = match.end;
        });

        // Remaining text
        if (lastPos < text.length) {
            var textToken = new Token('text', '', 0);
            textToken.content = text.slice(lastPos);
            tokens.push(textToken);
        }

        // If no matches, return original text
        if (tokens.length === 0) {
            var textToken = new Token('text', '', 0);
            textToken.content = text;
            return [textToken];
        }

        return tokens;
    }

    /**
     * Plugin initialization
     */
    function linkPatternsPlugin(md, config) {
        var rules = parsePatternConfig(config);

        if (rules.length === 0) {
            return md;
        }

        console.log('Loaded', rules.length, 'link pattern rules');

        md.core.ruler.after('linkify', 'custom_link_patterns', function(state) {
            applyLinkPatterns(state, rules);
        });

        return md;
    }

    // Export
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = linkPatternsPlugin;
    } else {
        window.markdownitLinkPatterns = linkPatternsPlugin;
    }

})(typeof window !== 'undefined' ? window : this);
```

---

### Task 2.5: Update Templates

**Estimated Time**: 3 hours
**Files Modified**: 1-2
**Location**: `askbot/jinja2/meta/markdown_javascript.html`

#### Subtasks
- [ ] Find current template loading markdown scripts
- [ ] Remove Showdown references
- [ ] Add markdown-it library loads
- [ ] Add plugin loads in correct order
- [ ] Pass askbot settings to JavaScript
- [ ] Test in browser

#### Implementation

**Current Template**: `askbot/jinja2/meta/markdown_javascript.html`

Likely contains:
```html
<!-- OLD Showdown -->
<script src="{{ '/wmd/showdown-min.js'|media }}"></script>
<script src="{{ '/wmd/Markdown.Converter.js'|media }}"></script>
```

**New Template** (replace with):
```html
{# Markdown rendering libraries #}

{# Option 1: Vendor files (production) #}
<script src="{{ '/markdown_it/markdown-it.min.js'|media }}"></script>
<script src="{{ '/markdown_it/markdown-it-footnote.min.js'|media }}"></script>
<script src="{{ '/markdown_it/markdown-it-task-lists.min.js'|media }}"></script>

{# Custom plugins #}
<script src="{{ '/markdown_it/markdown-it-video.js'|media }}"></script>
<script src="{{ '/markdown_it/markdown-it-link-patterns.js'|media }}"></script>

{# Askbot converter wrapper #}
<script src="{{ '/wmd/askbot_converter.js'|media }}"></script>

{# Pass settings to JavaScript #}
<script>
window.askbot = window.askbot || {};
window.askbot.settings = {
    mathjaxEnabled: {% if settings.ENABLE_MATHJAX %}true{% else %}false{% endif %},
    markupCodeFriendly: {% if settings.MARKUP_CODE_FRIENDLY %}true{% else %}false{% endif %},
    autoLinkPatterns: {
        enabled: {% if settings.ENABLE_AUTO_LINKING %}true{% else %}false{% endif %},
        patterns: {{ settings.AUTO_LINK_PATTERNS|tojson }},
        urls: {{ settings.AUTO_LINK_URLS|tojson }}
    }
};
</script>

{# WMD editor (still used) #}
<script src="{{ '/wmd/wmd.js'|media }}"></script>

{# Syntax highlighting (optional) #}
{% if settings.ENABLE_SYNTAX_HIGHLIGHTING %}
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/highlight.js@11/styles/default.min.css">
<script src="https://cdn.jsdelivr.net/npm/highlight.js@11/lib/core.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/highlight.js@11/lib/languages/python.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/highlight.js@11/lib/languages/javascript.min.js"></script>
{# Add more languages as needed #}
{% endif %}
```

---

### Task 2.6: Integration Testing

**Estimated Time**: 6 hours
**Files Created**: 1

#### Subtasks
- [ ] Create browser test suite
- [ ] Test live preview updates
- [ ] Test all markdown features
- [ ] Compare frontend vs backend rendering
- [ ] Test with real user input
- [ ] Performance testing

#### Manual Test Cases

1. **Basic Markdown**
   - Type: `**bold**` → Should show bold in preview
   - Type: `*italic*` → Should show italic

2. **Tables**
   ```markdown
   | Col 1 | Col 2 |
   |-------|-------|
   | A     | B     |
   ```
   → Should render table

3. **Video Embedding**
   - Type: `@[youtube](dQw4w9WgXcQ)`
   - Should show YouTube embed in preview

4. **Syntax Highlighting**
   ```markdown
   ```python
   def hello():
       pass
   ```
   ```
   → Should syntax highlight

5. **Link Patterns** (if configured)
   - Type: `Fixed #bug123`
   - Should auto-link to bug tracker

6. **MathJax** (if enabled)
   - Type: `$E = mc^2$`
   - Should render math

7. **Backend/Frontend Match**
   - Save post with complex markdown
   - Compare saved HTML (backend) vs preview (frontend)
   - Should be identical

#### Automated Testing

**File**: `askbot/tests/test_markdown_frontend.py`
```python
"""
Integration tests for frontend markdown rendering.
Uses Selenium or Playwright to test in real browser.
"""
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


@pytest.fixture
def browser():
    driver = webdriver.Chrome()
    yield driver
    driver.quit()


@pytest.mark.selenium
def test_live_preview_basic_markdown(browser, live_server):
    """Test live preview renders basic markdown"""
    browser.get(f"{live_server.url}/questions/ask/")

    # Find markdown input
    textarea = browser.find_element(By.ID, "id_text")
    textarea.send_keys("**bold text**")

    # Wait for preview to update
    preview = WebDriverWait(browser, 5).until(
        EC.presence_of_element_located((By.ID, "wmd-preview"))
    )

    # Check preview contains <strong>
    assert "<strong>bold text</strong>" in preview.get_attribute('innerHTML')


# More tests...
```

---

### Task 2.7: Remove Old Showdown Files

**Estimated Time**: 1 hour
**Files Deleted**: 2-3

#### Subtasks
- [ ] Verify new system works completely
- [ ] Remove `askbot/media/wmd/showdown-min.js`
- [ ] Remove `askbot/media/wmd/Markdown.Converter.js`
- [ ] Update any references in comments
- [ ] Git commit the removal

#### Commands
```bash
# After verifying everything works:
git rm askbot/media/wmd/showdown-min.js
git rm askbot/media/wmd/Markdown.Converter.js
git commit -m "Remove deprecated Showdown markdown library

Replaced with markdown-it.js to match Python backend.
Old files preserved in git history if needed."
```

---

## Phase 2 Deliverables

### Code Deliverables
- [ ] markdown-it.js and plugins installed
- [ ] New askbot_converter.js implementation
- [ ] Custom video plugin (JS)
- [ ] Custom link patterns plugin (JS)
- [ ] Updated templates
- [ ] Old Showdown files removed
- [ ] Browser tests passing

### Documentation Deliverables
- [ ] Comments in askbot_converter.js
- [ ] README for markdown_it directory
- [ ] Browser compatibility notes

### Validation Checklist
- [ ] Live preview works in Chrome
- [ ] Live preview works in Firefox
- [ ] Live preview works in Safari
- [ ] Preview matches backend HTML exactly
- [ ] MathJax still works
- [ ] WMD editor still works
- [ ] No JavaScript console errors
- [ ] Performance acceptable (<100ms render time)

## Phase 2 Exit Criteria

**Must Complete Before Phase 3:**

1. ✅ Frontend renders markdown identically to backend
2. ✅ All browser tests passing
3. ✅ No JavaScript errors in console
4. ✅ MathJax integration preserved
5. ✅ Performance benchmarks met (<100ms)
6. ✅ Manual testing on staging environment
7. ✅ Browser compatibility verified (Chrome, Firefox, Safari)
8. ✅ Code review approved

**Phase 2 Gate Review Questions:**
1. Does live preview match saved posts exactly?
2. Are all custom plugins working correctly?
3. Is performance acceptable?
4. Does it work across all supported browsers?
5. Are there any visual regressions?

**Sign-off Required:** Technical Lead + QA Lead

---

## Risk Mitigation

**Risk**: Browser compatibility issues
**Mitigation**: Test on Chrome, Firefox, Safari before release

**Risk**: Performance degradation
**Mitigation**: Benchmark, optimize, consider web workers for large posts

**Risk**: MathJax breaks
**Mitigation**: Dedicated tests for MathJax integration

---

## Next Steps After Phase 2

Once Phase 2 gate criteria are met:
1. Deploy to staging with frontend changes
2. Beta test with internal users
3. Collect feedback on preview accuracy
4. Monitor JavaScript errors
5. **Only then** proceed to Phase 3 (Testing & Deployment)

See: [Phase 3: Testing & Deployment](markdown-upgrade-phase3-testing.md)
