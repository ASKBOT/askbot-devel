"""Tests for the per-IP rate limit middleware shell and watched user post rate limiting."""
import json
import logging
import shutil
import tempfile
from types import SimpleNamespace
from unittest import mock

from django.core.cache import caches
from django.core.checks import run_checks
from django.test import RequestFactory, override_settings
from django.urls import reverse

from askbot import checks as askbot_checks
from askbot import signals
from askbot.middleware import ratelimit as ratelimit_mod
from askbot.tests.utils import (
    AskbotTestCase,
    livesettings_override,
    with_settings,
)


class _TypePatchableMock(mock.Mock):
    """Mock subclass for safely installing PropertyMock on its type.

    Patching ``type(plain_mock.Mock())`` would mutate the global
    ``mock.Mock`` class and leak into unrelated tests. Using this
    subclass keeps the patch local.
    """


# Mirrors testproject's MIDDLEWARE with RateLimitMiddleware added
# ahead of the askbot tail. The integration tests rely on
# RateLimitMiddleware running before ViewLogMiddleware.
TEST_MIDDLEWARE = (
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'askbot.middleware.ratelimit.RateLimitMiddleware',
    'askbot.middleware.anon_user.ConnectToSessionMessagesMiddleware',
    'askbot.middleware.forum_mode.ForumModeMiddleware',
    'askbot.middleware.cancel.CancelActionMiddleware',
    'askbot.middleware.view_log.ViewLogMiddleware',
)


