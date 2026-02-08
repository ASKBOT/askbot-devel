/**
 * Asterisk-only emphasis plugin for markdown-it.
 *
 * Code-friendly mode: disables underscore emphasis (_italic_ and __bold__)
 * while keeping asterisk emphasis (*italic* and **bold**) working.
 *
 * This prevents issues with snake_case variable names in programming discussions
 * while preserving basic text formatting.
 *
 * Ported from: askbot/utils/markdown_plugins/asterisk_emphasis.py
 */
(function(window) {
    'use strict';

    /**
     * Tokenize emphasis markers - ASTERISK ONLY.
     *
     * Inserts each marker as a separate text token, and adds it to delimiter list.
     * Only handles asterisk (*), ignores underscore (_).
     *
     * @param {Object} state - Inline parser state
     * @param {boolean} silent - If true, don't emit tokens
     * @returns {boolean} - True if marker was processed
     */
    function tokenize(state, silent) {
        var start = state.pos;
        var marker = state.src.charCodeAt(start);

        if (silent) {
            return false;
        }

        // KEY CHANGE: Only handle asterisk (0x2A = '*'), not underscore (0x5F = '_')
        if (marker !== 0x2A) {
            return false;
        }

        // scanDelims(pos, canSplitWord)
        // canSplitWord=true for asterisk (allows mid-word emphasis like w*or*d)
        var scanned = state.scanDelims(state.pos, true);

        var length = scanned.length;
        var ch = String.fromCharCode(marker);

        // Create a text token for each delimiter character
        for (var i = 0; i < length; i++) {
            var token = state.push('text', '', 0);
            token.content = ch;

            state.delimiters.push({
                marker: marker,
                length: 0,  // Disable "rule of 3" logic
                token: state.tokens.length - 1,
                end: -1,  // Will be set when matched with closer
                open: scanned.can_open,
                close: scanned.can_close
            });
        }

        state.pos += length;

        return true;
    }

    /**
     * Process delimiter list and convert matched pairs to emphasis tags.
     *
     * Internal function that handles a single delimiters array.
     *
     * @param {Object} state - Inline parser state
     * @param {Array} delimiters - Array of delimiter objects
     */
    function processDelimiters(state, delimiters) {
        var i = delimiters.length - 1;

        while (i >= 0) {
            var startDelim = delimiters[i];

            // KEY CHANGE: Only process asterisk markers (0x2A = '*')
            // Skip any other markers (like underscore 0x5F = '_')
            if (startDelim.marker !== 0x2A) {
                i--;
                continue;
            }

            // Process only opening markers that have been matched (end !== -1)
            if (startDelim.end === -1) {
                i--;
                continue;
            }

            var endDelim = delimiters[startDelim.end];

            // Detect if we should render as <strong> instead of <em>.
            // This happens when the previous delimiter:
            // 1. Has matching end position (end === startDelim.end + 1)
            // 2. Has same marker type
            // 3. Is adjacent to this one (token positions are consecutive)
            var isStrong = (
                i > 0 &&
                delimiters[i - 1].end === startDelim.end + 1 &&
                delimiters[i - 1].marker === startDelim.marker &&
                delimiters[i - 1].token === startDelim.token - 1 &&
                delimiters[startDelim.end + 1].token === endDelim.token + 1
            );

            var ch = String.fromCharCode(startDelim.marker);
            var token;

            // Convert opening text token to em_open or strong_open
            token = state.tokens[startDelim.token];
            token.type = isStrong ? 'strong_open' : 'em_open';
            token.tag = isStrong ? 'strong' : 'em';
            token.nesting = 1;
            token.markup = isStrong ? ch + ch : ch;
            token.content = '';

            // Convert closing text token to em_close or strong_close
            token = state.tokens[endDelim.token];
            token.type = isStrong ? 'strong_close' : 'em_close';
            token.tag = isStrong ? 'strong' : 'em';
            token.nesting = -1;
            token.markup = isStrong ? ch + ch : ch;
            token.content = '';

            // For strong emphasis, clear the content of the adjacent tokens
            // (the second * characters that got merged)
            if (isStrong) {
                state.tokens[delimiters[i - 1].token].content = '';
                state.tokens[delimiters[startDelim.end + 1].token].content = '';
                i--;
            }

            i--;
        }
    }

    /**
     * Post-process function for emphasis - walks delimiter list and replaces
     * text tokens with emphasis tags.
     *
     * @param {Object} state - Inline parser state
     */
    function postProcess(state) {
        // Process main delimiters list
        processDelimiters(state, state.delimiters);

        // Process nested delimiters in tokens_meta (for nested inline parsing)
        var tokens_meta = state.tokens_meta;
        var max = tokens_meta.length;

        for (var i = 0; i < max; i++) {
            if (tokens_meta[i] && tokens_meta[i].delimiters) {
                processDelimiters(state, tokens_meta[i].delimiters);
            }
        }
    }

    /**
     * Plugin to replace emphasis with asterisk-only version.
     *
     * Disables underscore emphasis (_italic_ and __bold__) while keeping
     * asterisk emphasis (*italic* and **bold**) working.
     *
     * Usage:
     *     var md = window.markdownit();
     *     md.use(window.markdownitAsteriskEmphasis);
     *
     * @param {Object} md - markdown-it instance
     * @returns {Object} - The modified markdown-it instance
     */
    function asteriskEmphasisPlugin(md) {
        // Replace the tokenize rule in inline parser (ruler)
        // This handles scanning for emphasis markers during tokenization
        md.inline.ruler.at('emphasis', tokenize);

        // Replace the postProcess rule in inline2 parser (ruler2)
        // This handles converting matched delimiters to em/strong tags
        md.inline.ruler2.at('emphasis', postProcess);

        return md;
    }

    // Export for browser and module environments
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = asteriskEmphasisPlugin;
    } else {
        window.markdownitAsteriskEmphasis = asteriskEmphasisPlugin;
    }

})(typeof window !== 'undefined' ? window : this);
