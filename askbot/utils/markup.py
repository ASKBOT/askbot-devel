"""methods that make parsing of post inputs possible,
handling of markdown and additional syntax rules -
such as optional link patterns, video embedding and
Twitter-style @mentions"""

import base64
import hashlib
import io
import logging
import re

from django.utils.html import urlize
from django.utils.module_loading import import_string
from django.urls.exceptions import NoReverseMatch

from markdown_it import MarkdownIt
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from pygments import highlight as pygments_highlight
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import HtmlFormatter
from pygments.util import ClassNotFound

from askbot import const
from askbot.utils.markdown_plugins.video_extract import (
    extract_video_embeds, restore_video_embeds
)
from askbot.utils.markdown_plugins.link_patterns import link_patterns_plugin
from askbot.utils.markdown_plugins.truncate_links import truncate_links_plugin
from askbot.conf import settings as askbot_settings
from askbot.utils.file_utils import store_file
from askbot.utils.functions import split_phrases
from askbot.utils.html import sanitize_html
from askbot.utils.html import strip_tags

# URL taken from http://regexlib.com/REDetails.aspx?regexp_id=501
URL_RE = re.compile("((?<!(href|.src|data)=['\"])((http|https|ftp)\://([a-zA-Z0-9\.\-]+(\:[a-zA-Z0-9\.&amp;%\$\-]+)*@)*((25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9])\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9]|0)\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9]|0)\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[0-9])|localhost|([a-zA-Z0-9\-]+\.)*[a-zA-Z0-9\-]+\.(com|edu|gov|int|mil|net|org|biz|arpa|info|name|pro|aero|coop|museum|[a-zA-Z]{2}))(\:[0-9]+)*(/($|[a-zA-Z0-9\.\,\?\'\\\+&amp;%\$#\=~_\-]+))*))") # pylint: disable=line-too-long


def highlight_code(code, lang, attrs):
    """
    Syntax highlighting using Pygments.

    markdown-it-py's highlight callback should return just the inner HTML content.
    markdown-it wraps the result in <pre><code class="language-X">...</code></pre>.

    We use nowrap=True to get just the <span> elements from Pygments.
    The CSS styles target pre code spans for syntax coloring.

    Args:
        code: Source code string
        lang: Language identifier (e.g., 'python', 'javascript')
        attrs: Additional attributes (unused, for markdown-it compatibility)

    Returns:
        HTML string with syntax highlighting (just spans, no wrapper)
    """
    from html import escape

    if not lang:
        # No language specified, return escaped code (markdown-it wraps it)
        return escape(code)

    try:
        lexer = get_lexer_by_name(lang)
        formatter = HtmlFormatter(
            nowrap=True,  # Return just spans, no <div>/<pre> wrapper
            noclasses=False,  # Use CSS classes
        )
        highlighted = pygments_highlight(code, lexer, formatter)
        return highlighted
    except ClassNotFound:
        # Unknown language, try guessing
        try:
            lexer = guess_lexer(code)
            formatter = HtmlFormatter(nowrap=True, noclasses=False)
            return pygments_highlight(code, lexer, formatter)
        except Exception:  # pylint: disable=broad-except
            # Give up, return escaped code
            return escape(code)
    except Exception as e:  # pylint: disable=broad-except
        # Log error but don't break rendering
        logger = logging.getLogger('askbot.markdown')
        logger.warning(f"Pygments highlighting failed for lang={lang}: {e}")
        return escape(code)


# Singleton pattern - create converter once
_MD_CONVERTER = None

def get_md_converter():
    """
    Returns a configured instance of MarkdownIt.

    Converts markdown with extra features:
    * Tables (GFM-like preset)
    * Footnotes
    * Task lists
    * Syntax highlighting (Pygments)
    * Video embedding (@[youtube](id))
    * Custom link patterns (#bug123 -> links)
    * Code-friendly mode (disable underscore emphasis)
    * Linkify URLs (automatic URL detection with truncation)

    Uses singleton pattern for performance.
    """
    global _MD_CONVERTER

    if _MD_CONVERTER is not None:
        return _MD_CONVERTER

    # Create markdown-it instance with commonmark preset
    # Enable linkify for automatic URL detection
    md = MarkdownIt('commonmark', {'linkify': True, 'typographer': False})

    # Enable GFM features: tables and strikethrough
    md.enable(['table', 'strikethrough'])

    # Explicitly enable linkify feature for automatic URL detection
    md.enable('linkify')

    # Configure syntax highlighting
    md.options['highlight'] = highlight_code

    # Enable standard plugins
    md.use(footnote_plugin)
    md.use(tasklists_plugin)

    # Note: Video embedding is handled by extract/restore pattern in
    # markdown_input_converter() for security (iframes after sanitization)

    # Enable custom link patterns
    md.use(link_patterns_plugin, {
        'enabled': askbot_settings.ENABLE_AUTO_LINKING,
        'patterns': askbot_settings.AUTO_LINK_PATTERNS,
        'urls': askbot_settings.AUTO_LINK_URLS,
    })

    # Enable URL truncation for auto-linkified URLs
    # Truncates display text to prevent layout issues, adds title attribute for accessibility
    md.use(truncate_links_plugin, {
        'trim_limit': 40  # Match Django's urlize trim_url_limit
    })

    # Code-friendly mode: disable underscore emphasis, keep asterisk
    # This prevents issues with snake_case variables while preserving *italic* and **bold**
    # Note: MathJax does NOT need emphasis disabled - math is extracted to @@N@@ tokens
    # before markdown runs, so emphasis never touches math content
    if askbot_settings.MARKUP_CODE_FRIENDLY:
        from askbot.utils.markdown_plugins.asterisk_emphasis import asterisk_emphasis_plugin
        md.use(asterisk_emphasis_plugin)

    _MD_CONVERTER = md
    return _MD_CONVERTER


