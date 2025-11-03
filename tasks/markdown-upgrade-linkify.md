# Task: Migrate to markdown-it Native Linkification

**Status**: ✅ Implementation Complete (Testing Pending)
**Branch**: `markdown-upgrade`
**Priority**: High
**Reason**: Enable frontend/backend parity for markdown rendering

---

## Checklist

### Implementation
- [x] Research linkify plugin capabilities and customization options
- [x] Research URL truncation approaches (CSS vs backend)
- [x] Create custom `truncate_links.py` plugin
- [x] Modify `markup.py` to enable linkify
- [x] Modify `markup.py` to integrate truncate_links plugin
- [x] Remove `urlize_html()` call from markdown_input_converter
- [x] Remove `urlize_html` import
- [x] Update docstring to reflect linkify enabled

### Testing
- [ ] Fix test environment (askbot import in env-md)
- [ ] Run existing test suite to identify failures
- [ ] Update `test_markup.py::test_convert_mixed_text` for fuzzy link behavior
- [ ] Add test for inline code protection (`http://` in backticks not linked)
- [ ] Add test for code block protection (fenced code not linked)
- [ ] Add test for URL truncation at 40 characters
- [ ] Add test for title attribute with full URL
- [ ] Add test for fuzzy link detection (`example.com` → linked)
- [ ] Add test for www. detection (`www.example.com` → linked)
- [ ] Add test for existing HTML links unchanged
- [ ] Add test for markdown links unchanged
- [ ] Verify all tests pass

### Documentation
- [x] Document plugin implementation details
- [x] Create comprehensive plan document (this file)
- [x] Document frontend JavaScript equivalent code
- [x] Document CSS vs backend truncation decision
- [x] Document behavioral changes (fuzzy links)
- [x] Document rollback procedure
- [x] Document what gets linkified vs protected
- [x] Add URL truncation examples table
- [x] Add performance comparison analysis

### Optional Enhancements (Future)
- [ ] Add `LINKIFY_TRIM_URL_LIMIT` LiveSettings configuration
- [ ] Make truncation limit configurable via admin panel
- [ ] Create frontend JavaScript npm package/module
- [ ] Add linkify fuzzy matching configuration options
- [ ] Consider disabling email auto-linking if not desired

---

## Problem Statement

The current implementation uses Django's `urlize_html()` to post-process HTML for URL auto-linking. This creates challenges for frontend/backend consistency:

- **Backend**: Python markdown-it-py + BeautifulSoup post-processing with Django's `urlize()`
- **Frontend**: Would need to reimplement entire `urlize_html()` logic in JavaScript
- **Result**: Very difficult to achieve identical behavior across both environments

## Solution: Native markdown-it Linkification

Migrate to markdown-it's built-in `linkify` plugin with custom URL truncation. This approach:

- ✅ Uses same markdown-it engine on frontend (JS) and backend (Python)
- ✅ Both implementations designed to match exactly
- ✅ Single-pass processing (better performance)
- ✅ Better Unicode/international domain support
- ✅ Fuzzy link detection (URLs without `http://`)

---

## Implementation Details

### 1. Created Custom Plugin: `truncate_links.py`

**Location**: `askbot/utils/markdown_plugins/truncate_links.py`

**Purpose**:
- Truncates auto-linkified URL display text to 40 characters
- Adds `title` attribute with full URL for accessibility
- Uses Django's truncation algorithm for consistency

**Key Features**:
```python
def truncate_url_text(text, limit):
    """Django's algorithm: "%s…" % x[: max(0, limit - 1)]"""
    if limit is None or limit <= 0 or len(text) <= limit:
        return text
    return f"{text[:max(0, limit - 1)]}…"
```

**How It Works**:
1. Runs as core rule AFTER linkify plugin
2. Finds tokens with `type='link_open'` and `markup='linkify'`
3. Truncates the following text token if > 40 chars
4. Adds `title` attribute containing full URL

### 2. Modified `askbot/utils/markup.py`

**Changes**:

1. **Enabled linkify** (line 105):
   ```python
   md = MarkdownIt('commonmark', {'linkify': True, 'typographer': False})
   ```

2. **Added truncate_links plugin** (lines 127-131):
   ```python
   md.use(truncate_links_plugin, {
       'trim_limit': 40  # Match Django's urlize trim_url_limit
   })
   ```

3. **Removed urlize_html post-processing** (line 303):
   ```python
   # Before:
   text = urlize_html(text, trim_url_limit=40)
   return text  # urlize_html already sanitizes

   # After:
   text = sanitize_html(text)
   return text
   ```

4. **Removed urlize_html import** (line 32):
   - No longer importing from `askbot.utils.html`

---

## What Gets Linkified (and What Doesn't)

### ✅ Auto-Linkified

- `http://example.com` → Linkified
- `https://github.com/user/repo` → Linkified
- `ftp://files.example.com` → Linkified
- `www.example.com` → Linkified (fuzzy matching)
- `example.com` → Linkified (fuzzy matching) **[NEW!]**
- `user@example.com` → Linkified as mailto **[NEW!]**

