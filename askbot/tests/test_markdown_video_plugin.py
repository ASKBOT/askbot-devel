"""Tests for video extract/restore functionality."""
from bs4 import BeautifulSoup
from django.test import TestCase
from askbot.utils.markdown_plugins.video_extract import (
    extract_video_embeds,
    restore_video_embeds,
    render_video_link,
)


class TestRenderVideoLink(TestCase):
    """Tests for the render_video_link function."""

    def test_youtube_link_without_title(self):
        """Video without title renders as (Video ▶) link."""
        html = render_video_link('youtube', 'dQw4w9WgXcQ')

        soup = BeautifulSoup(html, 'html5lib')
        link = soup.find('a', class_='js-video-link')

        self.assertIsNotNone(link)
        self.assertEqual(link['data-video-service'], 'youtube')
        self.assertEqual(link['data-video-id'], 'dQw4w9WgXcQ')
        self.assertFalse(link.has_attr('data-video-title'))
        self.assertIn('Video', link.get_text())

    def test_youtube_link_with_title(self):
        """Video with title renders as (Video "Title" ▶) link."""
        html = render_video_link('youtube', 'dQw4w9WgXcQ', 'Never Gonna Give You Up')

        soup = BeautifulSoup(html, 'html5lib')
        link = soup.find('a', class_='js-video-link')

        self.assertIsNotNone(link)
        self.assertEqual(link['data-video-service'], 'youtube')
        self.assertEqual(link['data-video-id'], 'dQw4w9WgXcQ')
        self.assertEqual(link['data-video-title'], 'Never Gonna Give You Up')
        self.assertIn('Never Gonna Give You Up', link.get_text())

    def test_vimeo_link(self):
        html = render_video_link('vimeo', '123456789')

        soup = BeautifulSoup(html, 'html5lib')
        link = soup.find('a', class_='js-video-link')

        self.assertIsNotNone(link)
        self.assertEqual(link['data-video-service'], 'vimeo')
        self.assertEqual(link['data-video-id'], '123456789')

    def test_dailymotion_link(self):
        html = render_video_link('dailymotion', 'x8abcdef')

        soup = BeautifulSoup(html, 'html5lib')
        link = soup.find('a', class_='js-video-link')

        self.assertIsNotNone(link)
        self.assertEqual(link['data-video-service'], 'dailymotion')
        self.assertEqual(link['data-video-id'], 'x8abcdef')

    def test_unsupported_service_returns_none(self):
        """Unsupported service returns None."""
        result = render_video_link('tiktok', '12345')
        self.assertIsNone(result)

    def test_title_with_special_characters_escaped(self):
        """Special characters in title are properly HTML escaped."""
        html = render_video_link('youtube', 'abc123', 'Test <b>bold</b> & "quoted"')

        # Verify XSS is escaped
        self.assertNotIn('<b>', html)
        self.assertIn('&lt;b&gt;', html)
        self.assertIn('&amp;', html)
        self.assertIn('&quot;', html)

    def test_service_specific_class(self):
        """Link wrapper has service-specific class."""
        html = render_video_link('youtube', 'abc123')
        self.assertIn('video-link-youtube', html)

        html = render_video_link('vimeo', 'abc123')
        self.assertIn('video-link-vimeo', html)


class TestExtractVideoEmbeds(TestCase):
    """Tests for the extract_video_embeds function."""

    def test_extract_without_title(self):
        """Extract video without title."""
        text = "Hello @[youtube](abc123) world"
        tokenized, blocks = extract_video_embeds(text)

        self.assertEqual(tokenized, "Hello @@VIDEO0@@ world")
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]['service'], 'youtube')
        self.assertEqual(blocks[0]['id'], 'abc123')
        self.assertIsNone(blocks[0]['title'])

    def test_extract_with_title(self):
        """Extract video with title."""
        text = '@[youtube](abc123 "My Video Title")'
        tokenized, blocks = extract_video_embeds(text)

        self.assertEqual(tokenized, "@@VIDEO0@@")
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]['service'], 'youtube')
        self.assertEqual(blocks[0]['id'], 'abc123')
        self.assertEqual(blocks[0]['title'], 'My Video Title')

    def test_extract_multiple_videos(self):
        """Extract multiple videos with and without titles."""
        text = '@[youtube](vid1)\n@[vimeo](vid2 "Vimeo Title")'
        tokenized, blocks = extract_video_embeds(text)

        self.assertEqual(tokenized, "@@VIDEO0@@\n@@VIDEO1@@")
        self.assertEqual(len(blocks), 2)

        self.assertEqual(blocks[0]['service'], 'youtube')
        self.assertEqual(blocks[0]['id'], 'vid1')
        self.assertIsNone(blocks[0]['title'])

        self.assertEqual(blocks[1]['service'], 'vimeo')
        self.assertEqual(blocks[1]['id'], 'vid2')
        self.assertEqual(blocks[1]['title'], 'Vimeo Title')

    def test_unsupported_service_left_unchanged(self):
        """Unsupported service is left as-is in text."""
        text = "@[tiktok](12345)"
        tokenized, blocks = extract_video_embeds(text)

        self.assertEqual(tokenized, "@[tiktok](12345)")
        self.assertEqual(len(blocks), 0)

    def test_invalid_video_id_left_unchanged(self):
        """Invalid video ID (with spaces/special chars) is left as-is."""
        text = "@[youtube](invalid id!)"
        tokenized, blocks = extract_video_embeds(text)

        self.assertEqual(tokenized, "@[youtube](invalid id!)")
        self.assertEqual(len(blocks), 0)

    def test_case_insensitive_service(self):
        """Service name is case-insensitive."""
        text = "@[YouTube](abc123)"
        tokenized, blocks = extract_video_embeds(text)

        self.assertEqual(tokenized, "@@VIDEO0@@")
        self.assertEqual(blocks[0]['service'], 'youtube')

    def test_video_id_with_dashes_and_underscores(self):
        """Video IDs can contain dashes and underscores."""
        text = "@[youtube](dQw4w9-WgX_cQ)"
        tokenized, blocks = extract_video_embeds(text)

        self.assertEqual(tokenized, "@@VIDEO0@@")
        self.assertEqual(blocks[0]['id'], 'dQw4w9-WgX_cQ')


