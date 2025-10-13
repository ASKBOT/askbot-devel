"""Tests for the video embedding plugin."""
from bs4 import BeautifulSoup
from django.test import TestCase
from markdown_it import MarkdownIt
from askbot.utils.markdown_plugins.video_embed import video_embed_plugin


class TestVideoEmbedPlugin(TestCase):

    def setUp(self):
        self.md = MarkdownIt().use(video_embed_plugin)

    def test_youtube_embed(self):
        text = "@[youtube](dQw4w9WgXcQ)"
        html = self.md.render(text)

        soup = BeautifulSoup(html, 'html5lib')

        # Find iframe element
        iframe = soup.find('iframe')
        self.assertIsNotNone(iframe, "No iframe element found")

        # Verify src attribute
        self.assertIn('youtube.com/embed/dQw4w9WgXcQ', iframe['src'])

    def test_vimeo_embed(self):
        text = "@[vimeo](123456789)"
        html = self.md.render(text)

        soup = BeautifulSoup(html, 'html5lib')

        iframe = soup.find('iframe')
        self.assertIsNotNone(iframe)
        self.assertIn('vimeo.com/video/123456789', iframe['src'])

    def test_dailymotion_embed(self):
        text = "@[dailymotion](x8abcdef)"
        html = self.md.render(text)

        soup = BeautifulSoup(html, 'html5lib')

        iframe = soup.find('iframe')
        self.assertIsNotNone(iframe)
        self.assertIn('dailymotion.com/embed/video/x8abcdef', iframe['src'])

    def test_unsupported_service_ignored(self):
        text = "@[tiktok](12345)"
        html = self.md.render(text)

        soup = BeautifulSoup(html, 'html5lib')

        # Unsupported service - no iframe should be created
        iframe = soup.find('iframe')
        self.assertIsNone(iframe, "Iframe created for unsupported service")

    def test_invalid_video_id_ignored(self):
        # IDs with spaces or special chars should be rejected
        text = "@[youtube](invalid id!)"
        html = self.md.render(text)

        soup = BeautifulSoup(html, 'html5lib')

        iframe = soup.find('iframe')
        self.assertIsNone(iframe, "Iframe created for invalid video ID")

    def test_video_in_paragraph(self):
        text = "Check this out: @[youtube](dQw4w9WgXcQ) cool right?"
        html = self.md.render(text)

        soup = BeautifulSoup(html, 'html5lib')

        # Verify iframe exists with correct src
        iframe = soup.find('iframe')
        self.assertIsNotNone(iframe)
        self.assertIn('dQw4w9WgXcQ', iframe['src'])

        # Verify surrounding text in same paragraph or adjacent
        # (depends on how plugin handles inline vs block)
        all_text = soup.get_text()
        self.assertIn('Check this out:', all_text)
        self.assertIn('cool right?', all_text)

    def test_multiple_videos(self):
        text = "@[youtube](abc123)\n\n@[vimeo](456789)"
        html = self.md.render(text)

        soup = BeautifulSoup(html, 'html5lib')

        # Should have exactly 2 iframes
        iframes = soup.find_all('iframe')
        self.assertEqual(len(iframes), 2)

        # Verify youtube iframe
        youtube_iframe = [i for i in iframes if 'youtube.com' in i['src']][0]
        self.assertIn('abc123', youtube_iframe['src'])

        # Verify vimeo iframe
        vimeo_iframe = [i for i in iframes if 'vimeo.com' in i['src']][0]
        self.assertIn('456789', vimeo_iframe['src'])
