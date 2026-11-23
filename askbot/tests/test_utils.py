import os
from django.conf import settings as django_settings
from django.test import TestCase
from askbot.tests.utils import with_settings
from askbot.utils.url_utils import urls_equal
from askbot.utils.html import absolutize_urls
from askbot.utils.html import replace_links_with_text
from askbot.utils.html import get_text_from_html
from askbot.utils.html import sanitize_html
from askbot.utils import html as html_utils
from askbot.utils.functions import list_directory_files, encode_jwt, decode_jwt
from askbot.conf import settings as askbot_settings
import askbot

class FunctionTests(TestCase):
    def test_list_directory_files(self):
        root_dir = askbot.get_install_directory()
        dir_path = os.path.join(root_dir, 'locale')
        file_list = list_directory_files(dir_path)
        file1 = os.path.join(root_dir, 'locale', 'en',
                             'LC_MESSAGES', 'django.po')
        file2 = os.path.join(root_dir, 'locale', 'en',
                             'LC_MESSAGES', 'djangojs.po')
        self.assertTrue(file1 in file_list)
        self.assertTrue(file2 in file_list)

    def test_encode_jwt_returns_string(self):
        token = encode_jwt({'next_url': '/questions/'})
        self.assertIsInstance(token, str)

    def test_encode_decode_jwt_roundtrip(self):
        data = {'next_url': '/questions/'}
        token = encode_jwt(data)
        result = decode_jwt(token)
        self.assertEqual(result, data)

    def test_encode_decode_jwt_with_multiple_keys(self):
        data = {'next_url': '/users/', 'extra': 'data'}
        token = encode_jwt(data)
        result = decode_jwt(token)
        self.assertEqual(result, data)

    def test_decode_jwt_rejects_tampered_token(self):
        token = encode_jwt({'next_url': '/questions/'})
        # Tamper with the payload segment so the signature no longer matches.
        # Mutating the last char of the signature is unreliable because
        # base64url's trailing bits may be unused, leaving the decoded
        # signature bytes unchanged.
        header, payload, signature = token.split('.')
        flipped = 'B' if payload[0] != 'B' else 'C'
        tampered = '.'.join([header, flipped + payload[1:], signature])
        with self.assertRaises(Exception):
            decode_jwt(tampered)


class UrlUtilsTests(TestCase):

    def tests_urls_equal(self):
        e = urls_equal
        self.assertTrue(e('', ''))
        self.assertTrue(e('', '/', True))
        self.assertTrue(e('http://cnn.com', 'http://cnn.com/', True))

        self.assertFalse(e('https://cnn.com', 'http://cnn.com'))
        self.assertFalse(e('http://cnn.com:80', 'http://cnn.com:8000'))

        self.assertTrue(e('http://cnn.com/path', 'http://cnn.com/path/', True))
        self.assertFalse(e('http://cnn.com/path', 'http://cnn.com/path/'))


class ReplaceLinksWithTextTests(TestCase):
    """testing correctness of `askbot.utils.html.replace_links_with_text"""

    def test_local_link_not_replaced(self):
        text = '<a href="/some-link">some link</a>'
        self.assertEqual(replace_links_with_text(text), text)

    def test_link_without_url_replaced(self):
        text = '<a>some link</a>'
        self.assertEqual(replace_links_with_text(text), 'some link')

    def test_external_link_without_text_replaced(self):
        text = '<a href="https://example.com/"></a>'
        #in this case we delete the link
        self.assertEqual(replace_links_with_text(text), '')

    def test_external_link_with_text_replaced(self):
        text = '<a href="https://example.com/">some link</a>'
        self.assertEqual(
            replace_links_with_text(text),
            'https://example.com/ (some link)'
        )

    def test_local_image_not_replaced(self):
        text = '<img src="/some-image.gif"/>'
        self.assertEqual(
                replace_links_with_text(text), 
                '<img src="/some-image.gif">'
            )

    def test_local_url_with_hotlinked_image_replaced(self):
        text = '<a href="/some-link"><img src="http://example.com/img.png" alt="picture""> some text</a>'
        self.assertEqual(
            replace_links_with_text(text),
            '<a href="/some-link">http://example.com/img.png (picture) some text</a>'
        )

    def test_hotlinked_image_without_alt_replaced(self):
        text = '<img src="https://example.com/some-image.gif"/>'
        self.assertEqual(
            replace_links_with_text(text),
            'https://example.com/some-image.gif'
        )

    def test_hotlinked_image_with_alt_replaced(self):
        text = '<img src="https://example.com/some-image.gif" alt="picture"/>'
        self.assertEqual(
            replace_links_with_text(text),
            'https://example.com/some-image.gif (picture)'
        )


