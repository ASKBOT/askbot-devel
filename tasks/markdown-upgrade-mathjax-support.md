# Task: Implement Proper MathJax Delimiter Protection

**Status**: 📝 Planning Complete (Implementation Pending)
**Branch**: `markdown-upgrade`
**Priority**: High
**Reason**: Current implementation is incomplete; linkify and link_patterns could interfere with math content

---

## Problem Statement

### Current Implementation is Incomplete

The current MathJax support in `askbot/utils/markup.py` is a crude workaround:

**Lines 136-151:**
```python
# Code-friendly mode: disable underscore emphasis for MathJax compatibility
if askbot_settings.MARKUP_CODE_FRIENDLY or askbot_settings.ENABLE_MATHJAX:
    md.disable('emphasis')
    # TODO: Add custom rule to re-enable * only if needed  (Line 142)

# Math delimiter protection for MathJax support
if askbot_settings.ENABLE_MATHJAX:
    # TODO: Implement math delimiter protection plugin  (Line 150)
    pass  # ← NOTHING IMPLEMENTED!
```

**What it does:** Disables ALL emphasis processing (`*` and `_`)
**What it doesn't do:** Actually protect math delimiters from markdown processing

### Critical Issues

1. **No Actual Protection**: Math delimiters (`$...$`, `$$...$$`) are NOT recognized as special
2. **Linkify Can Interfere**: `$x = y.com$` might be auto-linkified because linkify runs without math awareness
3. **Link Patterns Can Interfere**: `$bug123$` might be converted to link if pattern is `bug\d+`
4. **Over-Disabled Emphasis**: Users cannot use `**bold**` or `*italic*` in documents with math
5. **Wrong Plugin Order**: Linkify and link_patterns run BEFORE (non-existent) math protection

### Design Requirement

**User's mandate:** "Inside mathjax delimiters when mathjax is enabled, there should be NO markdown processing at all!!!"

This means:
- Math content must be treated as **verbatim/literal text**
- NO linkification inside math
- NO pattern matching inside math
- NO emphasis processing inside math
- NO any markdown rules inside math

---

## Solution: Math Protection Plugin

Create a dedicated `math_protect.py` plugin that:
1. Detects math delimiters FIRST (before any other inline processing)
2. Creates special tokens that preserve content verbatim
3. Renders math content unchanged (with delimiters intact)
4. Prevents other plugins from processing math content

---

## Checklist

### Implementation
- [ ] Create `askbot/utils/markdown_plugins/math_protect.py`
- [ ] Implement inline rule to detect `$...$` delimiters
- [ ] Implement block rule to detect `$$...$$` on separate lines
- [ ] Create `math_inline` and `math_block` token types
- [ ] Implement render functions (output raw content with delimiters)
- [ ] Integrate plugin into `markup.py` (register FIRST)
- [ ] Fix plugin ordering (math_protect before everything)
- [ ] Re-enable asterisk emphasis (after math is protected)
- [ ] Update docstrings

### Testing
- [ ] Add test for inline math with URLs: `$x = http://example.com$`
- [ ] Add test for inline math with patterns: `$bug123$`
- [ ] Add test for display math blocks
- [ ] Add test for multiple math expressions
- [ ] Add test for escaped delimiters: `\$100`
- [ ] Add test for single dollar signs: "I paid $100"
- [ ] Add test for mismatched delimiters
- [ ] Add test for * emphasis working with math
- [ ] Add test for _ remaining disabled in math
- [ ] Verify existing mathjax tests still pass
- [ ] Add integration tests for math + linkify
- [ ] Add integration tests for math + link_patterns

### Documentation
- [ ] Document plugin implementation
- [ ] Document token structure
- [ ] Document edge case handling
- [ ] Update markup.py docstring
- [ ] Create frontend JavaScript equivalent guide
- [ ] Document delimiter syntax

---

## Technical Design

### Plugin Structure

**File:** `askbot/utils/markdown_plugins/math_protect.py`