def reset_md_converter():
    """Reset the singleton converter (used in tests when settings change)"""
    global _MD_CONVERTER
    _MD_CONVERTER = None


def format_mention_in_html(mentioned_user):
    """formats mention as url to the user profile"""
    try:
        url = mentioned_user.get_profile_url()
        username = mentioned_user.username
        return '<a href="%s">@%s</a>' % (url, username)
    except NoReverseMatch:
        return ""


def extract_first_matching_mentioned_author(text, anticipated_authors):
    """matches beginning of ``text`` string with the names
    of ``anticipated_authors`` - list of user objects.
    Returns upon first match the first matched user object
    and the remainder of the ``text`` that is left unmatched"""

    if not text:
        return None, ''

    for author in anticipated_authors:
        if text.lower().startswith(author.username.lower()):
            ulen = len(author.username)
            if len(text) == ulen:
                text = ''
            elif text[ulen] in const.TWITTER_STYLE_MENTION_TERMINATION_CHARS:
                text = text[ulen:]
            else:
                # near miss, here we could insert a warning that perhaps
                # a termination character is needed
                continue
            return author, text
    return None, text


def extract_mentioned_name_seeds(text):
    """Returns list of strings that
    follow the '@' symbols in the text.
    The strings will be 10 characters long,
    or shorter, if the subsequent character
    is one of the list accepted to be termination
    characters.
    """
    extra_name_seeds = set()
    while '@' in text:
        pos = text.index('@')
        text = text[pos+1:]  # chop off prefix
        name_seed = ''
        for char in text:
            if char in const.TWITTER_STYLE_MENTION_TERMINATION_CHARS:
                extra_name_seeds.add(name_seed)
                name_seed = ''
                break
            if len(name_seed) > 10:
                extra_name_seeds.add(name_seed)
                name_seed = ''
                break
            if char == '@':
                if len(name_seed) > 0:
                    extra_name_seeds.add(name_seed)
                    name_seed = ''
                break
            name_seed += char
        if len(name_seed) > 0:
            # in case we run off the end of text
            extra_name_seeds.add(name_seed)

    return extra_name_seeds


def mentionize_text(text, anticipated_authors):
    """Returns a tuple of two items:
    * modified text where @mentions are
      replaced with urls to the corresponding user profiles
    * list of users whose names matched the @mentions
    """
    output = ''
    mentioned_authors = []
    while '@' in text:
        # the purpose of this loop is to convert any occurance of
        # '@mention ' syntax
        # to user account links leading space is required unless @ is the first
        # character in whole text, also, either a punctuation or
        # a ' ' char is required after the name
        pos = text.index('@')

        # save stuff before @mention to the output
        output += text[:pos]  # this works for pos == 0 too

        if len(text) == pos + 1:
            # finish up if the found @ is the last symbol
            output += '@'
            text = ''
            break

        if pos > 0:

            if text[pos-1] in const.TWITTER_STYLE_MENTION_TERMINATION_CHARS:
                # if there is a termination character before @mention
                # indeed try to find a matching person
                text = text[pos+1:]
                mentioned_author, text = \
                    extract_first_matching_mentioned_author(
                        text, anticipated_authors)
                if mentioned_author:
                    mentioned_authors.append(mentioned_author)
                    output += format_mention_in_html(mentioned_author)
                else:
                    output += '@'

            else:
                # if there isn't, i.e. text goes like something@mention,
                # do not look up people
                output += '@'
                text = text[pos+1:]
        else:
            # do this if @ is the first character
            text = text[1:]
            mentioned_author, text = \
                extract_first_matching_mentioned_author(
                    text, anticipated_authors)
            if mentioned_author:
                mentioned_authors.append(mentioned_author)
                output += format_mention_in_html(mentioned_author)
            else:
                output += '@'

    # append the rest of text that did not have @ symbols
    output += text
    return mentioned_authors, output


def plain_text_input_converter(text):
    """plain text to html converter"""
    return sanitize_html(urlize('<p>' + text + '</p>'))


