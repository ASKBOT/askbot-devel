import unittest
from askbot.utils.jive import JiveConverter
from askbot.utils.jive import internal_link_re as link_re

#class MockPost(object):
#    def __init__(self):
#        self.text = ''
#    def get_absolute_url(self):
#        return '/url'

class JiveTests(unittest.TestCase):

    def setUp(self):
        self.converter = JiveConverter()

    def convert(self, text):
        return self.converter.convert(text)

    def test_headings(self):
        text = """
h1. Heading1
blah blah
h2. Heading 2
blah blah
h3. Heading 3
blah blah
"""
        expected = """<h1>Heading1</h1>
<p>blah blah</p>
<h2>Heading 2</h2>
<p>blah blah</p>
<h3>Heading 3</h3>
<p>blah blah</p>"""
        output = self.convert(text)
        self.assertEqual(output, expected)

    def test_horizontal_rules(self):
        text = """
-----
some text
"""
        expected = '<hr/>\n<p>some text</p>'
        self.assertEqual(self.convert(text), expected)

    def test_list1(self):
        text = """
* one
* two
* three
"""
        expected = """<ul>
<li>one</li>
<li>two</li>
<li>three</li>
</ul>"""
        self.assertEqual(self.convert(text), expected)

    def test_list2(self):
        text = """
# one
# two
# three
"""
        expected = """<ol>
<li>one</li>
<li>two</li>
<li>three</li>
</ol>"""
        self.assertEqual(self.convert(text), expected)

    def test_list3(self):
        text = """
* one
** two
* three
"""
        expected = """<ul>
<li>one</li>
<li>
<ul>
<li>two</li>
</ul>
</li>
<li>three</li>
</ul>"""
        self.assertEqual(self.convert(text), expected)

    def test_bq1(self):
        text = """
bq. two plus two equals four
"""
        expected = """<blockquote><p>two plus two equals four</p></blockquote>"""
        self.assertEqual(self.convert(text), expected)

    def test_bq2(self):
        text = """{quote}
two plus two equals four
{quote}
"""
        expected = """<blockquote><p>two plus two equals four</p></blockquote>"""
        self.assertEqual(self.convert(text), expected)

    def test_bq3(self):
        text = """[quote=alex]
two plus two equals four
{quote}
"""
        expected = """<blockquote><span class="quote-header">alex wrote:</span><br/>
<p>two plus two equals four</p></blockquote>"""
        self.assertEqual(self.convert(text), expected)

    def test_bq4(self):
        text = """[quote=alex]
two plus two equals four

two plus two equals four
{quote}
"""
        expected = """<blockquote><span class="quote-header">alex wrote:</span><br/>
<p>two plus two equals four</p>
<p>two plus two equals four</p></blockquote>"""
        self.assertEqual(self.convert(text), expected)

    def test_bq5(self):
        text = """> {quote:title=alex wrote:}{quote}
> two plus two equals four
>
> two plus two equals four
"""
        expected = """<blockquote><span class="quote-header">alex wrote:</span><br/>
<p>two plus two equals four</p>
<p>two plus two equals four</p></blockquote>"""
        self.assertEqual(self.convert(text), expected)

    def test_code0(self):
        text = """something {code}#comment _haha_ http://example.com {code}"""
        expected = """<p>something</p>
<pre><code>#comment _haha_ http://example.com </code></pre>"""
        self.assertEqual(self.convert(text), expected)

    def test_code1(self):
        text = """something {code:html}#comment _haha_ http://example.com {code}"""
        expected = """<p>something</p>
<pre><code>#comment _haha_ http://example.com </code></pre>"""
        self.assertEqual(self.convert(text), expected)

    def test_links1(self):
        text = """[url]http://example.com/2[/url] blah
http://example.com/1 blah
[link text3|http://example.com/3|tooltip text3] blah2
[link text4|http://example.com/4|tooltip text4]
!http://example.com/img.png!
[email@example.com]
[/some/file/]
"""
        expected = """<p><a href="http://example.com/2">http://example.com/2</a> blah<br/>
<a href="http://example.com/1">http://example.com/1</a> blah<br/>
<a href="http://example.com/3" title="tooltip text3">link text3</a> blah2<br/>
<a href="http://example.com/4" title="tooltip text4">link text4</a><br/>
<img src="http://example.com/img.png"/><br/>
<a href="mailto:email@example.com">email@example.com</a><br/>
<a href="/some/file/">/some/file/</a></p>"""
        self.assertEqual(self.convert(text), expected)

    def test_bold(self):
        text = "*some text*"
        self.assertEqual(
            self.convert(text),
            '<p><strong>some text</strong></p>'
        )

    def test_italics(self):
        text = "+some text+"
        self.assertEqual(
            self.convert(text),
            '<p><em>some text</em></p>'
        )

    def test_underline(self):
        text = "_some text_"
        self.assertEqual(
            self.convert(text),
            '<p><span class="underline">some text</span></p>'
        )

    def test_super(self):
        text = "e = mc^2^"
        self.assertEqual(
            self.convert(text),
            '<p>e = mc<sup>2</sup></p>'
        )

    def test_sub(self):
        text = "e~1~"
        self.assertEqual(
            self.convert(text),
            '<p>e<sub>1</sub></p>'
        )

    def test_strike(self):
        text = "--A--"
        self.assertEqual(
            self.convert(text),
            '<p><strike>A</strike></p>'
        )

    def test_leading_spaces(self):
        """test lazy copy-pasted code"""
        text = """
function() {
    alert('hi');
}
"""
        expected = """<p>function() {<br/>
&nbsp;&nbsp;&nbsp;&nbsp;alert('hi');<br/>
}</p>"""
        self.assertEqual(self.convert(text), expected)

    def test_fancy(self):
        text = """
h1. Once [upon|http://example.com] a *time*
There was a queen who said:
{quote}
I _find_ *this* interesting

{code}e = mc^2;{code}

As you said:

# one
# two
# *three*
# [four|http://example.com/four|item four]
# *five*, --six--, +seven+, _eight_
{quote}
h2. Another time
Nothing happened.
"""
        expected = """<h1>Once <a href="http://example.com">upon</a> a <strong>time</strong></h1>
<p>There was a queen who said:</p>
<blockquote><p>I <span class="underline">find</span> <strong>this</strong> interesting</p>
<pre><code>e = mc^2;</code></pre>
<p>As you said:</p>
<ol>
<li>one</li>
<li>two</li>
<li><strong>three</strong></li>
<li><a href="http://example.com/four" title="item four">four</a></li>
<li><strong>five</strong>, <strike>six</strike>, <em>seven</em>, <span class="underline">eight</span></li>
</ol></blockquote>
<h2>Another time</h2>
<p>Nothing happened.</p>"""
        self.assertEqual(self.convert(text), expected)

    def test_internal_link_re(self):
        self.assertTrue(link_re.search('soasao /message.jspa?messageID=8477 a'))
        self.assertTrue(link_re.search('/thread.jspa?messageID=10175&amp;#10175'))
        self.assertTrue(link_re.search('/thread.jspa?messageID=10662#10662'))
        self.assertTrue(link_re.search('/thread.jspa?messageID=11058'))
        self.assertTrue(link_re.search('/thread.jspa?threadID=1888&amp;tstart=210'))
        self.assertTrue(link_re.search('/thread.jspa?threadID=3087&amp;tstart=-258'))

#    def test_fix_internal_links1(self):
#        from askbot.management.commands.askbot_import_jive import fix_internal_links_in_post
#        post = MockPost()
#        post.text = """/message.jspa?messageID=8477 sometext
#sometext /thread.jspa?messageID=10175&amp;#10175 sometext
#[sometext|/thread.jspa?messageID=10662#10662] [/thread.jspa?messageID=11058]
#[sometext|/thread.jspa?threadID=1888&amp;tstart=210|title]
#/thread.jspa?threadID=3087&amp;tstart=-258"""
#        expected = """<a href="/url">/url</a> sometext<br/>
#sometext <a href="/url">/url</a> sometext<br/>
#<a href="/url">sometext</a> <a href="/url">/url</a><br/>
#<a href="/url" title="title">sometext</a><br/>
#<a href="/url">/url</a>"""
#        fix_internal_links_in_post(post)
#        self.assertEqual(post.text, expected)

if __name__ == '__main__':
    unittest.main()