```python
"""
MathJax delimiter protection plugin for markdown-it-py.

Treats content inside $...$ (inline) and $$...$$ (display) as verbatim text
to prevent any markdown processing of mathematical expressions.

This plugin MUST run before all other inline rules to properly protect
math content from linkification, pattern matching, and emphasis processing.
"""

from markdown_it import MarkdownIt
from markdown_it.rules_inline import StateInline

def math_inline_rule(state: StateInline, silent: bool) -> bool:
    """
    Detect inline math delimiters: $...$

    Creates math_inline tokens that preserve content verbatim.
    """
    # Implementation here

def math_block_rule(state: StateBlock, startLine: int, endLine: int, silent: bool) -> bool:
    """
    Detect display math delimiters: $$...$$

    Creates math_block tokens for display equations.
    """
    # Implementation here

def render_math_inline(self, tokens, idx, options, env, renderer):
    """Render inline math with delimiters."""
    return f"${tokens[idx].content}$"

def render_math_block(self, tokens, idx, options, env, renderer):
    """Render display math with delimiters."""
    return f"$${tokens[idx].content}$$\n"

def math_protect_plugin(md: MarkdownIt) -> MarkdownIt:
    """
    Plugin to protect MathJax delimiters from markdown processing.

    Must be registered BEFORE other inline rules.
    """
    # Register inline rule FIRST
    md.inline.ruler.before('escape', 'math_inline', math_inline_rule)

    # Register block rule FIRST
    md.block.ruler.before('code', 'math_block', math_block_rule)

    # Register renderers
    md.add_render_rule('math_inline', render_math_inline)
    md.add_render_rule('math_block', render_math_block)

    return md
```

### Token Structure

**Inline Math Token:**
```python
Token(
    type='math_inline',
    tag='',
    content='E = mc^2',      # Raw LaTeX without delimiters
    markup='$',              # Delimiter character
    block=False,
    nesting=0
)
```

**Display Math Token:**
```python
Token(
    type='math_block',
    tag='',
    content='\\int_0^1 x dx = \\frac{1}{2}',  # Raw LaTeX
    markup='$$',             # Delimiter
    block=True,
    nesting=0
)
```

### Delimiter Detection Algorithm

**Inline Math (`$...$`):**

1. Must start with `$` not preceded by `\` (escape)
2. Must not be immediately followed by space (avoid false positives like "I paid $100")
3. Must have closing `$` before line end
4. Closing `$` must not be preceded by `\`
5. Content between delimiters becomes `math_inline` token

**Display Math (`$$...$$`):**

1. Must start on its own line or with `$$` at start of line
2. Can span multiple lines
3. Closes with `$$`
4. Content between delimiters becomes `math_block` token

**Edge Cases:**
- Single `$` in text: "I paid $100" → NOT math (no closing delimiter on same line)
- Escaped delimiter: `\$100` → Literal "$100", not math
- Adjacent dollars: `$$x$$` → Display math, not two inline maths
- Mismatched: `$x` without closing → NOT math, remains literal

---

## Integration into markup.py

### Before (Lines 103-151):

```python
def get_md_converter():
    # ...
    md = MarkdownIt('commonmark', {'linkify': True, 'typographer': False})
    md.enable(['table', 'strikethrough'])
    md.enable('linkify')

    # ... other plugins ...

    md.use(video_embed_plugin, {...})
    md.use(link_patterns_plugin, {...})
    md.use(truncate_links_plugin, {...})

    # Crude workaround: just disable emphasis
    if askbot_settings.MARKUP_CODE_FRIENDLY or askbot_settings.ENABLE_MATHJAX:
        md.disable('emphasis')
        # TODO: Add custom rule to re-enable * only if needed

    # TODO: Implement math delimiter protection plugin
    if askbot_settings.ENABLE_MATHJAX:
        pass

    return md
```

### After (Proposed):

```python
def get_md_converter():
    # ...
    md = MarkdownIt('commonmark', {'linkify': True, 'typographer': False})
    md.enable(['table', 'strikethrough'])
    md.enable('linkify')

    # 1. FIRST: Protect math delimiters if MathJax is enabled
    #    Must run BEFORE all other inline/block rules
    if askbot_settings.ENABLE_MATHJAX:
        md.use(math_protect_plugin)

    # 2. Configure syntax highlighting
    md.options['highlight'] = highlight_code

    # 3. Enable plugins (they will skip math tokens)
    md.use(footnote_plugin)
    md.use(tasklists_plugin)
    md.use(video_embed_plugin, {...})
    md.use(link_patterns_plugin, {...})
    md.use(truncate_links_plugin, {...})

    # 4. Re-enable emphasis for asterisks only
    #    Math protection prevents _ from affecting math content
    if askbot_settings.MARKUP_CODE_FRIENDLY:
        # Code-friendly: disable underscore emphasis only
        md.disable('emphasis')
        md.inline.ruler.enable(['emphasis_with_asterisks_only'])  # TODO: implement
    # Note: If MathJax is enabled, underscore emphasis is already safe
    # because math content is protected as verbatim tokens

    return md
