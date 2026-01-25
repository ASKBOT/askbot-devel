"""Utilities for working with HTML."""
import functools
import re
from urllib.parse import urlparse
import html.entities

import bleach
from bs4 import BeautifulSoup

from django.conf import settings as django_settings
from django.template.loader import get_template
from django.urls import reverse
from django.utils.html import strip_tags as strip_all_tags
from django.utils.html import urlize
from django.utils.translation import gettext as _

from askbot.conf import settings as askbot_settings
from askbot.utils.url_utils import get_login_url


# Additional tags/attributes needed for markdown conversion output
# These are required by:
# - Pygments syntax highlighting (span.class for color spans)
# - markdown-it code blocks (code.class for language-X classes)
# - Task lists (input.checkbox for [x] checkboxes)
#
# Note: Video embeds (iframes) are handled via token-based extraction in
# markup.py - iframes are inserted AFTER sanitization, so no iframe
# whitelist is needed here. This is more secure than allowing iframes.

# Users are allowed to enter these tags in Markdown input
ALLOWED_HTML_ELEMENTS = ('a', 'abbr', 'acronym', 'address', 'b', 'big',
    'blockquote', 'br', 'caption', 'center', 'cite', 'code', 'col',
    'colgroup', 'dd', 'del', 'dfn', 'dir', 'div', 'dl', 'dt', 'em',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'img', 'ins', 'kbd',
    'li', 'ol', 'p', 'pre', 'q', 's', 'samp', 'small', 'span', 'strike',
    'strong', 'sub', 'sup', 'table', 'tbody', 'td', 'tfoot', 'th', 'thead',
    'tr', 'tt', 'u', 'ul', 'var', 'param')

# Users are allowed to enter these html attributes in Markdown input
ALLOWED_HTML_ATTRIBUTES = {
    'a': ['href', 'title'],
    'abbr': ['title'],
    'acronym': ['title'],
    'td': ['colspan', 'rowspan'],
    'th': ['colspan', 'rowspan'],
    'col': ['span'],
    'colgroup': ['span'],
    'img': ['alt', 'src'],
    'blockquote': ['cite'],
    'del': ['cite', 'datetime'],
    'ins': ['cite', 'datetime'],
    'q': ['cite'],
}

MARKDOWN_EXTRA_TAGS = ('input',)
MARKDOWN_EXTRA_ATTRIBUTES = {
    'span': ['class'],  # For Pygments syntax highlighting
    'code': ['class'],  # For language-X classes from markdown-it
    'input': ['type', 'checked', 'disabled'],  # For task list checkboxes
}


def sanitize_html(html_string):
    """Sanitizes an HTML fragment from forbidden markup.

    Extends the base allowed tags/attributes from settings with
    markdown-specific needs:
    - span.class for Pygments syntax highlighting
    - code.class for markdown-it language classes
    - input[type,checked,disabled] for task list checkboxes

    Note: Video embeds (iframes) are NOT whitelisted here. They are
    handled via token-based extraction - iframes are inserted AFTER
    sanitization in markup.py/markdown_input_converter(). This is
    more secure than allowing arbitrary iframes through sanitization.
    """
    # Extend base allowed tags with markdown-specific ones
    tags = ALLOWED_HTML_ELEMENTS + MARKDOWN_EXTRA_TAGS

    # Merge base attributes with markdown-specific ones
    attributes = ALLOWED_HTML_ATTRIBUTES
    for tag, attrs in MARKDOWN_EXTRA_ATTRIBUTES.items():
        if tag in attributes:
            existing = set(attributes[tag])
            existing.update(attrs)
            attributes[tag] = list(existing)
        else:
            attributes[tag] = attrs

    return bleach.clean(html_string,
                        tags=tags,
                        attributes=attributes,
                        strip=True)


def sanitized(func):
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        return sanitize_html(func(*args, **kwargs))
    return wrapped


