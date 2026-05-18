"""Unit tests for ``RateLimitMiddleware.process_view`` and the
``ratelimit_exempt`` view decorator.

End-to-end tests that drive the real URL chain live in
``test_rate_limiting.py`` (``RateLimitIntegrationTests``); this file
covers the middleware in isolation via ``RequestFactory`` and
synthetic view callables.
"""
from django.core.cache import caches
from django.http import HttpResponse
from django.test import RequestFactory
from django.views.decorators import csrf

from askbot.middleware import ratelimit as ratelimit_mod
from askbot.middleware.ratelimit import RateLimitMiddleware
from askbot.tests.utils import AskbotTestCase, with_settings
from askbot.utils.ratelimit import askbot_ratelimit, ratelimit_exempt


def _passthrough(request):
    return HttpResponse('ok')


def _make_exempt_view():
    """Return a new exempt view callable.

    ``ratelimit_exempt`` is csrf_exempt-style — it mutates the passed
    function in place and returns it. Tests that need an exempt view
    MUST get a fresh callable; reusing ``_passthrough`` would mark
    that module-global function as exempt for every subsequent test
    in this module.
    """
    def view(request):
        return HttpResponse('ok')
    return ratelimit_exempt(view)


def _new_middleware():
    """Construct a middleware whose ``get_response`` is a no-op.

    Always reset ``MISCONFIG_CHECK_DONE`` BEFORE calling this so the
    boot-time warning from this unit-test instance does not bleed into
    neighboring assertions.
    """
    return RateLimitMiddleware(lambda r: HttpResponse('ok'))


class RatelimitExemptDecoratorTests(AskbotTestCase):
    """Contract tests for the ``ratelimit_exempt`` decorator itself.

    The strict-identity and "no wrapper" assertions lock in the
    csrf_exempt-style implementation so a future "helpful" rewrite
    that adds a wrapper or replaces ``True`` with a truthy value fails
    a focused test instead of breaking the middleware contract
    silently.
    """

    def test_sets_attribute_to_true(self):
        def view(request):
            return HttpResponse()

        decorated = ratelimit_exempt(view)
        self.assertIs(decorated.askbot_ratelimit_exempt, True)

    def test_returns_same_function_object(self):
        def view(request):
            """doc"""
            return HttpResponse()

        decorated = ratelimit_exempt(view)
        self.assertIs(decorated, view)
        self.assertEqual(decorated.__name__, 'view')
        self.assertEqual(decorated.__doc__, 'doc')