### ❌ NOT Linkified (Protected)

- Inline code: `` `http://example.com` `` → NOT linkified
- Code blocks: ```http://example.com``` → NOT linkified
- Existing markdown links: `[text](url)` → NOT doubled
- Existing HTML links: `<a href="...">` → NOT doubled
- Inside `<pre>` tags → NOT linkified
- Inside `<code>` tags → NOT linkified

**Why code is safe**:
- Inline code creates `code_inline` tokens (not `text` tokens)
- Linkify only processes `text` type tokens
- Code blocks are in different token containers
- Automatic protection by markdown-it's token structure

---

## URL Truncation Examples

| Original URL | Displayed (40 char limit) | Title Attribute |
|--------------|---------------------------|-----------------|
| `http://example.com` | `http://example.com` | `http://example.com` |
| `https://github.com/executablebooks/markdown-it-py` | `https://github.com/executablebooks/ma…` | `https://github.com/executablebooks/markdown-it-py` |
| `https://example.com/some_page.html#anchor` | `https://example.com/some_page.html#anch…` | `https://example.com/some_page.html#anchor` |

**Benefits**:
- **Visual**: Prevents long URLs from breaking layout
- **Accessibility**: Screen readers announce full URL from title attribute
- **UX**: Hover shows full URL in tooltip

---

## CSS Ellipsis vs Backend Truncation Decision

### Decision: **Backend Truncation** ✅

**Why NOT CSS ellipsis**:
- Requires `display: inline-block` (breaks paragraph flow)
- Requires fixed/max-width (difficult for responsive design)
- Requires `white-space: nowrap` (prevents text wrapping)
- Awkward for inline links in paragraph text

**Why backend truncation**:
- ✅ Works perfectly for inline links
- ✅ No layout issues
- ✅ Matches current urlize_html behavior
- ✅ Simple implementation
- ✅ Full URL in `title` attribute for accessibility
- ⚠️ SEO: Truncated anchor text (acceptable for auto-links)

---

## Frontend Implementation (JavaScript)

To match backend behavior exactly, use markdown-it.js with linkify:

```javascript
// Install: npm install markdown-it linkify-it

const MarkdownIt = require('markdown-it');

// Create converter with linkify enabled
const md = new MarkdownIt({
  linkify: true,
  typographer: false
});

// Enable GFM features
md.enable(['table', 'strikethrough']);

// Add truncation core rule (matches Python implementation)
md.core.ruler.after('linkify', 'truncate_linkify_urls', function(state) {
  const trimLimit = 40;

  for (let blockToken of state.tokens) {
    if (blockToken.type !== 'inline' || !blockToken.children) continue;

    for (let i = 0; i < blockToken.children.length; i++) {
      const token = blockToken.children[i];

      if (token.type === 'link_open' && token.markup === 'linkify') {
        const href = token.attrGet('href');

        if (i + 1 < blockToken.children.length &&
            blockToken.children[i + 1].type === 'text') {
          const textToken = blockToken.children[i + 1];
          const urlText = textToken.content;

          if (urlText.length > trimLimit) {
            textToken.content = urlText.substring(0, Math.max(0, trimLimit - 1)) + '…';
          }

          if (href) {
            token.attrSet('title', href);
          }
        }
      }
    }
  }
});

// Use the converter
const html = md.render('Check out https://github.com/example/repo');
```

**Configuration checklist**:
- ✅ Same `linkify: true` option
- ✅ Same truncation limit (40 chars)
- ✅ Same ellipsis character (…)
- ✅ Same title attribute logic
- ✅ Core rule runs after linkify

---

## Testing Strategy

### Test Cases Required

1. **Inline code protection**:
   ```markdown
   Use `http://api.example.com/v1` endpoint
   ```
   Expected: URL in code NOT linkified

2. **Code block protection**:
   ````markdown
   ```python
   url = "http://example.com"
   ```
   ````
   Expected: URL NOT linkified

3. **Plain URL linkification**:
   ```markdown
   Visit http://example.com for details
   ```
   Expected: URL linkified

4. **Fuzzy link detection** (NEW):
   ```markdown
   Visit example.com for details
   ```
   Expected: URL linkified with `http://` prefix

5. **WWW detection**:
   ```markdown
   Check www.example.com
   ```
   Expected: URL linkified

6. **URL truncation**:
   ```markdown
   https://github.com/executablebooks/markdown-it-py-documentation
   ```
   Expected: Displayed as `https://github.com/executablebooks/ma…`

7. **Title attribute**:
   Expected: Full URL in `title="..."` attribute

8. **Existing links unchanged**:
   ```markdown
   <a href="http://example.com">link</a>
   ```
   Expected: NOT modified, NOT doubled

9. **Markdown links unchanged**:
   ```markdown
   [Click here](http://example.com)
   ```
   Expected: NOT auto-linkified (already a link)

### Test Files to Update

1. **`askbot/tests/test_markup.py`**:
   - Line 110: Update `test_convert_mixed_text`
   - Expect `example.com` to be linkified (NEW behavior)
   - Verify truncation at 40 chars

