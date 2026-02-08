"""
Token-based math extraction (Stack Exchange approach).
Extracts math content before markdown processing to protect it from markdown rules.

Based on Stack Exchange's mathjax-editing.js by Geoff Dalgas.
Reference: https://gist.github.com/gdalgas/a652bce3a173ddc59f66
"""

import re


# Matches math delimiters and structural tokens
# Pattern matches: $$, $, \begin{...}, \end{...}, \[, \], {, }, newlines, existing tokens
MATH_SPLIT = re.compile(
    r'(\$\$?|\\(?:begin|end)\{[a-z]*\*?\}|\\[\[\]]|[{}]|(?:\n\s*)+|@@\d+@@)',
    re.IGNORECASE
)


def protect_code_dollars(text):
    """
    Replace $ with ~D inside backtick code spans.
    Prevents false math detection in code blocks.

    This is Stack Exchange's "detilde" approach.

    Args:
        text: Markdown source text

    Returns:
        str: Text with $ replaced by ~D inside code spans
    """
    # Find all inline code spans (single backticks)
    # Pattern: `...content...`
    # Must handle escaped backticks: \`

    result = []
    i = 0
    while i < len(text):
        # Check for backtick
        if text[i] == '`':
            # Check if it's escaped
            if i > 0 and text[i-1] == '\\':
                result.append(text[i])
                i += 1
                continue

            # Find matching closing backtick
            start = i
            i += 1

            # Count consecutive backticks for the opening
            backtick_count = 1
            while i < len(text) and text[i] == '`':
                backtick_count += 1
                i += 1

            # Now find the matching closing backticks
            code_content_start = i
            while i < len(text):
                if text[i] == '`':
                    # Count consecutive backticks
                    closing_count = 0
                    closing_start = i
                    while i < len(text) and text[i] == '`':
                        closing_count += 1
                        i += 1

                    if closing_count == backtick_count:
                        # Found matching close
                        # Extract code content and replace $ with ~D
                        code_content = text[code_content_start:closing_start]
                        code_content = code_content.replace('$', '~D')

                        # Append: opening backticks + modified content + closing backticks
                        result.append('`' * backtick_count)
                        result.append(code_content)
                        result.append('`' * backtick_count)
                        break
                else:
                    i += 1
            else:
                # No matching close found - treat as literal backticks
                result.append(text[start:i])
        else:
            result.append(text[i])
            i += 1

    return ''.join(result)


