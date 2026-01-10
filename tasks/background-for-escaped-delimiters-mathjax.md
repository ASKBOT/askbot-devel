# Background: Escaped Dollar Signs in MathJax Context

## Problem Statement

When MathJax is enabled on a site, the dollar sign `$` becomes a special delimiter for inline math (`$...$`) and display math (`$$...$$`).
This creates a problem: **how do users write literal dollar signs** (e.g., "$100") without MathJax interpreting them as math delimiters?

### The Standard Escape Approach

In markdown, backslash `\` is used to escape special characters. Users naturally expect `\$100` to render as a literal `$100`.

### The Core Problem

**Markdown-it does NOT process `\$` as an escape sequence** because `$` is not a markdown special character.
The standard markdown spec only recognizes escapes for:

```
\ ` * _ { } [ ] ( ) # + - . ! |
```

Dollar sign `$` is NOT in this list.

Therefore:
- User types: `\$100`
- Markdown-it sees: `\$100` (no processing)
- HTML output: `\$100` (backslash remains)
- Browser displays: `\$100` (backslash visible!)
- **MathJax might still see the `$` as a delimiter!**

## Multi-Layer Escaping Complexity

### Layer 1: Python String Literals

```python
# In Python test code:
r"\$"      # Raw string: stores one backslash + dollar: \$
r"\\$"     # Raw string: stores two backslashes + dollar: \\$
"\$"       # Regular string: stores one backslash + dollar: \$ (same as r"\$")
"\\$"      # Regular string: stores one backslash + dollar: \$
```

### Layer 2: Markdown-it Processing

Since `$` is not a markdown special char:
```
Input:  \$      → Output: \$  (no change)
Input:  \\$     → Output: \\$ (no change)
```

### Layer 3: Browser Rendering

The HTML is rendered as-is, backslashes are visible to the user.

### Layer 4: MathJax Processing

MathJax runs in the browser AFTER HTML rendering. It scans for `$` delimiters in the DOM. If it finds them, it processes the content as math.

## Critical Design Question #1: Markdown Processing After Escapes

**Scenario:**
```
User types: \$x = *y*$
```

**If we simply remove the backslash:**
```
HTML output: $x = <em>y</em>$
```

**The Problem:**
- Markdown correctly processes `*y*` → `<em>y</em>`
- But now MathJax sees `$x = <em>y</em>$`
- **MathJax will try to process this as math!**
- This defeats the purpose of escaping

**The Solution:**
Convert escaped dollar to an HTML entity that:
1. **Displays as `$`** in the browser
2. **Is NOT recognized by MathJax** as a delimiter

## Proposed Solution: HTML Entity Conversion

### Outside Math Mode

Convert `\$` → `&dollar;` HTML entity:

```
User input:  \$x = *y*$
Processing:  Escape detected → convert to &dollar;
             Markdown processes: *y* → <em>y</em>
HTML output: &dollar;x = <em>y</em>$
Browser:     $x = y$ (displays correctly)
MathJax:     Ignores &dollar; (not a $ delimiter)
```

### Inside Math Mode (LaTeX Context)

**Preserve `\$` as LaTeX syntax:**

```
User input:  $price = \$50 + tax$
Processing:  Math mode active → preserve LaTeX escape
HTML output: $price = \$50 + tax$
MathJax:     Interprets \$ as LaTeX literal dollar
Rendered:    price = $50 + tax (in math font)
```

### Display Math Delimiter Escape

**Convert `\$$` → `&dollar;&dollar;`:**

```
User input:  \$$x$$
Processing:  \$$ → &dollar;&dollar;, remaining: x$$
HTML output: &dollar;&dollar;x$$
Browser:     $$x$$ (literal text)
MathJax:     Ignores &dollar;&dollar; (not a valid $$ delimiter)
```

## Critical Design Question #2: Auto-Convert Unmatched Dollars?

**Scenario:**
```
Text: I paid $100 for lunch.
```

The `$100` has no closing `$`. Should the plugin auto-convert it to `&dollar;100`?

### Arguments For:
- Safer: prevents accidental math mode activation
- User-friendly: less cognitive load

### Arguments Against:
- **Explicit vs Implicit intent**: `\$` is explicit escape, `$100` is just text
- **Scope creep**: Plugin becomes auto-sanitizer, not just math protector
- **Site policy**: If MathJax is enabled, users should learn to escape
- **MathJax config**: Properly configured MathJax won't match `$100 ` (space breaks pattern)

### Decision: NO Auto-Conversion