```

### Key Changes:

1. **Math protection added FIRST** (line ~103)
2. **Moved before other plugins** to protect math from linkify, patterns, etc.
3. **Simplified emphasis handling** - math is protected, so can be more lenient
4. **Removed crude "disable emphasis" workaround**

---

## Correct Plugin Ordering

### Current Order (Incorrect):

```
1. Create MarkdownIt (linkify: True)
2. Enable table, strikethrough, linkify
3. video_embed_plugin
4. link_patterns_plugin
5. truncate_links_plugin
6. Disable emphasis entirely (crude workaround)
7. (NO math protection)
```

**Problem:** Linkify and patterns run WITHOUT math awareness

### Correct Order (Proposed):

```
1. Create MarkdownIt (linkify: True)
2. Enable table, strikethrough, linkify
3. *** math_protect_plugin (FIRST - if ENABLE_MATHJAX) ***
4. video_embed_plugin
5. link_patterns_plugin
6. truncate_links_plugin
7. (Emphasis stays enabled or only _ disabled)
```

**Why This Order:**

- **Math protection FIRST** ensures math delimiters are converted to special tokens
- **Other plugins** see `math_inline`/`math_block` tokens, not raw text with `$`
- **Linkify** skips math tokens (they're not text type)
- **Patterns** skip math tokens (they're not text type)
- **Emphasis** can safely run because math content is already protected

---

## How Math Protection Prevents Interference

### Example 1: Math with URL-like Content

**Input:**
```markdown
The formula $x = y.com$ is interesting.
```

**Without math protection:**
1. Linkify sees: "The formula $x = y.com$ is interesting."
2. Linkify detects "y.com" as URL
3. Creates link: `The formula $x = <a href="http://y.com">y.com</a>$ is interesting.`
4. **BROKEN MATH!**

**With math protection:**
1. Math plugin sees: "The formula $x = y.com$ is interesting."
2. Creates tokens: `text("The formula ")` + `math_inline("x = y.com")` + `text(" is interesting.")`
3. Linkify sees: `text` + `math_inline` + `text` tokens
4. Linkify only processes `text` tokens, skips `math_inline`
5. Renders: `The formula $x = y.com$ is interesting.`
6. **MATH INTACT!**

### Example 2: Math with Link Patterns

**Setup:** Link pattern `bug\d+` → `https://bugs.example.com/bug{id}`

**Input:**
```markdown
The equation $bug123 = x$ should not be linked.
```

**Without math protection:**
1. Link patterns plugin sees: "The equation $bug123 = x$ should not be linked."
2. Detects "bug123" pattern match
3. Creates link: `The equation $<a href="...">bug123</a> = x$ should not be linked.`
4. **BROKEN MATH!**

**With math protection:**
1. Math plugin creates: `text("The equation ")` + `math_inline("bug123 = x")` + `text(" should not be linked.")`
2. Link patterns plugin only processes `text` tokens
3. Skips `math_inline` token
4. Renders: `The equation $bug123 = x$ should not be linked.`
5. **MATH INTACT!**

### Example 3: Emphasis in Math

**Input:**
```markdown
The formula $a_b * c_d$ uses underscores and asterisk.
```

**Without math protection:**
1. Emphasis rule sees: "$a_b * c_d$"
2. Converts: `$a<em>b * c</em>d$`
3. **BROKEN MATH!**

**With math protection:**
1. Math plugin creates: `math_inline("a_b * c_d")` token
2. Emphasis rule only processes `text` tokens
3. Skips `math_inline` token
4. Renders: `$a_b * c_d$`
5. **MATH INTACT!**

---

## Edge Cases & Handling

### 1. Dollar Signs in Regular Text

**Case:** "I paid $100 and got $200 back"

**Handling:**
- Math rule requires closing `$` on same line
- Also checks that `$` is not followed by space
- Single `$` followed by space = literal dollar sign
- Result: Treated as literal text, not math

**Alternative approach:** Be stricter, require no space after opening `$` and no space before closing `$`

### 2. Escaped Delimiters

**Case:** "The price is \$100"

**Handling:**
- Math rule checks for `\` before `$`
- If found, skip (let escape rule handle it)
- Result: Renders as literal "$100"

### 3. Display Math on Separate Lines

**Case:**
```markdown
Here is a formula:

