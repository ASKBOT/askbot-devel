"""Tests for consistency between askbot.REQUIREMENTS and pyproject.toml dependencies."""
import re
import unittest
from pathlib import Path

import askbot


def parse_pyproject_dependencies(pyproject_path):
    """Parse the dependencies array from pyproject.toml using string/regex parsing.

    This is a temporary measure for Python 3.10 compatibility.
    Once Python 3.10 support is dropped, replace this with
    ``tomllib.load()`` from the standard library (available in 3.11+).

    Handles multiline arrays with quoted strings, trailing commas, and comments.
    """
    text = pyproject_path.read_text()

    # Find the dependencies array
    match = re.search(r'^dependencies\s*=\s*\[', text, re.MULTILINE)
    if not match:
        raise ValueError('Could not find dependencies array in pyproject.toml')

    # Extract content between the brackets, skipping brackets inside quoted strings
    start = match.end()
    bracket_depth = 1
    pos = start
    in_quote = False
    while pos < len(text) and bracket_depth > 0:
        ch = text[pos]
        if ch == '"':
            in_quote = not in_quote
        elif not in_quote:
            if ch == '[':
                bracket_depth += 1
            elif ch == ']':
                bracket_depth -= 1
        pos += 1

    array_content = text[start:pos - 1]

    # Extract quoted strings, ignoring comments
    deps = []
    for line in array_content.split('\n'):
        line = line.split('#')[0]  # strip comments
        match = re.search(r'"([^"]+)"', line)
        if match:
            deps.append(match.group(1).strip())

    return deps


class DependencyConsistencyTest(unittest.TestCase):
    """Verify that askbot.REQUIREMENTS and pyproject.toml dependencies stay in sync."""

    def test_requirements_match_pyproject(self):
        """askbot.REQUIREMENTS values must match pyproject.toml dependencies."""
        pyproject_path = Path(askbot.get_install_directory()).parent / 'pyproject.toml'

        if not pyproject_path.exists():
            self.skipTest('pyproject.toml not found (installed from wheel?)')

        pyproject_deps = parse_pyproject_dependencies(pyproject_path)
        requirements_deps = list(askbot.REQUIREMENTS.values())

        pyproject_sorted = sorted(dep.lower() for dep in pyproject_deps)
        requirements_sorted = sorted(dep.lower() for dep in requirements_deps)

        self.assertEqual(
            pyproject_sorted,
            requirements_sorted,
            'askbot.REQUIREMENTS and pyproject.toml dependencies are out of sync.\n'
            f'Only in REQUIREMENTS: {sorted(set(requirements_sorted) - set(pyproject_sorted))}\n'
            f'Only in pyproject.toml: {sorted(set(pyproject_sorted) - set(requirements_sorted))}'
        )
