# Markdown + MathJax Implementation Plan v2
## Hybrid Approach: Stack Exchange Preprocessing + Server-Side Dollar Escape

**Date:** 2025-11-10
**Status:** Proposed
**Supersedes:** Background document approach (entity conversion only)

---

## Executive Summary

This document proposes a **hybrid architecture** combining:
1. **Stack Exchange's token-based math extraction** (proven at scale)
2. **Server-side `\$` → `&dollar;` conversion** (clean HTML, no FOUC)

This approach solves the escaped dollar dilemma while maintaining perfect Python/JavaScript parity and avoiding the pitfalls of pure client-side processing.

---

## Background: What Stack Exchange/MathOverflow Does

### Their Architecture (Client-Side Processing)

Stack Exchange uses a **3-phase preprocessing system** for PageDown (JavaScript markdown editor):

```
Phase 1: removeMath()
---------------------
Input:  "The price is \$100 and $x = 5$ here"
Step 1: Detilde code spans (protect $ in `code`)
Step 2: Extract math: $x = 5$ → stored in math[0]
Step 3: Replace with token: @@0@@
Output: "The price is \$100 and @@0@@ here"

Phase 2: PageDown Markdown
---------------------------
Input:  "The price is \$100 and @@0@@ here"
Process: Standard markdown (sees no math, no dollars)
Output: "<p>The price is \$100 and @@0@@ here</p>"

Phase 3: replaceMath()
----------------------
Input:  "<p>The price is \$100 and @@0@@ here</p>"
Step: Replace @@0@@ with math[0] = "$x = 5$"
Output: "<p>The price is \$100 and @@0@@ here</p>"

Phase 4: MathJax (client-side, in browser)
-------------------------------------------
MathJax config: processEscapes: true
Process: \$ → literal $, $x = 5$ → rendered math
Display: "The price is $100 and [math rendering] here"
```

### Key Implementation Details

**From Stack Exchange's `mathjax-editing.js` (Geoff Dalgas):**

1. **Regex-based math detection:**
   ```javascript
   var SPLIT = /(\$\$?|\\(?:begin|end)\{[a-z]*\*?\}|\\[\\{}$]|[{}]|(?:\n\s*)+|@@\d+@@)/i;
   ```

2. **Token replacement:**
   ```javascript
   blocks[i] = "@@" + math.length + "@@";
   math.push(block);
   ```

3. **Code span protection:**
   - Replace `$` with `~D` inside backticks before processing
   - Prevents false math detection in code blocks

4. **MathJax configuration:**
   ```javascript
   tex2jax: {
     processEscapes: true,  // MathJax handles \$ → $
     inlineMath: [['$','$'], ['\\(','\\)']],
     displayMath: [['$$','$$'], ['\\[','\\]']]
   }
   ```

### How They Handle Literal Dollars

**Answer: They don't. MathJax does.**

- User types: `\$100`
- Markdown passes through: `\$100` (unchanged)
- HTML contains: `\$100` (backslash in HTML!)
- MathJax converts: `\$` → `$` (in browser, via `processEscapes: true`)
- User sees: `$100` (clean)

**Why This Works For Them:**
- ✅ PageDown runs **client-side** (JavaScript in browser)
- ✅ MathJax runs **immediately after** (same page load, ~100ms delay)
- ✅ User never sees intermediate `\$` state
- ✅ Proven at scale (millions of posts on Stack Exchange network)

---

## The Askbot Constraint: Server-Side Rendering

### Critical Difference

**Stack Exchange:**
```
Browser: User types → PageDown → MathJax → Render
Timeline: All happens in ~100ms during single page load
```

**Askbot:**
```
Server: User types → Python markdown-it → Save HTML to DB
        [Hours/Days/Years pass...]
Browser: Load HTML from DB → MathJax runs
```

### The FOUC Problem (Flash of Unescaped Content)

If we copy Stack Exchange's approach directly:

```
Server HTML:    <p>The price is \$100</p>
Browser initial: "The price is \$100"  ← Backslash visible!
MathJax loads:   "The price is $100"   ← Fixed
```

**Problems:**
- ❌ Backslash flicker during page load
- ❌ Broken if MathJax disabled/blocked
- ❌ Not SEO-friendly (crawlers see `\$`)
- ❌ Accessibility issues (screen readers read "backslash dollar")

---

## Proposed Solution: Hybrid Architecture

Combine **Stack Exchange's token extraction** with **server-side dollar escape**.

### The 4-Phase Processing Flow