class RateLimitMiddlewareProcessViewTests(AskbotTestCase):
    """Unit-level coverage of ``RateLimitMiddleware.process_view``.

    The middleware is driven directly with a ``RequestFactory`` request
    and a synthetic view callable so each behavior can be asserted in
    isolation.
    """

    # The unit-level tests in this class drive ``process_view``
    # directly with ``RequestFactory`` requests. ``RequestFactory``
    # does NOT run AuthenticationMiddleware, so ``request.user`` is
    # absent — and the HTML 429 render path needs it via a Jinja
    # context processor. Passing ``HTTP_X_REQUESTED_WITH`` routes the
    # 429 helper down the JSON path instead, which has no template
    # dependency. This matches how the AJAX client receives 429s in
    # production.
    XHR = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}

    def setUp(self):
        caches['default'].clear()
        # Reset BEFORE constructing the middleware so the boot warning
        # from the unit-test instance does not leak into other tests.
        self.addCleanup(
            setattr, ratelimit_mod, 'MISCONFIG_CHECK_DONE', False,
        )
        ratelimit_mod.MISCONFIG_CHECK_DONE = False
        self.factory = RequestFactory()

    def tearDown(self):
        caches['default'].clear()

    def _request(self, ip, method='get'):
        return getattr(self.factory, method)('/', REMOTE_ADDR=ip, **self.XHR)

    def _saturate(self, ip, max_requests):
        """Push the per-request bucket up to its cap for ``ip``.

        Drives ``process_view`` with a non-exempt view so each call
        consumes one slot. After ``max_requests`` calls, the next
        non-exempt request from the same IP will trip the limiter.
        """
        mw = _new_middleware()
        for _ in range(max_requests):
            result = mw.process_view(
                self._request(ip), _passthrough, [], {},
            )
            self.assertIsNone(result)

    @with_settings(
        REQUEST_RATE_LIMIT_ENABLED=True,
        REQUEST_RATE_LIMIT_MAX_REQUESTS=2,
    )
    def test_exempt_view_bypasses_saturated_bucket(self):
        ip = '11.0.0.1'
        self._saturate(ip, 2)

        exempt_view = _make_exempt_view()
        mw = _new_middleware()
        self.assertIsNone(
            mw.process_view(self._request(ip), exempt_view, [], {})
        )

    @with_settings(
        REQUEST_RATE_LIMIT_ENABLED=True,
        REQUEST_RATE_LIMIT_MAX_REQUESTS=2,
    )
    def test_non_exempt_view_429s_under_saturated_bucket(self):
        ip = '11.0.0.2'
        self._saturate(ip, 2)

        mw = _new_middleware()
        response = mw.process_view(
            self._request(ip), _passthrough, [], {},
        )
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 429)

    @with_settings(
        REQUEST_RATE_LIMIT_ENABLED=True,
        REQUEST_RATE_LIMIT_MAX_REQUESTS=3,
    )
    def test_exempt_requests_do_not_consume_bucket_slots(self):
        """With ``MAX_REQUESTS=N``, issue N-1 non-exempt + K exempt +
        one non-exempt — the final non-exempt must still pass (one
        slot left); a further non-exempt must 429."""
        ip = '11.0.0.3'
        mw = _new_middleware()
        exempt_view = _make_exempt_view()

        for _ in range(2):
            self.assertIsNone(
                mw.process_view(self._request(ip), _passthrough, [], {})
            )

        for _ in range(5):
            self.assertIsNone(
                mw.process_view(self._request(ip), exempt_view, [], {})
            )

        self.assertIsNone(
            mw.process_view(self._request(ip), _passthrough, [], {})
        )

        response = mw.process_view(
            self._request(ip), _passthrough, [], {},
        )
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 429)

    @with_settings(
        REQUEST_RATE_LIMIT_ENABLED=True,
        REQUEST_RATE_LIMIT_MAX_REQUESTS=1,
    )
    def test_canonical_stack_exempt_outermost_over_csrf_protect(self):
        """The configuration that ships on ``read_message``:
        ``@ratelimit_exempt`` outermost above ``@csrf.csrf_protect``.
        Confirms the attribute is visible on the wrapper returned by
        ``csrf_protect``."""
        ip = '11.0.0.4'
        self._saturate(ip, 1)

        @ratelimit_exempt
        @csrf.csrf_protect
        def view(request):
            return HttpResponse('ok')

        mw = _new_middleware()
        self.assertIsNone(
            mw.process_view(self._request(ip), view, [], {})
        )

    @with_settings(
        REQUEST_RATE_LIMIT_ENABLED=True,
        REQUEST_RATE_LIMIT_MAX_REQUESTS=1,
    )
    def test_non_wraps_inner_wrapper_shadows_attribute(self):
        """Locks in the "apply outermost" rule with the case it
        actually guards against: an inner wrapper that does NOT use
        ``functools.wraps`` shadows the exempt attribute, so the
        limiter still fires.

        ``functools.wraps`` updates ``__dict__`` from the wrapped
        function, so ``@wraps``-using decorators (``csrf_protect``,
        ``csrf_exempt``, ``login_required``, ...) actually do surface
        the attribute even when inner. A bare wrapper does not — and
        that is why the docstring rule is "outermost"."""
        ip = '11.0.0.5'
        self._saturate(ip, 1)

        def shadow_wrapper(view_func):
            # Deliberately no @functools.wraps — wrapper has its own
            # __dict__, so view_func.askbot_ratelimit_exempt does not
            # propagate up.
            def wrapper(request, *args, **kwargs):
                return view_func(request, *args, **kwargs)
            return wrapper

        @shadow_wrapper
        @ratelimit_exempt
        def view(request):
            return HttpResponse('ok')

        mw = _new_middleware()
        response = mw.process_view(self._request(ip), view, [], {})
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 429)

    @with_settings(
        REQUEST_RATE_LIMIT_ENABLED=True,
        REQUEST_RATE_LIMIT_MAX_REQUESTS=1,
    )
    def test_truthy_non_true_attribute_does_not_exempt(self):
        """``is True`` strict-identity contract: a truthy value that
        is not the ``True`` singleton must NOT exempt."""
        ip = '11.0.0.6'
        self._saturate(ip, 1)

        mw = _new_middleware()
        for truthy in (1, 'yes'):
            with self.subTest(value=repr(truthy)):
                view = lambda r: HttpResponse('ok')
                view.askbot_ratelimit_exempt = truthy
                response = mw.process_view(
                    self._request(ip), view, [], {},
                )
                self.assertIsNotNone(response)
                self.assertEqual(response.status_code, 429)

    @with_settings(
        REQUEST_RATE_LIMIT_ENABLED=True,
        REQUEST_RATE_LIMIT_MAX_REQUESTS=1,
    )
    def test_explicit_false_attribute_does_not_exempt(self):
        """Symmetric case: an explicit ``False`` value must also
        rate-limit (covers the falsy branch alongside truthy-non-True)."""
        ip = '11.0.0.7'
        self._saturate(ip, 1)

        mw = _new_middleware()
        view = lambda r: HttpResponse('ok')
        view.askbot_ratelimit_exempt = False
        response = mw.process_view(self._request(ip), view, [], {})
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 429)

    @with_settings(
        REQUEST_RATE_LIMIT_ENABLED=False,
        REGISTRATION_RATE_LIMIT_ENABLED=True,
        REGISTRATION_RATE_LIMIT_MAX_REGISTRATIONS=1,
    )
    def test_registration_policy_unaffected_by_exempt(self):
        """A view decorated with both ``@ratelimit_exempt`` AND
        ``@askbot_ratelimit(policy='registration')`` still enforces
        the registration bucket — exempt targets the middleware
        ``request`` policy only.

        Drives the registration decorator directly with the view's
        POSTs (the registration policy is POST-only) so the assertion
        is local to this file."""
        @ratelimit_exempt
        @askbot_ratelimit(policy='registration')
        def view(request):
            return HttpResponse('ok')

        ip = '11.0.0.8'
        first = view(self._request(ip, method='post'))
        self.assertEqual(first.status_code, 200)
        second = view(self._request(ip, method='post'))
        self.assertEqual(second.status_code, 429)

    @with_settings(
        REQUEST_RATE_LIMIT_ENABLED=True,
        REQUEST_RATE_LIMIT_MAX_REQUESTS=1,
    )
    def test_no_view_callable_falls_through(self):
        """``view_func=None`` (or a view without the attribute) must
        fall through to the normal limiter — never raise."""
        ip = '11.0.0.9'
        mw = _new_middleware()
        # First call (None view) must not raise; it consumes a slot.
        self.assertIsNone(
            mw.process_view(self._request(ip), None, [], {})
        )
        response = mw.process_view(self._request(ip), None, [], {})
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 429)


class RateLimitMiddlewareBootWarningTests(AskbotTestCase):
    """Smoke test: ``maybe_warn_misconfig`` still fires from
    ``__init__`` after the ``__call__`` -> ``process_view`` move."""

    LOGGER = 'askbot.middleware.ratelimit'

    def setUp(self):
        self.addCleanup(
            setattr, ratelimit_mod, 'MISCONFIG_CHECK_DONE', False,
        )
        ratelimit_mod.MISCONFIG_CHECK_DONE = False

    def test_misconfig_warning_still_fires_from_init(self):
        from django.test import override_settings
        with override_settings(CACHES={
            'default': {
                'BACKEND':
                    'django.core.cache.backends.locmem.LocMemCache',
                'LOCATION': 'rl-mw-init-locmem',
            },
        }):
            with self.assertLogs(self.LOGGER, level='WARNING') as cm:
                RateLimitMiddleware(lambda r: HttpResponse('ok'))
        self.assertTrue(any(
            'per-process' in r.getMessage() for r in cm.records
        ))
