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