**Only explicit escapes (`\$`) should be converted.**

Reasoning:
1. Respect explicit user intent
2. Limit plugin scope to deliberate actions
3. Site documentation can educate users: "Use `\$` for literal dollars"
4. MathJax configuration handles most edge cases

## Implementation Requirements

### New Inline Rule: `dollar_escape`

Create a new inline rule that:
1. Detects `\$` pattern (backslash + dollar)
2. Runs BEFORE other inline rules but AFTER math rules
3. Creates a special token or injects `&dollar;` directly
4. **Must NOT process inside existing math tokens**

### Rule Order

```
1. escape (built-in) - handles \*, \_, etc.
2. math_block (custom) - handles $$...$$
3. math_inline (custom) - handles $...$
4. dollar_escape (NEW) - handles \$ outside math
5. backticks - handles `code`
6. emphasis - handles *text*
... other rules
```

### Edge Cases to Handle

1. `\$` → `&dollar;`
2. `\$$` → `&dollar;&dollar;`
3. `\$\$` → `&dollar;&dollar;` (two separate escapes)
4. `$\$100$` → Math mode, preserve `\$` for LaTeX
5. `$$\$100$$` → Display math, preserve `\$` for LaTeX
6. `\\$` → Escaped backslash: `\$` (literal backslash + dollar)

## Test Requirements

### Outside Math Mode (Escape → Entity)

1. **Single escaped dollar**
   - Input: `\$100`
   - HTML: `&dollar;100`
   - Rendered: `$100`

2. **Escaped dollar with markdown**
   - Input: `\$x = *y*$`
   - HTML: `&dollar;x = <em>y</em>$`
   - Verify: emphasis processed, &dollar; prevents MathJax

3. **Both sides escaped**
   - Input: `\$x = y\$`
   - HTML: `&dollar;x = y&dollar;`
   - Rendered: `$x = y$`

4. **Display math delimiter escaped**
   - Input: `\$$x$$`
   - HTML: `&dollar;&dollar;x$$`
   - Rendered: `$$x$$` (literal, not math)

### Inside Math Mode (Preserve LaTeX)

1. **Escaped dollar in inline math**
   - Input: `$x = \$100$`
   - HTML: `$x = \$100$`
   - MathJax: interprets `\$` as LaTeX literal

2. **Escaped dollar in display math**
   - Input: `$$price = \$50$$`
   - HTML: `$$price = \$50$$`
   - MathJax: interprets `\$` as LaTeX literal

## Open Questions & Future Considerations

### 1. What about `\\\$`?

Escaped backslash followed by dollar:
- Standard markdown: `\\\$` → `\$` (first `\\` becomes `\`, third `\` escapes nothing)
- Should we process the `$` or leave it?
- **Suggestion**: If preceded by escaped backslash, leave the `$` alone

### 2. Performance considerations?

Adding another inline rule increases parsing overhead. For large documents with many `$` characters, this could be measurable.

**Mitigation**: Only run when MathJax is enabled (`ENABLE_MATHJAX` setting)

### 3. Should we support `\$` inside code blocks?

Code blocks should preserve literal text. Current behavior:
- `` `\$100` `` → `<code>\$100</code>` (backslash preserved)

This is correct - no action needed.

### 4. Interaction with other plugins?

If other plugins also look for `$` characters, there could be conflicts. Need to ensure rule order is correct and that our tokens are properly isolated.

## References

- Markdown-it escape processing: https://spec.commonmark.org/0.30/#backslash-escapes
- MathJax delimiter configuration: https://docs.mathjax.org/en/latest/input/tex/delimiters.html
- HTML entities: https://html.spec.whatwg.org/multipage/named-characters.html#named-character-references

## Decision Log

| Decision | Rationale |
|----------|-----------|
| Use `&dollar;` entity | Displays as `$`, blocks MathJax detection |
| Convert `\$$` → `&dollar;&dollar;` | Logical extension, prevents display math |
| Preserve `\$` in math mode | LaTeX syntax for literal dollar |
| NO auto-convert `$100` | Explicit intent only, limit scope |
| New inline rule vs modify existing | Cleaner separation of concerns |

## Next Steps

1. ✅ Document the requirements (this file)
2. ⏳ Update tests to reflect `&dollar;` conversion
3. ⏳ Implement `dollar_escape` inline rule
4. ⏳ Test TDD-style: tests fail first, then implement
5. ⏳ Document user-facing behavior
6. ⏳ Consider adding to askbot documentation