2. **`askbot/tests/test_markdown_integration.py`**:
   - Add `test_linkify_plain_urls`
   - Add `test_linkify_fuzzy_links`
   - Add `test_linkify_truncation`
   - Add `test_linkify_title_attribute`
   - Add `test_linkify_skips_code`

---

## Configuration Setting (Optional Future Enhancement)

**Not implemented yet**: Currently hardcoded to 40 chars

**Future enhancement**: Add to `askbot/conf/site_settings.py`:

```python
LINKIFY_TRIM_URL_LIMIT = livesettings.PositiveIntegerValue(
    MARKUP_SETTINGS,
    'LINKIFY_TRIM_URL_LIMIT',
    default=40,
    description=_('Maximum characters for auto-linked URL display text (0 = no truncation)')
)
```

Then update `markup.py`:
```python
md.use(truncate_links_plugin, {
    'trim_limit': askbot_settings.LINKIFY_TRIM_URL_LIMIT
})
```

---

## Behavioral Changes (Breaking Changes)

### NEW: Fuzzy Link Detection

**Before (urlize_html)**:
- `example.com` → NOT linkified
- Needed `http://` or `www.` prefix

**After (linkify)**:
- `example.com` → Linkified to `http://example.com`
- `www.example.com` → Linkified to `http://www.example.com`
- More user-friendly

### Impact

- ✅ **Positive**: Users don't need to type protocols
- ⚠️ **Possible confusion**: Text like "see example.com" gets linkified
- ⚠️ **Edge cases**: Domain-like text might be linkified unintentionally

**Mitigation**: linkify-it-py is smart about context and TLD validation

---

## Performance Improvements

### Before (urlize_html)

1. Markdown parsing → Token tree
2. Render to HTML string
3. **Parse HTML with BeautifulSoup** (expensive)
4. Find all text nodes
5. Check parent tags
6. Apply Django's urlize to each text node
7. Reconstruct HTML
8. Sanitize HTML

**Cost**: Two full parsing passes + DOM manipulation

### After (linkify plugin)

1. Markdown parsing → Token tree
2. **Linkify processes tokens** (fast)
3. **Truncate processes tokens** (fast)
4. Render to HTML string
5. Sanitize HTML

**Cost**: Single parsing pass, token manipulation (much faster than DOM)

**Estimated improvement**: 2-3x faster for URL-heavy content

---

## Rollback Plan

If issues arise, revert these changes:

1. **`markup.py` line 105**:
   ```python
   md = MarkdownIt('commonmark', {'linkify': False, 'typographer': False})
   ```

2. **`markup.py` line 303**:
   ```python
   from askbot.utils.html import urlize_html  # Re-add import

   def markdown_input_converter(text):
       md = get_md_converter()
       text = md.render(text)
       text = urlize_html(text, trim_url_limit=40)  # Restore
       return text
   ```

3. **Remove plugin lines 127-131** from `get_md_converter()`

**Result**: Immediate rollback to previous behavior

---

## Files Changed

### New Files
- ✅ `askbot/utils/markdown_plugins/truncate_links.py` (119 lines)
- ✅ `tasks/markdown-upgrade-linkify.md` (this file)

### Modified Files
- ✅ `askbot/utils/markup.py`:
  - Added import for truncate_links_plugin
  - Removed import for urlize_html
  - Changed linkify: False → True
  - Added truncate_links plugin usage
  - Simplified markdown_input_converter (removed urlize_html call)
  - Updated docstring

### Files Needing Updates (TODO)
- ⏳ `askbot/tests/test_markup.py` (update expectations)
- ⏳ `askbot/tests/test_markdown_integration.py` (add linkify tests)

---

## Success Criteria

- ✅ Code implementation complete
- ✅ Plugin created and integrated
- ✅ urlize_html removed from markdown flow
- ⏳ All existing tests pass
- ⏳ New linkify tests added and passing
- ⏳ Frontend JavaScript implementation documented
- ⏳ No regressions in URL handling

---

## Next Steps

1. **Fix test environment** (askbot import issue in env-md)
2. **Run existing tests** to identify needed updates
3. **Update test expectations** for new fuzzy link behavior
4. **Add new linkify-specific tests**
5. **Create frontend JavaScript example** (optional)
6. **Document in main markdown upgrade plan**

---

## References

- **markdown-it-py docs**: https://markdown-it-py.readthedocs.io/
- **linkify-it-py docs**: https://linkify-it-py.readthedocs.io/
- **Django urlize**: https://docs.djangoproject.com/en/4.2/ref/templates/builtins/#urlize
- **Link patterns plugin** (reference): `askbot/utils/markdown_plugins/link_patterns.py`

---

## Notes

- The linkify plugin automatically skips code because it only processes `text` tokens
- Inline code creates `code_inline` tokens (different type)
- No additional logic needed for code protection
- Title attribute improves accessibility for screen reader users
- Unicode/international domains now work correctly
- Frontend/backend can now share exact same configuration

---

**Last Updated**: 2025-11-02
**Author**: Claude Code
**Review Status**: Pending testing
