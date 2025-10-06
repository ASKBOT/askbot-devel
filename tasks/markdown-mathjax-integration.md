# Markdown + MathJax Integration Guide

## Overview

This document describes how the markdown-it upgrade integrates with MathJax for LaTeX math rendering support.

## Key Principle: Separation of Concerns

**Markdown parser and MathJax are independent layers:**

```
┌──────────────────────────────────────────┐
│  User Input (Markdown + LaTeX)          │
│  "The equation $E = mc^2$ is famous"    │
└──────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────┐
│  Markdown Parser (markdown-it)           │
│  - Converts markdown → HTML              │
│  - PRESERVES $...$ blocks verbatim       │
│  - Does NOT process LaTeX                │
└──────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────┐
│  HTML Output                             │
│  <p>The equation $E = mc^2$ is famous</p>│
└──────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────┐
│  MathJax (Client-side)                   │
│  - Scans HTML for $...$ delimiters       │
│  - Renders LaTeX → formatted math        │
│  - Independent of markdown               │
└──────────────────────────────────────────┘
```

## Problem: Markdown Processing Breaks LaTeX

Without protection, markdown parsers process text inside `$...$` delimiters:

### Example 1: Underscores → Emphasis
```markdown
Input:  $a_b$
Wrong:  $a<em>b</em>$  ← Markdown processed underscore as italic
Right:  $a_b$           ← Preserved verbatim for MathJax
```

### Example 2: Asterisks → Bold
```markdown
Input:  $x * y * z$
Wrong:  $x <strong> y </strong> z$  ← Markdown processed * as bold
Right:  $x * y * z$                  ← Preserved verbatim
```

### Example 3: Subscripts/Superscripts
```markdown
Input:  $x_{123}^{456}$
Wrong:  $x<sub>{123}</sub><sup>{456}</sup>$  ← HTML entities
Right:  $x_{123}^{456}$                       ← LaTeX preserved
```

## Solution: Math Delimiter Protection

### Two-Part Approach

#### 1. Code-Friendly Mode (Disables Underscore Emphasis)

When `ENABLE_MATHJAX = True`, automatically enable code-friendly mode:

**Backend (Python):**
```python
# askbot/utils/markup.py
if askbot_settings.ENABLE_MATHJAX or askbot_settings.MARKUP_CODE_FRIENDLY:
    md.disable('emphasis')  # Disables both * and _ emphasis
```

**Frontend (JavaScript):**
```javascript
// askbot/media/wmd/askbot_converter.js
if (settings.mathjaxEnabled || settings.markupCodeFriendly) {
    this._md.disable('emphasis');
}
```

#### 2. Math Delimiter Protection (Treats Math as Verbatim)

Add custom markdown-it rules to detect and preserve `$...$` and `$$...$$` blocks:

**Backend (Python):**
```python
# askbot/utils/markdown_plugins/math_protect.py
def math_inline_rule(state, silent):
    """Detect $...$ and create verbatim token"""
    if state.src[pos] == '$':
        # Find closing $
        # Create token with content preserved
        token = state.push('math_inline', '', 0)
        token.content = matched_text
    return True

def math_protect_plugin(md):
    md.inline.ruler.before('escape', 'math_inline', math_inline_rule)
    md.renderer.rules.math_inline = lambda tokens, idx: tokens[idx].content
```

**Frontend (JavaScript):**
```javascript
// askbot/media/wmd/askbot_converter.js
AskbotMarkdownConverter.prototype._protectMathDelimiters = function() {
    function mathInlineRule(state, silent) {
        // Detect $...$
        // Create token with verbatim content
    }

    this._md.inline.ruler.before('escape', 'math_inline', mathInlineRule);
    this._md.renderer.rules.math_inline = function(tokens, idx) {
        return tokens[idx].content;  // Render as-is
    };
};
```

## Implementation Locations

### Phase 1: Backend (Python)

**Files Modified:**
- `askbot/utils/markup.py` - Main converter configuration
- `askbot/utils/markdown_plugins/math_protect.py` - NEW plugin (to be created)