def absolutize_urls(html_string):
    """turns relative urls in <img> and <a> tags to absolute,
    starting with the ``askbot_settings.APP_URL``"""
    # temporal fix for bad regex with wysiwyg editor
    url_re1 = re.compile(r'(?P<prefix><img[^<]+src=)"(?P<url>/[^"]+)"', re.I)
    url_re2 = re.compile(r"(?P<prefix><img[^<]+src=)'(?P<url>/[^']+)'", re.I)
    url_re3 = re.compile(r'(?P<prefix><a[^<]+href=)"(?P<url>/[^"]+)"', re.I)
    url_re4 = re.compile(r"(?P<prefix><a[^<]+href=)'(?P<url>/[^']+)'", re.I)
    base_url = site_url('')  # important to have this without the slash
    img_replacement = rf'\g<prefix>"{base_url}/\g<url>"'
    replacement = rf'\g<prefix>"{base_url}\g<url>"'
    html_string = url_re1.sub(img_replacement, html_string)
    html_string = url_re2.sub(img_replacement, html_string)
    html_string = url_re3.sub(replacement, html_string)
    # temporal fix for bad regex with wysiwyg editor
    return url_re4.sub(replacement, html_string)\
        .replace(f'{base_url}//', f'{base_url}/')


def get_word_count(html_string):
    return len(strip_all_tags(html_string).split())


def format_url_replacement(url, text):
    url = url.strip()
    text = text.strip()
    url_domain = urlparse(url).netloc
    if url and text and url_domain != text and url != text:
        return f'{url} ({text})'
    return url or text or ''


@sanitized
def urlize_html(html_string, trim_url_limit=40):
    """will urlize html, while ignoring link
    patterns inside anchors, <pre> and <code> tags
    """
    soup = BeautifulSoup(html_string, 'html5lib')
    extract_nodes = []
    for node in soup.findAll(text=True):
        parent_tags = [p.name for p in node.parents]
        skip_tags = ['a', 'img', 'pre', 'code']
        if set(parent_tags) & set(skip_tags):
            continue

        # bs4 is weird, so we work around to replace nodes
        # maybe there is a better way though
        urlized_text = urlize(node, trim_url_limit=trim_url_limit)
        if str(node) == urlized_text:
            continue

        sub_soup = BeautifulSoup(urlized_text, 'html5lib')
        contents = sub_soup.find('body').contents
        num_items = len(contents)
        for _idx in range(num_items):
            # there is strange thing in bs4, can't iterate
            # as the tag seemingly can't belong to >1 soup object
            child = contents[0]  # always take first element
            # insure that text nodes are sandwiched by space
            have_string = (not hasattr(child, 'name'))
            if have_string:
                node.insert_before(soup.new_string(' '))
            node.insert_before(child)
            if have_string:
                node.insert_before(soup.new_string(' '))

        extract_nodes.append(node)

    # extract the nodes that we replaced
    for node in extract_nodes:
        node.extract()

    result = str(soup.find('body').renderContents(), 'utf8')
    if html_string.endswith('\n') and not result.endswith('\n'):
        result += '\n'

    return result


@sanitized
def replace_links_with_text(html_string):
    """any absolute links will be replaced with the
    url in plain text, same with any img tags
    """
    soup = BeautifulSoup(html_string, 'html5lib')
    abs_url_re = r'^http(s)?://'

    images = soup.find_all('img')
    for image in images:
        url = image.get('src', '')
        text = image.get('alt', '')
        if url == '' or re.match(abs_url_re, url):
            image.replaceWith(format_url_replacement(url, text))

    links = soup.find_all('a')
    for link in links:
        url = link.get('href', '')
        text = ''.join(link.text) or ''

        if text == '':#this is due to an issue with url inlining in comments
            link.replaceWith('')
        elif url == '' or re.match(abs_url_re, url):
            link.replaceWith(format_url_replacement(url, text))

    return str(soup.find('body').renderContents(), 'utf-8')


def get_text_from_html(html_text):
    """Returns the content part from an HTML document
    retains links and references to images and line breaks.
    """
    soup = BeautifulSoup(html_text, 'html5lib')

    # replace <a> links with plain text
    links = soup.find_all('a')
    for link in links:
        url = link.get('href', '')
        text = ''.join(link.text) or ''
        link.replaceWith(format_url_replacement(url, text))

    #replace <img> tags with plain text
    images = soup.find_all('img')
    for image in images:
        url = image.get('src', '')
        text = image.get('alt', '')
        image.replaceWith(format_url_replacement(url, text))

    #extract and join phrases
    body_element = soup.find('body')

    def filter_func(string):
        return bool(string.strip())

    phrases = [s.strip() for s in list(filter(filter_func, body_element.get_text().split('\n')))]
    return '\n\n'.join(phrases)


