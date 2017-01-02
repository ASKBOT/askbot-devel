"""Utilities for working with HTML."""
import functools
import re
from urlparse import urlparse

from bs4 import BeautifulSoup
import html5lib
from html5lib import sanitizer, serializer, tokenizer, treebuilders,\
    treewalkers
import htmlentitydefs

from django.conf import settings as django_settings
from django.core.urlresolvers import reverse
from django.template.loader import get_template
from django.utils.html import strip_tags as strip_all_tags
from django.utils.html import urlize
from django.utils.translation import ugettext as _


ALLOWED_HTML_ELEMENTS = ('a', 'abbr', 'acronym', 'address', 'b', 'big',
        'blockquote', 'br', 'caption', 'center', 'cite', 'code', 'col',
        'colgroup', 'dd', 'del', 'dfn', 'dir', 'div', 'dl', 'dt', 'em', 'font',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'img', 'ins', 'kbd',
        'li', 'ol', 'p', 'pre', 'q', 's', 'samp', 'small', 'span', 'strike',
        'strong', 'sub', 'sup', 'table', 'tbody', 'td', 'tfoot', 'th', 'thead',
        'tr', 'tt', 'u', 'ul', 'var', 'param')


ALLOWED_HTML_ATTRIBUTES = ('abbr', 'align', 'alt', 'axis', 'border', 'class',
        'cellpadding', 'cellspacing', 'char', 'charoff', 'charset', 'cite',
        'cols', 'colspan', 'datetime', 'dir', 'frame', 'headers', 'height',
        'href', 'hreflang', 'hspace', 'lang', 'longdesc', 'name', 'nohref',
        'noshade', 'nowrap', 'rel', 'rev', 'rows', 'rowspan', 'rules', 'scope',
        'span', 'src', 'start', 'summary', 'title', 'type', 'valign', 'vspace',
        'width')


class HTMLSanitizerMixin(sanitizer.HTMLSanitizerMixin):
    allowed_css_properties = ()
    allowed_css_keywords = ()
    allowed_svg_properties = ()

    def __init__(self, *args, **kwargs):
        self.allowed_elements = tuple(getattr(django_settings,
                                           'ASKBOT_ALLOWED_HTML_ELEMENTS',
                                           ALLOWED_HTML_ELEMENTS
                                           ))

        self.allowed_attributes = tuple(getattr(django_settings,
                                           'ASKBOT_ALLOWED_HTML_ATTRIBUTES',
                                           ALLOWED_HTML_ATTRIBUTES
                                           ))


class HTMLSanitizer(tokenizer.HTMLTokenizer, HTMLSanitizerMixin):
    def __init__(self, stream, encoding=None, parseMeta=True, useChardet=True,
                 lowercaseElementName=True, lowercaseAttrName=True, **kwargs):
        tokenizer.HTMLTokenizer.__init__(self, stream, encoding, parseMeta,
                                         useChardet, lowercaseElementName,
                                         lowercaseAttrName, **kwargs)

    def __iter__(self):
        for token in tokenizer.HTMLTokenizer.__iter__(self):
            token = self.sanitize_token(token)
            if token:
                yield token


def sanitize_html(html):
    """Sanitizes an HTML fragment.
    from forbidden markup
    """
    p = html5lib.HTMLParser(tokenizer=HTMLSanitizer,
                            tree=treebuilders.getTreeBuilder("dom"))
    dom_tree = p.parseFragment(html)
    walker = treewalkers.getTreeWalker("dom")
    stream = walker(dom_tree)
    s = serializer.HTMLSerializer(omit_optional_tags=False,
                                  quote_attr_values=True)
    output_generator = s.serialize(stream)
    return u''.join(output_generator)


def sanitized(func):
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        return sanitize_html(func(*args, **kwargs))
    return wrapped


def absolutize_urls(html):
    """turns relative urls in <img> and <a> tags to absolute,
    starting with the ``askbot_settings.APP_URL``"""
    # temporal fix for bad regex with wysiwyg editor
    url_re1 = re.compile(r'(?P<prefix><img[^<]+src=)"(?P<url>/[^"]+)"', re.I)
    url_re2 = re.compile(r"(?P<prefix><img[^<]+src=)'(?P<url>/[^']+)'", re.I)
    url_re3 = re.compile(r'(?P<prefix><a[^<]+href=)"(?P<url>/[^"]+)"', re.I)
    url_re4 = re.compile(r"(?P<prefix><a[^<]+href=)'(?P<url>/[^']+)'", re.I)
    base_url = site_url('')  # important to have this without the slash
    img_replacement = '\g<prefix>"%s/\g<url>"' % base_url
    replacement = '\g<prefix>"%s\g<url>"' % base_url
    html = url_re1.sub(img_replacement, html)
    html = url_re2.sub(img_replacement, html)
    html = url_re3.sub(replacement, html)
    # temporal fix for bad regex with wysiwyg editor
    return url_re4.sub(replacement, html)\
        .replace('%s//' % base_url, '%s/' % base_url)


def get_word_count(html):
    return len(strip_all_tags(html).split())


