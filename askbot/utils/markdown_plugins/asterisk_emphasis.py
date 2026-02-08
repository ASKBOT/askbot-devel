"""
Asterisk-only emphasis plugin for markdown-it-py.

Code-friendly mode: disables underscore emphasis (_italic_ and __bold__)
while keeping asterisk emphasis (*italic* and **bold**) working.

This prevents issues with snake_case variable names in programming discussions
while preserving basic text formatting.

Based on markdown-it-py's built-in emphasis rule, modified to only handle '*'.
"""

from __future__ import annotations

from markdown_it import MarkdownIt
from markdown_it.rules_inline.state_inline import Delimiter, StateInline


def tokenize(state: StateInline, silent: bool) -> bool:
    """Insert each marker as a separate text token, and add it to delimiter list.

    Only handles asterisk (*), ignores underscore (_).
    """
    start = state.pos
    marker = state.src[start]

    if silent:
        return False

    # KEY CHANGE: Only handle asterisk, not underscore
    if marker != "*":
        return False

    scanned = state.scanDelims(state.pos, True)  # canSplitWord=True for *

    for _ in range(scanned.length):
        token = state.push("text", "", 0)
        token.content = marker
        state.delimiters.append(
            Delimiter(
                marker=ord(marker),
                length=scanned.length,
                token=len(state.tokens) - 1,
                end=-1,
                open=scanned.can_open,
                close=scanned.can_close,
            )
        )

    state.pos += scanned.length

    return True


def _postProcess(state: StateInline, delimiters: list[Delimiter]) -> None:
    """Process delimiter list and convert matched pairs to emphasis tags."""
    i = len(delimiters) - 1
    while i >= 0:
        startDelim = delimiters[i]

        # KEY CHANGE: Only process asterisk markers (0x2A = '*')
        # Skip underscore (0x5F = '_')
        if startDelim.marker != 0x2A:
            i -= 1
            continue

        # Process only opening markers
        if startDelim.end == -1:
            i -= 1
            continue

        endDelim = delimiters[startDelim.end]

        # If the previous delimiter has the same marker and is adjacent to this one,
        # merge those into one strong delimiter.
        #
        # `<em><em>whatever</em></em>` -> `<strong>whatever</strong>`
        #
        isStrong = (
            i > 0
            and delimiters[i - 1].end == startDelim.end + 1
            # check that first two markers match and adjacent
            and delimiters[i - 1].marker == startDelim.marker
            and delimiters[i - 1].token == startDelim.token - 1
            # check that last two markers are adjacent (we can safely assume they match)
            and delimiters[startDelim.end + 1].token == endDelim.token + 1
        )

        ch = chr(startDelim.marker)

        token = state.tokens[startDelim.token]
        token.type = "strong_open" if isStrong else "em_open"
        token.tag = "strong" if isStrong else "em"
        token.nesting = 1
        token.markup = ch + ch if isStrong else ch
        token.content = ""

        token = state.tokens[endDelim.token]
        token.type = "strong_close" if isStrong else "em_close"
        token.tag = "strong" if isStrong else "em"
        token.nesting = -1
        token.markup = ch + ch if isStrong else ch
        token.content = ""

        if isStrong:
            state.tokens[delimiters[i - 1].token].content = ""
            state.tokens[delimiters[startDelim.end + 1].token].content = ""
            i -= 1

        i -= 1


def postProcess(state: StateInline) -> None:
    """Walk through delimiter list and replace text tokens with tags."""
    _postProcess(state, state.delimiters)

    for token in state.tokens_meta:
        if token and "delimiters" in token:
            _postProcess(state, token["delimiters"])


def asterisk_emphasis_plugin(md: MarkdownIt) -> None:
    """Plugin to replace emphasis with asterisk-only version.

    Disables underscore emphasis (_italic_ and __bold__) while keeping
    asterisk emphasis (*italic* and **bold**) working.

    Usage:
        md = MarkdownIt()
        md.use(asterisk_emphasis_plugin)
    """
    # Replace the tokenize rule in inline parser
    md.inline.ruler.at("emphasis", tokenize)

    # Replace the postProcess rule in inline2 parser
    md.inline.ruler2.at("emphasis", postProcess)
