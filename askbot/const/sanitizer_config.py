"""Sanitizer configuration constants (pure data, no imports).

Single source of truth for allowed HTML tags and attributes.
Used by both the Python sanitizer (askbot/utils/html.py) and
the JS build script (askbot/media/bin/sync_sanitize_config.py)
which generates the client-side DOMPurify config.
"""

# Users are allowed to enter these tags in Markdown input
ALLOWED_HTML_ELEMENTS = (
    # Core text formatting (from Stack Overflow)
    'a', 'b', 'blockquote', 'br', 'code', 'del', 'em',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'img',
    'kbd', 'li', 'ol', 'p', 'pre', 's', 'strike', 'strong',
    'sub', 'sup', 'ul',
    # Definition lists (SO allows)
    'dd', 'dl', 'dt',
    # Tables (SO markdown-only, we allow HTML)
    'table', 'tbody', 'td', 'th', 'thead', 'tr',
    # Collapsible sections (GitHub feature)
    'details', 'summary',
    # Required by Pygments syntax highlighting
    'span',
)

# Users are allowed to enter these html attributes in Markdown input
ALLOWED_HTML_ATTRIBUTES = {
    'a': ['href', 'title'],
    'td': ['colspan', 'rowspan'],
    'th': ['colspan', 'rowspan'],
    'img': ['alt', 'src'],
    'blockquote': ['cite'],
    'del': ['cite', 'datetime'],
}

# Additional tags/attributes needed for markdown conversion output
# These are required by:
# - Pygments syntax highlighting (span.class for color spans)
# - markdown-it code blocks (code.class for language-X classes)
# - Task lists (input.checkbox for [x] checkboxes)
#
# Note: Video embeds (iframes) are handled via token-based extraction in
# markup.py - iframes are inserted AFTER sanitization, so no iframe
# whitelist is needed here. This is more secure than allowing iframes.
MARKDOWN_EXTRA_TAGS = ('input',)
MARKDOWN_EXTRA_ATTRIBUTES = {
    'span': ['class'],  # For Pygments syntax highlighting
    'code': ['class'],  # For language-X classes from markdown-it
    'input': ['type', 'checked', 'disabled'],  # For task list checkboxes
    'ul': ['class'],  # For task list (contains-task-list)
    'li': ['class'],  # For task list (task-list-item)
}

# Tags to hide from the help panel (supported but not documented)
# These work but we simplify help by not listing them:
# - Tables: users should use markdown table syntax instead
# - span/input: internal use by Pygments and task lists
HIDDEN_HELP_HTML_ELEMENTS = (
    'table', 'tbody', 'td', 'th', 'thead', 'tr',
    'span', 'input',
)
