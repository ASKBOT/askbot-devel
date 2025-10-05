# Markdown Upgrade Assessment

## Current State

### Python Backend: ✅ Good start
- Transitioning to `markdown-it-py==2.2.0` (should upgrade to 4.0.0)
- Using 'gfm-like' preset (includes tables)
- Missing implementations for video, link patterns, code-friendly mode
- Location: `askbot/utils/markup.py:30-47`

### JavaScript Frontend: ⚠️ **MISMATCH**
- Currently using **Showdown/WMD** (`askbot/media/wmd/Markdown.Converter.js:1-100`)
- This is NOT markdown-it.js - it's the old Showdown library from ~2011
- Will produce **different HTML output** than Python backend
- Location: `askbot/media/wmd/askbot_converter.js:1-67`

## Is markdown-it Still Best? **YES**

According to research (2025):
- ✅ markdown-it-py 4.0.0 (Aug 2025) is actively maintained
- ✅ 100% CommonMark compliant (Showdown is not)
- ✅ Best Python/JS dual support
- ✅ Google Assured OSS program
- ✅ Strong plugin ecosystem (mdit-py-plugins 0.4.2)
- ✅ Used in production by Jupyter, MyST, fpdf2

## Required Features & Plugin Availability

| Feature | Python (markdown-it-py) | JavaScript (markdown-it.js) | Gap? |
|---------|------------------------|----------------------------|------|
| **Tables** | Built-in (gfm-like) | Built-in | ✅ |
| **Code highlighting** | Pygments integration | highlight.js | ✅ |
| **MathJax** | Pass-through (client renders) | Pass-through | ✅ |
| **Custom link patterns** | Custom plugin needed | markdown-it-linkify-it | ⚠️ |
| **Code-friendly mode** | Disable emphasis plugin | Same | ✅ |
| **Video embedding** | **NO PLUGIN** | markdown-it-video | ❌ |
| **Task lists** | mdit-py-plugins | markdown-it-task-lists | ✅ |
| **Footnotes** | mdit-py-plugins | markdown-it-footnote | ✅ |

## Plugins You Need to Write

### 1. Video Embedding Plugin (Python) - **REQUIRED**
- No official port exists
- Port markdown-it-video.js logic to Python
- Support YouTube, Vimeo syntax: `@[youtube](video_id)`
- Alternative: Use MyST Markdown's `{iframe}` directive

### 2. Custom Link Patterns Plugin (Both) - **REQUIRED**
- Implement AUTO_LINK_PATTERNS/AUTO_LINK_URLS settings
- Example: `#bug123` → `https://bugzilla.com/bug/123`
- Python: Custom markdown-it-py plugin
- JS: Extend markdown-it-linkify-it
- Settings: `askbot/conf/markup.py:86-138`

### 3. Code-Friendly Mode - **CONFIGURATION**
- Disable underscore emphasis when `MARKUP_CODE_FRIENDLY=True`
- Both: `md.disable('emphasis')` or selective rule tweaking
- Triggered by: `MARKUP_CODE_FRIENDLY` or `ENABLE_MATHJAX` settings

## Upgrade Strategy

### Phase 1: Foundation (Backend)

**Update dependencies:**
```python
# askbot/__init__.py - Update versions
'markdown_it': 'markdown-it-py==4.0.0',
'mdit_py_plugins': 'mdit-py-plugins==0.4.2',
'linkify_it': 'linkify-it-py==2.0.2',
```

**Update askbot_requirements.txt:**
```
markdown-it-py==4.0.0
mdit-py-plugins==0.4.2
linkify-it-py==2.0.2
```

