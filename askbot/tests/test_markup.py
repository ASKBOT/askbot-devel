# -*- coding: utf-8 -*-
from django.conf import settings as django_settings
from django.test import TestCase
from askbot.utils.markup import markdown_input_converter
from askbot.tests.utils import AskbotTestCase
from askbot.utils import markup

class MarkupTest(AskbotTestCase):

    def setUp(self):
        self.u1 = self.create_user('user1')

    def test_mentionize_text(self):
        '''this test also test implicitly
        test extract_first_matching_mentioned_author'''
        text = "oh hai @user1 how are you? @UsEr1"
        expected_output = 'oh hai <a href="%(user_url)s">@user1</a> how are you?'
        expected_output += ' <a href="%(user_url)s">@user1</a>'
        anticipated_authors = [self.u1,]
        mentioned_authors, output = markup.mentionize_text(text, anticipated_authors)
        self.assertTrue(self.u1 in mentioned_authors)
        self.assertEqual(output, expected_output % {'user_url': self.u1.get_profile_url()})

    def test_extract_mentioned_name_seeds(self):
        text = "oh hai @user1 how are you?"
        output = markup.extract_mentioned_name_seeds(text)
        self.assertEqual(output, set(['user1']))

"""
More test cases for the future, taken from
http://daringfireball.net/misc/2010/07/url-matching-regex-test-data.text

Matches the right thing in the following lines:

http://foo.com/blah_blah
http://foo.com/blah_blah/
(Something like http://foo.com/blah_blah)
http://foo.com/blah_blah_(wikipedia)
http://foo.com/more_(than)_one_(parens)
(Something like http://foo.com/blah_blah_(wikipedia))
http://foo.com/blah_(wikipedia)#cite-1
http://foo.com/blah_(wikipedia)_blah#cite-1
http://foo.com/unicode_(✪)_in_parens
http://foo.com/(something)?after=parens
http://foo.com/blah_blah.
http://foo.com/blah_blah/.
<http://foo.com/blah_blah>
<http://foo.com/blah_blah/>
http://foo.com/blah_blah,
http://www.extinguishedscholar.com/wpglob/?p=364.
http://✪df.ws/1234
rdar://1234
rdar:/1234
x-yojimbo-item://6303E4C1-6A6E-45A6-AB9D-3A908F59AE0E
message://%3c330e7f840905021726r6a4ba78dkf1fd71420c1bf6ff@mail.gmail.com%3e
http://➡.ws/䨹
www.c.ws/䨹
<tag>http://example.com</tag>
Just a www.example.com link.
http://example.com/something?with,commas,in,url, but not at end
What about <mailto:gruber@daringfireball.net?subject=TEST> (including brokets).
mailto:name@example.com
bit.ly/foo
“is.gd/foo/”
WWW.EXAMPLE.COM
http://www.asianewsphoto.com/(S(neugxif4twuizg551ywh3f55))/Web_ENG/View_DetailPhoto.aspx?PicId=752
http://www.asianewsphoto.com/(S(neugxif4twuizg551ywh3f55))
http://lcweb2.loc.gov/cgi-bin/query/h?pp/horyd:@field(NUMBER+@band(thc+5a46634))


Should fail against:
    6:00p
    filename.txt


Known to fail against:
    http://example.com/quotes-are-“part”
    ✪df.ws/1234
    example.com
    example.com/
"""

class MarkdownTestCase(TestCase):
    """tests markdown,
    todo: add more test cases from above"""
    def setUp(self):
        self.conv = markdown_input_converter
    def test_anchor_stays_untouched(self):
        text = """text <a href="http://example.com/">link</a> text"""
        self.assertHTMLEqual(self.conv(text), '<p>' + text + '</p>\n')

    def test_javascript_url_not_linked(self):
        """javascript: URLs should NOT be auto-linked (XSS prevention)"""
        text = "Click javascript:alert('xss') here"
        html = self.conv(text)
        # Should NOT create a link with javascript: href
        self.assertNotIn('href="javascript:', html)

    def test_javascript_url_variations(self):
        """Various javascript: URL forms should all be rejected"""
        variants = [
            "javascript:alert(1)",
            "JAVASCRIPT:alert(1)",
            "JavaScript:void(0)",
        ]
        for variant in variants:
            text = f"Test {variant} here"
            html = self.conv(text)
            self.assertNotIn('href="javascript:', html.lower(),
                f"javascript: URL should not be linked: {variant}")
