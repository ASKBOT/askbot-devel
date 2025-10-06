"""Tests for the video embedding plugin."""
from django.test import TestCase
from markdown_it import MarkdownIt
from askbot.utils.markdown_plugins.video_embed import video_embed_plugin


class TestVideoEmbedPlugin(TestCase):

    def setUp(self):
        self.md = MarkdownIt().use(video_embed_plugin)

    def test_youtube_embed(self):
        text = "@[youtube](dQw4w9WgXcQ)"
        html = self.md.render(text)
        self.assertIn('https://www.youtube.com/embed/dQw4w9WgXcQ', html)
        self.assertIn('iframe', html)
        self.assertIn('video-embed-youtube', html)

    def test_vimeo_embed(self):
        text = "@[vimeo](123456789)"
        html = self.md.render(text)
        self.assertIn('https://player.vimeo.com/video/123456789', html)
        self.assertIn('iframe', html)

    def test_dailymotion_embed(self):
        text = "@[dailymotion](x8abcdef)"
        html = self.md.render(text)
        self.assertIn('dailymotion.com/embed/video/x8abcdef', html)

    def test_unsupported_service_ignored(self):
        text = "@[tiktok](12345)"
        html = self.md.render(text)
        # Unsupported service - no iframe should be created
        # Note: markdown-it will parse [tiktok](12345) as a regular link
        self.assertNotIn('iframe', html)
        self.assertNotIn('video-embed', html)

    def test_invalid_video_id_ignored(self):
        # IDs with spaces or special chars should be rejected
        text = "@[youtube](invalid id!)"
        html = self.md.render(text)
        self.assertNotIn('iframe', html)

    def test_video_in_paragraph(self):
        text = "Check this out: @[youtube](dQw4w9WgXcQ) cool right?"
        html = self.md.render(text)
        self.assertIn('Check this out:', html)
        self.assertIn('youtube.com/embed', html)
        self.assertIn('cool right?', html)

    def test_multiple_videos(self):
        text = "@[youtube](abc123)\n\n@[vimeo](456789)"
        html = self.md.render(text)
        self.assertIn('youtube.com/embed/abc123', html)
        self.assertIn('vimeo.com/video/456789', html)