**Enhanced setup in askbot/utils/markup.py:**
```python
from markdown_it import MarkdownIt
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter

def highlight_code(code, lang, attrs):
    """Code highlighting using Pygments"""
    try:
        lexer = get_lexer_by_name(lang)
        formatter = HtmlFormatter(cssclass='highlight')
        return highlight(code, lexer, formatter)
    except:
        return f'<pre><code class="language-{lang}">{code}</code></pre>'

def get_md_converter():
    """Returns a configured instance of MarkdownIt.
    Converts markdown with extra features:
    * link-patterns
    * video embedding
    * code-friendly - no underscores to italic (if mathjax or code friendly settings are true)
    * urlizing of link-like text - this may need to depend on reputation

    code-friendly hints: https://github.com/markdown-it/markdown-it/issues/404
    """
    md = MarkdownIt('gfm-like')
    md.options['highlight'] = highlight_code

    # Enable standard plugins
    md.use(footnote_plugin)
    md.use(tasklists_plugin)

    # Code-friendly mode - disable underscore emphasis
    if askbot_settings.MARKUP_CODE_FRIENDLY or askbot_settings.ENABLE_MATHJAX:
        md.disable('emphasis')  # Disables _ → <em>

    # TODO: Add custom plugins
    # md.use(video_embed_plugin)
    # md.use(custom_link_patterns_plugin, {
    #     'enabled': askbot_settings.ENABLE_AUTO_LINKING,
    #     'patterns': askbot_settings.AUTO_LINK_PATTERNS,
    #     'urls': askbot_settings.AUTO_LINK_URLS
    # })

    return md
```

### Phase 2: Frontend Migration

**Replace Showdown with markdown-it:**
```javascript
// askbot/media/markdown_it/markdown-it.min.js (from CDN or npm)
// Download from: https://cdn.jsdelivr.net/npm/markdown-it@latest/dist/markdown-it.min.js

// Update askbot/media/wmd/askbot_converter.js
var AskbotMarkdownConverter = function() {
  this._md = window.markdownit('gfm-like')
    .use(window.markdownitFootnote)
    .use(window.markdownitTaskLists)
    .use(window.markdownitVideo) // Video embedding
    .use(window.markdownitCustomLinks, linkPatterns); // Custom patterns

  // Code highlighting
  this._md.options.highlight = function(str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(str, { language: lang }).value;
    }
    return '';
  };

  this._timeout = null;
};

AskbotMarkdownConverter.prototype.makeHtml = function(text) {
  var baseHtml = this._md.render(text);

  if (askbot['settings']['mathjaxEnabled'] === false){
    return baseHtml;
  } else if (typeof MathJax != 'undefined') {
    MathJax.Hub.queue.Push(
      function(){
        $('.wmd-preview').html(baseHtml);
      }
    );
    this.scheduleMathJaxRendering();
    return $('.wmd-preview').html();
  } else {
    console.log('Could not load MathJax');
    return baseHtml;
  }
};
```

**Update template (askbot/jinja2/meta/markdown_javascript.html):**
```html
<script src="https://cdn.jsdelivr.net/npm/markdown-it@latest/dist/markdown-it.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/markdown-it-footnote@latest/dist/markdown-it-footnote.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/markdown-it-task-lists@latest/dist/markdown-it-task-lists.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/markdown-it-video@latest/dist/markdown-it-video.min.js"></script>
<script src="{{ '/wmd/askbot_converter.js'|media }}"></script>
<script src="{{ '/js/utils/expander_toggle.js'|media }}"></script>
<script src="{{ '/js/editors/wmd_expander_toggle.js'|media }}"></script>
<script src="{{ '/js/editors/simple_editor.js'|media }}"></script>
<script src="{{ '/js/editors/wmd.js'|media }}"></script>
<script src="{{ '/wmd/wmd.js'|media }}"></script>
```

### Phase 3: Write Custom Plugins

#### Video Plugin (Python)

Create: `askbot/utils/markdown_plugins/video_embed.py`

