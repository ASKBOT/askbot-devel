#!/usr/bin/env node
/**
 * Markdown parity test runner for Node.js
 *
 * Receives JSON input via stdin with test cases and settings,
 * processes markdown with the same plugins as the Python/frontend converters,
 * and outputs rendered HTML as JSON.
 *
 * Input format (stdin):
 *   {
 *     "markdown": "**bold** text",
 *     "settings": {
 *       "mathjaxEnabled": true,
 *       "videoEmbeddingEnabled": true,
 *       "autoLinkEnabled": false,
 *       "autoLinkPatterns": "",
 *       "autoLinkUrls": "",
 *       "markupCodeFriendly": false
 *     }
 *   }
 *
 * Output format (stdout):
 *   {
 *     "html": "<p><strong>bold</strong> text</p>\n"
 *   }
 */

'use strict';

const path = require('path');
const markdownit = require('markdown-it');
const markdownitFootnote = require('markdown-it-footnote');
const markdownitTaskLists = require('markdown-it-task-lists');
const hljs = require('highlight.js');

// Load local plugins
const pluginDir = path.join(__dirname, '../../media/wmd/markdown-it/plugins');
const linkPatternsPlugin = require(path.join(pluginDir, 'link_patterns.js'));
const truncateLinksPlugin = require(path.join(pluginDir, 'truncate_links.js'));
const asteriskEmphasisPlugin = require(path.join(pluginDir, 'asterisk_emphasis.js'));
const mathExtract = require(path.join(pluginDir, 'math_extract.js'));
const videoExtract = require(path.join(pluginDir, 'video_extract.js'));

// Set up DOMPurify with jsdom
const { JSDOM } = require('jsdom');
const createDOMPurify = require('dompurify');
const domWindow = new JSDOM('').window;
const DOMPurify = createDOMPurify(domWindow);

/**
 * Create and configure a markdown-it instance with the given settings.
 *
 * @param {Object} settings - Configuration settings
 * @returns {Object} Configured markdown-it instance
 */
function createMarkdownInstance(settings) {
    // Initialize with commonmark preset, linkify enabled
    const md = markdownit('commonmark', {
        linkify: true,
        typographer: false
    });

    // Enable GFM extensions
    md.enable(['table', 'strikethrough']);
    md.enable('linkify');

    // Configure syntax highlighting with highlight.js
    md.options.highlight = function(code, lang) {
        if (lang && hljs.getLanguage(lang)) {
            try {
                return hljs.highlight(code, { language: lang }).value;
            } catch (_) {}
        }
        return ''; // Let markdown-it escape the code
    };

    // Apply plugins in order (matching Python backend)
    md.use(markdownitFootnote);
    md.use(markdownitTaskLists);

    // Custom link patterns (auto-linking based on regex patterns)
    md.use(linkPatternsPlugin, {
        enabled: settings.autoLinkEnabled || false,
        patterns: settings.autoLinkPatterns || '',
        urls: settings.autoLinkUrls || ''
    });

    // Truncate long auto-linked URLs
    md.use(truncateLinksPlugin, { trim_limit: 40 });

    // Code-friendly mode: asterisk-only emphasis
    if (settings.markupCodeFriendly) {
        md.use(asteriskEmphasisPlugin);
    }

    return md;
}

/**
 * Convert markdown to HTML using the same pipeline as the frontend converter.
 *
 * @param {string} text - Markdown source text
 * @param {Object} settings - Configuration settings
 * @returns {string} Rendered and sanitized HTML
 */
function convertMarkdown(text, settings) {
    const md = createMarkdownInstance(settings);

    const mathjaxEnabled = settings.mathjaxEnabled || false;
    const videoEmbeddingEnabled = settings.videoEmbeddingEnabled || false;

    // Phase 1: Extract video embeds to tokens (before any processing)
    let videoBlocks = [];
    if (videoEmbeddingEnabled) {
        const videoResult = videoExtract.extractVideoEmbeds(text);
        text = videoResult.text;
        videoBlocks = videoResult.videoBlocks;
    }

    // MathJax preprocessing
    let mathBlocks = null;
    if (mathjaxEnabled) {
        // Protect $ inside code spans
        text = mathExtract.protectCodeDollars(text);
        // Extract math to @@N@@ tokens
        const result = mathExtract.extractMath(text);
        text = result.text;
        mathBlocks = result.mathBlocks;
        // Convert \$ to &dollar;
        text = mathExtract.escapeDollars(text);
    }

    // Render markdown to HTML
    let html = md.render(text);

    // MathJax postprocessing
    if (mathjaxEnabled) {
        // Restore $ in code spans
        html = mathExtract.restoreCodeDollars(html);
        // Restore math blocks from tokens
        if (mathBlocks && mathBlocks.length > 0) {
            html = mathExtract.restoreMath(html, mathBlocks);
        }
    }

    // Sanitization (CRITICAL for XSS prevention)
    // No iframe whitelist needed - video tokens (@@VIDEO0@@) pass through as text
    html = DOMPurify.sanitize(html);

    // Restore video tokens to iframes (AFTER sanitization)
    if (videoEmbeddingEnabled && videoBlocks.length > 0) {
        html = videoExtract.restoreVideoEmbeds(html, videoBlocks);
    }

    return html;
}

/**
 * Main entry point - read from stdin and write to stdout.
 */
async function main() {
    let inputData = '';

    // Read all input from stdin
    process.stdin.setEncoding('utf8');
    for await (const chunk of process.stdin) {
        inputData += chunk;
    }

    try {
        const input = JSON.parse(inputData);
        const markdown = input.markdown || '';
        const settings = input.settings || {};

        const html = convertMarkdown(markdown, settings);

        const output = { html: html };
        process.stdout.write(JSON.stringify(output));
    } catch (error) {
        const output = { error: error.message };
        process.stdout.write(JSON.stringify(output));
        process.exit(1);
    }
}

main();
