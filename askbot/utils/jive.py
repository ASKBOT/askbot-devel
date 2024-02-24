#!/usr/bin/env python
# Copyright (c) Askbot S.p.A. 2013
# License: MIT (http://www.opensource.org/licenses/mit-license.php)
r"""Converter of Jive markup to markdown,
some parts and the method are based on the
python-markdown2 library.
"""
__version_info__ = (0, 0, 0)
__version__ = '.'.join([str(v) for v in __version_info__])
__author__ = "Evgeny Fadeev"

from html import escape
import sys
#from pprint import pprint
import re
import logging
try:
    from hashlib import md5
except ImportError:
    from md5 import md5
from random import randint
import codecs

#---- Python version compat
def _unicode_decode(s, encoding, errors='strict'):
    return s.decode(encoding, errors)


#---- globals

DEBUG = False
log = logging.getLogger("jiveMarkup")

DEFAULT_TAB_WIDTH = 4

"""
Samples from the source (jive_url prefix is stripped)
/message.jspa?messageID=8477
/thread.jspa?messageID=10175&amp;#10175
/thread.jspa?messageID=10662#10662
/thread.jspa?messageID=11058
/thread.jspa?threadID=1888&amp;tstart=210
/thread.jspa?threadID=3087&amp;tstart=-258
"""
internal_link_pattern  = r"""(?:message|thread)   #junk
                   \.jspa\?
                   (message|thread)   #link type
                   ID=(\d+)           #either post or thread id
                   (?:(?:&amp;)?\#\d+|&amp;tstart=-?\d+)?  #junk
                """
internal_link_re = re.compile(internal_link_pattern, re.X)


try:
    import uuid
except ImportError:
    SECRET_SALT = str(randint(0, 1000000)).encode("utf-8")
else:
    SECRET_SALT = str(uuid.uuid4()).encode("utf-8")

def _hash_ascii(s: bytes) -> str:
    #return md5(s).hexdigest()   # Markdown.pl effectively does this.
    return 'md5-' + md5(SECRET_SALT + s).hexdigest()
def _hash_text(s: str) -> str:
    return 'md5-' + md5(SECRET_SALT + s.encode("utf-8")).hexdigest()

def _regularize_eols(text):
    """strip eols and replace consecutive eols with single"""
    text = re.sub(r'\n{2,}', '\n', text)
    return text.strip('\n')