$$
\int_0^1 x dx = \frac{1}{2}
$$

That was interesting.
```

**Handling:**
- Block rule detects `$$` at start of line
- Captures content until closing `$$`
- Creates `math_block` token
- Renders with delimiters intact

### 4. Nested or Adjacent Delimiters

**Case:** `$$x$$` (should be display math, not two inline)

**Handling:**
- Block rule has priority over inline rule
- Checks for `$$` first
- If detected, creates block token
- Inline rule doesn't run

### 5. Mismatched Delimiters

**Case:** "The formula $x is incomplete"

**Handling:**
- Math rule requires closing delimiter
- If not found before line end, returns false
- Content remains as literal text with `$`

### 6. Math in Code Blocks

**Case:**
````markdown
```python
price = $100
```
````

**Handling:**
- Code blocks are processed at block level before inline rules
- Math inline rule only runs on text outside code blocks
- No interference

### 7. Math in HTML Blocks

**Case:**
```html
<div>$x = y$</div>
```

**Handling:**
- HTML blocks are treated as opaque
- Inline rules don't process content inside HTML
- Math rule doesn't interfere

---

## Testing Strategy

### Unit Tests (new file: `test_markdown_math_plugin.py`)

**Test Class:** `TestMathProtectPlugin`

1. **`test_inline_math_basic()`**
   - Input: `$E = mc^2$`
   - Expected: `<p>$E = mc^2$</p>`

2. **`test_display_math_block()`**
   - Input: `$$\int_0^1 x dx$$` on separate lines
   - Expected: Display math preserved

3. **`test_math_with_url()`** ⭐ Critical
   - Input: `$x = http://example.com$`
   - Expected: NO linkification inside math

4. **`test_math_with_www()`** ⭐ Critical
   - Input: `$y = www.example.com$`
   - Expected: NO linkification inside math

5. **`test_math_with_fuzzy_link()`** ⭐ Critical
   - Input: `$z = example.com$`
   - Expected: NO linkification inside math

6. **`test_math_with_pattern()`** ⭐ Critical
   - Input: `$bug123 = x$` with pattern `bug\d+`
   - Expected: NO link creation inside math

7. **`test_math_with_underscores()`**
   - Input: `$a_b + c_d$`
   - Expected: NO emphasis tags

8. **`test_math_with_asterisk()`**
   - Input: `$a * b$`
   - Expected: NO emphasis tags

9. **`test_single_dollar_not_math()`**
   - Input: `I paid $100`
   - Expected: Literal dollar sign

10. **`test_escaped_dollar()`**
    - Input: `\$100`
    - Expected: Literal `$100`

11. **`test_multiple_math_expressions()`**
    - Input: `$x$ and $y$ are variables`
    - Expected: Both preserved

12. **`test_mismatched_delimiters()`**
    - Input: `$x is incomplete`
    - Expected: Literal text

13. **`test_empty_math()`**
    - Input: `$$`
    - Expected: Literal or ignored

14. **`test_math_with_newlines()`**
    - Input: Display math spanning multiple lines
    - Expected: Content preserved

### Integration Tests (add to `test_markdown_integration.py`)

1. **`test_math_linkify_no_interference()`**
   - Complex document with math and URLs
   - Verify URLs outside math are linked
   - Verify URLs inside math are NOT linked

2. **`test_math_patterns_no_interference()`**
   - Document with math and link patterns
   - Verify patterns outside math work
   - Verify patterns inside math are ignored

3. **`test_math_emphasis_safe()`**
   - Document with math and ** bold ** text
   - Verify bold works outside math
   - Verify *, _ inside math are literal

### Existing Tests (should still pass)

- `test_mathjax_math_delimiters_preserved()`
- `test_mathjax_underscores_not_emphasis()`

---

## Re-enabling Asterisk Emphasis

### Current Problem

When `ENABLE_MATHJAX = True`, ALL emphasis is disabled:
- `*italic*` doesn't work
- `**bold**` doesn't work
- `_underscore_` doesn't work (this is desired for LaTeX)

### Desired Behavior

With math protection in place:
- Math content is protected as special tokens
- `_` can remain disabled for code-friendly compatibility
- `*` should work for emphasis outside of math

### Implementation Options

**Option 1: Custom Emphasis Rule**
```python
def emphasis_asterisk_only(state: StateInline, silent: bool) -> bool:
    """Emphasis using * and ** only (not _)"""
    # Implement asterisk-only emphasis
    pass

if askbot_settings.MARKUP_CODE_FRIENDLY:
    md.disable('emphasis')
    md.inline.ruler.enable(['emphasis_asterisk_only'])
```