```python
"""
Port of markdown-it-video for Python
Supports: @[youtube](video_id), @[vimeo](video_id)
"""
import re

def video_embed_plugin(md):
    """
    Plugin to embed videos from YouTube, Vimeo, etc.
    Syntax: @[youtube](video_id) or @[vimeo](video_id)
    """

    VIDEO_SERVICES = {
        'youtube': 'https://www.youtube.com/embed/{0}',
        'vimeo': 'https://player.vimeo.com/video/{0}',
    }

    def video_rule(state, silent):
        """Parse video embed syntax"""
        pos = state.pos
        maximum = state.posMax

        # Check for @[
        if state.src[pos:pos+2] != '@[':
            return False

        # Find service name
        service_end = state.src.find(']', pos + 2)
        if service_end == -1:
            return False

        service = state.src[pos+2:service_end]
        if service not in VIDEO_SERVICES:
            return False

        # Find video ID in (...)
        if state.src[service_end+1:service_end+2] != '(':
            return False

        id_end = state.src.find(')', service_end + 2)
        if id_end == -1:
            return False

        video_id = state.src[service_end+2:id_end]

        if not silent:
            token = state.push('video_embed', '', 0)
            token.meta = {'service': service, 'id': video_id}

        state.pos = id_end + 1
        return True

    def render_video(tokens, idx, options, env, renderer):
        """Render video iframe"""
        token = tokens[idx]
        service = token.meta['service']
        video_id = token.meta['id']

        url = VIDEO_SERVICES[service].format(video_id)

        return (
            f'<iframe width="640" height="360" '
            f'src="{url}" '
            f'frameborder="0" allowfullscreen></iframe>'
        )

    md.inline.ruler.before('link', 'video_embed', video_rule)
    md.renderer.rules['video_embed'] = render_video

    return md
```

#### Link Patterns Plugin (Python)

Create: `askbot/utils/markdown_plugins/link_patterns.py`

```python
"""
Custom auto-linking for askbot patterns
Implements AUTO_LINK_PATTERNS and AUTO_LINK_URLS settings
"""
import re

def link_patterns_plugin(md, config):
    """
    Plugin to auto-link custom patterns

    Args:
        config: dict with keys:
            - enabled: bool
            - patterns: str (newline-separated regexes)
            - urls: str (newline-separated URL templates)
    """
    if not config.get('enabled', False):
        return md

    patterns_str = config.get('patterns', '').strip()
    urls_str = config.get('urls', '').strip()

    if not patterns_str or not urls_str:
        return md

    pattern_list = patterns_str.split('\n')
    url_list = urls_str.split('\n')

    if len(pattern_list) != len(url_list):
        # Validation failed, skip
        return md

    # Compile patterns
    rules = []
    for pattern_str, url_template in zip(pattern_list, url_list):
        pattern_str = pattern_str.strip()
        url_template = url_template.strip()
        if pattern_str and url_template:
            try:
                pattern = re.compile(pattern_str)
                rules.append((pattern, url_template))
            except re.error:
                continue

    def link_replace(state):
        """Replace text tokens matching patterns with links"""
        for idx, token in enumerate(state.tokens):
            if token.type != 'inline':
                continue

            for child_idx, child in enumerate(token.children or []):
                if child.type != 'text':
                    continue

                text = child.content
                new_children = []
                last_end = 0

                for pattern, url_template in rules:
                    for match in pattern.finditer(text):
                        # Add text before match
                        if match.start() > last_end:
                            text_token = state.Token('text', '', 0)
                            text_token.content = text[last_end:match.start()]
                            new_children.append(text_token)

                        # Create link
                        link_open = state.Token('link_open', 'a', 1)
                        link_open.attrs = {'href': url_template.replace('\\1', match.group(1))}
                        new_children.append(link_open)

                        text_token = state.Token('text', '', 0)
                        text_token.content = match.group(0)
                        new_children.append(text_token)

                        link_close = state.Token('link_close', 'a', -1)
                        new_children.append(link_close)

                        last_end = match.end()

                # Add remaining text
                if last_end < len(text):
                    text_token = state.Token('text', '', 0)
                    text_token.content = text[last_end:]
                    new_children.append(text_token)

                # Replace children if we made changes
                if new_children:
                    token.children[child_idx:child_idx+1] = new_children

    md.core.ruler.after('linkify', 'custom_patterns', link_replace)
    return md
```

#### Integration in markup.py

Update `askbot/utils/markup.py:30-47`:

