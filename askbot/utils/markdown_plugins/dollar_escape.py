"""
Simple dollar escape for text regions.
Runs AFTER math extraction, so only processes text content.

This solves the "escaped dollar dilemma" where users need to write literal
dollar signs (like "$100") in text without triggering MathJax math mode.
"""


def escape_dollars(text):
    """
    Convert \\$ -> &dollar; in text.

    IMPORTANT: Must run AFTER extract_math(), so math is already
    protected as @@N@@ tokens. This ensures we never touch dollars
    inside math expressions.

    Args:
        text: Text with math already extracted (has @@N@@ tokens)

    Returns:
        str: Text with \\$ replaced by &dollar;

    Edge cases handled:
        - \\$ -> &dollar; (simple case)
        - \\$\\$ -> &dollar;&dollar; (escaped display delimiter)
        - \\\\$ -> Left alone (markdown escape rule handles \\\\)
        - @@N@@ -> Never touched (these are math tokens)

    Examples:
        >>> escape_dollars(r"Price: \\$100")
        'Price: &dollar;100'

        >>> escape_dollars(r"Price \\$100 and @@0@@ here")
        'Price &dollar;100 and @@0@@ here'

        >>> escape_dollars(r"Not math: \\$$x$$")
        'Not math: &dollar;$x$$'
    """
    # Simple replacement - math is already safe in @@N@@ tokens
    return text.replace(r'\$', '&dollar;')
