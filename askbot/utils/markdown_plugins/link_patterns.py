"""
Custom link patterns plugin for markdown-it-py.

Automatically converts text matching regex patterns to links.

Example:
    Settings:
        AUTO_LINK_PATTERNS = "#bug(\\d+)"
        AUTO_LINK_URLS = "https://bugs.example.com/show?id=\\1"

    Text:
        "Fixed #bug123"

    Output:
        Fixed <a href="https://bugs.example.com/show?id=123">#bug123</a>

Based on askbot settings:
    - ENABLE_AUTO_LINKING (bool)
    - AUTO_LINK_PATTERNS (multiline string of regexes)
    - AUTO_LINK_URLS (multiline string of URL templates)
"""

import re
import logging
from markdown_it import MarkdownIt
from markdown_it.rules_core import StateCore
from markdown_it.token import Token


logger = logging.getLogger('askbot.markdown.link_patterns')


def parse_pattern_config(patterns_str, urls_str):
    """
    Parse pattern and URL configuration strings.

    Args:
        patterns_str: Newline-separated regex patterns
        urls_str: Newline-separated URL templates

    Returns:
        List of (compiled_regex, url_template) tuples
    """
    if not patterns_str or not urls_str:
        return []

    pattern_lines = [p.strip() for p in patterns_str.strip().split('\n') if p.strip()]
    url_lines = [u.strip() for u in urls_str.strip().split('\n') if u.strip()]

    if len(pattern_lines) != len(url_lines):
        logger.warning(
            f"Pattern count ({len(pattern_lines)}) != URL count ({len(url_lines)}). "
            f"Auto-linking disabled."
        )
        return []

    rules = []
    for idx, (pattern_str, url_template) in enumerate(zip(pattern_lines, url_lines)):
        try:
            compiled_pattern = re.compile(pattern_str)
            rules.append((compiled_pattern, url_template))
        except re.error as e:
            logger.error(
                f"Invalid regex pattern at line {idx+1}: {pattern_str}. Error: {e}"
            )
            continue

    return rules


def apply_link_patterns(state: StateCore, rules):
    """
    Traverse token tree and replace matching text with links.
    """
    if not rules:
        return

    for block_idx, block_token in enumerate(state.tokens):
        if block_token.type != 'inline' or not block_token.children:
            continue

        new_children = []

        for child_token in block_token.children:
            if child_token.type != 'text':
                new_children.append(child_token)
                continue

            text = child_token.content
            processed_tokens = process_text_with_patterns(text, rules, state)
            new_children.extend(processed_tokens)

        block_token.children = new_children


def process_text_with_patterns(text, rules, state):
    """
    Process a text string, replacing pattern matches with link tokens.

    Returns:
        List of tokens (text and link tokens)
    """
    tokens = []

    # Track all matches across all patterns
    all_matches = []
    for pattern, url_template in rules:
        for match in pattern.finditer(text):
            all_matches.append({
                'start': match.start(),
                'end': match.end(),
                'matched_text': match.group(0),
                'url_template': url_template,
                'groups': match.groups(),
            })

    # Sort matches by start position
    all_matches.sort(key=lambda m: m['start'])

    # Merge overlapping matches (keep first)
    merged_matches = []
    for match in all_matches:
        if not merged_matches:
            merged_matches.append(match)
            continue

        last_match = merged_matches[-1]
        if match['start'] < last_match['end']:
            # Overlapping, skip this match
            continue

        merged_matches.append(match)

    # Build token list
    last_pos = 0
    for match in merged_matches:
        # Add text before match
        if match['start'] > last_pos:
            text_token = Token('text', '', 0)
            text_token.content = text[last_pos:match['start']]
            tokens.append(text_token)

        # Build URL from template
        url = match['url_template']
        for idx, group in enumerate(match['groups'], start=1):
            if group is not None:
                # Replace \1, \2, etc. with captured groups
                url = url.replace(f'\\{idx}', group)

        # Create link tokens
        link_open = Token('link_open', 'a', 1)
        link_open.attrs = {'href': url}
        link_open.markup = 'autolink'
        tokens.append(link_open)

        link_text = Token('text', '', 0)
        link_text.content = match['matched_text']
        tokens.append(link_text)

        link_close = Token('link_close', 'a', -1)
        tokens.append(link_close)

        last_pos = match['end']

    # Add remaining text
    if last_pos < len(text):
        text_token = Token('text', '', 0)
        text_token.content = text[last_pos:]
        tokens.append(text_token)

    # If no matches, return original text as single token
    if not tokens:
        text_token = Token('text', '', 0)
        text_token.content = text
        return [text_token]

    return tokens


def link_patterns_plugin(md: MarkdownIt, config: dict) -> MarkdownIt:
    """
    Plugin to auto-link text matching custom patterns.

    Args:
        config: Dictionary with keys:
            - enabled (bool): Whether plugin is active
            - patterns (str): Newline-separated regex patterns
            - urls (str): Newline-separated URL templates

    Usage:
        md = MarkdownIt()
        md.use(link_patterns_plugin, {
            'enabled': True,
            'patterns': '#bug(\\\\d+)',
            'urls': 'https://bugs.example.com/\\\\1'
        })
    """
    if not config.get('enabled', False):
        return md

    patterns_str = config.get('patterns', '')
    urls_str = config.get('urls', '')

    rules = parse_pattern_config(patterns_str, urls_str)

    if not rules:
        logger.info("No valid link pattern rules configured")
        return md

    logger.info(f"Loaded {len(rules)} link pattern rules")

    def link_patterns_core_rule(state: StateCore):
        apply_link_patterns(state, rules)

    # Run after linkify but before other core rules
    md.core.ruler.after('linkify', 'custom_link_patterns', link_patterns_core_rule)

    return md
