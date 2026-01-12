"""
Token-based video extraction for safe post-sanitization embedding.

Extracts video embed syntax (@[service](id)) before markdown processing,
replaces with tokens, then restores as safe iframe HTML after sanitization.

This prevents the need to whitelist iframes in the sanitizer while still
supporting video embeds from trusted services.

Pattern based on: askbot/utils/markdown_plugins/math_extract.py
"""

import re


# Supported video services with embed URLs and dimensions
VIDEO_SERVICES = {
    'youtube': {
        'url': 'https://www.youtube.com/embed/{0}',
        'width': 640,
        'height': 390,
    },
    'vimeo': {
        'url': 'https://player.vimeo.com/video/{0}',
        'width': 640,
        'height': 360,
    },
    'dailymotion': {
        'url': 'https://www.dailymotion.com/embed/video/{0}',
        'width': 640,
        'height': 360,
    },
}

# Pattern to match video embed syntax: @[service](video_id)
# Captures: service name, video ID
VIDEO_EMBED_PATTERN = re.compile(
    r'@\[([a-zA-Z]+)\]\(([a-zA-Z0-9_-]+)\)'
)

# Valid video ID pattern (alphanumeric, dashes, underscores)
VIDEO_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')


def extract_video_embeds(text):
    """
    Extract video embed syntax and replace with tokens.

    Finds all @[service](video_id) patterns, validates them,
    and replaces with @@VIDEOn@@ tokens.

    Args:
        text: Markdown source text

    Returns:
        tuple: (tokenized_text, video_blocks)
        - tokenized_text: Text with video embeds replaced by @@VIDEOn@@ tokens
        - video_blocks: List of dicts with 'service' and 'id' keys
    """
    video_blocks = []

    def replace_video(match):
        service = match.group(1).lower()
        video_id = match.group(2)

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
        })
        return f'@@VIDEO{token_index}@@'

    tokenized_text = VIDEO_EMBED_PATTERN.sub(replace_video, text)
    return tokenized_text, video_blocks


def restore_video_embeds(html, video_blocks):
    """
    Restore video tokens to iframe HTML.

    Replaces @@VIDEOn@@ tokens with safe iframe embed HTML.
    Only creates iframes for whitelisted services.

    Args:
        html: Sanitized HTML with @@VIDEOn@@ tokens
        video_blocks: List of dicts with 'service' and 'id' keys

    Returns:
        str: HTML with tokens replaced by iframe embeds
    """
    for i, video in enumerate(video_blocks):
        token = f'@@VIDEO{i}@@'

        service = video['service']
        video_id = video['id']

        # Get service config (already validated during extraction)
        config = VIDEO_SERVICES.get(service)
        if not config:
            # Safety check - should not happen if extraction worked
            continue

        # Build safe iframe HTML
        url = config['url'].format(video_id)
        width = config['width']
        height = config['height']

        iframe_html = (
            f'<div class="video-embed video-embed-{service}">'
            f'<div class="video-embed-wrapper">'
            f'<iframe '
            f'src="{url}" '
            f'frameborder="0" '
            f'allowfullscreen '
            f'loading="lazy"'
            f'></iframe>'
            f'</div>'
            f'</div>'
        )

        html = html.replace(token, iframe_html)

    return html