```
Input:  "Price \$100 and $x = 5$ here"

Phase 1: extract_math() [NEW - from Stack Exchange]
----------------------------------------------------
- Find: $x = 5$ → math[0]
- Replace with token: @@0@@
Output: "Price \$100 and @@0@@ here"
Storage: math = ["$x = 5$"]

Phase 2: escape_dollars() [NEW - our addition]
-----------------------------------------------
- Any \$ in text (not in math) → &dollar;
- Math already extracted, so safe to convert
Output: "Price &dollar;100 and @@0@@ here"

Phase 3: markdown-it processing
--------------------------------
- Standard markdown processing
- Sees no math, no dollars
Output: "<p>Price &dollar;100 and @@0@@ here</p>"

Phase 4: restore_math() [NEW - from Stack Exchange]
----------------------------------------------------
- Replace @@0@@ with math[0]
Output: "<p>Price &dollar;100 and $x = 5$ here</p>"

FINAL SERVER HTML:
<p>Price $100 and $x = 5$ here</p>

Browser (No MathJax needed for dollars!):
"Price $100 and [math rendering] here"
```

### Why This Is Better

| Feature | Stack Exchange | Our Hybrid | Pure Plugin |
|---------|---------------|------------|-------------|
| Math protection | ✅ Token-based | ✅ Token-based | ⚠️ Plugin-based |
| Clean HTML | ❌ Contains `\$` | ✅ Contains `$` | ✅ Contains `$` |
| Works w/o MathJax | ❌ Needs `processEscapes` | ✅ Server-rendered | ✅ Server-rendered |
| No FOUC | ❌ Brief flicker | ✅ Immediate | ✅ Immediate |
| SEO friendly | ❌ Crawlers see `\$` | ✅ Crawlers see `$` | ✅ Crawlers see `$` |
| Proven at scale | ✅ Stack Exchange | ⚠️ New approach | ❌ Untested |
| Implementation | ✅ Simple | ✅ Simple | ⚠️ Complex state |
| Edge cases | ✅ Minimal | ✅ Minimal | ⚠️ Many |

---

## Implementation Details

### Python Backend

#### 1. Math Extraction Utility

**File:** `askbot/utils/markdown_plugins/math_extract.py`

```python
"""
Token-based math extraction (Stack Exchange approach).
Extracts math content before markdown processing.
"""

import re

# Matches: $$, $, \[...\], \begin{...}
MATH_SPLIT = re.compile(
    r'(\$\$?|\\(?:begin|end)\{[a-z]*\*?\}|\\[\[\]]|[{}]|(?:\n\s*)+|@@\d+@@)',
    re.IGNORECASE
)

def extract_math(text):
    """
    Extract math expressions and replace with tokens.

    Args:
        text: Markdown source text

    Returns:
        tuple: (tokenized_text, math_blocks)
        - tokenized_text: Text with math replaced by @@N@@
        - math_blocks: List of extracted math strings

    Algorithm:
        1. Split text by math delimiters
        2. Track delimiter state ($, $$, \[, \begin)
        3. Extract complete math blocks
        4. Replace with @@N@@ tokens
        5. Store original math in array
    """
    math_blocks = []
    # TODO: Implement similar to Stack Exchange's removeMath()
    # Handle: $...$, $$...$$, \[...\], \begin{...}\end{...}
    return tokenized_text, math_blocks


def restore_math(html, math_blocks):
    """
    Restore math blocks from tokens.

    Args:
        html: Markdown-rendered HTML with @@N@@ tokens
        math_blocks: List of original math strings

    Returns:
        str: HTML with tokens replaced by original math
    """
    for i, math in enumerate(math_blocks):
        token = f"@@{i}@@"
        html = html.replace(token, math)
    return html


def protect_code_dollars(text):
    """
    Replace $ with ~D inside backtick code spans.
    Prevents false math detection in code blocks.

    This is Stack Exchange's "detilde" approach.
    """
    # TODO: Implement backtick detection and $ replacement
    return text
```

#### 2. Dollar Escape Plugin

**File:** `askbot/utils/markdown_plugins/dollar_escape.py`

```python
"""
Simple dollar escape for text regions.
Runs AFTER math extraction, so only processes text content.
"""

def escape_dollars(text):
    """
    Convert \$ → &dollar; in text.

    IMPORTANT: Must run AFTER extract_math(), so math is already
    protected as @@N@@ tokens. This ensures we never touch dollars
    inside math expressions.

    Args:
        text: Text with math already extracted (has @@N@@ tokens)

    Returns:
        str: Text with \$ replaced by &dollar;

    Edge cases handled:
        - \$ → &dollar; (simple case)
        - \$\$ → &dollar;&dollar; (escaped display delimiter)
        - \\$ → Left alone (markdown escape rule handles \\)
        - @@N@@ → Never touched (these are math tokens)
    """
    # Simple replacement - math is already safe
    return text.replace(r'\$', '&dollar;')
```

#### 3. Integration in markup.py

**File:** `askbot/utils/markup.py`