**Changes:**
```python
# In get_md_converter():

# 1. Auto-enable code-friendly mode
if askbot_settings.ENABLE_MATHJAX or askbot_settings.MARKUP_CODE_FRIENDLY:
    md.disable('emphasis')

# 2. Protect math delimiters
if askbot_settings.ENABLE_MATHJAX:
    from askbot.utils.markdown_plugins.math_protect import math_protect_plugin
    md.use(math_protect_plugin)
```

### Phase 2: Frontend (JavaScript)

**Files Modified:**
- `askbot/media/wmd/askbot_converter.js` - Add `_protectMathDelimiters()` method

**Changes:**
```javascript
// In _configureSettings():

// 1. Code-friendly mode
if (settings.mathjaxEnabled || settings.markupCodeFriendly) {
    this._md.disable('emphasis');
}

// 2. Math delimiter protection
if (settings.mathjaxEnabled) {
    this._protectMathDelimiters();
}
```

### Phase 3: Testing

**Test Cases Added:**

**Backend Tests** (`askbot/tests/test_markdown_integration.py`):
- `test_mathjax_math_delimiters_preserved()` - Check $...$ preserved
- `test_mathjax_underscores_not_emphasis()` - Check underscores work
- `test_mathjax_complex_latex()` - Check complex expressions

**Edge Case Tests** (`askbot/tests/test_markdown_edge_cases.py`):
- `test_mathjax_inline_math_preserved()` - Inline math
- `test_mathjax_display_math_preserved()` - Display math
- `test_mathjax_underscores_not_processed()` - Underscore handling

## Configuration

### Settings Interaction

| Setting | Effect |
|---------|--------|
| `ENABLE_MATHJAX = False` | Normal markdown (underscores create emphasis) |
| `ENABLE_MATHJAX = True` | Code-friendly mode + math protection enabled |
| `MARKUP_CODE_FRIENDLY = True` | Code-friendly mode (no underscore emphasis) |

### Automatic Behavior

When admin enables MathJax in settings (`ENABLE_MATHJAX = True`):

1. ✅ Code-friendly mode activates automatically
2. ✅ Underscore emphasis disabled
3. ✅ Math delimiter protection enabled
4. ✅ LaTeX content preserved verbatim
5. ✅ MathJax can render math on client-side

## Testing Strategy

### Manual Testing Checklist

**Backend (Python):**
```bash
cd testproject/
python manage.py shell

from askbot.utils.markup import get_md_converter
md = get_md_converter()

# Test 1: Inline math preserved
text = "The equation $E = mc^2$ is famous"
html = md.render(text)
assert '$E = mc^2$' in html

# Test 2: Underscores not processed
text = "$a_b$ and $x_{123}$"
html = md.render(text)
assert '$a_b$' in html
assert '<em>' not in html
assert '<sub>' not in html

# Test 3: Display math preserved
text = "$$\\int_0^1 x dx$$"
html = md.render(text)
assert '$$' in html
assert '\\int' in html
```

**Frontend (JavaScript):**
```javascript
// In browser console
var converter = new AskbotMarkdownConverter();

// Test 1: Inline math
var html = converter.makeHtml("The equation $E = mc^2$ is famous");
console.log(html);  // Should contain $E = mc^2$

// Test 2: Underscores
var html = converter.makeHtml("$a_b$ and $x_{123}$");
console.log(html);  // Should NOT have <em> or <sub> tags

// Test 3: MathJax rendering (if enabled)
// After typing in editor, MathJax should render the math
```

### Automated Testing

**Run backend tests:**
```bash
cd testproject/
python manage.py test askbot.tests.test_markdown_integration -k mathjax
python manage.py test askbot.tests.test_markdown_edge_cases -k mathjax
```

**Run frontend tests:**
```bash
# Browser-based testing (Selenium/Playwright)
python manage.py test askbot.tests.test_markdown_frontend -k mathjax
```

## Edge Cases and Gotchas

### 1. Dollar Signs in Regular Text

