/**
 * link_patterns.js - Custom link patterns plugin for markdown-it
 *
 * Automatically converts text matching regex patterns to links.
 * Port of askbot/utils/markdown_plugins/link_patterns.py
 *
 * Example:
 *   Config:
 *     patterns: "#bug(\\d+)"
 *     urls: "https://bugs.example.com/show?id=\\1"
 *
 *   Text:
 *     "Fixed #bug123"
 *
 *   Output:
 *     Fixed <a href="https://bugs.example.com/show?id=123">#bug123</a>
 */
(function(window) {
  'use strict';

  /**
   * Utility: Replace element at position with multiple elements.
   * Same pattern as markdown-it uses internally.
   */
  function arrayReplaceAt(src, pos, newElements) {
    return [].concat(src.slice(0, pos), newElements, src.slice(pos + 1));
  }

  /**
   * Parse pattern and URL configuration strings.
   *
   * @param {string} patternsStr - Newline-separated regex patterns
   * @param {string} urlsStr - Newline-separated URL templates
   * @returns {Array} Array of {pattern: RegExp, urlTemplate: string} objects
   */
  function parsePatternConfig(patternsStr, urlsStr) {
    if (!patternsStr || !urlsStr) {
      return [];
    }

    var patternLines = patternsStr.trim().split('\n').filter(function(p) {
      return p.trim();
    }).map(function(p) {
      return p.trim();
    });

    var urlLines = urlsStr.trim().split('\n').filter(function(u) {
      return u.trim();
    }).map(function(u) {
      return u.trim();
    });

    if (patternLines.length !== urlLines.length) {
      console.warn(
        'link_patterns: Pattern count (' + patternLines.length +
        ') != URL count (' + urlLines.length + '). Auto-linking disabled.'
      );
      return [];
    }

    var rules = [];
    for (var i = 0; i < patternLines.length; i++) {
      try {
        var compiledPattern = new RegExp(patternLines[i], 'g');
        rules.push({
          pattern: compiledPattern,
          urlTemplate: urlLines[i]
        });
      } catch (e) {
        console.error(
          'link_patterns: Invalid regex at line ' + (i + 1) +
          ': ' + patternLines[i] + '. Error: ' + e.message
        );
      }
    }

    return rules;
  }

  /**
   * Process a text string, replacing pattern matches with link tokens.
   *
   * @param {string} text - The text to process
   * @param {Array} rules - Array of {pattern, urlTemplate} objects
   * @param {Object} state - markdown-it state object
   * @returns {Array} Array of tokens (text and link tokens)
   */
  function processTextWithPatterns(text, rules, state) {
    var Token = state.Token;
    var tokens = [];

    // Track all matches across all patterns
    var allMatches = [];
    for (var r = 0; r < rules.length; r++) {
      var rule = rules[r];
      // Reset lastIndex for global regex
      rule.pattern.lastIndex = 0;
      var match;
      while ((match = rule.pattern.exec(text)) !== null) {
        // Capture groups (match[1], match[2], etc.)
        var groups = [];
        for (var g = 1; g < match.length; g++) {
          groups.push(match[g]);
        }
        allMatches.push({
          start: match.index,
          end: match.index + match[0].length,
          matchedText: match[0],
          urlTemplate: rule.urlTemplate,
          groups: groups
        });
      }
    }

    // Sort matches by start position
    allMatches.sort(function(a, b) {
      return a.start - b.start;
    });

    // Merge overlapping matches (keep first)
    var mergedMatches = [];
    for (var m = 0; m < allMatches.length; m++) {
      var currentMatch = allMatches[m];
      if (mergedMatches.length === 0) {
        mergedMatches.push(currentMatch);
        continue;
      }

      var lastMatch = mergedMatches[mergedMatches.length - 1];
      if (currentMatch.start < lastMatch.end) {
        // Overlapping, skip this match
        continue;
      }

      mergedMatches.push(currentMatch);
    }

    // Build token list
    var lastPos = 0;
    for (var i = 0; i < mergedMatches.length; i++) {
      var matchInfo = mergedMatches[i];

      // Add text before match
      if (matchInfo.start > lastPos) {
        var textToken = new Token('text', '', 0);
        textToken.content = text.slice(lastPos, matchInfo.start);
        tokens.push(textToken);
      }

      // Build URL from template
      var url = matchInfo.urlTemplate;
      for (var idx = 0; idx < matchInfo.groups.length; idx++) {
        var group = matchInfo.groups[idx];
        if (group !== undefined && group !== null) {
          // Replace \1, \2, etc. with captured groups
          url = url.split('\\' + (idx + 1)).join(group);
        }
      }

      // Create link tokens
      var linkOpen = new Token('link_open', 'a', 1);
      linkOpen.attrs = [['href', url]];
      linkOpen.markup = 'autolink';
      tokens.push(linkOpen);

      var linkText = new Token('text', '', 0);
      linkText.content = matchInfo.matchedText;
      tokens.push(linkText);

      var linkClose = new Token('link_close', 'a', -1);
      tokens.push(linkClose);

      lastPos = matchInfo.end;
    }

    // Add remaining text
    if (lastPos < text.length) {
      var remainingToken = new Token('text', '', 0);
      remainingToken.content = text.slice(lastPos);
      tokens.push(remainingToken);
    }

    // If no matches, return original text as single token
    if (tokens.length === 0) {
      var originalToken = new Token('text', '', 0);
      originalToken.content = text;
      return [originalToken];
    }

    return tokens;
  }

  /**
   * Traverse token tree and replace matching text with links.
   *
   * @param {Object} state - markdown-it StateCore object
   * @param {Array} rules - Array of {pattern, urlTemplate} objects
   */
  function applyLinkPatterns(state, rules) {
    if (!rules || rules.length === 0) {
      return;
    }

    var blockTokens = state.tokens;

    for (var j = 0; j < blockTokens.length; j++) {
      var blockToken = blockTokens[j];

      if (blockToken.type !== 'inline' || !blockToken.children) {
        continue;
      }

      var children = blockToken.children;

      // Process children in reverse to handle index shifts
      for (var i = children.length - 1; i >= 0; i--) {
        var childToken = children[i];

        if (childToken.type !== 'text') {
          continue;
        }

        var text = childToken.content;
        var processedTokens = processTextWithPatterns(text, rules, state);

        // Only replace if we actually created links
        if (processedTokens.length > 1 ||
            (processedTokens.length === 1 && processedTokens[0] !== childToken)) {
          children = arrayReplaceAt(children, i, processedTokens);
        }
      }

      blockToken.children = children;
    }
  }

  /**
   * Plugin to auto-link text matching custom patterns.
   *
   * @param {MarkdownIt} md - markdown-it instance
   * @param {Object} config - Configuration object
   * @param {boolean} config.enabled - Whether plugin is active
   * @param {string} config.patterns - Newline-separated regex patterns
   * @param {string} config.urls - Newline-separated URL templates
   * @returns {MarkdownIt} The markdown-it instance
   */
  function linkPatternsPlugin(md, config) {
    config = config || {};

    if (!config.enabled) {
      return md;
    }

    var patternsStr = config.patterns || '';
    var urlsStr = config.urls || '';

    var rules = parsePatternConfig(patternsStr, urlsStr);

    if (rules.length === 0) {
      return md;
    }

    // Run after linkify but before other core rules
    md.core.ruler.after('linkify', 'custom_link_patterns', function(state) {
      applyLinkPatterns(state, rules);
    });

    return md;
  }

  // Export for browser and module environments
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = linkPatternsPlugin;
  } else {
    window.linkPatternsPlugin = linkPatternsPlugin;
  }

})(typeof window !== 'undefined' ? window : this);
