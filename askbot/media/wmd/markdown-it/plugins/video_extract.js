/**
 * Token-based video extraction for safe post-sanitization embedding.
 *
 * Extracts video embed syntax (@[service](id)) before markdown processing,
 * replaces with tokens, then restores as safe iframe HTML after sanitization.
 *
 * This prevents the need to whitelist iframes in the sanitizer while still
 * supporting video embeds from trusted services.
 *
 * Pattern based on: math_extract.js
 * Python equivalent: askbot/utils/markdown_plugins/video_extract.py
 */
(function(window) {
    'use strict';

    // Supported video services with embed URLs and dimensions
    var VIDEO_SERVICES = {
        youtube: {
            url: 'https://www.youtube.com/embed/{0}',
            width: 640,
            height: 390
        },
        vimeo: {
            url: 'https://player.vimeo.com/video/{0}',
            width: 640,
            height: 360
        },
        dailymotion: {
            url: 'https://www.dailymotion.com/embed/video/{0}',
            width: 640,
            height: 360
        }
    };

    // Pattern to match video embed syntax: @[service](video_id)
    var VIDEO_EMBED_PATTERN = /@\[([a-zA-Z]+)\]\(([a-zA-Z0-9_-]+)\)/g;

    // Valid video ID pattern
    var VIDEO_ID_PATTERN = /^[a-zA-Z0-9_-]+$/;

    /**
     * Extract video embed syntax and replace with tokens.
     *
     * Finds all @[service](video_id) patterns, validates them,
     * and replaces with @@VIDEOn@@ tokens.
     *
     * @param {string} text - Markdown source text
     * @returns {Object} - {text: tokenized_text, videoBlocks: array}
     */
    function extractVideoEmbeds(text) {
        var videoBlocks = [];

        var tokenizedText = text.replace(VIDEO_EMBED_PATTERN, function(match, service, videoId) {
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
                id: videoId
            });
            return '@@VIDEO' + tokenIndex + '@@';
        });

        return {
            text: tokenizedText,
            videoBlocks: videoBlocks
        };
    }

    /**
     * Restore video tokens to iframe HTML.
     *
     * Replaces @@VIDEOn@@ tokens with safe iframe embed HTML.
     * Only creates iframes for whitelisted services.
     *
     * @param {string} html - Sanitized HTML with @@VIDEOn@@ tokens
     * @param {Array} videoBlocks - Array of {service, id} objects
     * @returns {string} - HTML with tokens replaced by iframe embeds
     */
    function restoreVideoEmbeds(html, videoBlocks) {
        for (var i = 0; i < videoBlocks.length; i++) {
            var token = '@@VIDEO' + i + '@@';
            var video = videoBlocks[i];

            var service = video.service;
            var videoId = video.id;

            // Get service config (already validated during extraction)
            var config = VIDEO_SERVICES[service];
            if (!config) {
                // Safety check - should not happen if extraction worked
                continue;
            }

            // Build safe iframe HTML
            var url = config.url.replace('{0}', videoId);
            var width = config.width;
            var height = config.height;

            var iframeHtml =
                '<div class="video-embed video-embed-' + service + '">' +
                '<div class="video-embed-wrapper">' +
                '<iframe ' +
                'src="' + url + '" ' +
                'frameborder="0" ' +
                'allowfullscreen ' +
                'loading="lazy"' +
                '></iframe>' +
                '</div>' +
                '</div>';

            html = html.split(token).join(iframeHtml);
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
