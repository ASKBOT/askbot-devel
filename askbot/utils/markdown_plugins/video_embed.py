"""
Video embedding plugin for markdown-it-py.

Syntax:
    @[youtube](video_id)
    @[vimeo](video_id)
    @[dailymotion](video_id)

Renders as iframe embed for supported services.

Based on: https://github.com/CenterForOpenScience/markdown-it-video
"""

import re
from markdown_it import MarkdownIt
from markdown_it.rules_inline import StateInline


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


def video_embed_rule(state: StateInline, silent: bool) -> bool:
    """
    Parse video embed syntax: @[service](video_id)

    Returns True if pattern matches and token created.
    """
    pos = state.pos
    maximum = state.posMax

    # Must start with @[
    if state.src[pos:pos+2] != '@[':
        return False

    # Find closing ]
    service_start = pos + 2
    service_end = state.src.find(']', service_start)

    if service_end == -1 or service_end >= maximum:
        return False

    service = state.src[service_start:service_end].strip().lower()

    # Check if it's a supported service
    if service not in VIDEO_SERVICES:
        return False

    # Must have opening (
    if service_end + 1 >= maximum or state.src[service_end + 1] != '(':
        return False

    # Find closing )
    id_start = service_end + 2
    id_end = state.src.find(')', id_start)

    if id_end == -1 or id_end >= maximum:
        return False

    video_id = state.src[id_start:id_end].strip()

    # Validate video ID (alphanumeric, dashes, underscores)
    if not re.match(r'^[a-zA-Z0-9_-]+$', video_id):
        return False

    if not silent:
        token = state.push('video_embed', '', 0)
        token.meta = {
            'service': service,
            'id': video_id,
        }
        token.markup = state.src[pos:id_end+1]

    state.pos = id_end + 1
    return True


def render_video_embed(self, tokens, idx, options, env):
    """
    Render video embed token as iframe.
    """
    token = tokens[idx]
    service = token.meta['service']
    video_id = token.meta['id']

    config = VIDEO_SERVICES[service]
    url = config['url'].format(video_id)
    width = config['width']
    height = config['height']

    # Security: Only allow whitelisted domains
    # HTML escaping handled by renderer

    iframe = (
        f'<div class="video-embed video-embed-{service}">'
        f'<iframe '
        f'width="{width}" '
        f'height="{height}" '
        f'src="{url}" '
        f'frameborder="0" '
        f'allowfullscreen '
        f'loading="lazy"'
        f'></iframe>'
        f'</div>'
    )

    return iframe


def video_embed_plugin(md: MarkdownIt) -> MarkdownIt:
    """
    Plugin to enable video embedding in markdown.

    Usage:
        md = MarkdownIt()
        md.use(video_embed_plugin)
    """
    # Register inline rule before 'link' to give it priority
    md.inline.ruler.before('link', 'video_embed', video_embed_rule)

    # Register renderer
    md.add_render_rule('video_embed', render_video_embed)

    return md