```python
from askbot.utils.markdown_plugins.math_extract import (
    extract_math, restore_math, protect_code_dollars
)
from askbot.utils.markdown_plugins.dollar_escape import escape_dollars

def markdown_input_converter(text):
    """Markdown to html converter with math protection"""

    if askbot_settings.ENABLE_MATHJAX:
        # Phase 1: Protect code spans
        text = protect_code_dollars(text)

        # Phase 2: Extract math to tokens
        text, math_blocks = extract_math(text)

        # Phase 3: Escape dollars in text regions
        text = escape_dollars(text)

    # Phase 4: Standard markdown processing
    md = get_md_converter()
    html = md.render(text)

    if askbot_settings.ENABLE_MATHJAX:
        # Phase 5: Restore math from tokens
        html = restore_math(html, math_blocks)

    # Phase 6: Sanitize HTML
    html = sanitize_html(html)

    return html
```

### JavaScript Frontend (When migrating to markdown-it.js)

**File:** `askbot/media/js/markdown_plugins/math_extract.js`

```javascript
/**
 * Token-based math extraction (port of Python version).
 * Must behave identically to Python for preview parity.
 */

const MATH_SPLIT = /(\$\$?|\\(?:begin|end)\{[a-z]*\*?\}|\\[\[\]]|[{}]|(?:\n\s*)+|@@\d+@@)/i;

export function extractMath(text) {
  const mathBlocks = [];
  // TODO: Port Python logic exactly
  return { tokenizedText, mathBlocks };
}

export function restoreMath(html, mathBlocks) {
  mathBlocks.forEach((math, i) => {
    const token = `@@${i}@@`;
    html = html.replace(token, math);
  });
  return html;
}

export function protectCodeDollars(text) {
  // TODO: Port Python logic exactly
  return text;
}
```

**File:** `askbot/media/js/markdown_plugins/dollar_escape.js`

```javascript
/**
 * Simple dollar escape (port of Python version).
 */

export function escapeDollars(text) {
  // Simple replacement - math already extracted
  return text.replace(/\\\$/g, '&dollar;');
}
```

---

## Test Strategy

### Test Files

**Python:** `askbot/tests/test_markdown_dollar_escape.py`
**JavaScript:** `askbot/media/js/tests/test_markdown_dollar_escape.js`

### Test Cases (Must Pass in Both Languages)

```python
def test_simple_escaped_dollar():
    """Basic case: \$100 → $100"""
    input_text = r"Price: \$100"
    expected = "<p>Price: $100</p>"
    assert convert(input_text) == expected

def test_escaped_dollar_with_math():
    """Math preserved, text dollar escaped"""
    input_text = r"Price \$100 and $x = 5$ here"
    expected = "<p>Price $100 and $x = 5$ here</p>"
    assert convert(input_text) == expected

def test_escaped_display_delimiter():
    """Escaped $$ becomes literal $$"""
    input_text = r"Not math: \$$x$$"
    expected = "<p>Not math: $$x$$</p>"
    assert convert(input_text) == expected

def test_math_with_latex_dollar():
    """LaTeX \$ inside math is preserved"""
    input_text = r"$price = \$50 + tax$"
    # Math extraction preserves content
    assert "$price = \$50 + tax$" in convert(input_text)

def test_multiple_escaped_dollars():
    """Multiple \$ in text"""
    input_text = r"\$50 to \$100"
    expected = "<p>$50 to $100</p>"
    assert convert(input_text) == expected

def test_complex_integration():
    """Kitchen sink test"""
    input_text = """
Price range: \$50-\$100

Inline math: $x = 5$

Display math:
$$
y = mx + b
$$

Code: `$variable` should not become math

LaTeX dollar: $cost = \$25$ in equation
"""
    result = convert(input_text)
    # Verify:
    # - Text dollars show as $
    # - Math preserved with delimiters
    # - Code span protected
    # - LaTeX \$ preserved in math
```

### Parity Testing

```python
def test_python_js_parity():
    """
    Generate 100 test cases with various combinations.
    Render in Python and JavaScript.
    Assert outputs are identical.
    """
    test_cases = generate_test_suite()

    for case in test_cases:
        python_output = python_convert(case)
        js_output = js_convert(case)  # Via Node.js

        assert python_output == js_output, \
            f"Mismatch on: {case}"
```

---

## Edge Cases & Decisions

### 1. Double Backslash + Dollar: `\\$100`