class HTMLUtilsTests(TestCase):
    """tests for :mod:`askbot.utils.html` module"""
    @with_settings(APP_URL='http://example.com')
    def test_absolutize_urls(self):
        text = """<img class="junk" src="/some.gif"> <img class="junk" src="/cat.gif"> <IMG SRC='/some.png'>"""
        #jinja register.filter decorator works in a weird way
        self.assertEqual(
            absolutize_urls(text),
            '<img class="junk" src="http://example.com/some.gif"> <img class="junk" src="http://example.com/cat.gif"> <IMG SRC="http://example.com/some.png">'
        )

        text = """<a class="junk" href="/something">link</a> <A HREF='/something'>link</A>"""
        #jinja register.filter decorator works in a weird way
        self.assertEqual(
            absolutize_urls(text),
            '<a class="junk" href="http://example.com/something">link</a> <A HREF="http://example.com/something">link</A>'
        )

        text = '<img src="/upfiles/13487900323638005.png" alt="" />'
        self.assertEqual(
            absolutize_urls(text),
            '<img src="http://example.com/upfiles/13487900323638005.png" alt="" />'
        )

        text = 'ohaouhaosthoanstoahuaou<br /><img src="/upfiles/13487906221942257.png" alt="" /><img class="gravatar" title="Evgeny4" src="http://kp-dev.askbot.com/avatar/render_primary/5/32/" alt="Evgeny4 gravatar image" width="32" height="32" />'
        self.assertEqual(
            absolutize_urls(text),
            'ohaouhaosthoanstoahuaou<br /><img src="http://example.com/upfiles/13487906221942257.png" alt="" /><img class="gravatar" title="Evgeny4" src="http://kp-dev.askbot.com/avatar/render_primary/5/32/" alt="Evgeny4 gravatar image" width="32" height="32" />'
        )

        text = '<a href="/upfiles/13487909784287052.png"><img src="/upfiles/13487909942351405.png" alt="" /></a><img src="http://i2.cdn.turner.com/cnn/dam/assets/120927033530-ryder-cup-captains-wall-4-tease.jpg" alt="" width="160" height="90" border="0" />and some text<br />aouaosutoaehut'
        self.assertEqual(
            absolutize_urls(text),
            '<a href="http://example.com/upfiles/13487909784287052.png"><img src="http://example.com/upfiles/13487909942351405.png" alt="" /></a><img src="http://i2.cdn.turner.com/cnn/dam/assets/120927033530-ryder-cup-captains-wall-4-tease.jpg" alt="" width="160" height="90" border="0" />and some text<br />aouaosutoaehut'
        )

    def test_get_text_from_html(self):
        self.assertEqual(
            get_text_from_html('ataoesa uau <a>link</a>aueaotuosu ao <a href="http://cnn.com">CNN!</a>\nnaouaouuau<img> <img src="http://cnn.com/1.png"/> <img src="http://cnn.com/2.png" alt="sometext">'),
            'ataoesa uau linkaueaotuosu ao http://cnn.com (CNN!)\n\nnaouaouuau http://cnn.com/1.png http://cnn.com/2.png (sometext)'
        )


class UrlizeHtmlTests(TestCase):
    def test_bare_url_linked(self):
        self.assertEqual(
            html_utils.urlize_html('see http://example.com now'),
            'see <a href="http://example.com">http://example.com</a> now'
        )

    def test_www_domain_linked_and_existing_link_kept(self):
        self.assertEqual(
            html_utils.urlize_html(
                '<p>visit www.example.com and <a href="http://x.com">http://y.com</a></p>'
            ),
            '<p>visit <a href="http://www.example.com">www.example.com</a>'
            ' and <a href="http://x.com">http://y.com</a></p>'
        )

    def test_urls_in_pre_and_code_untouched(self):
        html = '<pre>http://in-pre.com</pre><code>http://in-code.com</code>'
        self.assertEqual(html_utils.urlize_html(html), html)

    def test_entities_and_trailing_newline_kept(self):
        self.assertEqual(
            html_utils.urlize_html('<p>a &amp; b http://e.com/?a=1&amp;b=2</p>\n'),
            '<p>a &amp; b <a href="http://e.com/?a=1&amp;b=2">'
            'http://e.com/?a=1&amp;b=2</a></p>\n'
        )

    def test_text_without_links_unchanged(self):
        html = '<p>plain text, no links</p>'
        self.assertEqual(html_utils.urlize_html(html), html)

    def test_non_ascii_text(self):
        self.assertEqual(
            html_utils.urlize_html('<p>caf\u00e9 http://\u00fcnicode.example/</p>'),
            '<p>caf\u00e9 <a href="http://%C3%BCnicode.example/">'
            'http://\u00fcnicode.example/</a></p>'
        )


class StripTagsTests(TestCase):
    def test_strips_given_tags_with_contents(self):
        self.assertEqual(
            html_utils.strip_tags('<p>a<img src="http://e.com/i.png">b</p>', tags=['img']),
            '<p>ab</p>'
        )
        self.assertEqual(
            html_utils.strip_tags('<p><a href="http://e.com">x</a> y <b>z</b></p>',
                                  tags=['a', 'b']),
            '<p> y </p>'
        )

    def test_blank_input_returned_as_is(self):
        self.assertEqual(html_utils.strip_tags('   ', tags=['a']), '   ')

    def test_non_ascii_text(self):
        self.assertEqual(
            html_utils.strip_tags('<p>caf\u00e9 <i>x</i></p>', tags=['i']),
            '<p>caf\u00e9 </p>'
        )


