import markdown2
from django.conf import settings as django_settings
from django.test import TestCase
from askbot.tests.utils import with_settings
from askbot.utils.url_utils import urls_equal
from askbot.utils.html import absolutize_urls
from askbot.utils.html import replace_links_with_text
from askbot.utils.html import get_text_from_html
from askbot.utils.html import sanitize_html
from askbot.utils import html as html_utils
from askbot.utils.markup import get_parser
from askbot.conf import settings as askbot_settings


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
        text = u'<img src="/some-image.gif"/>'
        self.assertEqual(
                replace_links_with_text(text), 
                u'<img src="/some-image.gif">'
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
            u'ataoesa uau linkaueaotuosu ao http://cnn.com (CNN!)\n\nnaouaouuau http://cnn.com/1.png http://cnn.com/2.png (sometext)'
        )


class GetParserTest(TestCase):
    def test_func(self):
        parser = get_parser()
        self.assertIsInstance(parser, markdown2.Markdown)

    def test_markdown_class_addr(self):
        parser = get_parser('askbot.tests.utils.Markdown')
        self.assertIsInstance(parser, markdown2.Markdown)


class SanitizeHtml(TestCase):
    def test_sanitize_html(self):
        html = '<p id="foo" class="bar">TEXT</p>'
        new_html = sanitize_html(html)
        self.assertNotIn('foo', new_html)
        self.assertIn('bar', new_html)

    def test_sanitize_html_with_extra_elements(self):
        setattr(django_settings, 'ASKBOT_ALLOWED_HTML_ELEMENTS',
                html_utils.ALLOWED_HTML_ELEMENTS + ('ham',))
        html = '<p id="foo" class="bar">TEXT</p><p><ham></ham></p>'
        new_html = sanitize_html(html)
        self.assertIn('<ham>', new_html)
        self.assertNotIn('foo', new_html)
        self.assertIn('bar', new_html)
        delattr(django_settings, 'ASKBOT_ALLOWED_HTML_ELEMENTS')

    def test_sanitize_html_with_extra_attrs(self):
        setattr(django_settings, 'ASKBOT_ALLOWED_HTML_ATTRIBUTES',
                html_utils.ALLOWED_HTML_ATTRIBUTES + ('id',))
        html = '<p id="foo" class="bar">TEXT</p>'
        new_html = sanitize_html(html)
        self.assertIn('id="foo"', new_html)
        self.assertIn('class="bar"', new_html)
        delattr(django_settings, 'ASKBOT_ALLOWED_HTML_ATTRIBUTES')