class JiveConverter:
    """converts Jive Markup into HTML"""

    def __init__(self):
        self.tab_width = 4
        self._blocks = dict()
        self._outdent_re = re.compile(r'^(\t|[ ]{1,%d})' % self.tab_width, re.M)
        self.list_level = 0

    def reset(self):
        """erase the memory of html blocks"""
        self._blocks = dict()
        self.list_level = 0

    _ws_only_line_re = re.compile(r"^[ \t]+$", re.M)
    def convert(self, text):
        """main function that converts markup --> html.
        Strategy: go line by line then parse lines.
        Determine state (e.g. in quote, etc.) then process
        text according to current state.
        """
        self.reset()
        text = self._normalize(text)
        text = self._run_block_gamut(text)
        text = self._unhash_html_blocks(text)
        html = _regularize_eols(text)#maybe prettyfy
        return html

    def _hashed(self, html):
        """hashes html block and returns the hash surrounded by eols"""
        html_hash = _hash_text(html)
        self._blocks[html_hash] = html
        return '\n\n' + html_hash + '\n\n'

    def _normalize(self, text):
        if not isinstance(text, str):
            #TODO: perhaps shouldn't presume UTF-8 for string input?
            text = str(text, 'utf-8')

        #escape any html special chars globally as in jive they can be anywhere
        text = escape(text, quote=False)
        #delete "Edited by" comments
        text = re.sub(r'\n\s*Edited by:[^\n]*(\n|$)', '\n', text)
        # Standardize line endings:
        text = re.sub("\r\n|\r", "\n", text)
        # Convert all tabs to spaces.
        text = self._detab(text)
        # Strip any lines consisting only of spaces and tabs.
        # This makes subsequent regexen easier to write, because we can
        # match consecutive blank lines with /\n+/ instead of something
        # contorted like /[ \t]*\n+/ .
        text = self._ws_only_line_re.sub("", text)
        # must end with a bunch of empty lines
        return text + '\n\n'

    # Cribbed from a post by Bart Lateur:
    # <http://www.nntp.perl.org/group/perl.macperl.anyperl/154>
    _detab_re = re.compile(r'(.*?)\t', re.M)
    def _detab_sub(self, match):
        g1 = match.group(1)
        return g1 + (' ' * (self.tab_width - len(g1) % self.tab_width))

    def _detab(self, text):
        r"""Remove (leading?) tabs from a file.

            >>> m = JiveConverter()
            >>> m._detab("\tfoo")
            '    foo'
            >>> m._detab("  \tfoo")
            '    foo'
            >>> m._detab("\t  foo")
            '      foo'
            >>> m._detab("  foo")
            '  foo'
            >>> m._detab("  foo\n\tbar\tblam")
            '  foo\n    bar blam'
        """
        if '\t' not in text:
            return text
        return self._detab_re.subn(self._detab_sub, text)[0]

    def _run_block_gamut(self, text):
        # These are all the transformations that form block-level
        # tags like paragraphs, headers, and list items.
        text = self._do_headers(text)
        text = self._do_horizontal_rules(text)
        text = self._do_lists(text)
        text = self._do_code_blocks(text)
        text = self._do_block_quotes(text)
        return self._form_paragraphs(text)

    def _run_span_gamut(self, text):
        # These are all the transformations that occur *within* block-level
        # tags like paragraphs, headers, and list items.

        # Process anchor and image tags.
        text = self._do_links(text)

        text = self._do_inline_styling(text)

        # Do hard breaks:
        return re.sub(r" {2,}\n", "\n\n", text)

    def _is_auto_link(self, s):
        if ':' in s and self._auto_link_re.match(s):
            return True
        elif '@' in s and self._auto_email_link_re.match(s):
            return True
        return False

    def _unhash_html_blocks(self, text):
        for hash, html in list(self._blocks.items()):
            text = text.replace(hash, html)
        return text

    _email_pattern = r'[-.\w]+\@[-\w]+(?:\.[-\w]+)*\.[a-z]+'
    _url_pattern = "((http|https|ftp)\://([a-zA-Z0-9\.\-]+(\:[a-zA-Z0-9\.&amp;%\$\-]+)*@)*((25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9])\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9]|0)\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9]|0)\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[0-9])|localhost|([a-zA-Z0-9\-]+\.)*[a-zA-Z0-9\-]+\.(com|edu|gov|int|mil|net|org|biz|arpa|info|name|pro|aero|coop|museum|[a-zA-Z]{2}))(\:[0-9]+)*(/($|[a-zA-Z0-9\.\,\?\'\\\+&amp;%\$#\=~_\-]+))*)"
    _email_re = re.compile(_email_pattern, re.I | re.U)
    _url_re = re.compile(_url_pattern)
    _hypertext_link_re1 = re.compile(r'\[(.*?)\]')
    def _hypertext_link_sub1(self, match):
        link_bits = match.group(1).split('|')
        num_bits = len(link_bits)
        if num_bits == 0:
            return match.group(0)#return the whole thing
        elif num_bits == 1:
            link = link_bits[0]
            if self._url_re.match(link) or not self._email_re.match(link):
                return f'<a href="{link}">{link}</a>'
        elif num_bits in (2, 3):
            #if self._url_re.match(link_bits[1]):
            if num_bits == 2:
                return f'<a href="{link_bits[1]}">{link_bits[0]}</a>'
            else:
                bits = link_bits
                return f'<a href="{bits[1]}" title="{bits[2]}">{bits[0]}</a>'
        return '[' + '|'.join(link_bits) + ']'

    _hypertext_link_re2 = re.compile(r'\[url\]%s\[/url\]' % _url_pattern)
    def _hypertext_link_sub2(self, match):
        """convert to plain autolink"""
        link = match.group(1)
        return link

    def _do_hypertext_links(self, text):
        """
        """
        #now do these:
        #[Пример сайта|http://www.example.com|Образец подсказки по сайту]
        #[Пример сайта|http://www.example.com]
        #[http://www.example.com]
        return self._hypertext_link_re1.sub(self._hypertext_link_sub1, text)

    def _image_link_sub(self, match):
        src = match.group(1)
        return '<img src="%s"/>' % src

    _image_link_re = re.compile(r'!(.*?)!')
    def _do_image_links(self, text):
        """
        !http://../post.gif!
        !post.gif!
        """
        return self._image_link_re.sub(self._image_link_sub, text)

    def _do_links(self, text):
        """
        now do only image and href links
        todo: more link types https://community.jivesoftware.com/markuphelpfull.jspa
        """
        #do this first [url]http://...[/url] --> plain http://...
        text = self._hypertext_link_re2.sub(self._hypertext_link_sub2, text)
        text = self._do_hypertext_links(text)
        text = self._do_image_links(text)
        #now take care of plain links
        return self._do_auto_links(text)

    _h_re = re.compile(r'''
        ^h([1-6])\. # \1 = level
        [ \t]*
        (.+?)       # \2 = Header text
        \n+
        ''', re.X | re.M)
    def _h_sub(self, match):
        n = match.group(1)
        text = self._run_span_gamut(match.group(2))
        html = f'<h{n}>{text}</h{n}>'
        return self._hashed(html)

    def _do_headers(self, text):
        """convert
        h1. Header1
        to <hx></hx>
        """
        return self._h_re.sub(self._h_sub, text)

    def _code_block_sub(self, match):
        code_block = match.group(1).strip('\n')
        return self._hashed('<pre><code>%s</code></pre>' % code_block)

    def _do_code_blocks(self, text):
        """Process Markdown `<pre><code>` blocks."""
        code_block_re = re.compile(r'{code(?:\:\w+)?}(.*?){code}', re.S)
        return code_block_re.sub(self._code_block_sub, text)

    _bold_re = re.compile(r"\*(?=\S)(.+?[*_]*)(?<=\S)\*")
    _italics_re = re.compile(r"\+(?=\S)(.+?)(?<=\S)\+")
    _underline_re = re.compile(r"\_(?=\S)(.+?[*_]*)(?<=\S)\_")
    _super_re = re.compile(r"\^(?=\S)(.+?)(?<=\S)\^")
    _sub_re = re.compile(r"\~(?=\S)(.+?)(?<=\S)\~")
    _strike_re = re.compile(r"--(?=\S)(.+?)(?<=\S)--")
    def _do_inline_styling(self, text):
        text = self._bold_re.sub(r'<strong>\1</strong>', text)
        text = self._italics_re.sub(r'<em>\1</em>', text)
        text = self._underline_re.sub(r'<span class="underline">\1</span>', text)
        text = self._super_re.sub(r'<sup>\1</sup>', text)
        text = self._sub_re.sub(r'<sub>\1</sub>', text)
        return self._strike_re.sub(r'<strike>\1</strike>', text)

    def _block_quote_sub0(self, match):
        bq = match.group(1)
        #span gamut on this type of quote
        html = '<blockquote><p>%s</p></blockquote>' % self._run_span_gamut(bq)
        return self._hashed(html)

    _block_quote_re0 = re.compile(r'^bq. (.*?)\n', re.M)
    def _do_block_quotes0(self, text):
        """single line block quotes"""
        return self._block_quote_re0.sub(self._block_quote_sub0, text)

    def _block_quote_sub1(self, match):
        num_groups = len(match.groups())

        if num_groups == 1:
            author = None
            text = match.group(1)
        else:
            author = match.group(1)
            text = match.group(2)

        html = ''
        if author:
            #todo: add i18n
            html = '<span class="quote-header">%s wrote:</span><br/>\n\n' % author

        html += self._run_block_gamut(text)
        return self._hashed('<blockquote>%s</blockquote>' % html)

    _block_quote_regexes1 = (
        re.compile(r'^{quote}(.*?){quote}', re.M | re.S),
        re.compile(r'^\[quote=([^]]+)\](.*?){quote}', re.M | re.S)
    )
    def _do_block_quotes1(self, text):
        """regexable multiline block quotes"""
        for regex in self._block_quote_regexes1:
            text = regex.sub(self._block_quote_sub1, text)
        return text

    _block_quote_sub2_re = re.compile('^&gt; ?', re.M | re.S)
    def _block_quote_sub2(self, match):
        title = match.group(1)
        text = match.group(2)
        text = self._block_quote_sub2_re.sub('', text)
        html = '<span class="quote-header">%s:</span><br/>\n\n' % title
        html = html + self._run_block_gamut(text)
        return self._hashed('<blockquote>%s</blockquote>' % html)

    _block_quote_re2 = re.compile(
        r'^&gt; {quote:title\=(.+?):}{quote}\n((:?&gt;(:? .*?)?\n)+)',
        re.S | re.M
    )
    def _do_block_quotes2(self, text):
        """do block quote of type:
        &gt; {quote:title=some title:}{quote}
        &gt; some text
        &gt;
        &gt; some more ...
        """
        return self._block_quote_re2.sub(self._block_quote_sub2, text)

    def _do_block_quotes(self, text):
        #single line quotes
        text = self._do_block_quotes0(text)
        #potentially multiline quotes
        text = self._do_block_quotes1(text)
        return self._do_block_quotes2(text)

    def _horizontal_rules_sub(self, match):
        return self._hashed('<hr/>')

    def _do_horizontal_rules(self, text):
        hr_re = re.compile(r'^-{5,}\n', re.M)
        return hr_re.sub(self._horizontal_rules_sub, text)

    _nested_list_re = re.compile(
        r'^((#|\*)(#|\*)+\s+(.*?)\n(\2(#|\*)*\s+(.*?)\n)*)',
        re.M
    )
    def _nested_list_sub(self, match):
        text = match.group(1)
        #strip the first char of each line (either * or #)
        text = re.sub(r'^.(.*?)\n', r'\1\n', text)
        return '<li>%s</li>\n' % self._do_lists(text)

    _list_item_re = re.compile(r'^(:?#|\*)\s+(.*?)\n', re.M)
    def _list_item_sub(self, match):
        list_item_html = self._run_span_gamut(match.group(2))
        return '<li>%s</li>\n' % list_item_html

    def _list_sub(self, match):
        text = match.group(1)
        text = self._list_item_re.sub(self._list_item_sub, text)
        text = self._nested_list_re.sub(self._nested_list_sub, text)
        tag = (match.group(2) == '*' and 'ul' or 'ol')
        html = f'<{tag}>\n{text}</{tag}>'
        return self._hashed(html)

    _list_re = re.compile(
        r'^((#|\*)(#|\*)*\s+(.*?)\n(\2(#|\*)*\s+(.*?)\n)*)',
        re.M
    )
    def _do_lists(self, text):
        #detect the list in the pattern and run the replacement
        #this is used recursively for the nested lists
        return self._list_re.sub(self._list_sub, text)

    _leading_blanks_re = re.compile(r'^(\s*)(.*?)\n', re.M)
    def _leading_blanks_sub(self, match):
        spaces = match.group(1)
        text = match.group(2)
        return '{}{}\n'.format('&nbsp;'*len(spaces), text)

    def _preserve_leading_blanks(self, text):
        """replace leading blanks with &nbsp;"""
        return self._leading_blanks_re.sub(self._leading_blanks_sub, text)

    def _form_paragraphs(self, text):
        # Strip leading and trailing lines:
        text = text.strip('\n')

        grafs = []
        for i, graf in enumerate(re.split(r"\n{2,}", text)):
            if graf in self._blocks:
                # Unhashify HTML blocks
                grafs.append(self._blocks[graf])
            else:
                graf = self._run_span_gamut(graf.strip())
                #preserve the line breaks
                graf = re.sub('\n', '<br/>\n', graf)
                #convert leading blanks into nbsp
                graf = self._preserve_leading_blanks(graf)
                grafs.append('<p>%s</p>' % graf)

        return '\n'.join(grafs)

    _auto_link_re = re.compile("((?<!(href|.src|data)=['\"])%s)" % _url_pattern)
    def _auto_link_sub(self, match):
        """auto-links are just passed through"""
        link = match.group(1)
        return f'<a href="{link}">{link}</a>'

    _auto_email_link_re = re.compile(r"""
          \[
          (
            %s
          )
          \]
        """ % _email_pattern, re.I | re.X | re.U)
    def _auto_email_link_sub(self, match):
        email = match.group(1)
        return f'<a href="mailto:{email}">{email}</a>'

    def _do_auto_links(self, text):
        text = self._auto_link_re.sub(self._auto_link_sub, text)
        return self._auto_email_link_re.sub(self._auto_email_link_sub, text)

    _indent_re = re.compile(r'^(.*?)$', re.M)
    def _indent(self, text, indent_pattern=r'    \1'):
        # Remove one level of line-leading tabs or spaces
        return self._indent_re.sub(indent_pattern, text)

    def _outdent(self, text):
        # Remove one level of line-leading tabs or spaces
        return self._outdent_re.sub('', text)
