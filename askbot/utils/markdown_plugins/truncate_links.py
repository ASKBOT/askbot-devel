"""
Custom truncate links plugin for markdown-it-py.

Truncates auto-linkified URLs to a specified character limit and adds
a title attribute with the full URL for accessibility.

This plugin processes tokens created by the linkify plugin and:
1. Truncates display text of auto-linked URLs to prevent layout issues
2. Adds title attribute containing full URL (visible on hover, read by screen readers)
3. Uses Django's truncation algorithm for consistency

Example:
    Input (after linkify):
        <a href="https://github.com/example/very-long-repository-name">https://github.com/example/very-long-repository-name</a>

    Output (after truncation with limit=40):
        <a href="https://github.com/example/very-long-repository-name" title="https://github.com/example/very-long-repository-name">https://github.com/example/very-lon…</a>

Based on Django's urlize trim_url_limit functionality.
"""

from markdown_it import MarkdownIt
from markdown_it.rules_core import StateCore


def truncate_url_text(text, limit):
    """
    Truncate URL text using Django's algorithm.

    Args:
        text: URL text to truncate
        limit: Maximum length (including ellipsis)

    Returns:
        Truncated string with ellipsis, or original if under limit

    Uses Django's algorithm from django.utils.html.urlize:
        "%s…" % x[: max(0, limit - 1)]
    """
    if limit is None or limit <= 0 or len(text) <= limit:
        return text

    # Truncate to (limit - 1) chars and add ellipsis
    return f"{text[:max(0, limit - 1)]}…"


def truncate_linkify_urls(state: StateCore, trim_limit):
    """
    Traverse token tree and truncate auto-linkified URL display text.

    Only processes links created by the linkify plugin (markup='linkify').
    Adds title attribute with full URL for accessibility.

    Args:
        state: StateCore object from markdown-it
        trim_limit: Maximum character length for displayed URL text
    """
    if trim_limit is None or trim_limit <= 0:
        # Truncation disabled
        return

    for block_token in state.tokens:
        if block_token.type != 'inline' or not block_token.children:
            continue

        children = block_token.children
        i = 0

        while i < len(children):
            token = children[i]

            # Find link_open tokens created by linkify
            if (token.type == 'link_open' and
                token.markup == 'linkify'):

                # Get the href from attributes
                href = None
                if hasattr(token, 'attrs') and token.attrs:
                    if isinstance(token.attrs, dict):
                        href = token.attrs.get('href')
                    else:
                        # attrs might be list of [key, value] pairs
                        for attr in token.attrs:
                            if attr[0] == 'href':
                                href = attr[1]
                                break

                # Find the text token that follows (should be next token)
                if i + 1 < len(children) and children[i + 1].type == 'text':
                    text_token = children[i + 1]
                    original_text = text_token.content

                    # Truncate the display text if it exceeds the limit
                    if len(original_text) > trim_limit:
                        text_token.content = truncate_url_text(original_text, trim_limit)

                        # Add title attribute with full URL for accessibility
                        # Only add when truncated, so users can see the full URL on hover
                        if href:
                            if isinstance(token.attrs, dict):
                                token.attrs['title'] = href
                            else:
                                # Convert to dict for easier manipulation
                                attrs_dict = dict(token.attrs) if token.attrs else {}
                                attrs_dict['title'] = href
                                token.attrs = attrs_dict

            i += 1


def truncate_links_plugin(md: MarkdownIt, config: dict = None) -> MarkdownIt:
    """
    Plugin to truncate auto-linkified URLs.

    Args:
        md: MarkdownIt instance
        config: Dictionary with optional key:
            - trim_limit (int): Maximum URL display length (default: 40)

    Usage:
        md = MarkdownIt('commonmark', {'linkify': True})
        md.enable(['linkify'])
        md.use(truncate_links_plugin, {'trim_limit': 40})
    """
    config = config or {}
    trim_limit = config.get('trim_limit', 40)

    def truncate_links_core_rule(state: StateCore):
        truncate_linkify_urls(state, trim_limit)

    # Run after linkify to process its output
    md.core.ruler.after('linkify', 'truncate_linkify_urls', truncate_links_core_rule)

    return md
