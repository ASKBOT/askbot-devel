/* global askbot, markdownit, markdownitFootnote, markdownitTaskLists,
   linkPatternsPlugin, truncateLinksPlugin,
   markdownitAsteriskEmphasis, markdownitMathExtract, videoExtract,
   DOMPurify, MathJax, hljs */
/**
 * Askbot markdown converter using markdown-it.
 *
 * Replaces Showdown with markdown-it, matching the Python backend's plugin
 * configuration and rendering behavior.
 */
var getAskbotMarkdownConverter = function() {
  askbot['controllers'] = askbot['controllers'] || {};
  var converter = askbot['controllers']['markdownConverter'];
  if (!converter) {
    converter = new AskbotMarkdownConverter();
    askbot['controllers']['markdownConverter'] = converter;
  }
  return converter;
};

var AskbotMarkdownConverter = function() {
  this._md = this._createMarkdownInstance();
  this._timeout = null;
};

/**
 * Create and configure the markdown-it instance.
 *
 * Plugin load order matches Python backend exactly.
 */
AskbotMarkdownConverter.prototype._createMarkdownInstance = function() {
  // Initialize with commonmark preset, linkify enabled
  var md = markdownit('commonmark', {
    linkify: true,
    typographer: false
  });

  // Enable GFM extensions
  md.enable(['table', 'strikethrough']);
  md.enable('linkify');

  // Configure syntax highlighting with highlight.js
  // Must be set before plugins
  md.options.highlight = function(code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(code, {language: lang}).value;
      } catch (_) {}
    }
    return ''; // Let markdown-it escape the code
  };

  // Apply plugins in order (matching Python backend)
  md.use(markdownitFootnote);
  md.use(markdownitTaskLists);
  // Note: Video embedding is handled by extract/restore pattern in makeHtml()
  // for security (iframes inserted after sanitization)

  // Custom link patterns (auto-linking based on regex patterns)
  var settings = askbot['settings'] || {};
  md.use(linkPatternsPlugin, {
    enabled: settings.autoLinkEnabled || false,
    patterns: settings.autoLinkPatterns || '',
    urls: settings.autoLinkUrls || ''
  });

  // Truncate long auto-linked URLs
  md.use(truncateLinksPlugin, {trim_limit: 40});

  // Code-friendly mode: asterisk-only emphasis
  if (settings.markupCodeFriendly) {
    md.use(markdownitAsteriskEmphasis);
  }

  return md;
};

/**
 * Schedule MathJax typesetting with 500ms debounce.
 */
AskbotMarkdownConverter.prototype.scheduleMathJaxRendering = function() {
  if (this._timeout) {
    clearTimeout(this._timeout);
  }
  var renderFunc = function() {
    MathJax.Hub.Queue(['Typeset', MathJax.Hub, 'previewer']);
  };
  this._timeout = setTimeout(renderFunc, 500);
};

/**
 * Convert markdown text to HTML.
 *
 * Handles video embed extraction, MathJax preprocessing/postprocessing,
 * and sanitization with post-sanitization video restoration.
 *
 * @param {string} text - Markdown source text
 * @returns {string} Sanitized HTML
 */
AskbotMarkdownConverter.prototype.makeHtml = function(text) {
  var settings = askbot['settings'] || {};
  var mathjaxEnabled = settings.mathjaxEnabled !== false &&
                       typeof MathJax !== 'undefined';
  var videoEmbeddingEnabled = settings.videoEmbeddingEnabled || false;

  // Phase 1: Extract video embeds to tokens (before any processing)
  // This happens BEFORE sanitization, tokens restored AFTER
  var videoBlocks = [];
  if (videoEmbeddingEnabled) {
    var videoResult = videoExtract.extractVideoEmbeds(text);
    text = videoResult.text;
    videoBlocks = videoResult.videoBlocks;
  }

  // MathJax preprocessing
  var mathBlocks = null;
  if (mathjaxEnabled) {
    // Protect $ inside code spans
    text = markdownitMathExtract.protectCodeDollars(text);
    // Extract math to @@N@@ tokens
    var result = markdownitMathExtract.extractMath(text);
    text = result.text;
    mathBlocks = result.mathBlocks;
    // Convert \$ to &dollar;
    text = markdownitMathExtract.escapeDollars(text);
  }

  // Render markdown to HTML
  var html = this._md.render(text);

  // MathJax postprocessing
  if (mathjaxEnabled) {
    // Restore $ in code spans
    html = markdownitMathExtract.restoreCodeDollars(html);
    // Restore math blocks from tokens
    if (mathBlocks && mathBlocks.length > 0) {
      html = markdownitMathExtract.restoreMath(html, mathBlocks);
    }
  }

  // Sanitization (CRITICAL for XSS prevention)
  // No iframe whitelist needed - video tokens (@@VIDEO0@@) pass through as text
  html = DOMPurify.sanitize(html);

  // Phase 6: Restore video tokens to iframes (AFTER sanitization)
  // This is the key security improvement - iframes are never subject to sanitization
  if (videoEmbeddingEnabled && videoBlocks.length > 0) {
    html = videoExtract.restoreVideoEmbeds(html, videoBlocks);
  }

  // MathJax re-rendering
  if (mathjaxEnabled) {
    // Push HTML update to MathJax queue (ensures proper sequencing)
    MathJax.Hub.queue.Push(function() {
      $('.wmd-preview').html(html);
    });
    // Schedule typesetting with debounce
    this.scheduleMathJaxRendering();
    return $('.wmd-preview').html();
  }

  return html;
};