class RateLimitMisconfigWarningTests(AskbotTestCase):
    """Boot-time misconfig WARNINGs from ``maybe_warn_misconfig``.

    Each test calls the function directly and resets the
    ``MISCONFIG_CHECK_DONE`` one-shot flag in ``setUp`` so cases are
    order-independent.
    """

    LOGGER = 'askbot.middleware.ratelimit'

    def setUp(self):
        ratelimit_mod.MISCONFIG_CHECK_DONE = False

    @override_settings(CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'rl-test-locmem-default',
        },
    })
    def test_warning_fires_under_locmem_cache(self):
        with self.assertLogs(self.LOGGER, level='WARNING') as cm:
            ratelimit_mod.maybe_warn_misconfig()
        self.assertEqual(len(cm.records), 1)
        self.assertIn(
            'rate limiting state is per-process',
            cm.records[0].getMessage(),
        )

    @override_settings(CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
        },
    })
    def test_warning_fires_under_dummy_cache(self):
        with self.assertLogs(self.LOGGER, level='WARNING') as cm:
            ratelimit_mod.maybe_warn_misconfig()
        self.assertEqual(len(cm.records), 1)

    def test_warning_silent_under_non_locmem_backend(self):
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)
        with override_settings(CACHES={
            'default': {
                'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
                'LOCATION': tmpdir,
            },
        }):
            with self.assertNoLogs(self.LOGGER, level='WARNING'):
                ratelimit_mod.maybe_warn_misconfig()

    @override_settings(CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'rl-test-locmem-oneshot',
        },
    })
    def test_one_shot_does_not_reemit(self):
        """Two calls in a row must produce only one warning."""
        with self.assertLogs(self.LOGGER, level='WARNING') as cm:
            ratelimit_mod.maybe_warn_misconfig()
            ratelimit_mod.maybe_warn_misconfig()
        self.assertEqual(len(cm.records), 1)

    # --- Check 1: RATELIMIT_ENABLE consistency ---

    def _filebased_caches(self, tmpdir):
        return {
            'default': {
                'BACKEND':
                    'django.core.cache.backends.filebased.FileBasedCache',
                'LOCATION': tmpdir,
            },
        }

    def test_misconfig_warns_when_ratelimit_enable_false_contradicts(self):
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)
        with override_settings(
            RATELIMIT_ENABLE=False,
            CACHES=self._filebased_caches(tmpdir),
        ):
            with livesettings_override(REQUEST_RATE_LIMIT_ENABLED=True):
                ratelimit_mod.MISCONFIG_CHECK_DONE = False
                with self.assertLogs(self.LOGGER, level='WARNING') as cm:
                    ratelimit_mod.maybe_warn_misconfig()
        self.assertEqual(len(cm.records), 1)
        self.assertIn(
            'RATELIMIT_ENABLE is falsy',
            cm.records[0].getMessage(),
        )

    def test_misconfig_warns_for_other_falsy_ratelimit_enable_values(self):
        """All falsy values (0, '', None) must trigger the warning,
        not just ``False``."""
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)
        for falsy_value in (0, '', None):
            with self.subTest(value=repr(falsy_value)):
                with override_settings(
                    RATELIMIT_ENABLE=falsy_value,
                    CACHES=self._filebased_caches(tmpdir),
                ):
                    with livesettings_override(REQUEST_RATE_LIMIT_ENABLED=True):
                        ratelimit_mod.MISCONFIG_CHECK_DONE = False
                        with self.assertLogs(
                            self.LOGGER, level='WARNING',
                        ) as cm:
                            ratelimit_mod.maybe_warn_misconfig()
                self.assertEqual(len(cm.records), 1)
                self.assertIn(
                    'RATELIMIT_ENABLE is falsy',
                    cm.records[0].getMessage(),
                )

    def test_misconfig_silent_when_ratelimit_enable_consistent(self):
        """Uses a file-based cache instead of the project default
        LocMem so the cache-backend check stays silent too."""
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)
        with override_settings(
            RATELIMIT_ENABLE=True,
            CACHES=self._filebased_caches(tmpdir),
        ):
            ratelimit_mod.MISCONFIG_CHECK_DONE = False
            with self.assertNoLogs(self.LOGGER, level='WARNING'):
                ratelimit_mod.maybe_warn_misconfig()

    def test_misconfig_silent_when_all_policies_disabled(self):
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)
        with override_settings(
            RATELIMIT_ENABLE=False,
            CACHES=self._filebased_caches(tmpdir),
        ):
            with livesettings_override(
                REQUEST_RATE_LIMIT_ENABLED=False,
                REGISTRATION_RATE_LIMIT_ENABLED=False,
                WATCHED_USER_POST_RATE_LIMIT_ENABLED=False,
            ):
                ratelimit_mod.MISCONFIG_CHECK_DONE = False
                with self.assertNoLogs(self.LOGGER, level='WARNING'):
                    ratelimit_mod.maybe_warn_misconfig()

    # --- Check 2: RATELIMIT_USE_CACHE-aware cache check ---

    def test_misconfig_uses_ratelimit_use_cache_not_default(self):
        """The check must read ``RATELIMIT_USE_CACHE``, not just the
        ``default`` cache. ``default`` is file-based (silent); ``other``
        is LocMem and is the cache the warning should flag."""
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)
        with override_settings(
            RATELIMIT_USE_CACHE='other',
            CACHES={
                'default': {
                    'BACKEND':
                        'django.core.cache.backends.filebased.FileBasedCache',
                    'LOCATION': tmpdir,
                },
                'other': {
                    'BACKEND':
                        'django.core.cache.backends.locmem.LocMemCache',
                    'LOCATION': 'rl-test-other',
                },
            },
        ):
            ratelimit_mod.MISCONFIG_CHECK_DONE = False
            with self.assertLogs(self.LOGGER, level='WARNING') as cm:
                ratelimit_mod.maybe_warn_misconfig()
        self.assertEqual(len(cm.records), 1)
        self.assertIn("'other'", cm.records[0].getMessage())
        self.assertIn(
            'rate limiting state is per-process',
            cm.records[0].getMessage(),
        )

    def test_misconfig_warns_when_use_cache_missing_entry(self):
        """Boot-time mirror of W004: warns when ``RATELIMIT_USE_CACHE``
        points at a key with no matching ``CACHES`` entry, before
        django-ratelimit would raise on the first request."""
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)
        with override_settings(
            RATELIMIT_USE_CACHE='nonexistent',
            CACHES=self._filebased_caches(tmpdir),
        ):
            ratelimit_mod.MISCONFIG_CHECK_DONE = False
            with self.assertLogs(self.LOGGER, level='WARNING') as cm:
                ratelimit_mod.maybe_warn_misconfig()
        self.assertEqual(len(cm.records), 1)
        self.assertIn("'nonexistent'", cm.records[0].getMessage())
        self.assertIn('has no entry', cm.records[0].getMessage())

    def test_misconfig_warns_when_use_cache_non_dict(self):
        """Boot-time mirror of W004: warns when the matching
        ``CACHES`` entry is not a dict."""
        with override_settings(
            RATELIMIT_USE_CACHE='broken',
            CACHES={'broken': 'redis://example.com/0'},
        ):
            ratelimit_mod.MISCONFIG_CHECK_DONE = False
            with self.assertLogs(self.LOGGER, level='WARNING') as cm:
                ratelimit_mod.maybe_warn_misconfig()
        self.assertEqual(len(cm.records), 1)
        self.assertIn("'broken'", cm.records[0].getMessage())
        self.assertIn('not a dict', cm.records[0].getMessage())

    # --- Inspection-pass guard semantics ---

    def test_misconfig_emits_both_warnings_when_both_conditions_hold(self):
        """Both warnings fire in one inspection pass when
        ``RATELIMIT_ENABLE=False`` contradicts an enabled livesetting
        AND the cache backend is per-process LocMem."""
        with override_settings(
            RATELIMIT_ENABLE=False,
            CACHES={
                'default': {
                    'BACKEND':
                        'django.core.cache.backends.locmem.LocMemCache',
                    'LOCATION': 'rl-test-locmem-both',
                },
            },
        ):
            with livesettings_override(REQUEST_RATE_LIMIT_ENABLED=True):
                ratelimit_mod.MISCONFIG_CHECK_DONE = False
                with self.assertLogs(self.LOGGER, level='WARNING') as cm:
                    ratelimit_mod.maybe_warn_misconfig()
        self.assertEqual(len(cm.records), 2)
        # Order matters for operator logs: the kill-switch warning
        # must come before the cache-backend warning.
        self.assertIn(
            'RATELIMIT_ENABLE is falsy', cm.records[0].getMessage(),
        )
        self.assertIn(
            'RATELIMIT_USE_CACHE=', cm.records[1].getMessage(),
        )
        self.assertIn(
            'per-process', cm.records[1].getMessage(),
        )

    def test_misconfig_emits_both_w001_and_w004_in_order(self):
        """W001 must be emitted before W004 when both fire in the same
        pass (``RATELIMIT_ENABLE=False`` with a contradicting
        livesetting and ``RATELIMIT_USE_CACHE`` pointing at a missing
        key)."""
        with override_settings(
            RATELIMIT_ENABLE=False,
            RATELIMIT_USE_CACHE='nonexistent',
            CACHES={
                'default': {
                    'BACKEND':
                        'django.core.cache.backends.dummy.DummyCache',
                },
            },
        ):
            with livesettings_override(REQUEST_RATE_LIMIT_ENABLED=True):
                ratelimit_mod.MISCONFIG_CHECK_DONE = False
                with self.assertLogs(self.LOGGER, level='WARNING') as cm:
                    ratelimit_mod.maybe_warn_misconfig()
        self.assertEqual(len(cm.records), 2)
        self.assertIn(
            'RATELIMIT_ENABLE is falsy', cm.records[0].getMessage(),
        )
        self.assertIn(
            'has no entry', cm.records[1].getMessage(),
        )

    def test_inspection_pass_short_circuits_after_silent_first_call(self):
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)
        with override_settings(
            RATELIMIT_ENABLE=True,
            CACHES=self._filebased_caches(tmpdir),
        ):
            ratelimit_mod.MISCONFIG_CHECK_DONE = False
            ratelimit_mod.maybe_warn_misconfig()
            self.assertTrue(ratelimit_mod.MISCONFIG_CHECK_DONE)
            # The second call must skip both ``settings`` and
            # ``askbot_settings`` lookups. ``new=mock.MagicMock()`` is
            # passed explicitly because patch.object's auto-create path
            # probes the target with ``hasattr(obj, '__func__')`` and
            # the livesettings ``__getattr__`` raises ``KeyError`` for
            # that name instead of ``AttributeError``.
            settings_mock = mock.MagicMock()
            askbot_settings_mock = mock.MagicMock()
            with mock.patch.object(
                ratelimit_mod, 'settings', new=settings_mock,
            ), mock.patch.object(
                ratelimit_mod, 'askbot_settings',
                new=askbot_settings_mock,
            ):
                ratelimit_mod.maybe_warn_misconfig()
            # Plain attribute access on a MagicMock does not record in
            # ``mock_calls``, but calls on child mocks do — so a
            # missed short-circuit would show up here as a
            # ``caches.get(cache_name)`` call on the settings mock.
            self.assertEqual(settings_mock.mock_calls, [])
            self.assertEqual(askbot_settings_mock.mock_calls, [])

    def test_misconfig_logs_info_when_livesettings_db_raises(self):
        """A livesettings DB failure at worker boot must log INFO and
        not crash. Mirrors the broad except in ``checks.py`` so a
        transient DB hiccup cannot bring down gunicorn."""
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)
        raising = _TypePatchableMock()
        type(raising).REQUEST_RATE_LIMIT_ENABLED = mock.PropertyMock(
            side_effect=Exception('boom'))
        with override_settings(
            RATELIMIT_ENABLE=False,
            CACHES=self._filebased_caches(tmpdir),
        ):
            with mock.patch.object(
                ratelimit_mod, 'askbot_settings', raising,
            ):
                ratelimit_mod.MISCONFIG_CHECK_DONE = False
                # ``level='INFO'`` captures INFO and above; the
                # no-WARNING guarantee comes from the levelno filter
                # below.
                with self.assertLogs(self.LOGGER, level='INFO') as cm:
                    ratelimit_mod.maybe_warn_misconfig()
        info_records = [
            r for r in cm.records if r.levelno == logging.INFO
        ]
        warning_records = [
            r for r in cm.records if r.levelno >= logging.WARNING
        ]
        self.assertEqual(len(info_records), 1)
        self.assertIn(
            'could not be read', info_records[0].getMessage(),
        )
        self.assertEqual(warning_records, [])
        self.assertTrue(ratelimit_mod.MISCONFIG_CHECK_DONE)


