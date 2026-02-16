/**
 * Video embedding plugin for markdown-it.
 *
 * Syntax:
 *     @[youtube](video_id)
 *     @[vimeo](video_id)
 *     @[dailymotion](video_id)
 *
 * Renders as iframe embed for supported services.
 *
 * Based on: https://github.com/CenterForOpenScience/markdown-it-video
 * Ported from: askbot/utils/markdown_plugins/video_embed.py
 */
(function(window) {
    'use strict';

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

    // Regex for valid video ID: alphanumeric, dashes, underscores
    var VIDEO_ID_REGEX = /^[a-zA-Z0-9_-]+$/;

    /**
     * Parse video embed syntax: @[service](video_id)
     *
     * Returns true if pattern matches and token created.
     */
    function videoEmbedRule(state, silent) {
        var pos = state.pos;
        var max = state.posMax;
        var src = state.src;

        // Must start with @[
        if (src.charCodeAt(pos) !== 0x40 /* @ */ ||
            src.charCodeAt(pos + 1) !== 0x5B /* [ */) {
            return false;
        }

        // Find closing ]
        var serviceStart = pos + 2;
        var serviceEnd = src.indexOf(']', serviceStart);

        if (serviceEnd === -1 || serviceEnd >= max) {
            return false;
        }

        var service = src.slice(serviceStart, serviceEnd).trim().toLowerCase();

        // Check if it's a supported service
        if (!VIDEO_SERVICES.hasOwnProperty(service)) {
            return false;
        }

        // Must have opening (
        if (serviceEnd + 1 >= max || src.charCodeAt(serviceEnd + 1) !== 0x28 /* ( */) {
            return false;
        }

        // Find closing )
        var idStart = serviceEnd + 2;
        var idEnd = src.indexOf(')', idStart);

        if (idEnd === -1 || idEnd >= max) {
            return false;
        }

        var videoId = src.slice(idStart, idEnd).trim();

        // Validate video ID (alphanumeric, dashes, underscores)
        if (!VIDEO_ID_REGEX.test(videoId)) {
            return false;
        }

        if (!silent) {
            var token = state.push('video_embed', '', 0);
            token.meta = {
                service: service,
                id: videoId
            };
            token.markup = src.slice(pos, idEnd + 1);
        }

        state.pos = idEnd + 1;
        return true;
    }

    /**
     * Render video embed token as iframe.
     */
    function renderVideoEmbed(tokens, idx, options, env, self) {
        var token = tokens[idx];
        var service = token.meta.service;
        var videoId = token.meta.id;

        var config = VIDEO_SERVICES[service];
        var url = config.url.replace('{0}', videoId);
        var width = config.width;
        var height = config.height;

        // Security: Only allow whitelisted domains (enforced by VIDEO_SERVICES)
        // HTML escaping handled by using safe string construction

        return '<div class="video-embed video-embed-' + service + '">' +
            '<div class="video-embed-wrapper">' +
            '<iframe ' +
            'src="' + url + '" ' +
            'frameborder="0" ' +
            'allowfullscreen ' +
            'loading="lazy"' +
            '></iframe>' +
            '</div>' +
            '</div>';
    }

    /**
     * Plugin to enable video embedding in markdown.
     *
     * Usage:
     *     var md = window.markdownit();
     *     md.use(window.markdownitVideoEmbed);
     */
    function videoEmbedPlugin(md) {
        // Register inline rule before 'link' to give it priority
        md.inline.ruler.before('link', 'video_embed', videoEmbedRule);

        // Register renderer
        md.renderer.rules.video_embed = renderVideoEmbed;

        return md;
    }

    // Export for browser and module environments
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = videoEmbedPlugin;
    } else {
        window.markdownitVideoEmbed = videoEmbedPlugin;
    }

})(typeof window !== 'undefined' ? window : this);