class ModerateTagsTests(TestCase):
    link_html = '<p>see <a href="http://e.com">link</a></p>'
    image_html = '<p>pic <img src="http://e.com/i.png" alt="i"></p>'
    moderated_link_html = ('<p>see <span class="moderated-item"><i></i>'
                           'link awaiting moderation</span></p>')
    moderated_image_html = ('<p>pic <span class="moderated-item"><i></i>'
                            'link awaiting moderation</span></p>')

    @with_settings(MODERATE_LINKS=True, MODERATE_IMAGES=True)
    def test_links_and_images_moderated(self):
        self.assertEqual(html_utils.moderate_tags(self.link_html), self.moderated_link_html)
        self.assertEqual(html_utils.moderate_tags(self.image_html), self.moderated_image_html)
        self.assertEqual(html_utils.moderate_tags('<p>no links</p>'), '<p>no links</p>')

    @with_settings(MODERATE_LINKS=True, MODERATE_IMAGES=False)
    def test_only_links_moderated(self):
        self.assertEqual(html_utils.moderate_tags(self.link_html), self.moderated_link_html)
        self.assertEqual(html_utils.moderate_tags(self.image_html), self.image_html)

    @with_settings(MODERATE_LINKS=False, MODERATE_IMAGES=True)
    def test_only_images_moderated(self):
        self.assertEqual(html_utils.moderate_tags(self.link_html), self.link_html)
        self.assertEqual(html_utils.moderate_tags(self.image_html), self.moderated_image_html)

    @with_settings(MODERATE_LINKS=False, MODERATE_IMAGES=False)
    def test_nothing_moderated(self):
        self.assertEqual(html_utils.moderate_tags(self.link_html), self.link_html)
        self.assertEqual(html_utils.moderate_tags(self.image_html), self.image_html)


class SanitizeHtml(TestCase):
    def test_strip_forbidden_attributes(self):
        html = '<p id="foo" class="bar">TEXT</p>'
        new_html = sanitize_html(html)
        self.assertEqual(new_html, '<p>TEXT</p>')

    def test_strip_forbidden_tags(self):
        html = '<button onClick="javascript:alert(\'foobar\')">click me</button>'
        new_html = sanitize_html(html)
        self.assertEqual(new_html, 'click me')

    def assertSanitized(self, html, expected):
        self.assertEqual(sanitize_html(html), expected)

    def test_javascript_href_removed(self):
        self.assertSanitized('<a href="javascript:alert(1)">x</a>', '<a>x</a>')

    def test_javascript_href_with_zero_width_space_removed(self):
        # GHSA-8rfp-98v4-mmr6, fixed in bleach 6.4
        self.assertSanitized('<a href="javascript​:alert(1)">x</a>', '<a>x</a>')

    def test_safe_link_kept(self):
        html = '<a href="http://example.com/" title="t">x</a>'
        self.assertSanitized(html, html)

    def test_image_kept(self):
        html = '<img src="http://example.com/a.png" alt="pic">'
        self.assertSanitized(html, html)

    def test_comments_stripped(self):
        self.assertSanitized('<p>a<!-- secret -->b</p>', '<p>ab</p>')

    def test_task_list_kept(self):
        html = ('<ul class="contains-task-list"><li class="task-list-item">'
                '<input type="checkbox" checked disabled> done</li></ul>')
        self.assertSanitized(html, html)

    def test_task_list_input_extra_attributes_stripped(self):
        self.assertSanitized('<input type="text" name="q" value="v">',
                             '<input type="text">')

    def test_code_highlight_classes_kept(self):
        html = ('<pre><code class="language-python">'
                '<span class="k">def</span></code></pre>')
        self.assertSanitized(html, html)

    def test_iframe_stripped(self):
        self.assertSanitized('<iframe src="http://evil.example/"></iframe>after',
                             'after')

    def test_script_tag_stripped(self):
        self.assertSanitized('<script>alert(1)</script>after', 'alert(1)after')

    def test_entities_preserved(self):
        self.assertSanitized('<p title="x">&amp; &lt;b&gt; 5 &gt; 3</p>',
                             '<p>&amp; &lt;b&gt; 5 &gt; 3</p>')
        html = '<a href="http://e.com/?a=1&amp;b=2">q</a>'
        self.assertSanitized(html, html)

    def test_uppercase_tags_lowercased(self):
        self.assertSanitized('<P>Upper <B>bold</B></P>', '<p>Upper <b>bold</b></p>')

    def test_table_attributes(self):
        self.assertSanitized(
            '<table><tbody><tr><td colspan="2" style="color:red">c</td></tr></tbody></table>',
            '<table><tbody><tr><td colspan="2">c</td></tr></tbody></table>'
        )

    def test_shared_attribute_config_not_modified(self):
        from askbot.const.sanitizer_config import ALLOWED_HTML_ATTRIBUTES
        sanitize_html('<p>x</p>')
        self.assertNotIn('span', ALLOWED_HTML_ATTRIBUTES)