class RateLimitSystemCheckTests(AskbotTestCase):
    """Tests for the Django system checks in ``askbot/checks.py``.

    Calls the check functions directly under various
    ``override_settings`` scenarios. They do not touch the middleware
    one-shot flag because the checks bypass the middleware.
    """

    # --- W001 ---

    def test_check_w001_fires_when_contradicts(self):
        with override_settings(RATELIMIT_ENABLE=False):
            with livesettings_override(REQUEST_RATE_LIMIT_ENABLED=True):
                results = (
                    askbot_checks.check_ratelimit_enable_consistency(None)
                )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, 'askbot.W001')
        self.assertIn(
            'RATELIMIT_ENABLE is falsy', results[0].msg,
        )

    def test_check_w001_silent_when_consistent(self):
        with override_settings(RATELIMIT_ENABLE=True):
            results = askbot_checks.check_ratelimit_enable_consistency(None)
        self.assertEqual(results, [])

    def test_check_i001_when_livesettings_db_raises(self):
        """Returns I001 (not W001) when livesettings cannot be read.
        Mirrors the middleware's broad except so a transient DB
        failure does not fail ``manage.py check``."""
        from django.core import checks as django_checks
        from askbot import conf as askbot_conf
        raising = _TypePatchableMock()
        type(raising).REQUEST_RATE_LIMIT_ENABLED = mock.PropertyMock(
            side_effect=Exception('boom'))
        with override_settings(RATELIMIT_ENABLE=False):
            with mock.patch.object(askbot_conf, 'settings', raising):
                results = (
                    askbot_checks.check_ratelimit_enable_consistency(None)
                )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, 'askbot.I001')
        # ``== INFO`` (not ``<= INFO``): a DEBUG result would still
        # satisfy ``<=`` and slip through.
        self.assertEqual(results[0].level, django_checks.INFO)
        self.assertEqual(
            results[0].hint,
            'This is expected during collectstatic / migrate / fresh '
            'bootstrap. If it persists during normal worker '
            'operation, investigate the livesettings DB connection.',
        )
        # I001 and W001 must be mutually exclusive.
        self.assertNotIn(
            'askbot.W001', [w.id for w in results],
        )

    def test_check_i001_silent_when_ratelimit_enable_missing_or_true(self):
        # I001 must fire only when RATELIMIT_ENABLE is falsy and
        # reading livesettings fails. Any other case stays silent.
        from askbot import conf as askbot_conf
        raising = _TypePatchableMock()
        type(raising).REQUEST_RATE_LIMIT_ENABLED = mock.PropertyMock(
            side_effect=Exception('boom'))
        with self.subTest(case='RATELIMIT_ENABLE=True'):
            with override_settings(RATELIMIT_ENABLE=True):
                with mock.patch.object(
                    askbot_conf, 'settings', raising,
                ):
                    results = (
                        askbot_checks
                        .check_ratelimit_enable_consistency(None)
                    )
            self.assertEqual(results, [])
        with self.subTest(case='RATELIMIT_ENABLE unset'):
            # When the setting is missing, ``getattr`` falls back to
            # ``True`` and the check returns silently.
            ns = SimpleNamespace()  # no RATELIMIT_ENABLE attribute
            with mock.patch.object(askbot_checks, 'settings', ns):
                with mock.patch.object(
                    askbot_conf, 'settings', raising,
                ):
                    results = (
                        askbot_checks
                        .check_ratelimit_enable_consistency(None)
                    )
            self.assertEqual(results, [])

    def test_check_i001_does_not_fail_deploy_gate(self):
        """Every ``askbot.I*`` result must stay at INFO level so
        ``manage.py check`` keeps passing. A selective proxy is used
        instead of a wholesale mock so unrelated reads (e.g. Jinja2's
        ``ASKBOT_DEFAULT_SKIN``) reach the real settings."""
        from django.core import checks as django_checks
        from askbot import conf as askbot_conf

        real_settings = askbot_conf.settings
        raising_attrs = {
            'REQUEST_RATE_LIMIT_ENABLED',
            'REGISTRATION_RATE_LIMIT_ENABLED',
            'WATCHED_USER_POST_RATE_LIMIT_ENABLED',
        }

        class SelectiveRaising:
            def __getattr__(self, name):
                if name in raising_attrs:
                    raise Exception('boom')
                return getattr(real_settings, name)

        # Pin the W003 logger below WARNING so it cannot fire and
        # pollute the result list.
        ratelimit_logger = logging.getLogger('askbot.utils.ratelimit')
        original = ratelimit_logger.level
        ratelimit_logger.setLevel(logging.WARNING)
        try:
            with override_settings(RATELIMIT_ENABLE=False):
                with mock.patch.object(
                    askbot_conf, 'settings', SelectiveRaising(),
                ):
                    results = run_checks(app_configs=None)
        finally:
            ratelimit_logger.setLevel(original)
        info_results = [
            r for r in results
            if getattr(r, 'id', '').startswith('askbot.I')
        ]
        self.assertTrue(info_results)
        for result in info_results:
            self.assertEqual(result.level, django_checks.INFO)

    # --- W002 ---

    def test_check_w002_fires_when_use_cache_points_at_locmem(self):
        with override_settings(
            RATELIMIT_USE_CACHE='other',
            CACHES={
                'default': {
                    'BACKEND':
                        'django.core.cache.backends.dummy.DummyCache',
                },
                'other': {
                    'BACKEND':
                        'django.core.cache.backends.locmem.LocMemCache',
                    'LOCATION': 'rl-w002-other',
                },
            },
        ):
            results = askbot_checks.check_ratelimit_cache_backend(None)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, 'askbot.W002')
        self.assertIn("'other'", results[0].msg)

    def test_check_w002_silent_under_filebased_cache(self):
        """Uses ``FileBasedCache`` as the non-per-process stand-in.
        Redis would attempt a real connection at cache init."""
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)
        with override_settings(
            RATELIMIT_USE_CACHE='default',
            CACHES={
                'default': {
                    'BACKEND':
                        'django.core.cache.backends.filebased.FileBasedCache',
                    'LOCATION': tmpdir,
                },
            },
        ):
            results = askbot_checks.check_ratelimit_cache_backend(None)
        self.assertEqual(results, [])

    def test_check_w002_uses_default_when_use_cache_unset(self):
        """When ``RATELIMIT_USE_CACHE`` is not set, the check must
        fall back to ``'default'``. Drops the fallback and the
        attribute lookup would raise only in production."""
        with override_settings(
            CACHES={
                'default': {
                    'BACKEND':
                        'django.core.cache.backends.locmem.LocMemCache',
                    'LOCATION': 'rl-w002-default',
                },
            },
        ):
            results = askbot_checks.check_ratelimit_cache_backend(None)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, 'askbot.W002')

    def test_check_w004_fires_when_use_cache_missing(self):
        """W004 fires when ``RATELIMIT_USE_CACHE`` points at a key
        with no ``CACHES`` entry. W002 must not also fire — the two
        IDs are mutually exclusive."""
        with override_settings(
            RATELIMIT_USE_CACHE='nonexistent',
            CACHES={
                'default': {
                    'BACKEND':
                        'django.core.cache.backends.locmem.LocMemCache',
                    'LOCATION': 'rl-w004-missing',
                },
            },
        ):
            results = askbot_checks.check_ratelimit_cache_backend(None)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, 'askbot.W004')
        self.assertIn('has no entry', results[0].msg)
        self.assertNotIn(
            'askbot.W002', [r.id for r in results],
        )

    def test_check_w004_fires_when_use_cache_non_dict(self):
        """W004 fires when the ``CACHES`` entry exists but is not a
        dict. W002 must not also fire."""
        with override_settings(
            RATELIMIT_USE_CACHE='broken',
            CACHES={
                'broken': 'redis://example.com/0',  # not a dict
            },
        ):
            results = askbot_checks.check_ratelimit_cache_backend(None)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, 'askbot.W004')
        self.assertIn('not a dict', results[0].msg)
        self.assertNotIn(
            'askbot.W002', [r.id for r in results],
        )

    def test_check_w004_fires_when_caches_empty(self):
        """``CACHES={}`` makes the ``'default'`` lookup return None,
        which the missing-entry branch reports as W004."""
        with override_settings(CACHES={}):
            results = askbot_checks.check_ratelimit_cache_backend(None)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, 'askbot.W004')
        self.assertIn('has no entry', results[0].msg)

    def test_check_w004_fires_when_caches_undefined(self):
        """A settings object with no ``CACHES`` attribute at all must
        also reach W004 via the ``getattr(..., None) or {}`` fallback,
        not raise."""
        ns = SimpleNamespace()  # neither RATELIMIT_USE_CACHE nor CACHES
        with mock.patch.object(askbot_checks, 'settings', ns):
            results = askbot_checks.check_ratelimit_cache_backend(None)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, 'askbot.W004')

    # --- Registration check ---

    def test_system_check_w004_registered(self):
        """Registration sweep for W004. The ``W002 not in IDs`` check
        is load-bearing — without it, a regression that surfaces both
        IDs would go unnoticed. As above, W001/W003 require opposing
        ``RATELIMIT_ENABLE`` values so the sweep unions two passes."""
        cache_overrides = dict(
            RATELIMIT_USE_CACHE='nonexistent',
            CACHES={
                'default': {
                    'BACKEND':
                        'django.core.cache.backends.dummy.DummyCache',
                },
            },
        )
        ratelimit_logger = logging.getLogger('askbot.utils.ratelimit')
        original = ratelimit_logger.level
        ratelimit_logger.setLevel(logging.ERROR)
        try:
            with override_settings(
                RATELIMIT_ENABLE=False, **cache_overrides,
            ):
                with livesettings_override(REQUEST_RATE_LIMIT_ENABLED=True):
                    w001_w004_results = run_checks(app_configs=None)
            with override_settings(
                RATELIMIT_ENABLE=True, **cache_overrides,
            ):
                with livesettings_override(REQUEST_RATE_LIMIT_ENABLED=True):
                    w003_results = run_checks(app_configs=None)
        finally:
            ratelimit_logger.setLevel(original)
        all_results = (*w001_w004_results, *w003_results)
        askbot_ids = {
            warning.id for warning in all_results
            if getattr(warning, 'id', '').startswith('askbot.W')
        }
        self.assertIn('askbot.W001', askbot_ids)
        self.assertIn('askbot.W003', askbot_ids)
        self.assertIn('askbot.W004', askbot_ids)
        self.assertNotIn('askbot.W002', askbot_ids)