def extract_math(text):
    """
    Extract math expressions and replace with tokens.

    Implements Stack Exchange's removeMath() algorithm using a state machine
    to track delimiter contexts and extract complete math blocks.

    Args:
        text: Markdown source text (already processed by protect_code_dollars)

    Returns:
        tuple: (tokenized_text, math_blocks)
        - tokenized_text: Text with math replaced by @@N@@
        - math_blocks: List of extracted math strings

    Algorithm:
        1. Split text by math delimiters and structural tokens
        2. Track delimiter state ($, $$, \[, \begin{env})
        3. Extract complete math blocks
        4. Replace with @@N@@ tokens
        5. Store original math in array

    Supported formats:
        - Inline: $...$
        - Display: $$...$$
        - LaTeX display: \[...\]
        - LaTeX environments: \begin{env}...\end{env}
    """
    math_blocks = []

    # Split text by delimiters
    parts = MATH_SPLIT.split(text)

    result = []
    math_start = None
    math_delimiter = None
    math_content = []
    brace_depth = 0
    env_stack = []

    for part in parts:
        # Check if we're currently inside math
        if math_start is not None:
            # We're inside math - look for closing delimiter

            if math_delimiter == '$$':
                if part == '$$':
                    # Found closing $$
                    math_content.append(part)
                    full_math = ''.join(math_content)
                    token = f"@@{len(math_blocks)}@@"
                    math_blocks.append(full_math)
                    result.append(token)

                    # Reset state
                    math_start = None
                    math_delimiter = None
                    math_content = []
                else:
                    math_content.append(part)

            elif math_delimiter == '$':
                if part == '$':
                    # Check if this $ is escaped (preceded by \)
                    # Look at the last character of the accumulated math content
                    content_so_far = ''.join(math_content)
                    if content_so_far.endswith('\\'):
                        # This is \$ (escaped dollar in LaTeX), not a closing delimiter
                        math_content.append(part)
                    else:
                        # Found closing $
                        math_content.append(part)
                        full_math = ''.join(math_content)
                        token = f"@@{len(math_blocks)}@@"
                        math_blocks.append(full_math)
                        result.append(token)

                        # Reset state
                        math_start = None
                        math_delimiter = None
                        math_content = []
                elif part == '$$':
                    # Check if this $$ is escaped
                    content_so_far = ''.join(math_content)
                    if content_so_far.endswith('\\'):
                        # This is \$$ (escaped), treat first $ as escaped
                        math_content.append('$')  # Add first $ as part of \$
                        # Second $ might be closing delimiter
                        # Check again after adding first $
                        content_after = ''.join(math_content)
                        if content_after.endswith('\\$'):
                            # Both are escaped: \$$
                            math_content.append('$')
                        else:
                            # First was escaped \$, second closes
                            math_content.append('$')
                            full_math = ''.join(math_content)
                            token = f"@@{len(math_blocks)}@@"
                            math_blocks.append(full_math)
                            result.append(token)

                            # Reset state
                            math_start = None
                            math_delimiter = None
                            math_content = []
                    else:
                        # This is NOT an escaped delimiter for single $
                        # Treat as two separate $ signs - close current and open new
                        math_content.append('$')
                        full_math = ''.join(math_content)
                        token = f"@@{len(math_blocks)}@@"
                        math_blocks.append(full_math)
                        result.append(token)

                        # Start new $$ block
                        math_start = True
                        math_delimiter = '$$'
                        math_content = ['$$']
                else:
                    math_content.append(part)

            elif math_delimiter == '\\[':
                if part == '\\]':
                    # Found closing \]
                    math_content.append(part)
                    full_math = ''.join(math_content)
                    token = f"@@{len(math_blocks)}@@"
                    math_blocks.append(full_math)
                    result.append(token)

                    # Reset state
                    math_start = None
                    math_delimiter = None
                    math_content = []
                else:
                    math_content.append(part)

            elif math_delimiter.startswith('\\begin'):
                # Track brace depth for environments
                if part == '{':
                    brace_depth += 1
                    math_content.append(part)
                elif part == '}':
                    brace_depth -= 1
                    math_content.append(part)
                elif part.startswith('\\end'):
                    # Extract environment name from \end{name}
                    end_match = re.match(r'\\end\{([a-z]*\*?)\}', part, re.IGNORECASE)
                    begin_match = re.match(r'\\begin\{([a-z]*\*?)\}', math_delimiter, re.IGNORECASE)

                    if end_match and begin_match and end_match.group(1) == begin_match.group(1):
                        # Found matching \end
                        math_content.append(part)
                        full_math = ''.join(math_content)
                        token = f"@@{len(math_blocks)}@@"
                        math_blocks.append(full_math)
                        result.append(token)

                        # Reset state
                        math_start = None
                        math_delimiter = None
                        math_content = []
                        brace_depth = 0
                    else:
                        # Not matching environment
                        math_content.append(part)
                else:
                    math_content.append(part)

        else:
            # Not inside math - check for opening delimiters

            if part == '$$':
                # Start display math
                math_start = True
                math_delimiter = '$$'
                math_content = ['$$']

            elif part == '$':
                # Start inline math
                math_start = True
                math_delimiter = '$'
                math_content = ['$']

            elif part == '\\[':
                # Start LaTeX display math
                math_start = True
                math_delimiter = '\\['
                math_content = ['\\[']

            elif part.startswith('\\begin'):
                # Start LaTeX environment
                math_start = True
                math_delimiter = part
                math_content = [part]
                brace_depth = 0

            elif part.startswith('@@') and part.endswith('@@'):
                # Existing token - preserve it
                result.append(part)

            else:
                # Regular text
                result.append(part)

    # Handle unclosed math (treat as regular text)
    if math_start is not None:
        result.extend(math_content)

    tokenized_text = ''.join(result)
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


def restore_code_dollars(html):
    """
    Restore dollars in code spans after markdown processing.

    This reverses protect_code_dollars() by replacing ~D back to $.
    Must be called AFTER markdown rendering.

    Args:
        html: HTML with ~D placeholders in code spans

    Returns:
        str: HTML with $ restored in code spans
    """
    return html.replace('~D', '$')
