/**
 * truncate_links plugin for markdown-it
 * Truncates auto-linkified URLs to prevent layout issues.
 * Matches Python backend: askbot/utils/markdown_plugins/truncate_links.py
 */
(function (root, factory) {
  if (typeof exports === 'object') {
    module.exports = factory();
  } else {
    root.truncateLinksPlugin = factory();
  }
}(this, function () {
  'use strict';

  var DEFAULT_LIMIT = 40;

  function truncateUrlText(text, limit) {
    if (limit == null || limit <= 0 || text.length <= limit) {
      return text;
    }
    return text.slice(0, Math.max(0, limit - 1)) + '\u2026';
  }

  function truncateLinkifyUrls(state, trimLimit) {
    if (trimLimit == null || trimLimit <= 0) return;

    state.tokens.forEach(function (blockToken) {
      if (blockToken.type !== 'inline' || !blockToken.children) return;

      var children = blockToken.children;
      for (var i = 0; i < children.length; i++) {
        var token = children[i];

        if (token.type === 'link_open' && token.markup === 'linkify') {
          var href = token.attrGet('href');

          if (i + 1 < children.length && children[i + 1].type === 'text') {
            var textToken = children[i + 1];
            var originalText = textToken.content;

            if (originalText.length > trimLimit) {
              textToken.content = truncateUrlText(originalText, trimLimit);
              if (href) {
                token.attrSet('title', href);
              }
            }
          }
        }
      }
    });
  }

  return function truncateLinksPlugin(md, options) {
    options = options || {};
    var trimLimit = options.trim_limit != null ? options.trim_limit : DEFAULT_LIMIT;

    md.core.ruler.after('linkify', 'truncate_links', function (state) {
      truncateLinkifyUrls(state, trimLimit);
    });
  };
}));