**Problem:** `$100 and $200` might be treated as math

**Solution:**
- Math detection requires closing `$`
- `$100` alone won't match (no closing delimiter)
- To write literal `$`, use `\$` or just `$` (works fine)

### 2. Escaped Dollar Signs

**Problem:** How to write literal `$` in text?

**Solution:**
- Just use `$` - it's fine if not followed by matching `$`
- Or use `\$` if you want to be explicit

### 3. Nested Delimiters

**Problem:** `$outer $inner$ outer$`

**Solution:**
- Current implementation uses simple matching
- First `$` matches with next `$`
- Nested delimiters not supported (rare in LaTeX)

### 4. Display Math on Own Line

**Problem:** `$$..$$` should be block-level, not inline

**Solution:**
- Put `$$` on separate lines:
  ```markdown
  Text before

  $$
  \int_0^1 x dx
  $$

  Text after
  ```

## Relationship to MathJax Upgrade

This math protection is **orthogonal** to the MathJax v2→v4 upgrade:

| Concern | Markdown Upgrade | MathJax Upgrade |
|---------|------------------|-----------------|
| **Scope** | Preserve LaTeX in HTML | Render LaTeX visually |
| **When** | During markdown→HTML | After HTML loaded |
| **Where** | Server + client | Client only |
| **Plugin** | Math delimiter protection | MathJax library |

**Both projects are independent:**
- Markdown upgrade works with MathJax v2 OR v4
- MathJax upgrade doesn't require markdown upgrade
- But doing both together is ideal

## Migration Notes

### For Existing Installations

**Before markdown-it upgrade:**
- MathJax works (if configured)
- Some edge cases may fail (e.g., complex underscores)

**After markdown-it upgrade:**
- MathJax still works
- Better math delimiter protection
- More reliable with complex LaTeX

**No content re-rendering needed:**
- Math delimiters already in database
- MathJax processes them client-side
- No server-side changes to stored HTML

## Future Enhancements

### Potential Improvements (Not in Current Scope)

1. **Server-Side Math Rendering**
   - Render LaTeX → SVG on server
   - Better SEO, faster initial load
   - Complexity: High, security concerns

2. **Alternative Delimiters**
   - Support `\(...\)` and `\[...\]`
   - CommonMark math extension
   - Complexity: Medium

3. **Math Block Plugin**
   - Dedicated fenced code blocks: ` ```math `
   - Clearer syntax
   - Complexity: Low

4. **Syntax Validation**
   - Validate LaTeX syntax in editor
   - Show errors before save
   - Complexity: Medium

## References

### Documentation
- [MathJax Documentation](https://docs.mathjax.org/)
- [markdown-it Documentation](https://markdown-it.github.io/)
- [CommonMark Spec](https://spec.commonmark.org/)

### Related Tasks
- `tasks/markdown-upgrade-phase1-backend.md` - Backend implementation
- `tasks/markdown-upgrade-phase2-frontend.md` - Frontend implementation
- `tasks/markdown-upgrade-phase3-testing.md` - Testing strategy
- `tasks/upgrade-mathjax.md` - MathJax v4 upgrade plan

### Code Locations
- `askbot/conf/markup.py:54-65` - MathJax settings
- `askbot/jinja2/meta/bottom_scripts.html:192-205` - MathJax loading
- `askbot/media/wmd/askbot_converter.js` - Editor preview
- `askbot/utils/markup.py` - Backend markdown conversion

## Summary

**Key Takeaways:**

1. ✅ Markdown parser does NOT render MathJax - it preserves delimiters
2. ✅ Two mechanisms: code-friendly mode + delimiter protection
3. ✅ Works on both backend (Python) and frontend (JavaScript)
4. ✅ Automatic when `ENABLE_MATHJAX = True`
5. ✅ No breaking changes to existing math content
6. ✅ Independent of MathJax version (v2/v3/v4)

**The relationship is simple:**
- Markdown creates HTML with `$...$` preserved
- MathJax renders `$...$` into beautiful math
- They never need to "talk" to each other