**Input:** `\\$100`
**Markdown escape:** `\\` → `\`
**Our processing:** After markdown, text contains `\$100`
**Our escape:** Not processed (no backslash before $)
**Output:** `\$100` (backslash shows, dollar literal)

**Decision:** This is a markdown edge case, not our problem. Users should use `&dollar;` if they need `\$` literally.

### 2. Triple Backslash: `\\\$100`

**Input:** `\\\$100`
**Math extraction:** No math found
**Dollar escape:** `\$` → `&dollar;`
**Markdown escape:** `\\` → `\`
**Output:** `\$100` or `\&dollar;100` (depends on order)

**Decision:** Undefined behavior. Document as edge case. Users should use `&dollar;`.

### 3. Math Inside Code Spans: `` `$x$` ``

**Input:** `` `$x$` ``
**Code protection:** `$` → `~D` inside backticks
**Math extraction:** Doesn't see `~D` as delimiter
**Markdown:** Renders as `<code>$x$</code>`
**Output:** `<code>$x$</code>` (literal dollars in code)

**Decision:** This is correct. Code spans should show literal text.

### 4. URL with Dollar: `http://example.com?price=$100`

**Input:** `http://example.com?price=$100`
**Math extraction:** `$100` has no closing `$` → not math
**Dollar escape:** No `\` prefix → not escaped
**Output:** `http://example.com?price=$100` (unchanged)

**Decision:** This is correct. Only `\$` triggers escape, not bare `$`.

### 5. Escaped Dollar in Math: `$price = \$50$`

**Input:** `$price = \$50$`
**Math extraction:** Entire thing is math, extracted as-is
**Dollar escape:** Never sees it (already in math token)
**Output:** `$price = \$50$` (preserved for MathJax LaTeX)

**Decision:** This is correct. MathJax interprets `\$` as LaTeX literal dollar.

---

## Migration Path

### Phase 1: Backend Only (Current)
1. Implement Python math extraction
2. Implement Python dollar escape
3. Integrate into `markup.py`
4. Deploy with comprehensive tests
5. **Frontend still uses WMD/Showdown** (preview may differ slightly)

### Phase 2: Frontend Migration (Future)
1. Migrate from WMD/Showdown to markdown-it.js
2. Port math extraction to JavaScript
3. Port dollar escape to JavaScript
4. Verify Python/JS parity
5. **Perfect preview/save match achieved**

---

## Documentation for Users

### Help Text in Editor

```markdown
## Writing Literal Dollar Signs

When MathJax is enabled, use `\$` for literal dollars:

✅ Correct:
- Price: \$100 → displays as: $100
- Range: \$50-\$100 → displays as: $50-$100

✅ Math works normally:
- Inline: $x = 5$ → renders as math
- Display: $$y = mx + b$$ → renders as math

✅ Dollar in math (LaTeX):
- $cost = \$25$ → renders with literal $ in equation

❌ Edge cases (use &dollar; instead):
- After backslash: \\$100 → use &dollar;100
- Complex escapes → use &dollar; for reliability
```

---

## Comparison with Original Plan

### Original Plan (background-for-escaped-delimiters-mathjax.md)
- Pure plugin-based approach
- Dollar escape inline rule in markdown-it
- Context-aware state tracking
- Run inside markdown-it processing

### New Plan (This Document)
- Token extraction preprocessing (Stack Exchange)
- Dollar escape between extraction and markdown
- No context tracking needed (math already removed)
- Run outside markdown-it processing

### Why the Change?

| Aspect | Original | New | Winner |
|--------|----------|-----|--------|
| Complexity | Medium | Low | New ✅ |
| Edge cases | Many | Few | New ✅ |
| Proven approach | Novel | Stack Exchange | New ✅ |
| State tracking | Required | Not needed | New ✅ |
| Plugin architecture | Used | Not used | Original |
| Elegance | High | Medium | Original |

**Decision:** New approach is simpler, proven, and more robust despite being less "pure" in design.

---

## References

### Stack Exchange Implementation
- **Source:** https://gist.github.com/gdalgas/a652bce3a173ddc59f66
- **File:** `mathjax-editing.js` by Geoff Dalgas
- **Algorithm:** Token-based extraction with `removeMath()` and `replaceMath()`
- **Scale:** Proven on millions of posts across Stack Exchange network

### MathJax Documentation
- `processEscapes: true` - Handles `\$` conversion client-side
- Delimiter configuration: `inlineMath: [['$','$']]`

### Community Discussions
- Math.SE Meta: "How to enter a dollar sign?"
- Stack Exchange Meta: Multiple bug reports and discussions
- General consensus: `\$` is the standard escape

---

## Conclusion

The hybrid approach combines:
- ✅ **Stack Exchange's proven architecture** (token extraction)
- ✅ **Server-side dollar escape** (clean HTML, no FOUC)
- ✅ **Simple implementation** (no complex state tracking)
- ✅ **Perfect parity possible** (same logic in Python and JS)

This solves the escaped dollar dilemma with minimal second-order complexity while maintaining the benefits of server-side rendering.

**Next Steps:**
1. Implement Python math extraction utilities
2. Implement Python dollar escape
3. Add comprehensive test suite
4. Deploy backend changes
5. Plan JavaScript migration (future)

**Status:** Ready for implementation ✅