def markdown_input_converter(text):
    """
    Markdown to HTML converter with MathJax and video embed support.

    Implements token-based extraction for safe content handling:
    1. Extract video embeds to tokens (@[youtube](id) → @@VIDEO0@@)
    2. MathJax preprocessing (protect code dollars, extract math, escape dollars)
    3. Standard markdown processing
    4. MathJax postprocessing (restore code dollars, restore math)
    5. Sanitize HTML (no iframes allowed - they're still tokens!)
    6. Restore video tokens to iframes (safe - after sanitization)
    """
    # Get converter lazily to avoid accessing settings at module load time
    md = get_md_converter()

    # Phase 1: Extract video embeds to tokens (before any processing)
    # This happens BEFORE sanitization, tokens restored AFTER
    video_blocks = []
    if askbot_settings.ENABLE_VIDEO_EMBEDDING:
        text, video_blocks = extract_video_embeds(text)

    # MathJax preprocessing (only if MathJax is enabled)
    math_blocks = []
    if askbot_settings.ENABLE_MATHJAX:
        from askbot.utils.markdown_plugins.math_extract import (
            extract_math, restore_math, protect_code_dollars, restore_code_dollars
        )
        from askbot.utils.markdown_plugins.dollar_escape import escape_dollars

        # Phase 2a: Protect $ in code spans
        text = protect_code_dollars(text)

        # Phase 2b: Extract math to tokens
        text, math_blocks = extract_math(text)

        # Phase 2c: Escape dollars in text regions
        text = escape_dollars(text)

    # Phase 3: Standard markdown processing
    html = md.render(text)

    # MathJax postprocessing (only if MathJax is enabled)
    if askbot_settings.ENABLE_MATHJAX:
        from askbot.utils.markdown_plugins.math_extract import restore_math, restore_code_dollars

        # Phase 4a: Restore code dollars
        html = restore_code_dollars(html)

        # Phase 4b: Restore math from tokens
        if math_blocks:
            html = restore_math(html, math_blocks)

    # Phase 5: Sanitize HTML to prevent XSS and enforce allowed tags/attributes
    # Video tokens (@@VIDEO0@@) pass through safely as plain text
    html = sanitize_html(html)

    # Phase 6: Restore video tokens to iframes (AFTER sanitization)
    # This is the key security improvement - iframes are never subject to sanitization
    if video_blocks:
        html = restore_video_embeds(html, video_blocks)

    return html


def convert_text(text):
    parser_type = askbot_settings.EDITOR_TYPE
    if parser_type == 'plain-text':
        return plain_text_input_converter(text)
    if parser_type == 'markdown':
        return markdown_input_converter(text)
    raise NotImplementedError


def find_forbidden_phrase(text):
    """returns string or None"""
    def norm_text(text_string):
        return ' '.join(text_string.split()).lower()

    forbidden_phrases = askbot_settings.FORBIDDEN_PHRASES.strip()
    text = norm_text(text)
    if forbidden_phrases:
        phrases = split_phrases(forbidden_phrases)
        for phrase in phrases:
            phrase = norm_text(phrase)
            if phrase in text:
                return phrase
    return None

def markdown_is_line_empty(line): #pylint: disable=missing-docstring
    assert('\n' not in line)
    return len(line.strip()) == 0

def markdown_force_linebreaks(text):
    """Appends a linebreak to all newlines inside the paragraphs"""
    lines = text.split('\n')
    num_lines = len(lines)
    result = []
    for idx in range(num_lines):
        cline = lines[idx]
        if idx + 1 == num_lines:
            result.append(cline)
            break

        if markdown_is_line_empty(cline):
            result.append(cline)
            continue

        nline = lines[idx + 1]
        if markdown_is_line_empty(nline):
            result.append(cline)
            continue

        cline = cline.rstrip() + '  ' # appends two empty spaces to force newline
        result.append(cline)

    return '\n'.join(result)


MARKDOWN_INLINE_IMAGE_RE = '\!\[([^]]*)\]\(data:image/([^)]*)\)'

def markdown_extract_inline_images(text):
    """
    * extracts inline images from markdown text
    * places image as file in the media storage
    * replaces the inline image markup with the linked image markup
    * returns modified markdown text
    """
    def repl_func(match):
        """For the given match, extracts the
        image content and stores in the file storage
        Returns markdown for the linked uploaded file."""
        file_display_name = match.group(1) or 'uploaded file'
        b64_encoded_img = match.group(2).split(',')[1]
        file_ext = match.group(2).split(',')[0].split(';')[0]
        img_bytes = base64.b64decode(b64_encoded_img)
        img_file = io.BytesIO(img_bytes)
        file_name = hashlib.md5(img_bytes).hexdigest() + '.' + file_ext
        file_url = store_file(file_name, img_file)
        return f'![{file_display_name}]({file_url})'

    return re.sub(MARKDOWN_INLINE_IMAGE_RE, repl_func, text, flags=re.MULTILINE)


def markdown_split_paragraphs(text):
    """
    Returns list of paragraphs.
    """
    pars = []
    cpar_lines = []
    for line in text.split('\n'):
        if re.match(r' *$', line):
            if cpar_lines:
                cpar = '\n'.join(cpar_lines)
                pars.append(cpar)
            cpar_lines = []
            continue

        cpar_lines.append(line)

    if cpar_lines:
        cpar = '\n'.join(cpar_lines)
        pars.append(cpar)

    return pars