```python
from askbot.utils.markdown_plugins.video_embed import video_embed_plugin
from askbot.utils.markdown_plugins.link_patterns import link_patterns_plugin

def get_md_converter():
    """Returns a configured instance of MarkdownIt."""
    md = MarkdownIt('gfm-like')
    md.options['highlight'] = highlight_code

    # Enable standard plugins
    md.use(footnote_plugin)
    md.use(tasklists_plugin)

    # Code-friendly mode
    if askbot_settings.MARKUP_CODE_FRIENDLY or askbot_settings.ENABLE_MATHJAX:
        md.disable('emphasis')

    # Video embedding
    md.use(video_embed_plugin)

    # Custom link patterns
    md.use(link_patterns_plugin, {
        'enabled': askbot_settings.ENABLE_AUTO_LINKING,
        'patterns': askbot_settings.AUTO_LINK_PATTERNS,
        'urls': askbot_settings.AUTO_LINK_URLS
    })

    return md
```

## Alternative: Use MyST Markdown

If writing custom plugins seems too complex, consider **MyST Markdown**:

### Pros:
- Built on markdown-it-py
- Has Python AND JavaScript implementations
- Native video embedding: `{iframe} https://youtube.com/embed/ID`
- Extensible directive system
- Used in Jupyter Book ecosystem
- More powerful than plain markdown-it

### Cons:
- Different syntax for advanced features (directives)
- May confuse users familiar with standard markdown
- Heavier dependency

### Example:
```markdown
# Standard markdown still works

## Video embedding
{iframe} https://www.youtube.com/embed/VIDEO_ID
:width: 640

Video caption here
```

## Migration Risks

1. **Breaking changes** - HTML output will differ from markdown2/Showdown
2. **Testing burden** - Need to verify all existing content renders correctly
3. **Custom extensions** - markdown2 extras won't directly port
4. **User disruption** - Preview and saved HTML may differ

## Recommended Approach

### Conservative (Recommended):

1. ✅ Upgrade Python to markdown-it-py 4.0.0 + mdit-py-plugins
2. ✅ Keep Showdown on frontend temporarily
3. ✅ Write Python video + link patterns plugins
4. ✅ Test with existing content using management command
5. ✅ Create migration script to test all posts
6. ⏳ Migrate frontend to markdown-it.js in phase 2
7. ⏳ Write JS equivalents of custom plugins
8. ⏳ Run side-by-side comparison testing
9. ⏳ Deploy when output matches 99%+

### Aggressive:

1. Switch both Python + JS to markdown-it simultaneously
2. Accept breaking changes in HTML output
3. Run migration script on all existing posts
4. Write custom plugins for both platforms at once
5. Deploy immediately

**Recommendation:** Use **conservative approach** given you have production content. Test thoroughly in `askbot/utils/markup.py:186-191` before touching the frontend.

## Testing Strategy

1. **Unit tests** for custom plugins
2. **Integration tests** for markdown converter
3. **Migration script** to test rendering of all existing posts
4. **Visual comparison** of old vs new HTML output
5. **User acceptance testing** with preview pane

## Files to Update

### Phase 1 (Backend):
- [ ] `askbot/__init__.py` - Update dependencies
- [ ] `askbot_requirements.txt` - Update requirements
- [ ] `askbot/utils/markup.py` - Enhanced converter setup
- [ ] `askbot/utils/markdown_plugins/video_embed.py` - New plugin
- [ ] `askbot/utils/markdown_plugins/link_patterns.py` - New plugin
- [ ] `askbot/tests/test_markup.py` - Add tests for plugins

### Phase 2 (Frontend):
- [ ] `askbot/jinja2/meta/markdown_javascript.html` - Update script includes
- [ ] `askbot/media/wmd/askbot_converter.js` - Rewrite for markdown-it
- [ ] `askbot/media/markdown_it/` - Add markdown-it.js libraries
- [ ] Download and vendor markdown-it plugins

### Phase 3 (Testing):
- [ ] Create migration test script
- [ ] Test all existing posts
- [ ] Visual regression testing
- [ ] Update user documentation

## References

- markdown-it-py: https://github.com/executablebooks/markdown-it-py
- mdit-py-plugins: https://github.com/executablebooks/mdit-py-plugins
- markdown-it.js: https://github.com/markdown-it/markdown-it
- MyST Markdown: https://mystmd.org/
- CommonMark Spec: https://spec.commonmark.org/