class RateLimitLoggerLevelCheckTests(AskbotTestCase):
    """Tests for the ``askbot.W003`` system check.

    The logger level is process-global, so each case restores the
    prior level via ``addCleanup``. W003 only fires when rate limiting
    is enabled, so most cases enable a livesetting first.
    """

    LOGGER = 'askbot.utils.ratelimit'

    def _set_logger_level(self, level):
        ratelimit_logger = logging.getLogger(self.LOGGER)
        original = ratelimit_logger.level
        ratelimit_logger.setLevel(level)
        self.addCleanup(ratelimit_logger.setLevel, original)

    def test_check_w003_fires_when_logger_above_warning(self):
        self._set_logger_level(logging.ERROR)
        with livesettings_override(REQUEST_RATE_LIMIT_ENABLED=True):
            results = askbot_checks.check_ratelimit_logger_level(None)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, 'askbot.W003')
        self.assertEqual(
            results[0].msg,
            'Rate-limit logger is muted above WARNING.',
        )
        self.assertEqual(
            results[0].hint,
            'Set askbot.utils.ratelimit logger to WARNING or lower '
            'in LOGGING; otherwise rate-limit hit events will be '
            'dropped silently and log-tailer integrations '
            '(fail2ban / CrowdSec / Wazuh / Filebeat) will fail.',
        )

    def test_check_w003_silent_when_logger_at_warning(self):
        self._set_logger_level(logging.WARNING)
        with livesettings_override(REQUEST_RATE_LIMIT_ENABLED=True):
            results = askbot_checks.check_ratelimit_logger_level(None)
        self.assertEqual(results, [])

    def test_check_w003_silent_when_logger_below_warning(self):
        self._set_logger_level(logging.DEBUG)
        with livesettings_override(REQUEST_RATE_LIMIT_ENABLED=True):
            results = askbot_checks.check_ratelimit_logger_level(None)
        self.assertEqual(results, [])

    def test_check_w003_silent_when_no_ratelimit_livesetting_enabled(self):
        """Deployments with no rate limiting enabled must not see a
        warning about a logger that has nothing to log."""
        self._set_logger_level(logging.ERROR)
        with livesettings_override(
            REQUEST_RATE_LIMIT_ENABLED=False,
            REGISTRATION_RATE_LIMIT_ENABLED=False,
            WATCHED_USER_POST_RATE_LIMIT_ENABLED=False,
        ):
            results = askbot_checks.check_ratelimit_logger_level(None)
        self.assertEqual(results, [])

    def test_check_w003_silent_when_ratelimit_enable_falsy(self):
        """If ``RATELIMIT_ENABLE`` is falsy, django-ratelimit is
        bypassed and the logger level no longer matters — even if a
        livesetting is on."""
        self._set_logger_level(logging.ERROR)
        with override_settings(RATELIMIT_ENABLE=False):
            with livesettings_override(REQUEST_RATE_LIMIT_ENABLED=True):
                results = askbot_checks.check_ratelimit_logger_level(None)
        self.assertEqual(results, [])

    def test_check_w003_silent_when_livesettings_access_raises(self):
        """A livesettings DB failure (common during collectstatic,
        migrate, or fresh bootstrap) must be swallowed silently rather
        than crash ``manage.py check``."""
        from askbot import conf as askbot_conf

        real_settings = askbot_conf.settings
        raising_attrs = {
            'REQUEST_RATE_LIMIT_ENABLED',
            'REGISTRATION_RATE_LIMIT_ENABLED',
            'WATCHED_USER_POST_RATE_LIMIT_ENABLED',
        }

        class SelectiveRaising:
            def __getattr__(self, name):
                if name in raising_attrs:
                    raise Exception('boom')
                return getattr(real_settings, name)

        self._set_logger_level(logging.ERROR)
        with mock.patch.object(
            askbot_conf, 'settings', SelectiveRaising(),
        ):
            results = askbot_checks.check_ratelimit_logger_level(None)
        self.assertEqual(results, [])


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class RateLimitIntegrationTests(AskbotTestCase):
    """End-to-end tests through the real URL and middleware chain.

    ``testproject`` does not include ``RateLimitMiddleware``, so the
    class-level override splices it in at the production position.
    """

    def setUp(self):
        # Cleared in both setUp and tearDown: livesettings share the
        # cache, and ``with_settings`` populates it after setUp runs.
        caches['default'].clear()
        ratelimit_mod.MISCONFIG_CHECK_DONE = False

    def tearDown(self):
        caches['default'].clear()

    @with_settings(
        REGISTRATION_RATE_LIMIT_ENABLED=True,
        REGISTRATION_RATE_LIMIT_MAX_REGISTRATIONS=2,
        REQUEST_RATE_LIMIT_ENABLED=False,
        USE_RECAPTCHA=False,
        TERMS_CONSENT_REQUIRED=False,
        NEW_REGISTRATIONS_DISABLED=False,
        EMAIL_VALIDATION_REQUIRED=False,
        BLANK_EMAIL_ALLOWED=False,
    )
    def test_signup_endpoint_returns_429_at_limit(self):
        url = reverse('user_signup_with_password')
        # Each attempt uses a distinct username and email so form
        # validation cannot fail first and mask the rate-limit check.
        for i in range(2):
            response = self.client.post(
                url,
                {
                    'next': '/',
                    'username': f'rl{i}',
                    'email': f'rl{i}@example.com',
                    'password1': 'TestPass12345!',
                    'password2': 'TestPass12345!',
                },
                REMOTE_ADDR='5.5.5.5',
            )
            self.assertLess(response.status_code, 400)
        over = self.client.post(
            url,
            {
                'next': '/',
                'username': 'rl2',
                'email': 'rl2@example.com',
                'password1': 'TestPass12345!',
                'password2': 'TestPass12345!',
            },
            REMOTE_ADDR='5.5.5.5',
        )
        self.assertEqual(over.status_code, 429)

    @with_settings(
        REGISTRATION_RATE_LIMIT_ENABLED=True,
        REGISTRATION_RATE_LIMIT_MAX_REGISTRATIONS=2,
        REQUEST_RATE_LIMIT_ENABLED=False,
        USE_RECAPTCHA=False,
        TERMS_CONSENT_REQUIRED=False,
        NEW_REGISTRATIONS_DISABLED=False,
        EMAIL_VALIDATION_REQUIRED=False,
        BLANK_EMAIL_ALLOWED=False,
    )
    def test_signup_endpoint_under_limit_passes_through(self):
        """Control case: a single request must not trip the limiter."""
        response = self.client.post(
            reverse('user_signup_with_password'),
            {
                'next': '/',
                'username': 'rlctl',
                'email': 'rlctl@example.com',
                'password1': 'TestPass12345!',
                'password2': 'TestPass12345!',
            },
            REMOTE_ADDR='6.6.6.6',
        )
        self.assertLess(response.status_code, 400)

    @with_settings(
        REQUEST_RATE_LIMIT_ENABLED=True,
        REQUEST_RATE_LIMIT_MAX_REQUESTS=2,
    )
    def test_request_middleware_429_short_circuits_view_dispatch(self):
        """A 429 from the rate-limit middleware must skip view
        dispatch. ``site_visited`` is emitted from
        ``ViewLogMiddleware.process_view``, which Django skips for
        every middleware once any of them short-circuits."""
        approved = self.create_user('rl_approved', status='a')
        self.client.force_login(approved)

        handler_calls = []

        def handler(sender, **kwargs):
            handler_calls.append(kwargs)

        signals.site_visited.connect(handler)
        try:
            for i in range(2):
                before = len(handler_calls)
                response = self.client.get('/', REMOTE_ADDR='7.7.7.7')
                self.assertLess(response.status_code, 400)
                self.assertEqual(len(handler_calls) - before, 1)
            self.assertEqual(len(handler_calls), 2)

            before = len(handler_calls)
            over = self.client.get('/', REMOTE_ADDR='7.7.7.7')
            self.assertEqual(over.status_code, 429)
            self.assertEqual(len(handler_calls) - before, 0)
            self.assertEqual(len(handler_calls), 2)
        finally:
            signals.site_visited.disconnect(handler)

    @with_settings(
        REQUEST_RATE_LIMIT_ENABLED=True,
        REQUEST_RATE_LIMIT_MAX_REQUESTS=1,
    )
    def test_request_middleware_429_emits_warning_on_logger(self):
        """End-to-end check for the structured WARNING log line. Kept
        separate from the signal-skip and Retry-After tests so a
        regression in any one surface points to its own assertion."""
        self.client.get('/', REMOTE_ADDR='9.9.9.9')
        with self.assertLogs(
            'askbot.utils.ratelimit', level='WARNING',
        ) as cm:
            over = self.client.get('/', REMOTE_ADDR='9.9.9.9')
        self.assertEqual(over.status_code, 429)
        anchor = 'askbot.ratelimit hit '
        hits = [
            r for r in cm.records
            if r.getMessage().startswith(anchor)
        ]
        self.assertEqual(len(hits), 1)
        msg = hits[0].getMessage()
        self.assertIn('policy=request', msg)
        self.assertIn('group=askbot.ratelimit.request', msg)

    @with_settings(
        REQUEST_RATE_LIMIT_ENABLED=True,
        REQUEST_RATE_LIMIT_MAX_REQUESTS=1,
    )
    def test_request_middleware_429_emits_retry_after_header(self):
        """The ``Retry-After`` header set by the helper must survive
        the full middleware response cycle. The unit suite covers the
        helper output in isolation."""
        self.client.get('/', REMOTE_ADDR='8.8.8.8')
        over = self.client.get('/', REMOTE_ADDR='8.8.8.8')
        self.assertEqual(over.status_code, 429)
        self.assertIn('Retry-After', over)

    @with_settings(
        REQUEST_RATE_LIMIT_ENABLED=True,
        REQUEST_RATE_LIMIT_MAX_REQUESTS=1,
    )
    def test_request_middleware_429_returns_json_for_xhr_on_get_tag_list(self):
        """End-to-end check for the JSON 429 response on AJAX requests.

        The frontend handler in ``askbot/media/js/utils.js`` expects
        status 429, ``Content-Type: application/json``, a body of
        ``{error: 'rate_limited', retry_after: <int>, message: <str>}``,
        and a ``Retry-After`` header. A regression in any of these
        would silently break the user-facing "too many requests"
        banner for AJAX callers.
        """
        url = reverse('get_tag_list')
        self.client.get(
            url,
            REMOTE_ADDR='10.10.10.10',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        over = self.client.get(
            url,
            REMOTE_ADDR='10.10.10.10',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(over.status_code, 429)
        self.assertTrue(
            over['Content-Type'].startswith('application/json')
        )
        self.assertIn('Retry-After', over)
        body = json.loads(over.content)
        self.assertEqual(body['error'], 'rate_limited')
        self.assertIsInstance(body['retry_after'], int)
        self.assertIn('message', body)


class WatchedUserPostRateLimitTests(AskbotTestCase):
    """Tests for post rate limiting of watched users."""

    def setUp(self):
        self.watched_user = self.create_user('watched_user', status='w')
        self.approved_user = self.create_user('approved_user', status='a')

    def _request(self, ip='8.8.8.8'):
        return RequestFactory().get('/', REMOTE_ADDR=ip)

    @with_settings(
        WATCHED_USER_POST_RATE_LIMIT_ENABLED=True,
        WATCHED_USER_POST_RATE_LIMIT_MAX_POSTS=3,
    )
    def test_watched_user_blocked_over_limit(self):
        from askbot.views.writers import check_watched_user_post_rate_limit
        from django.core import exceptions as django_exceptions

        for i in range(3):
            self.post_question(user=self.watched_user,
                               title='question %d' % i)

        with self.assertRaises(django_exceptions.PermissionDenied):
            check_watched_user_post_rate_limit(
                self.watched_user, self._request(),
            )

    @with_settings(
        WATCHED_USER_POST_RATE_LIMIT_ENABLED=True,
        WATCHED_USER_POST_RATE_LIMIT_MAX_POSTS=5,
    )
    def test_watched_user_allowed_under_limit(self):
        from askbot.views.writers import check_watched_user_post_rate_limit

        for i in range(3):
            self.post_question(user=self.watched_user,
                               title='question %d' % i)

        check_watched_user_post_rate_limit(
            self.watched_user, self._request(),
        )

    @with_settings(
        WATCHED_USER_POST_RATE_LIMIT_ENABLED=True,
        WATCHED_USER_POST_RATE_LIMIT_MAX_POSTS=3,
    )
    def test_approved_user_not_affected(self):
        """Approved users are not watched, so the limit must not
        apply even with more posts than the cap."""
        from askbot.views.writers import check_watched_user_post_rate_limit

        for i in range(5):
            self.post_question(user=self.approved_user,
                               title='question %d' % i)

        check_watched_user_post_rate_limit(
            self.approved_user, self._request(),
        )

    @with_settings(
        WATCHED_USER_POST_RATE_LIMIT_ENABLED=False,
        WATCHED_USER_POST_RATE_LIMIT_MAX_POSTS=3,
    )
    def test_disabled_allows_all(self):
        from askbot.views.writers import check_watched_user_post_rate_limit

        for i in range(10):
            self.post_question(user=self.watched_user,
                               title='question %d' % i)

        check_watched_user_post_rate_limit(
            self.watched_user, self._request(),
        )

    @with_settings(
        WATCHED_USER_POST_RATE_LIMIT_ENABLED=True,
        WATCHED_USER_POST_RATE_LIMIT_MAX_POSTS=3,
    )
    def test_watched_user_post_allowlist_bypass(self):
        """A watched user at the limit but posting from an allowlisted
        IP must not trip the post-rate gate. Pairs with the control
        test below, which checks the same scenario without the
        allowlist entry."""
        from askbot.views.writers import check_watched_user_post_rate_limit
        from askbot.conf import settings as askbot_settings

        for i in range(3):
            self.post_question(user=self.watched_user,
                               title='question %d' % i)

        askbot_settings.update('RATE_LIMIT_IP_ALLOWLIST', ['1.2.3.4'])
        try:
            check_watched_user_post_rate_limit(
                self.watched_user, self._request(ip='1.2.3.4'),
            )
        finally:
            askbot_settings.update('RATE_LIMIT_IP_ALLOWLIST', [])

    @with_settings(
        WATCHED_USER_POST_RATE_LIMIT_ENABLED=True,
        WATCHED_USER_POST_RATE_LIMIT_MAX_POSTS=3,
    )
    def test_watched_user_post_allowlist_bypass_control(self):
        """Control for ``test_watched_user_post_allowlist_bypass``: the
        same over-limit scenario WITHOUT the allowlist entry raises."""
        from askbot.views.writers import check_watched_user_post_rate_limit
        from django.core import exceptions as django_exceptions

        for i in range(3):
            self.post_question(user=self.watched_user,
                               title='question %d' % i)

        with self.assertRaises(django_exceptions.PermissionDenied):
            check_watched_user_post_rate_limit(
                self.watched_user, self._request(ip='1.2.3.4'),
            )
