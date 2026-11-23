"""Tests for askbot.startup_procedures helpers."""
from unittest import mock

from django.test import SimpleTestCase

from askbot import startup_procedures
from askbot.startup_procedures import get_staticfiles_backend


LEGACY_BACKEND = 'django.contrib.staticfiles.storage.StaticFilesStorage'
MODERN_BACKEND = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'
DEFAULT_FILE_BACKEND = 'django.core.files.storage.FileSystemStorage'


class _StubSettings:
    """A tiny object used in place of django.conf.settings.

    getattr falls back to the requested default when an attribute is
    missing, so we can model a project that has STATICFILES_STORAGE
    set but no STORAGES, or vice versa.
    """

    def __init__(self, **attrs):
        for key, value in attrs.items():
            setattr(self, key, value)


class GetStaticfilesBackendTests(SimpleTestCase):
    """get_staticfiles_backend prefers STORAGES, falls back to legacy."""

    def _run_with(self, stub):
        with mock.patch.object(startup_procedures,
                               'django_settings', stub):
            return get_staticfiles_backend()

    def test_legacy_only(self):
        """returns STATICFILES_STORAGE when no STORAGES dict configured."""
        stub = _StubSettings(STATICFILES_STORAGE=LEGACY_BACKEND)
        self.assertEqual(self._run_with(stub), LEGACY_BACKEND)

    def test_storages_only(self):
        """reads from STORAGES dict without falling back to legacy."""
        stub = _StubSettings(STORAGES={
            'default': {'BACKEND': DEFAULT_FILE_BACKEND},
            'staticfiles': {'BACKEND': MODERN_BACKEND},
        })
        self.assertEqual(self._run_with(stub), MODERN_BACKEND)

    def test_storages_wins_when_both_present(self):
        """STORAGES['staticfiles'] beats legacy STATICFILES_STORAGE."""
        stub = _StubSettings(
            STATICFILES_STORAGE=LEGACY_BACKEND,
            STORAGES={
                'default': {'BACKEND': DEFAULT_FILE_BACKEND},
                'staticfiles': {'BACKEND': MODERN_BACKEND},
            },
        )
        self.assertEqual(self._run_with(stub), MODERN_BACKEND)


class TestVersionsTests(SimpleTestCase):
    """test_versions rejects Python older than 3.11.5"""

    def _run_with(self, version_info):
        with mock.patch.object(startup_procedures.django, 'VERSION', (4, 2, 0)), \
                mock.patch.object(startup_procedures.sys, 'version_info', version_info):
            startup_procedures.test_versions()

    def test_python_3_11_4_rejected(self):
        with self.assertRaises(startup_procedures.AskbotConfigError) as context:
            self._run_with((3, 11, 4, 'final', 0))
        self.assertIn('Askbot requires Python 3.11.5 - 3.12', str(context.exception))

    def test_python_3_11_5_accepted(self):
        self._run_with((3, 11, 5, 'final', 0))


class StdinIsTtyTests(SimpleTestCase):
    """stdin_is_tty never raises, whatever state stdin is in"""

    def _run_with(self, stdin):
        with mock.patch.object(startup_procedures.sys, '__stdin__', stdin):
            return startup_procedures.stdin_is_tty()

    def test_terminal(self):
        self.assertTrue(self._run_with(mock.Mock(isatty=mock.Mock(return_value=True))))

    def test_not_a_terminal(self):
        self.assertFalse(self._run_with(mock.Mock(isatty=mock.Mock(return_value=False))))

    def test_missing_stdin(self):
        self.assertFalse(self._run_with(None))

    def test_closed_stdin(self):
        closed = mock.Mock(isatty=mock.Mock(side_effect=ValueError('closed file')))
        self.assertFalse(self._run_with(closed))
