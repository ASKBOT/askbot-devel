/**
 * MathJax preprocessing plugin for markdown-it.
 *
 * Extracts math content before markdown processing to protect it from
 * markdown rules (linkify, emphasis, etc), then restores after.
 *
 * Based on Stack Exchange's mathjax-editing.js by Geoff Dalgas.
 * Ported from:
 *   - askbot/utils/markdown_plugins/math_extract.py (337 lines)
 *   - askbot/utils/markdown_plugins/dollar_escape.py (42 lines)
 *
 * Functions:
 *   - protectCodeDollars(text)  - $ -> ~D inside backtick code spans
 *   - extractMath(text)         - Extract math to @@N@@ tokens
 *   - escapeDollars(text)       - \$ -> &dollar;
 *   - restoreCodeDollars(html)  - ~D -> $
 *   - restoreMath(html, blocks) - @@N@@ -> original math
 *
 * Supported math delimiters:
 *   - Inline: $...$
 *   - Display: $$...$$
 *   - LaTeX display: \[...\]
 *   - LaTeX environments: \begin{env}...\end{env}
 */
(function(window) {
    'use strict';

    // Matches math delimiters and structural tokens
    // Pattern matches: $$, $, \begin{...}, \end{...}, \[, \], {, }, newlines, existing tokens
    var MATH_SPLIT = /(\$\$?|\\(?:begin|end)\{[a-z]*\*?\}|\\[\[\]]|[{}]|(?:\n\s*)+|@@\d+@@)/gi;

    /**
     * Replace $ with ~D inside backtick code spans.
     * Prevents false math detection in code blocks.
     *
     * This is Stack Exchange's "detilde" approach.
     *
     * @param {string} text - Markdown source text
     * @returns {string} Text with $ replaced by ~D inside code spans
     */
    function protectCodeDollars(text) {
        var result = [];
        var i = 0;
        var len = text.length;

        while (i < len) {
            // Check for backtick
            if (text[i] === '`') {
                // Check if it's escaped
                if (i > 0 && text[i - 1] === '\\') {
                    result.push(text[i]);
                    i++;
                    continue;
                }

                // Find matching closing backtick
                var start = i;
                i++;

                // Count consecutive backticks for the opening
                var backtickCount = 1;
                while (i < len && text[i] === '`') {
                    backtickCount++;
                    i++;
                }

                // Now find the matching closing backticks
                var codeContentStart = i;
                var found = false;

                while (i < len) {
                    if (text[i] === '`') {
                        // Count consecutive backticks
                        var closingCount = 0;
                        var closingStart = i;
                        while (i < len && text[i] === '`') {
                            closingCount++;
                            i++;
                        }

                        if (closingCount === backtickCount) {
                            // Found matching close
                            // Extract code content and replace $ with ~D
                            var codeContent = text.slice(codeContentStart, closingStart);
                            codeContent = codeContent.replace(/\$/g, '~D');

                            // Append: opening backticks + modified content + closing backticks
                            result.push(repeatChar('`', backtickCount));
                            result.push(codeContent);
                            result.push(repeatChar('`', backtickCount));
                            found = true;
                            break;
                        }
                        // Not matching - continue looking
                    } else {
                        i++;
                    }
                }

                if (!found) {
                    // No matching close found - treat as literal backticks
                    result.push(text.slice(start, i));
                }
            } else {
                result.push(text[i]);
                i++;
            }
        }

        return result.join('');
    }

    /**
     * Extract math expressions and replace with tokens.
     *
     * Implements Stack Exchange's removeMath() algorithm using a state machine
     * to track delimiter contexts and extract complete math blocks.
     *
     * @param {string} text - Markdown source text (already processed by protectCodeDollars)
     * @returns {object} { text: tokenizedText, mathBlocks: array }
     *
     * Supported formats:
     *   - Inline: $...$
     *   - Display: $$...$$
     *   - LaTeX display: \[...\]
     *   - LaTeX environments: \begin{env}...\end{env}
     */
    function extractMath(text) {
        var mathBlocks = [];

        // Split text by delimiters
        var parts = text.split(MATH_SPLIT);

        var result = [];
        var mathStart = null;
        var mathDelimiter = null;
        var mathContent = [];
        var braceDepth = 0;

        for (var idx = 0; idx < parts.length; idx++) {
            var part = parts[idx];
            if (part === undefined || part === '') continue;

            // Check if we're currently inside math
            if (mathStart !== null) {
                // We're inside math - look for closing delimiter

                if (mathDelimiter === '$$') {
                    if (part === '$$') {
                        // Found closing $$
                        mathContent.push(part);
                        var fullMath = mathContent.join('');
                        var token = '@@' + mathBlocks.length + '@@';
                        mathBlocks.push(fullMath);
                        result.push(token);

                        // Reset state
                        mathStart = null;
                        mathDelimiter = null;
                        mathContent = [];
                    } else {
                        mathContent.push(part);
                    }

                } else if (mathDelimiter === '$') {
                    if (part === '$') {
                        // Check if this $ is escaped (preceded by \)
                        var contentSoFar = mathContent.join('');
                        if (contentSoFar.endsWith('\\')) {
                            // This is \$ (escaped dollar in LaTeX), not a closing delimiter
                            mathContent.push(part);
                        } else {
                            // Found closing $
                            mathContent.push(part);
                            fullMath = mathContent.join('');
                            token = '@@' + mathBlocks.length + '@@';
                            mathBlocks.push(fullMath);
                            result.push(token);

                            // Reset state
                            mathStart = null;
                            mathDelimiter = null;
                            mathContent = [];
                        }
                    } else if (part === '$$') {
                        // Check if this $$ is escaped
                        contentSoFar = mathContent.join('');
                        if (contentSoFar.endsWith('\\')) {
                            // This is \$$ (escaped), treat first $ as escaped
                            mathContent.push('$');
                            // Check again after adding first $
                            var contentAfter = mathContent.join('');
                            if (contentAfter.endsWith('\\$')) {
                                // Both are escaped: \$$
                                mathContent.push('$');
                            } else {
                                // First was escaped \$, second closes
                                mathContent.push('$');
                                fullMath = mathContent.join('');
                                token = '@@' + mathBlocks.length + '@@';
                                mathBlocks.push(fullMath);
                                result.push(token);

                                // Reset state
                                mathStart = null;
                                mathDelimiter = null;
                                mathContent = [];
                            }
                        } else {
                            // This is NOT an escaped delimiter for single $
                            // Treat as two separate $ signs - close current and open new
                            mathContent.push('$');
                            fullMath = mathContent.join('');
                            token = '@@' + mathBlocks.length + '@@';
                            mathBlocks.push(fullMath);
                            result.push(token);

                            // Start new $$ block
                            mathStart = true;
                            mathDelimiter = '$$';
                            mathContent = ['$$'];
                        }
                    } else {
                        mathContent.push(part);
                    }

                } else if (mathDelimiter === '\\[') {
                    if (part === '\\]') {
                        // Found closing \]
                        mathContent.push(part);
                        fullMath = mathContent.join('');
                        token = '@@' + mathBlocks.length + '@@';
                        mathBlocks.push(fullMath);
                        result.push(token);

                        // Reset state
                        mathStart = null;
                        mathDelimiter = null;
                        mathContent = [];
                    } else {
                        mathContent.push(part);
                    }

                } else if (mathDelimiter.indexOf('\\begin') === 0) {
                    // Track brace depth for environments
                    if (part === '{') {
                        braceDepth++;
                        mathContent.push(part);
                    } else if (part === '}') {
                        braceDepth--;
                        mathContent.push(part);
                    } else if (part.indexOf('\\end') === 0) {
                        // Extract environment name from \end{name}
                        var endMatch = part.match(/\\end\{([a-z]*\*?)\}/i);
                        var beginMatch = mathDelimiter.match(/\\begin\{([a-z]*\*?)\}/i);

                        if (endMatch && beginMatch && endMatch[1] === beginMatch[1]) {
                            // Found matching \end
                            mathContent.push(part);
                            fullMath = mathContent.join('');
                            token = '@@' + mathBlocks.length + '@@';
                            mathBlocks.push(fullMath);
                            result.push(token);

                            // Reset state
                            mathStart = null;
                            mathDelimiter = null;
                            mathContent = [];
                            braceDepth = 0;
                        } else {
                            // Not matching environment
                            mathContent.push(part);
                        }
                    } else {
                        mathContent.push(part);
                    }
                }

            } else {
                // Not inside math - check for opening delimiters

                if (part === '$$') {
                    // Start display math
                    mathStart = true;
                    mathDelimiter = '$$';
                    mathContent = ['$$'];

                } else if (part === '$') {
                    // Start inline math
                    mathStart = true;
                    mathDelimiter = '$';
                    mathContent = ['$'];

                } else if (part === '\\[') {
                    // Start LaTeX display math
                    mathStart = true;
                    mathDelimiter = '\\[';
                    mathContent = ['\\['];

                } else if (part.indexOf('\\begin') === 0) {
                    // Start LaTeX environment
                    mathStart = true;
                    mathDelimiter = part;
                    mathContent = [part];
                    braceDepth = 0;

                } else if (part.indexOf('@@') === 0 && part.slice(-2) === '@@') {
                    // Existing token - preserve it
                    result.push(part);

                } else {
                    // Regular text
                    result.push(part);
                }
            }
        }

        // Handle unclosed math (treat as regular text)
        if (mathStart !== null) {
            for (var j = 0; j < mathContent.length; j++) {
                result.push(mathContent[j]);
            }
        }

        return {
            text: result.join(''),
            mathBlocks: mathBlocks
        };
    }

    /**
     * Convert \$ -> &dollar; in text.
     *
     * IMPORTANT: Must run AFTER extractMath(), so math is already
     * protected as @@N@@ tokens. This ensures we never touch dollars
     * inside math expressions.
     *
     * @param {string} text - Text with math already extracted (has @@N@@ tokens)
     * @returns {string} Text with \$ replaced by &dollar;
     */
    function escapeDollars(text) {
        // Simple replacement - math is already safe in @@N@@ tokens
        return text.replace(/\\\$/g, '&dollar;');
    }

    /**
     * Restore dollars in code spans after markdown processing.
     *
     * This reverses protectCodeDollars() by replacing ~D back to $.
     * Must be called AFTER markdown rendering.
     *
     * @param {string} html - HTML with ~D placeholders in code spans
     * @returns {string} HTML with $ restored in code spans
     */
    function restoreCodeDollars(html) {
        return html.replace(/~D/g, '$');
    }

    /**
     * Restore math blocks from tokens.
     *
     * @param {string} html - Markdown-rendered HTML with @@N@@ tokens
     * @param {array} mathBlocks - Array of original math strings
     * @returns {string} HTML with tokens replaced by original math
     */
    function restoreMath(html, mathBlocks) {
        for (var i = 0; i < mathBlocks.length; i++) {
            var token = '@@' + i + '@@';
            html = html.split(token).join(mathBlocks[i]);
        }
        return html;
    }

    /**
     * Helper: repeat a character n times
     */
    function repeatChar(char, count) {
        var result = '';
        for (var i = 0; i < count; i++) {
            result += char;
        }
        return result;
    }

    // Export for browser and module environments
    var exports = {
        protectCodeDollars: protectCodeDollars,
        extractMath: extractMath,
        escapeDollars: escapeDollars,
        restoreCodeDollars: restoreCodeDollars,
        restoreMath: restoreMath
    };

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = exports;
    } else {
        window.markdownitMathExtract = exports;
    }

})(typeof window !== 'undefined' ? window : this);
