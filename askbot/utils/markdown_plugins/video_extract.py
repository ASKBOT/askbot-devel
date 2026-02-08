"""
Token-based video extraction for safe post-sanitization embedding.

Extracts video embed syntax (@[service](id) or @[service](id "title")) before
markdown processing, replaces with tokens, then restores as clickable link HTML
after sanitization. Clicking the link opens a modal video player.

This prevents the need to whitelist iframes in the sanitizer while still
supporting video embeds from trusted services.

Pattern based on: askbot/utils/markdown_plugins/math_extract.py
"""

import html
import re


# Supported video services with embed URLs
VIDEO_SERVICES = {
    'youtube': {
        'url': 'https://www.youtube.com/embed/{0}',
    },
    'vimeo': {
        'url': 'https://player.vimeo.com/video/{0}',
    },
    'dailymotion': {
        'url': 'https://www.dailymotion.com/embed/video/{0}',
    },
}

# Pattern to match video embed syntax: @[service](video_id) or @[service](video_id "title")
# Captures: service name, video ID, optional title
VIDEO_EMBED_PATTERN = re.compile(
    r'@\[([a-zA-Z]+)\]\(([a-zA-Z0-9_-]+)(?:\s+"([^"]*)")?\)'
)

# Valid video ID pattern (alphanumeric, dashes, underscores)
VIDEO_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')


def extract_video_embeds(text):
    """
    Extract video embed syntax and replace with tokens.

    Finds all @[service](video_id) or @[service](video_id "title") patterns,
    validates them, and replaces with @@VIDEOn@@ tokens.

    Args:
        text: Markdown source text

    Returns:
        tuple: (tokenized_text, video_blocks)
        - tokenized_text: Text with video embeds replaced by @@VIDEOn@@ tokens
        - video_blocks: List of dicts with 'service', 'id', and 'title' keys
    """
    video_blocks = []

    def replace_video(match):
        service = match.group(1).lower()
        video_id = match.group(2)
        title = match.group(3)  # May be None

        # Validate service
        if service not in VIDEO_SERVICES:
            # Unknown service, leave as-is
            return match.group(0)

        # Validate video ID
        if not VIDEO_ID_PATTERN.match(video_id):
            # Invalid video ID, leave as-is
            return match.group(0)

        # Store video info and return token
        token_index = len(video_blocks)
        video_blocks.append({
            'service': service,
            'id': video_id,
            'title': title,
        })
        return f'@@VIDEO{token_index}@@'

    tokenized_text = VIDEO_EMBED_PATTERN.sub(replace_video, text)
    return tokenized_text, video_blocks


def render_video_link(service, video_id, title=None):
    """
    Render a video as a clickable link that opens a modal player.

    Args:
        service: Video service name (youtube, vimeo, dailymotion)
        video_id: Video ID for the service
        title: Optional video title

    Returns:
        str: HTML for clickable video link, or None if service not supported
    """
    if service not in VIDEO_SERVICES:
        return None

    # Escape title for safe inclusion in HTML attributes and content
    escaped_title = html.escape(title) if title else None

    # Build display text: "(Video ▶)" or '(Video "Title" ▶)'
    if escaped_title:
        display_text = f'(Video "{escaped_title}" <i class="fa fa-play-circle"></i>)'
    else:
        display_text = '(Video <i class="fa fa-play-circle"></i>)'

    # Build data attributes
    title_attr = f' data-video-title="{escaped_title}"' if escaped_title else ''

    return (
        f'<span class="video-link video-link-{service}">'
        f'<a href="#" class="js-video-link" '
        f'data-video-service="{service}" '
        f'data-video-id="{video_id}"'
        f'{title_attr}>'
        f'{display_text}'
        f'</a>'
        f'</span>'
    )


def restore_video_embeds(html_content, video_blocks):
    """
    Restore video tokens to clickable link HTML.

    Replaces @@VIDEOn@@ tokens with clickable video links that open
    a modal player when clicked. Only creates links for whitelisted services.

    Args:
        html_content: Sanitized HTML with @@VIDEOn@@ tokens
        video_blocks: List of dicts with 'service', 'id', and 'title' keys

    Returns:
        str: HTML with tokens replaced by video links
    """
    for i, video in enumerate(video_blocks):
        token = f'@@VIDEO{i}@@'

        link_html = render_video_link(
            video['service'],
            video['id'],
            video.get('title')
        )

        if link_html:
            html_content = html_content.replace(token, link_html)

    return html_content