class TestRestoreVideoEmbeds(TestCase):
    """Tests for the restore_video_embeds function."""

    def test_restore_without_title(self):
        """Restore video without title renders (Video ▶) link."""
        blocks = [{'service': 'youtube', 'id': 'abc123', 'title': None}]
        html = restore_video_embeds("@@VIDEO0@@", blocks)

        soup = BeautifulSoup(html, 'html5lib')
        link = soup.find('a', class_='js-video-link')

        self.assertIsNotNone(link)
        self.assertEqual(link['data-video-service'], 'youtube')
        self.assertEqual(link['data-video-id'], 'abc123')
        self.assertFalse(link.has_attr('data-video-title'))
        self.assertIn('Video', link.get_text())

    def test_restore_with_title(self):
        """Restore video with title renders (Video "Title" ▶) link."""
        blocks = [{'service': 'vimeo', 'id': '123456', 'title': 'My Title'}]
        html = restore_video_embeds("@@VIDEO0@@", blocks)

        soup = BeautifulSoup(html, 'html5lib')
        link = soup.find('a', class_='js-video-link')

        self.assertIsNotNone(link)
        self.assertEqual(link['data-video-service'], 'vimeo')
        self.assertEqual(link['data-video-id'], '123456')
        self.assertEqual(link['data-video-title'], 'My Title')
        self.assertIn('My Title', link.get_text())

    def test_restore_escapes_special_characters(self):
        """Special characters in title are HTML escaped."""
        blocks = [{'service': 'youtube', 'id': 'x', 'title': '<b>Bold</b> & "quoted"'}]
        html = restore_video_embeds("@@VIDEO0@@", blocks)

        # Verify XSS prevention
        self.assertNotIn('<b>', html)
        self.assertIn('&lt;b&gt;', html)
        self.assertIn('&amp;', html)
        self.assertIn('&quot;', html)

    def test_restore_multiple_videos(self):
        """Restore multiple videos in order."""
        blocks = [
            {'service': 'youtube', 'id': 'abc123', 'title': None},
            {'service': 'vimeo', 'id': '456789', 'title': 'Vimeo Vid'},
        ]
        html = restore_video_embeds("First: @@VIDEO0@@ Second: @@VIDEO1@@", blocks)

        soup = BeautifulSoup(html, 'html5lib')
        links = soup.find_all('a', class_='js-video-link')

        self.assertEqual(len(links), 2)

        # First link is youtube
        self.assertEqual(links[0]['data-video-service'], 'youtube')
        self.assertEqual(links[0]['data-video-id'], 'abc123')

        # Second link is vimeo
        self.assertEqual(links[1]['data-video-service'], 'vimeo')
        self.assertEqual(links[1]['data-video-id'], '456789')

    def test_restore_preserves_surrounding_content(self):
        """Surrounding HTML content is preserved."""
        blocks = [{'service': 'youtube', 'id': 'abc123', 'title': None}]
        html = restore_video_embeds("<p>Check this: @@VIDEO0@@ cool!</p>", blocks)

        soup = BeautifulSoup(html, 'html5lib')

        # Verify link exists
        link = soup.find('a', class_='js-video-link')
        self.assertIsNotNone(link)

        # Verify surrounding text preserved
        all_text = soup.get_text()
        self.assertIn('Check this:', all_text)
        self.assertIn('cool!', all_text)


class TestFullExtractRestoreFlow(TestCase):
    """Integration tests for extract → process → restore flow."""

    def test_full_flow_single_video(self):
        """Full flow: extract, (simulate processing), restore."""
        text = "Watch this: @[youtube](dQw4w9WgXcQ)"

        # Extract
        tokenized, blocks = extract_video_embeds(text)
        self.assertEqual(tokenized, "Watch this: @@VIDEO0@@")

        # Simulate markdown + sanitization (wrap in <p>)
        processed = f"<p>{tokenized}</p>"

        # Restore
        html = restore_video_embeds(processed, blocks)

        soup = BeautifulSoup(html, 'html5lib')
        link = soup.find('a', class_='js-video-link')
        self.assertIsNotNone(link)
        self.assertEqual(link['data-video-id'], 'dQw4w9WgXcQ')

    def test_full_flow_mixed_content(self):
        """Full flow with valid and invalid video syntax."""
        text = '@[youtube](valid123) and @[tiktok](invalid) and @[vimeo](also456 "Title")'

        # Extract - only valid services are tokenized
        tokenized, blocks = extract_video_embeds(text)

        self.assertIn('@@VIDEO0@@', tokenized)
        self.assertIn('@[tiktok](invalid)', tokenized)  # Left as-is
        self.assertIn('@@VIDEO1@@', tokenized)
        self.assertEqual(len(blocks), 2)

        # Restore
        html = restore_video_embeds(tokenized, blocks)

        soup = BeautifulSoup(html, 'html5lib')
        links = soup.find_all('a', class_='js-video-link')
        self.assertEqual(len(links), 2)

        # TikTok text remains as plain text
        self.assertIn('@[tiktok](invalid)', html)
