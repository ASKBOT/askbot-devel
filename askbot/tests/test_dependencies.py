"""Tests for consistency between askbot.REQUIREMENTS and pyproject.toml dependencies."""
import tomllib
import unittest
from pathlib import Path

import askbot


class DependencyConsistencyTest(unittest.TestCase):
    """Verify that askbot.REQUIREMENTS and pyproject.toml dependencies stay in sync."""

    def test_requirements_match_pyproject(self):
        """askbot.REQUIREMENTS values must match pyproject.toml dependencies."""
        pyproject_path = Path(askbot.get_install_directory()).parent / 'pyproject.toml'

        if not pyproject_path.exists():
            self.skipTest('pyproject.toml not found (installed from wheel?)')

        with pyproject_path.open('rb') as pyproject_file:
            pyproject_deps = tomllib.load(pyproject_file)['project']['dependencies']
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
