/**
 * Token-based video extraction for safe post-sanitization embedding.
 *
 * Extracts video embed syntax (@[service](id) or @[service](id "title")) before
 * markdown processing, replaces with tokens, then restores as clickable link HTML
 * after sanitization. Clicking the link opens a modal video player.
 *
 * This prevents the need to whitelist iframes in the sanitizer while still
 * supporting video embeds from trusted services.
 *
 * Pattern based on: math_extract.js
 * Python equivalent: askbot/utils/markdown_plugins/video_extract.py
 */
(function(window) {
    'use strict';

    // Supported video services with embed URLs
    var VIDEO_SERVICES = {
        youtube: {
            url: 'https://www.youtube.com/embed/{0}'
        },
        vimeo: {
            url: 'https://player.vimeo.com/video/{0}'
        },
        dailymotion: {
            url: 'https://www.dailymotion.com/embed/video/{0}'
        }
    };

    // Pattern to match video embed syntax: @[service](video_id) or @[service](video_id "title")
    // Captures: service name, video ID, optional title
    var VIDEO_EMBED_PATTERN = /@\[([a-zA-Z]+)\]\(([a-zA-Z0-9_-]+)(?:\s+"([^"]*)")?\)/g;

    // Valid video ID pattern
    var VIDEO_ID_PATTERN = /^[a-zA-Z0-9_-]+$/;

    /**
     * Escape HTML special characters for safe inclusion in attributes and content.
     * @param {string} str - String to escape
     * @returns {string} - Escaped string
     */
    function escapeHtml(str) {
        if (!str) return '';
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#x27;');
    }

    /**
     * Extract video embed syntax and replace with tokens.
     *
     * Finds all @[service](video_id) or @[service](video_id "title") patterns,
     * validates them, and replaces with @@VIDEOn@@ tokens.
     *
     * @param {string} text - Markdown source text
     * @returns {Object} - {text: tokenized_text, videoBlocks: array}
     */
    function extractVideoEmbeds(text) {
        var videoBlocks = [];

        var tokenizedText = text.replace(VIDEO_EMBED_PATTERN, function(match, service, videoId, title) {
            service = service.toLowerCase();

            // Validate service
            if (!VIDEO_SERVICES.hasOwnProperty(service)) {
                // Unknown service, leave as-is
                return match;
            }

            // Validate video ID
            if (!VIDEO_ID_PATTERN.test(videoId)) {
                // Invalid video ID, leave as-is
                return match;
            }

            // Store video info and return token
            var tokenIndex = videoBlocks.length;
            videoBlocks.push({
                service: service,
                id: videoId,
                title: title || null
            });
            return '@@VIDEO' + tokenIndex + '@@';
        });

        return {
            text: tokenizedText,
            videoBlocks: videoBlocks
        };
    }

    /**
     * Restore video tokens to clickable link HTML.
     *
     * Replaces @@VIDEOn@@ tokens with clickable video links that open
     * a modal player when clicked. Only creates links for whitelisted services.
     *
     * @param {string} html - Sanitized HTML with @@VIDEOn@@ tokens
     * @param {Array} videoBlocks - Array of {service, id, title} objects
     * @returns {string} - HTML with tokens replaced by video links
     */
    function restoreVideoEmbeds(html, videoBlocks) {
        for (var i = 0; i < videoBlocks.length; i++) {
            var token = '@@VIDEO' + i + '@@';
            var video = videoBlocks[i];

            var service = video.service;
            var videoId = video.id;
            var title = video.title;

            // Get service config (already validated during extraction)
            var config = VIDEO_SERVICES[service];
            if (!config) {
                // Safety check - should not happen if extraction worked
                continue;
            }

            // Build clickable link HTML
            // Escape title for safe inclusion in HTML attributes and content
            var escapedTitle = title ? escapeHtml(title) : null;

            // Build display text: "(Video ▶)" or '(Video "Title" ▶)'
            var displayText;
            if (escapedTitle) {
                displayText = '(Video "' + escapedTitle + '" <i class="fa fa-play-circle"></i>)';
            } else {
                displayText = '(Video <i class="fa fa-play-circle"></i>)';
            }

            // Build data attributes
            var titleAttr = escapedTitle ? ' data-video-title="' + escapedTitle + '"' : '';

            var linkHtml =
                '<span class="video-link video-link-' + service + '">' +
                '<a href="#" class="js-video-link" ' +
                'data-video-service="' + service + '" ' +
                'data-video-id="' + videoId + '"' +
                titleAttr + '>' +
                displayText +
                '</a>' +
                '</span>';

            html = html.split(token).join(linkHtml);
        }

        return html;
    }

    // Export for browser and module environments
    var exports = {
        extractVideoEmbeds: extractVideoEmbeds,
        restoreVideoEmbeds: restoreVideoEmbeds,
        VIDEO_SERVICES: VIDEO_SERVICES
    };

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = exports;
    } else {
        window.videoExtract = exports;
    }

})(typeof window !== 'undefined' ? window : this);
