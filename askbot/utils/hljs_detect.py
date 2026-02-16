"""
highlight.js language detection algorithm ported to Python.

This module implements the same language auto-detection algorithm used by
highlight.js v11.11.1, ensuring consistent behavior between backend (Pygments)
and frontend (highlight.js) syntax highlighting.

Usage:
    from askbot.utils.hljs_detect import detect_language

    lang, score = detect_language(code)
    if lang:
        # Use Pygments with the detected language
        pass
"""

import re
from typing import Dict, List, Optional, Tuple

from askbot.utils.hljs_languages import (
    LANGUAGES,
    COMMON_KEYWORDS,
    SUPERSETS,
    MAX_KEYWORD_HITS,
    ALIAS_MAP,
)


def detect_language(
    code: str,
    languages: Optional[List[str]] = None,
    min_relevance: int = 2,
) -> Tuple[Optional[str], int]:
    """
    Detect the programming language of a code snippet.

    Uses the highlight.js relevance scoring algorithm:
    1. For each language, calculate a relevance score based on keyword matches
    2. Keywords in COMMON_KEYWORDS get zero relevance
    3. Each keyword match adds 1 to relevance (capped at MAX_KEYWORD_HITS per word)
    4. High-relevance patterns add additional score
    5. Sort by relevance and apply superset tie-breaking

    Args:
        code: Source code to analyze
        languages: Optional list of language IDs to consider. If None, all
                   languages in LANGUAGES are considered.
        min_relevance: Minimum relevance score to return a match.
                       Below this threshold, returns (None, 0).

    Returns:
        Tuple of (language_id, relevance_score).
        Returns (None, 0) if no language meets the minimum relevance threshold.

    Example:
        >>> code = "def hello():\\n    print('Hello, world!')"
        >>> lang, score = detect_language(code)
        >>> print(lang)  # 'python'
    """
    if not code or not code.strip():
        return (None, 0)

    if languages is None:
        languages = list(LANGUAGES.keys())
    else:
        # Normalize language names through alias map
        normalized = []
        for lang in languages:
            if lang in ALIAS_MAP:
                normalized.append(ALIAS_MAP[lang])
            elif lang in LANGUAGES:
                normalized.append(lang)
        languages = list(set(normalized))

    results: List[Tuple[str, int]] = []
    for lang_id in languages:
        if lang_id not in LANGUAGES:
            continue
        lang_def = LANGUAGES[lang_id]
        relevance = _calculate_relevance(code, lang_def)
        results.append((lang_id, relevance))

    if not results:
        return (None, 0)

    # Sort by relevance (descending), then apply superset tie-breaker
    results.sort(key=lambda x: x[1], reverse=True)
    results = _apply_superset_tiebreaker(results)

    best_lang, best_score = results[0]

    # Check minimum relevance threshold
    if best_score < min_relevance:
        return (None, 0)

    return (best_lang, best_score)


def _calculate_relevance(code: str, lang_def: Dict) -> int:
    """
    Calculate relevance score for code against a language definition.

    The algorithm follows highlight.js:
    1. Extract all word tokens from the code
    2. For each keyword match, add 1 to relevance (capped per word)
    3. Common keywords (COMMON_KEYWORDS) contribute 0 relevance
    4. High-relevance regex patterns add their relevance value

    Args:
        code: Source code to analyze
        lang_def: Language definition dictionary

    Returns:
        Integer relevance score
    """
    relevance = 0
    keyword_hits: Dict[str, int] = {}

    case_insensitive = lang_def.get('case_insensitive', False)

    # Extract words from code
    words = re.findall(r'\b[A-Za-z_][A-Za-z0-9_]*\b', code)

    # Build keyword sets for efficient lookup
    all_keywords: Dict[str, int] = {}  # word -> relevance
    keywords_dict = lang_def.get('keywords', {})

    for _category, kw_list in keywords_dict.items():
        for kw in kw_list:
            # Handle keywords with explicit relevance suffix (e.g., "nonlocal|10")
            if '|' in kw:
                kw, rel_str = kw.split('|', 1)
                kw_relevance = int(rel_str)
            else:
                kw_relevance = 1

            # Skip common keywords
            if kw.lower() in COMMON_KEYWORDS:
                kw_relevance = 0

            key = kw.lower() if case_insensitive else kw
            # Keep highest relevance if keyword appears in multiple categories
            if key not in all_keywords or kw_relevance > all_keywords[key]:
                all_keywords[key] = kw_relevance

    # Score keywords
    for word in words:
        lookup_word = word.lower() if case_insensitive else word

        if lookup_word in all_keywords:
            kw_relevance = all_keywords[lookup_word]
            if kw_relevance > 0:
                keyword_hits[lookup_word] = keyword_hits.get(lookup_word, 0) + 1
                if keyword_hits[lookup_word] <= MAX_KEYWORD_HITS:
                    relevance += kw_relevance

    # Score high-relevance patterns
    for pattern_def in lang_def.get('patterns', []):
        pattern = pattern_def.get('pattern')
        pattern_relevance = pattern_def.get('relevance', 1)

        if not pattern or pattern_relevance <= 0:
            continue

        try:
            matches = re.findall(pattern, code, re.MULTILINE)
            relevance += len(matches) * pattern_relevance
        except re.error:
            # Invalid regex pattern, skip it
            continue

    return relevance


def _apply_superset_tiebreaker(
    results: List[Tuple[str, int]]
) -> List[Tuple[str, int]]:
    """
    Apply superset relationship tie-breaking.

    When two languages have the same relevance score and one is a superset
    of the other (e.g., Arduino is a superset of C++), the base language wins.

    This matches highlight.js behavior where, for example, if C++ and Arduino
    are tied, C++ wins because Arduino's `supersetOf: 'cpp'`.

    Args:
        results: List of (language_id, relevance) tuples sorted by relevance

    Returns:
        List with tie-breaker applied (base languages sorted before supersets)
    """
    if len(results) < 2:
        return results

    def sort_key(item: Tuple[str, int]) -> Tuple[int, int]:
        lang, score = item
        # Check if this language is a superset of another
        is_superset = 1 if lang in SUPERSETS else 0
        # Return (negative_score, is_superset) - base languages sort first
        return (-score, is_superset)

    return sorted(results, key=sort_key)


def get_pygments_lexer_name(hljs_lang: str) -> Optional[str]:
    """
    Map highlight.js language name to Pygments lexer name.

    Most names are the same, but some differ. This function handles
    the mapping.

    Args:
        hljs_lang: highlight.js language identifier

    Returns:
        Pygments lexer name, or None if no mapping exists
    """
    # Most names match directly
    # Map any known differences here
    mapping = {
        'bash': 'bash',
        'c': 'c',
        'cpp': 'cpp',
        'css': 'css',
        'go': 'go',
        'java': 'java',
        'javascript': 'javascript',
        'json': 'json',
        'php': 'php',
        'python': 'python',
        'ruby': 'ruby',
        'rust': 'rust',
        'sql': 'sql',
        'typescript': 'typescript',
        'xml': 'xml',
        'yaml': 'yaml',
    }

    return mapping.get(hljs_lang, hljs_lang)