def format_url_replacement(url, text):
    url = url.strip()
    text = text.strip()
    url_domain = urlparse(url).netloc
    if url and text and url_domain != text and url != text:
        return '%s (%s)' % (url, text)
    return url or text or ''


@sanitized
def urlize_html(html, trim_url_limit=40):
    """will urlize html, while ignoring link
    patterns inside anchors, <pre> and <code> tags
    """
    soup = BeautifulSoup(html, 'html5lib')
    extract_nodes = list()
    for node in soup.findAll(text=True):
        parent_tags = [p.name for p in node.parents]
        skip_tags = ['a', 'img', 'pre', 'code']
        if set(parent_tags) & set(skip_tags):
            continue

        # bs4 is weird, so we work around to replace nodes
        # maybe there is a better way though
        urlized_text = urlize(node, trim_url_limit=trim_url_limit)
        if unicode(node) == urlized_text:
            continue

        sub_soup = BeautifulSoup(urlized_text, 'html5lib')
        contents = sub_soup.find('body').contents
        num_items = len(contents)
        for i in range(num_items):
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

    result = unicode(soup.find('body').renderContents(), 'utf8')
    if html.endswith('\n') and not result.endswith('\n'):
        result += '\n'

    return result


@sanitized
def replace_links_with_text(html):
    """any absolute links will be replaced with the
    url in plain text, same with any img tags
    """
    soup = BeautifulSoup(html, 'html5lib')
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

    return unicode(soup.find('body').renderContents(), 'utf-8')


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
    filter_func = lambda s: bool(s.strip())
    phrases = map(
        lambda s: s.strip(),
        filter(filter_func, body_element.get_text().split('\n'))
    )
    return '\n\n'.join(phrases)


@sanitized
def strip_tags(html, tags=None):
    """strips tags from given html output"""
    #a corner case
    if html.strip() == '':
        return html

    assert(tags != None)

    soup = BeautifulSoup(html, 'html5lib')
    for tag in tags:
        tag_matches = soup.find_all(tag)
        map(lambda v: v.replaceWith(''), tag_matches)
    return unicode(soup.find('body').renderContents(), 'utf-8')


def has_moderated_tags(html):
    """True, if html contains tags subject to moderation
    (images and/or links)"""
    from askbot.conf import settings
    soup = BeautifulSoup(html, 'html5lib')
    if settings.MODERATE_LINKS:
        links = soup.find_all('a')
        if links:
            return True

    if settings.MODERATE_IMAGES:
        images = soup.find_all('img')
        if images:
            return True

    return False


@sanitized
def moderate_tags(html):
    """replaces instances of <a> and <img>
    with "item in moderation" alerts
    """
    from askbot.conf import settings
    soup = BeautifulSoup(html, 'html5lib')
    replaced = False
    if settings.MODERATE_LINKS:
        links = soup.find_all('a')
        if links:
            template = get_template('widgets/moderated_link.html')
            aviso = BeautifulSoup(template.render(), 'html5lib').find('body')
            map(lambda v: v.replaceWith(aviso), links)
            replaced = True

    if settings.MODERATE_IMAGES:
        images = soup.find_all('img')
        if images:
            template = get_template('widgets/moderated_link.html')
            aviso = BeautifulSoup(template.render(), 'html5lib').find('body')
            map(lambda v: v.replaceWith(aviso), images)
            replaced = True

    if replaced:
        return unicode(soup.find('body').renderContents(), 'utf-8')

    return html


def site_url(url):
    from askbot.conf import settings
    base_url = urlparse(settings.APP_URL or 'http://localhost/')
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
    return '<a href="%s">%s</a>' % (url, title)


def site_link(url_name, title, kwargs=None, anchor=None):
    """same as internal_link, but with the site domain"""
    return internal_link(
        url_name, title, kwargs=kwargs, anchor=anchor, absolute=True
    )


def get_login_link(text=None):
    from askbot.utils.url_utils import get_login_url
    text = text or _('please login')
    return '<a href="%s">%s</a>' % (get_login_url(), text)


def get_visible_text(html):
    """returns visible text from html
    http://stackoverflow.com/a/19760007/110274
    """
    soup = BeautifulSoup(html, 'html5lib')
    [s.extract()
     for s in soup(['style', 'script', '[document]', 'head', 'title'])]
    return soup.get_text()


def unescape(text):
    """source: http://effbot.org/zone/re-sub.htm#unescape-html
    Removes HTML or XML character references and entities from a text string.
    @param text The HTML (or XML) source text.
    @return The plain text, as a Unicode string, if necessary.
    """
    def fixup(m):
        text = m.group(0)
        if text[:2] == "&#":
            # character reference
            try:
                if text[:3] == "&#x":
                    return unichr(int(text[3:-1], 16))
                else:
                    return unichr(int(text[2:-1]))
            except ValueError:
                pass
        else:
            # named entity
            try:
                text = unichr(htmlentitydefs.name2codepoint[text[1:-1]])
            except KeyError:
                pass
        return text  # leave as is
    return re.sub("&#?\w+;", fixup, text)
