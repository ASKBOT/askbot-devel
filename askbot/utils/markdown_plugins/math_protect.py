"""
MathJax delimiter protection plugin for markdown-it-py.

Treats content inside $...$ (inline) and $$...$$ (display) as verbatim text
to prevent any markdown processing of mathematical expressions.

This plugin MUST run before all other inline rules to properly protect
math content from linkification, pattern matching, and emphasis processing.

Delimiter Syntax:
    $E = mc^2$              # Inline math
    $$                      # Display math (block)
    \int_0^1 x dx
    $$

Edge Cases:
    - Single dollar: "I paid $100" → NOT math (no closing delimiter)
    - Escaped: \$100 → Literal "$100" (handled by escape rule)
    - Mismatched: "$x" without closing → NOT math
    - Adjacent: $$x$$ → Display math (block has priority)
"""

from markdown_it import MarkdownIt
from markdown_it.rules_inline import StateInline
from markdown_it.rules_block import StateBlock


def math_inline_rule(state: StateInline, silent: bool) -> bool:
    """
    Detect inline math delimiters: $...$

    Creates math_inline tokens that preserve content verbatim.

    Algorithm:
        1. Must start with $ not preceded by \ (escape)
        2. Must not be immediately followed by space (avoid "$100 paid")
        3. Must have closing $ before line end
        4. Closing $ must not be preceded by \
        5. Content between delimiters becomes math_inline token

    Returns:
        True if pattern matches and token created, False otherwise
    """
    pos = state.pos
    maximum = state.posMax

    # Must have at least 3 chars: $x$
    if pos + 2 >= maximum:
        return False

    # Must start with $
    if state.src[pos] != '$':
        return False

    # Check if it's escaped (preceded by \)
    if pos > 0 and state.src[pos - 1] == '\\':
        return False

    # Check if followed by another $ (might be display math $$)
    # Let the display math rule handle it
    if pos + 1 < maximum and state.src[pos + 1] == '$':
        return False

    # Must not be followed by space (avoid false positives like "$100 paid")
    if state.src[pos + 1] == ' ':
        return False

    # Find closing $
    # Start search from pos + 1 (after opening $)
    closing_pos = pos + 1

    while closing_pos < maximum:
        if state.src[closing_pos] == '$':
            # Check if it's escaped
            if closing_pos > 0 and state.src[closing_pos - 1] == '\\':
                closing_pos += 1
                continue

            # Found unescaped closing $
            # Extract content between delimiters
            content = state.src[pos + 1:closing_pos]

            # Content should not be empty
            if not content:
                return False

            if not silent:
                token = state.push('math_inline', '', 0)
                token.content = content
                token.markup = '$'

            state.pos = closing_pos + 1
            return True

        # Stop at newline (inline math must be on same line)
        if state.src[closing_pos] == '\n':
            return False

        closing_pos += 1

    # No closing delimiter found
    return False


def math_block_rule(state: StateBlock, startLine: int, endLine: int, silent: bool) -> bool:
    """
    Detect display math delimiters: $$...$$

    Creates math_block tokens for display equations.

    Algorithm:
        1. Must start with $$ at beginning of line (with optional whitespace)
        2. Can span multiple lines
        3. Closes with $$ (can be on same line or different line)
        4. Content between delimiters becomes math_block token

    Returns:
        True if pattern matches and token created, False otherwise
    """
    pos = state.bMarks[startLine] + state.tShift[startLine]
    maximum = state.eMarks[startLine]

    # Must have at least $$
    if pos + 1 >= maximum:
        return False

    # Check for $$ at start of line
    if state.src[pos:pos + 2] != '$$':
        return False

    # Move past opening $$
    pos += 2

    # Check if this is inline display math ($$...$$ on same line)
    # Look for closing $$ on the same line
    closing_pos = state.src.find('$$', pos)

    if closing_pos != -1 and closing_pos < maximum:
        # Found closing $$ on same line
        content = state.src[pos:closing_pos]

        if not silent:
            token = state.push('math_block', '', 0)
            token.content = content
            token.markup = '$$'
            token.block = True
            token.map = [startLine, startLine + 1]

        state.line = startLine + 1
        return True

    # Multi-line display math
    # Search for closing $$ on subsequent lines
    nextLine = startLine
    auto_closed = False

    # Collect content from current line (after opening $$)
    first_line_content = state.src[pos:maximum]
    lines = [first_line_content]

    # Search subsequent lines
    while nextLine < endLine - 1:
        nextLine += 1

        pos = state.bMarks[nextLine] + state.tShift[nextLine]
        maximum = state.eMarks[nextLine]

        line_content = state.src[pos:maximum]

        # Check if this line has closing $$
        if '$$' in line_content:
            closing_idx = line_content.find('$$')
            # Add content before closing $$
            if closing_idx > 0:
                lines.append(line_content[:closing_idx])
            auto_closed = True
            nextLine += 1
            break

        # Add entire line
        lines.append(line_content)

    # Must have found closing $$
    if not auto_closed:
        return False

    content = '\n'.join(lines)

    if not silent:
        token = state.push('math_block', '', 0)
        token.content = content
        token.markup = '$$'
        token.block = True
        token.map = [startLine, nextLine]

    state.line = nextLine
    return True


def render_math_inline(self, tokens, idx, options, env):
    """
    Render inline math with delimiters.

    Output is raw LaTeX wrapped in $ delimiters for MathJax to process.
    """
    return f"${tokens[idx].content}$"


def render_math_block(self, tokens, idx, options, env):
    """
    Render display math with delimiters.

    Output is raw LaTeX wrapped in $$ delimiters for MathJax to process.
    """
    return f"$${tokens[idx].content}$$\n"


def math_protect_plugin(md: MarkdownIt) -> MarkdownIt:
    """
    Plugin to protect MathJax delimiters from markdown processing.

    CRITICAL: Must be registered BEFORE other inline/block rules.

    This ensures that math content is converted to special tokens
    before linkify, patterns, emphasis, and other plugins run.
    Those plugins will skip math tokens since they only process text.

    Usage:
        md = MarkdownIt()
        md.use(math_protect_plugin)  # Register FIRST
        md.use(other_plugins...)     # Other plugins after

    Tokens Created:
        - math_inline: Inline math ($...$)
        - math_block: Display math ($$...$$)

    Both token types preserve content verbatim with delimiters intact.
    """
    # Register inline rule FIRST (before 'escape' to catch math early)
    # Note: We want escape to run first, but escape is already built-in
    # So we insert after escape but before everything else
    md.inline.ruler.before('backticks', 'math_inline', math_inline_rule)

    # Register block rule FIRST (before 'code' blocks)
    md.block.ruler.before('fence', 'math_block', math_block_rule)

    # Register renderers
    md.add_render_rule('math_inline', render_math_inline)
    md.add_render_rule('math_block', render_math_block)

    return md