@sanitized
def strip_tags(html_string, tags=None):
    """strips tags from given html output"""
    #a corner case
    if html_string.strip() == '':
        return html_string

    assert tags is not None

    soup = BeautifulSoup(html_string, 'html5lib')
    for tag in tags:
        tag_matches = soup.find_all(tag)
        list(map(lambda v: v.replaceWith(''), tag_matches))
    return str(soup.find('body').renderContents(), 'utf-8')


def has_moderated_tags(html_string):
    """True, if html contains tags subject to moderation
    (images and/or links)"""
    soup = BeautifulSoup(html_string, 'html5lib')
    if askbot_settings.MODERATE_LINKS:
        links = soup.find_all('a')
        if links:
            return True

    if askbot_settings.MODERATE_IMAGES:
        images = soup.find_all('img')
        if images:
            return True

    return False


@sanitized
def moderate_tags(html_string):
    """replaces instances of <a> and <img>
    with "item in moderation" alerts
    """
    soup = BeautifulSoup(html_string, 'html5lib')
    replaced = False
    if askbot_settings.MODERATE_LINKS:
        links = soup.find_all('a')
        if links:
            template = get_template('widgets/moderated_link.html')
            aviso = BeautifulSoup(template.render(), 'html5lib').find('body')
            list(map(lambda v: v.replaceWith(aviso), links))
            replaced = True

    if askbot_settings.MODERATE_IMAGES:
        images = soup.find_all('img')
        if images:
            template = get_template('widgets/moderated_link.html')
            aviso = BeautifulSoup(template.render(), 'html5lib').find('body')
            list(map(lambda v: v.replaceWith(aviso), images))
            replaced = True

    if replaced:
        return str(soup.find('body').renderContents(), 'utf-8')

    return html_string


def site_url(url):
    base_url = urlparse(askbot_settings.APP_URL or 'http://localhost/')
    return base_url.scheme + '://' + base_url.netloc + url


def internal_link(url_name, title, kwargs=None, anchor=None, absolute=False):
    """returns html for the link to the given url
    todo: may be improved to process url parameters, keyword
    and other arguments

    link url does not have domain
    """
    url = reverse(url_name, kwargs=kwargs)
    if anchor:
        url += '#' + anchor
    if absolute:
        url = site_url(url)
    return f'<a href="{url}">{title}</a>'


def site_link(url_name, title, kwargs=None, anchor=None):
    """same as internal_link, but with the site domain"""
    return internal_link(
        url_name, title, kwargs=kwargs, anchor=anchor, absolute=True
    )


def get_login_link(text=None):
    text = text or _('please login')
    url = get_login_url()
    return f'<a href="{url}">{text}</a>'


def get_visible_text(html_string):
    """returns visible text from html
    http://stackoverflow.com/a/19760007/110274
    """
    soup = BeautifulSoup(html_string, 'html5lib')
    for item in soup(['style', 'script', '[document]', 'head', 'title']):
        item.extract()
    return soup.get_text()


def unescape(text):
    """source: http://effbot.org/zone/re-sub.htm#unescape-html
    Removes HTML or XML character references and entities from a text string.
    @param text The HTML (or XML) source text.
    @return The plain text, as a Unicode string, if necessary.
    """
    def fixup(match):
        text = match.group(0)
        if text[:2] == "&#":
            # character reference
            try:
                if text[:3] == "&#x":
                    return chr(int(text[3:-1], 16))
                return chr(int(text[2:-1]))
            except ValueError:
                pass
        else:
            # named entity
            try:
                text = chr(html.entities.name2codepoint[text[1:-1]])
            except KeyError:
                pass
        return text  # leave as is
    return re.sub(r'&#?\w+;', fixup, text)