**Option 2: Modify markdown-it-py**
- Fork and modify emphasis rule
- Check if delimiter is `*` or `_`
- Only process `*`

**Option 3: Accept Current Behavior**
- Document that emphasis is unavailable with MathJax
- Rely on HTML tags: `<em>`, `<strong>`

**Recommendation:** Start with Option 3 (accept), add Option 1 as enhancement later

---

## Frontend JavaScript Equivalent

To match backend behavior in preview, implement in `askbot_converter.js`:

```javascript
// Install: npm install markdown-it

const MarkdownIt = require('markdown-it');

// Custom math protection plugin
function mathProtectPlugin(md) {
  // Inline rule for $...$
  md.inline.ruler.before('escape', 'math_inline', function(state, silent) {
    // Implementation matching Python version
  });

  // Block rule for $$...$$
  md.block.ruler.before('code', 'math_block', function(state, startLine, endLine, silent) {
    // Implementation matching Python version
  });

  // Renderers
  md.renderer.rules.math_inline = function(tokens, idx) {
    return '$' + tokens[idx].content + '$';
  };

  md.renderer.rules.math_block = function(tokens, idx) {
    return '$$' + tokens[idx].content + '$$\n';
  };
}

// Configure converter
const md = new MarkdownIt({ linkify: true });

// Enable math protection FIRST if mathjax enabled
if (askbot.settings.mathjaxEnabled) {
  md.use(mathProtectPlugin);
}

// Then other plugins
md.enable(['table', 'strikethrough']);
// ... video, patterns, truncate plugins ...

// Use converter
const html = md.render(text);
```

---

## Success Criteria

- [x] Plan document created
- [ ] Math protection plugin implemented
- [ ] Plugin integrated into markup.py
- [ ] Plugin ordering corrected (math first)
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Existing mathjax tests still pass
- [ ] No linkification inside math
- [ ] No pattern matching inside math
- [ ] No emphasis processing inside math
- [ ] Math delimiters preserved in output
- [ ] Frontend JavaScript implementation documented
- [ ] Edge cases handled correctly

---

## Implementation Phases

### Phase 1: Core Plugin (MVP)
1. Create `math_protect.py` with inline rule only
2. Detect simple `$...$` patterns
3. Create `math_inline` tokens
4. Add render function
5. Basic unit tests

### Phase 2: Integration
1. Import into `markup.py`
2. Register before other plugins
3. Test with linkify
4. Test with link_patterns
5. Integration tests

### Phase 3: Display Math
1. Add block rule for `$$...$$`
2. Create `math_block` tokens
3. Handle multiline math
4. Additional tests

### Phase 4: Edge Cases
1. Handle escaped delimiters
2. Handle single `$` in text
3. Handle mismatched delimiters
4. Comprehensive edge case tests

### Phase 5: Emphasis Re-enabling
1. Implement asterisk-only emphasis (optional)
2. Update settings handling
3. Test emphasis + math interaction

### Phase 6: Frontend Parity
1. Document JavaScript implementation
2. Create example code
3. Test in preview mode

---

## Related TODOs

### Resolved by This Implementation

- **Line 150 TODO in markup.py:** `# TODO: Implement math delimiter protection plugin`
  - ✅ Will be resolved by creating `math_protect.py`

### Partially Addressed

- **Line 142 TODO in markup.py:** `# TODO: Add custom rule to re-enable * only if needed`
  - 🔄 Math protection makes this safer, but full implementation is optional enhancement

---

## References

- **markdown-it-py docs**: https://markdown-it-py.readthedocs.io/
- **MathJax delimiters**: https://docs.mathjax.org/en/latest/input/tex/delimiters.html
- **Inline rules**: markdown-it-py StateInline documentation
- **Block rules**: markdown-it-py StateBlock documentation
- **Similar implementations**: markdown-it-texmath (JavaScript), markdown-it-py-plugins

---

## Notes

- Math protection is CRITICAL before markdown upgrade is complete
- Current workaround (disabling emphasis) is insufficient
- Linkify and patterns WILL interfere with math without protection
- Plugin ordering is essential - math must be FIRST
- Frontend should match backend behavior for preview accuracy
- Tests must cover interaction scenarios, not just basic cases

---

**Created:** 2025-11-03
**Author:** Claude Code
**Status:** Ready for Implementation
