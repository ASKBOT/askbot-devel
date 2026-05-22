"""Unit tests for askbot.utils.ratelimit.

Preconditions for this test module:

1. Django's ``RATELIMIT_ENABLE`` setting is True (the default). If a
   future test settings module sets it to False, ``get_usage`` in
   django_ratelimit returns None and every test here silently passes
   as 'under limit'. ``test_global_ratelimit_enable_setting_disables_helper``
   exercises the False path explicitly so a regression is caught in
   one place.

2. ``CACHES['default']`` is NOT ``DummyCache``. The test project uses
   ``LocMemCache`` (askbot_site/askbot_site/settings.py), which
   supports ``cache.add`` / ``cache.incr`` as django-ratelimit
   requires. ``DummyCache`` silently makes every over-limit test
   pass: ``cache.add`` always returns True, count stays at
   ``initial_value=1``, and ``count > MAX`` is never True. If the
   test settings are ever swapped to a dummy backend, add an explicit
   ``@override_settings`` for ``CACHES`` on this TestCase.
"""
import json
from unittest import mock

from django.contrib.auth.models import AnonymousUser
from django.core.cache import caches
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

from askbot import const
from askbot.tests.utils import livesettings_override, with_settings
from askbot.utils.ratelimit import (
    # Used only in JSON-branch 'message' field assertions; no longer
    # the raw response body.
    _RATELIMITED_RESPONSE_BODY,
    resolve_request_ip,
    askbot_ratelimit,
    check_askbot_ratelimit,
    is_allowlisted,
    is_askbot_ratelimited,
    is_internal_ip,
    subnet_ip_key,
)


def _dummy_view(request):
    return HttpResponse('ok', status=200)


# The default LocMemCache holds 300 entries and culls a third of them
# once full. Askbot's many livesettings fill the cache quickly, so a
# cull can evict a rate-limit bucket mid-test and make accumulation
# tests flaky. A large limit keeps every bucket alive for the test.
_NO_CULL_CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'askbot-ratelimit-tests',
        'KEY_PREFIX': 'askbot',
        'OPTIONS': {'MAX_ENTRIES': 1000000},
    },
}


@override_settings(CACHES=_NO_CULL_CACHES)
class AskbotRatelimitHelperTests(TestCase):

    def setUp(self):
        caches['default'].clear()
        self.factory = RequestFactory()

    def tearDown(self):
        caches['default'].clear()

    def _attach_browser_state(self, request):
        """Mirror SessionMiddleware + AuthenticationMiddleware.

        RequestFactory does not run middleware, so by default
        ``request.user`` and ``request.session`` are unset. Setting
        both here guarantees ``_build_429``'s HTML branch can render
        ``429.html`` (which fans out through
        ``askbot.context.application_settings`` reading
        ``request.user.is_authenticated``; ``request.session`` is set
        DEFENSIVELY for forward-compatibility with future processors).
        """
        request.user = AnonymousUser()
        request.session = {}
        return request

    def _get(self, path='/', ip='1.2.3.4', **headers):
        request = self.factory.get(path, REMOTE_ADDR=ip, **headers)
        return self._attach_browser_state(request)

    def _post(self, path='/', ip='1.2.3.4', **headers):
        request = self.factory.post(path, REMOTE_ADDR=ip, **headers)
        return self._attach_browser_state(request)

    def _get_browser_request(self, path='/', ip='1.2.3.4', **headers):
        """Browser-shaped GET (forces HTML branch via Accept header).

        Thin wrapper over ``_get`` that adds a browser-style ``Accept``.
        Use in tests that explicitly assert HTML-branch behavior; tests
        that don't care about content negotiation should use ``_get``.
        """
        headers.setdefault('HTTP_ACCEPT', 'text/html,*/*;q=0.8')
        return self._get(path=path, ip=ip, **headers)

    @with_settings(REQUEST_RATE_LIMIT_ENABLED=False,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=2)
    def test_disabled_flag_short_circuits_decorator(self):
        wrapped = askbot_ratelimit(policy='request')(_dummy_view)

        for _ in range(10):
            response = wrapped(self._get())
            self.assertEqual(response.status_code, 200)

    @with_settings(REQUEST_RATE_LIMIT_ENABLED=False,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=2)
    def test_disabled_flag_short_circuits_check(self):
        for _ in range(10):
            result = check_askbot_ratelimit(
                self._get(),
                policy='request',
            )
            self.assertIsNone(result)

    @with_settings(REQUEST_RATE_LIMIT_ENABLED=True,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=5)
    def test_under_limit_passes(self):
        wrapped = askbot_ratelimit(policy='request')(_dummy_view)

        for _ in range(5):
            request = self._get()
            response = wrapped(request)
            self.assertEqual(response.status_code, 200)

    @with_settings(REQUEST_RATE_LIMIT_ENABLED=True,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=5)
    def test_over_limit_returns_429_and_view_not_called(self):
        mock_view = mock.MagicMock(
            return_value=HttpResponse('ok', status=200)
        )
        mock_view.__name__ = 'mock_view'

        wrapped = askbot_ratelimit(policy='request')(mock_view)

        for _ in range(5):
            response = wrapped(self._get())
            self.assertEqual(response.status_code, 200)

        over_request = self._get()
        response = wrapped(over_request)
        self.assertEqual(response.status_code, 429)
        # Wrapped view must NOT be invoked on the over-limit request.
        self.assertEqual(mock_view.call_count, 5)

    def test_livesettings_read_at_request_time(self):
        wrapped = askbot_ratelimit(policy='request')(_dummy_view)

        with livesettings_override(REQUEST_RATE_LIMIT_ENABLED=True,
                                   REQUEST_RATE_LIMIT_MAX_REQUESTS=2):
            self.assertEqual(wrapped(self._get()).status_code, 200)
            self.assertEqual(wrapped(self._get()).status_code, 200)
            self.assertEqual(wrapped(self._get()).status_code, 429)

            # Flip enabled off. Per the INVARIANT in _is_over_limit,
            # the disabled branch short-circuits BEFORE is_ratelimited
            # is called, so stale bucket state is never consulted. No
            # cache clear here — adding one would hide a regression
            # where the disabled check accidentally falls through.
            with livesettings_override(REQUEST_RATE_LIMIT_ENABLED=False):
                self.assertEqual(wrapped(self._get()).status_code, 200)

    def test_rate_string_reflects_current_max_count(self):
        """Changing MAX mid-window starts a fresh bucket.

        Corollary: lowering MAX does NOT evict existing offenders from
        the in-progress window; the old bucket persists under its old
        cache key until expiry. Symmetric property of the same
        mechanism (different rate string → different cache key).
        """
        from django_ratelimit.core import is_ratelimited as real_impl

        wrapped = askbot_ratelimit(policy='request')(_dummy_view)

        with livesettings_override(REQUEST_RATE_LIMIT_ENABLED=True,
                                   REQUEST_RATE_LIMIT_MAX_REQUESTS=2):
            with mock.patch(
                'askbot.utils.ratelimit.is_ratelimited',
                wraps=real_impl,
            ) as spy:
                self.assertEqual(wrapped(self._get()).status_code, 200)
                self.assertEqual(wrapped(self._get()).status_code, 200)
                self.assertEqual(wrapped(self._get()).status_code, 429)

                with livesettings_override(
                    REQUEST_RATE_LIMIT_MAX_REQUESTS=10
                ):
                    # Fresh bucket under new rate string — allowed.
                    self.assertEqual(
                        wrapped(self._get()).status_code, 200
                    )
                    self.assertEqual(
                        wrapped(self._get()).status_code, 200
                    )

                    rate_kwargs = [
                        c.kwargs['rate'] for c in spy.call_args_list
                    ]
                    self.assertIn('2/60s', rate_kwargs)
                    self.assertIn('10/60s', rate_kwargs)

    @with_settings(REQUEST_RATE_LIMIT_ENABLED=True,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=1)
    def test_429_is_json_for_ajax_requests(self):
        wrapped = askbot_ratelimit(policy='request')(_dummy_view)

        # Burn the one allowed slot.
        self.assertEqual(wrapped(self._get()).status_code, 200)

        over_request = self._get(HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        response = wrapped(over_request)
        self.assertEqual(response.status_code, 429)
        self.assertTrue(
            response['Content-Type'].startswith('application/json')
        )
        self.assertEqual(
            json.loads(response.content),
            {
                'error': 'rate_limited',
                'message': _RATELIMITED_RESPONSE_BODY,
                'retry_after': const.REQUEST_RATE_LIMIT_WINDOW_SECONDS,
            },
        )
        self.assertEqual(
            response['Retry-After'],
            str(const.REQUEST_RATE_LIMIT_WINDOW_SECONDS),
        )
        self.assertIn('Accept', response['Vary'])
        self.assertIn('X-Requested-With', response['Vary'])

    @with_settings(REQUEST_RATE_LIMIT_ENABLED=True,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=1)
    def test_429_is_json_for_explicit_accept_header(self):
        wrapped = askbot_ratelimit(policy='request')(_dummy_view)
        self.assertEqual(wrapped(self._get()).status_code, 200)

        over_request = self._get(HTTP_ACCEPT='application/json')
        response = wrapped(over_request)
        self.assertEqual(response.status_code, 429)
        self.assertTrue(
            response['Content-Type'].startswith('application/json')
        )
        self.assertEqual(
            json.loads(response.content),
            {
                'error': 'rate_limited',
                'message': _RATELIMITED_RESPONSE_BODY,
                'retry_after': const.REQUEST_RATE_LIMIT_WINDOW_SECONDS,
            },
        )
        self.assertEqual(
            response['Retry-After'],
            str(const.REQUEST_RATE_LIMIT_WINDOW_SECONDS),
        )
        self.assertIn('Accept', response['Vary'])
        self.assertIn('X-Requested-With', response['Vary'])

    @with_settings(REQUEST_RATE_LIMIT_ENABLED=True,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=1)
    def test_ajax_header_wins_over_html_accept(self):
        # X-Requested-With must beat Accept: text/html. jQuery callers
        # routinely send both and expect JSON back.
        wrapped = askbot_ratelimit(policy='request')(_dummy_view)
        self.assertEqual(wrapped(self._get()).status_code, 200)

        over_request = self._get(
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='text/html',
        )
        response = wrapped(over_request)
        self.assertEqual(response.status_code, 429)
        self.assertTrue(
            response['Content-Type'].startswith('application/json')
        )

    @with_settings(REQUEST_RATE_LIMIT_ENABLED=True,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=1)
    def test_429_is_html_for_browser_request(self):
        wrapped = askbot_ratelimit(policy='request')(_dummy_view)
        self.assertEqual(wrapped(self._get()).status_code, 200)

        over_request = self._get_browser_request()
        response = wrapped(over_request)
        self.assertEqual(response.status_code, 429)
        self.assertTrue(
            response['Content-Type'].startswith('text/html')
        )
        self.assertIn(b'<html', response.content.lower())
        # Locks in that the 429.html template specifically rendered
        # (not just *some* base page).
        self.assertIn(b'Too many requests', response.content)
        # Locks in the visual-identity contract used by ops/CSS.
        self.assertIn(b'error-429-page', response.content)
        self.assertEqual(
            response['Retry-After'],
            str(const.REQUEST_RATE_LIMIT_WINDOW_SECONDS),
        )
        self.assertIn('Accept', response['Vary'])
        self.assertIn('X-Requested-With', response['Vary'])

    @with_settings(REQUEST_RATE_LIMIT_ENABLED=True,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=1)
    def test_429_is_html_when_accept_is_wildcard(self):
        # `_wants_json` must require JSON to be explicitly preferred
        # over HTML, not just accepted via */*.
        wrapped = askbot_ratelimit(policy='request')(_dummy_view)
        self.assertEqual(wrapped(self._get()).status_code, 200)

        over_request = self._get_browser_request(HTTP_ACCEPT='*/*')
        response = wrapped(over_request)
        self.assertEqual(response.status_code, 429)
        self.assertTrue(
            response['Content-Type'].startswith('text/html')
        )

    @with_settings(REQUEST_RATE_LIMIT_ENABLED=True,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=1)
    def test_429_is_html_when_accept_header_absent(self):
        # Django 4.x treats a missing Accept as */*, so `_wants_json`
        # should return False -> HTML branch. Distinct from explicit
        # */* (which is `test_429_is_html_when_accept_is_wildcard`).
        wrapped = askbot_ratelimit(policy='request')(_dummy_view)
        self.assertEqual(wrapped(self._get()).status_code, 200)

        over_request = self._get()
        # Defensive: if RequestFactory ever starts injecting a default
        # Accept, this keeps the test exercising the truly-absent path.
        over_request.META.pop('HTTP_ACCEPT', None)
        response = wrapped(over_request)
        self.assertEqual(response.status_code, 429)
        self.assertTrue(
            response['Content-Type'].startswith('text/html')
        )

    @with_settings(REQUEST_RATE_LIMIT_ENABLED=True,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=1)
    def test_429_html_when_accept_mixes_q_values_preferring_json(self):
        wrapped = askbot_ratelimit(policy='request')(_dummy_view)
        self.assertEqual(wrapped(self._get()).status_code, 200)

        over_request = self._get(
            HTTP_ACCEPT='application/json;q=0.9,text/html;q=0.5',
        )
        response = wrapped(over_request)
        self.assertEqual(response.status_code, 429)
        self.assertTrue(
            response['Content-Type'].startswith('text/html')
        )

    @with_settings(REQUEST_RATE_LIMIT_ENABLED=True,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=1)
    def test_retry_after_matches_policy_window_seconds(self):
        # Inject a synthetic policy with window_seconds=42. The '42'
        # literal is intentional: this test asserts an arbitrary
        # synthetic-policy window flows through verbatim, so a const
        # comparison would defeat the test.
        from django_ratelimit import ALL as _ALL_METHODS
        synthetic = {
            'window-42': {
                'enabled_setting': 'REQUEST_RATE_LIMIT_ENABLED',
                'rate_setting': 'REQUEST_RATE_LIMIT_MAX_REQUESTS',
                'window_seconds': 42,
                'group': 'askbot.ratelimit.test.window-42',
                'key': 'ip',
                'methods': _ALL_METHODS,
            },
        }
        with mock.patch.dict(
            'askbot.utils.ratelimit._POLICIES', synthetic,
        ):
            wrapped = askbot_ratelimit(policy='window-42')(_dummy_view)
            self.assertEqual(wrapped(self._get()).status_code, 200)

            over_request = self._get(
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
            response = wrapped(over_request)
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response['Retry-After'], '42')
            payload = json.loads(response.content)
            self.assertEqual(payload['retry_after'], 42)
            self.assertIsInstance(payload['retry_after'], int)

    @with_settings(REQUEST_RATE_LIMIT_ENABLED=True,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=1)
    def test_check_variant_also_returns_content_negotiated_response(self):
        # Mirror of test_429_is_json_for_ajax_requests but through
        # check_askbot_ratelimit -- guards against the two variants
        # drifting apart. Also covers the under-limit None case.
        request_ok = self._get(HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertIsNone(check_askbot_ratelimit(
            request_ok,
            policy='request',
        ))

        request_over = self._get(HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        response = check_askbot_ratelimit(
            request_over,
            policy='request',
        )
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 429)
        self.assertTrue(
            response['Content-Type'].startswith('application/json')
        )
        self.assertEqual(
            json.loads(response.content),
            {
                'error': 'rate_limited',
                'message': _RATELIMITED_RESPONSE_BODY,
                'retry_after': const.REQUEST_RATE_LIMIT_WINDOW_SECONDS,
            },
        )
        self.assertEqual(
            response['Retry-After'],
            str(const.REQUEST_RATE_LIMIT_WINDOW_SECONDS),
        )
        self.assertIn('Accept', response['Vary'])
        self.assertIn('X-Requested-With', response['Vary'])

    @with_settings(REQUEST_RATE_LIMIT_ENABLED=True,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=2)
    def test_method_filter_only_limits_specified_verbs(self):
        # The method filter is a per-policy field in _POLICIES; inject
        # a synthetic POST-only policy reusing the request livesettings
        # so this test stays decoupled from any specific real policy's
        # method choice.
        synthetic = {
            'post-only-request': {
                'enabled_setting': 'REQUEST_RATE_LIMIT_ENABLED',
                'rate_setting': 'REQUEST_RATE_LIMIT_MAX_REQUESTS',
                'window_seconds': const.REQUEST_RATE_LIMIT_WINDOW_SECONDS,
                'group': 'method-filter-test',
                'key': subnet_ip_key,
                'methods': ['POST'],
            },
        }
        with mock.patch.dict(
            'askbot.utils.ratelimit._POLICIES', synthetic
        ):
            wrapped = askbot_ratelimit(
                policy='post-only-request',
            )(_dummy_view)

            def post():
                return self._post(ip='1.2.3.4')

            def get():
                return self._get(ip='1.2.3.4')

            self.assertEqual(wrapped(post()).status_code, 200)
            self.assertEqual(wrapped(get()).status_code, 200)
            self.assertEqual(wrapped(post()).status_code, 200)
            self.assertEqual(wrapped(get()).status_code, 200)
            # Third POST trips the limit.
            self.assertEqual(wrapped(post()).status_code, 429)
            # GET is unaffected.
            self.assertEqual(wrapped(get()).status_code, 200)

    @override_settings(RATELIMIT_ENABLE=False)
    @with_settings(REQUEST_RATE_LIMIT_ENABLED=True,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=1)
    def test_global_ratelimit_enable_setting_disables_helper(self):
        wrapped = askbot_ratelimit(policy='request')(_dummy_view)

        for _ in range(5):
            request = self._get()
            response = wrapped(request)
            self.assertEqual(response.status_code, 200)

    @with_settings(REQUEST_RATE_LIMIT_ENABLED=True,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=2)
    def test_window_seconds_included_in_cache_key(self):
        """Different window_seconds → different bucket, same group+IP.

        Locks in the cache-keying invariant: a future refactor that
        hardcoded ``'%d/60s'`` (dropping the policy's window) would
        silently collapse two policies with different windows onto one
        bucket.

        Uses ``mock.patch.dict`` to inject two synthetic policies that
        differ ONLY in ``window_seconds`` — all other variables
        (enabled setting, rate setting, group, IP) are held constant,
        isolating the window as the single differing input.
        """
        from django_ratelimit import ALL as _ALL_METHODS
        synthetic = {
            'window-short': {
                'enabled_setting': 'REQUEST_RATE_LIMIT_ENABLED',
                'rate_setting': 'REQUEST_RATE_LIMIT_MAX_REQUESTS',
                'window_seconds': 60,
                'group': 'window-test-shared',
                'key': 'ip',
                'methods': _ALL_METHODS,
            },
            'window-long': {
                'enabled_setting': 'REQUEST_RATE_LIMIT_ENABLED',
                'rate_setting': 'REQUEST_RATE_LIMIT_MAX_REQUESTS',
                'window_seconds': 3600,
                'group': 'window-test-shared',
                'key': 'ip',
                'methods': _ALL_METHODS,
            },
        }
        with mock.patch.dict(
            'askbot.utils.ratelimit._POLICIES', synthetic
        ):
            wrapped_short = askbot_ratelimit(
                policy='window-short',
            )(_dummy_view)
            wrapped_long = askbot_ratelimit(
                policy='window-long',
            )(_dummy_view)

            # Exhaust wrapped_short at MAX=2.
            self.assertEqual(wrapped_short(self._get()).status_code, 200)
            self.assertEqual(wrapped_short(self._get()).status_code, 200)
            self.assertEqual(wrapped_short(self._get()).status_code, 429)

            # Fresh bucket for the 3600s window — not shared.
            self.assertEqual(wrapped_long(self._get()).status_code, 200)
            self.assertEqual(wrapped_long(self._get()).status_code, 200)

    def test_unknown_policy_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            askbot_ratelimit(policy='nonexistent')(_dummy_view)
        self.assertIn('nonexistent', str(ctx.exception))

        with self.assertRaises(ValueError):
            check_askbot_ratelimit(
                self._get(),
                policy='nonexistent',
            )

    @with_settings(
        REGISTRATION_RATE_LIMIT_ENABLED=True,
        REGISTRATION_RATE_LIMIT_MAX_REGISTRATIONS=2,
        # MUST enable the `request` policy too: the isolation arm
        # below uses policy='request' for dummy_other, and if this
        # flag is False, _is_over_limit short-circuits at the
        # enabled-flag check (utils/ratelimit.py:77) and dummy_other
        # returns 200 regardless of bucket state — silently hiding
        # whether isolation is real or is just the disabled path.
        # Pair with a high MAX so the isolation arm cannot be tripped
        # by preceding registration traffic (different buckets, but
        # belt-and-braces).
        REQUEST_RATE_LIMIT_ENABLED=True,
        REQUEST_RATE_LIMIT_MAX_REQUESTS=1000,
    )
    def test_same_policy_implies_shared_bucket(self):
        """Smoke: registration policy 429s on limit; both registration
        views share one per-IP bucket; non-registration policies are
        unaffected. Cache-clear inherited from class setUp/tearDown."""
        # supersedes test_decorator_uses_view_qualname_for_group_by_default
        # — the policy is now the bucket discriminator
        from askbot import const
        from askbot.utils import ratelimit as ratelimit_module
        from django_ratelimit.core import is_ratelimited as real_impl

        # Pin the policy row shape (guard against silent edits).
        self.assertEqual(
            ratelimit_module._POLICIES['registration'],
            {
                'enabled_setting': 'REGISTRATION_RATE_LIMIT_ENABLED',
                'rate_setting':
                    'REGISTRATION_RATE_LIMIT_MAX_REGISTRATIONS',
                'window_seconds':
                    const.REGISTRATION_RATE_LIMIT_WINDOW_SECONDS,
                'group': 'askbot.ratelimit.registration',
                'key': subnet_ip_key,
                'methods': ratelimit_module._ALL_METHODS,
            },
        )

        # Three dummy views: two registration (shared via policy), one
        # unrelated (different policy → different bucket).
        dummy_register = askbot_ratelimit(policy='registration')(_dummy_view)
        dummy_signup = askbot_ratelimit(policy='registration')(_dummy_view)
        dummy_other = askbot_ratelimit(policy='request')(_dummy_view)

        ip = '1.2.3.4'

        def post(view):
            return view(self._post(ip=ip))

        def get(view):
            return view(self._get(ip=ip))

        with mock.patch(
            'askbot.utils.ratelimit.is_ratelimited',
            wraps=real_impl,
        ) as spy:
            # Exhaust via dummy_register at MAX=2.
            self.assertEqual(post(dummy_register).status_code, 200)
            self.assertEqual(post(dummy_register).status_code, 200)

            # Shared bucket: dummy_signup hits 429 even though it has
            # not been called yet (same group, same IP).
            over_request = self._post(ip=ip)
            response = dummy_signup(over_request)
            self.assertEqual(response.status_code, 429)

            # The registration policy now counts every method, so a
            # GET also evaluates the limit. The bucket is already over
            # limit (three prior POSTs), so this GET 429s too.
            self.assertEqual(get(dummy_register).status_code, 429)

            # Non-registration policy on the same IP: unaffected.
            # REQUEST_RATE_LIMIT_ENABLED=True ensures a real
            # evaluation, not the disabled-flag short-circuit.
            self.assertEqual(post(dummy_other).status_code, 200)

            # Spy: registration decorator passed the expected rate
            # string (compare against const, NOT a bare literal, so a
            # legitimate const tweak re-runs without a mystery fail).
            expected_rate = (
                f'2/{const.REGISTRATION_RATE_LIMIT_WINDOW_SECONDS}s'
            )
            registration_rates = [
                c.kwargs['rate'] for c in spy.call_args_list
                if c.kwargs.get('group') == 'askbot.ratelimit.registration'
            ]
            self.assertIn(expected_rate, registration_rates)

    @with_settings(REQUEST_RATE_LIMIT_ENABLED=True,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=5)
    def test_is_askbot_ratelimited_returns_false_under_limit(self):
        request = self._get()
        result = is_askbot_ratelimited(
            request,
            policy='request',
        )
        self.assertIs(result, False)

    @with_settings(REQUEST_RATE_LIMIT_ENABLED=True,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=2)
    def test_is_askbot_ratelimited_over_limit(
        self,
    ):
        with mock.patch(
            'askbot.utils.ratelimit._build_429',
        ) as spy:
            # Burn the two allowed slots.
            self.assertIs(
                is_askbot_ratelimited(
                    self._get(),
                    policy='request',
                ),
                False,
            )
            self.assertIs(
                is_askbot_ratelimited(
                    self._get(),
                    policy='request',
                ),
                False,
            )

            over_request = self._get()
            result = is_askbot_ratelimited(
                over_request,
                policy='request',
            )
            self.assertIs(result, True)
            self.assertIsInstance(result, bool)
            # Locks in the no-response-built contract: the primitive
            # must NOT route through the response builder.
            self.assertEqual(spy.call_count, 0)

    @with_settings(REQUEST_RATE_LIMIT_ENABLED=False,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=2)
    def test_is_askbot_ratelimited_disabled_flag_short_circuits(self):
        for _ in range(10):
            request = self._get()
            result = is_askbot_ratelimited(
                request,
                policy='request',
            )
            self.assertIs(result, False)

    def test_is_askbot_ratelimited_unknown_policy_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            is_askbot_ratelimited(
                self._get(),
                policy='nonexistent',
            )
        self.assertIn('nonexistent', str(ctx.exception))


class RateLimitWarningEmissionTests(TestCase):
    """Asserts the structured WARNING line emitted by ``_is_over_limit``
    on every rate-limit hit, across all three entry points (decorator,
    middleware-style check, and primitive). Locks in:

    - WARNING fires once per hit on each entry point.
    - WARNING line carries the stable ``askbot.ratelimit hit `` anchor
      (trailing space) plus ``policy=``, ``ip=``, ``group=`` fields.
    - No WARNING under limit on any entry point.
    - No WARNING when allowlist or enabled-flag short-circuits, on
      any entry point.
    """

    LOGGER = 'askbot.utils.ratelimit'
    ANCHOR = 'askbot.ratelimit hit '

    def setUp(self):
        caches['default'].clear()
        self.factory = RequestFactory()

    def tearDown(self):
        caches['default'].clear()

    def _attach_browser_state(self, request):
        request.user = AnonymousUser()
        request.session = {}
        return request

    def _get(self, ip='1.2.3.4', **headers):
        request = self.factory.get('/', REMOTE_ADDR=ip, **headers)
        return self._attach_browser_state(request)

    def _hit_records(self, captured):
        return [
            r for r in captured.records
            if r.getMessage().startswith(self.ANCHOR)
        ]

    @with_settings(RATE_LIMIT_IP_ALLOWLIST=[],
                   REQUEST_RATE_LIMIT_ENABLED=True,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=1)
    def test_warning_fires_on_decorator_hit(self):
        wrapped = askbot_ratelimit(policy='request')(_dummy_view)
        self.assertEqual(wrapped(self._get()).status_code, 200)
        with self.assertLogs(self.LOGGER, level='WARNING') as cm:
            self.assertEqual(wrapped(self._get()).status_code, 429)
        hits = self._hit_records(cm)
        self.assertEqual(len(hits), 1)
        msg = hits[0].getMessage()
        self.assertIn('policy=request', msg)
        self.assertIn('ip=1.2.3.4', msg)
        self.assertIn('group=askbot.ratelimit.request', msg)

    @with_settings(RATE_LIMIT_IP_ALLOWLIST=[],
                   REQUEST_RATE_LIMIT_ENABLED=True,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=1)
    def test_warning_fires_on_check_askbot_ratelimit_hit(self):
        # Headline path the issue is named for.
        self.assertIsNone(check_askbot_ratelimit(
            self._get(), policy='request',
        ))
        with self.assertLogs(self.LOGGER, level='WARNING') as cm:
            response = check_askbot_ratelimit(
                self._get(), policy='request',
            )
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 429)
        hits = self._hit_records(cm)
        self.assertEqual(len(hits), 1)
        msg = hits[0].getMessage()
        self.assertIn('policy=request', msg)
        self.assertIn('ip=1.2.3.4', msg)
        self.assertIn('group=askbot.ratelimit.request', msg)

    @with_settings(RATE_LIMIT_IP_ALLOWLIST=[],
                   REQUEST_RATE_LIMIT_ENABLED=True,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=1)
    def test_warning_fires_on_is_askbot_ratelimited_hit(self):
        self.assertIs(
            is_askbot_ratelimited(
                self._get(), policy='request',
            ),
            False,
        )
        with self.assertLogs(self.LOGGER, level='WARNING') as cm:
            self.assertIs(
                is_askbot_ratelimited(
                    self._get(), policy='request',
                ),
                True,
            )
        hits = self._hit_records(cm)
        self.assertEqual(len(hits), 1)
        msg = hits[0].getMessage()
        self.assertIn('policy=request', msg)
        self.assertIn('ip=1.2.3.4', msg)
        self.assertIn('group=askbot.ratelimit.request', msg)

    @with_settings(RATE_LIMIT_IP_ALLOWLIST=[],
                   REQUEST_RATE_LIMIT_ENABLED=True,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=5)
    def test_no_warning_on_decorator_under_limit(self):
        wrapped = askbot_ratelimit(policy='request')(_dummy_view)
        with self.assertNoLogs(self.LOGGER, level='WARNING'):
            self.assertEqual(wrapped(self._get()).status_code, 200)

    @with_settings(RATE_LIMIT_IP_ALLOWLIST=[],
                   REQUEST_RATE_LIMIT_ENABLED=True,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=5)
    def test_no_warning_on_check_askbot_ratelimit_under_limit(self):
        with self.assertNoLogs(self.LOGGER, level='WARNING'):
            self.assertIsNone(check_askbot_ratelimit(
                self._get(), policy='request',
            ))

    @with_settings(RATE_LIMIT_IP_ALLOWLIST=[],
                   REQUEST_RATE_LIMIT_ENABLED=True,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=5)
    def test_no_warning_on_is_askbot_ratelimited_under_limit(self):
        with self.assertNoLogs(self.LOGGER, level='WARNING'):
            self.assertIs(
                is_askbot_ratelimited(
                    self._get(), policy='request',
                ),
                False,
            )

    @with_settings(RATE_LIMIT_IP_ALLOWLIST=['1.2.3.4'],
                   REQUEST_RATE_LIMIT_ENABLED=True,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=1)
    def test_no_warning_on_decorator_allowlist_bypass(self):
        wrapped = askbot_ratelimit(policy='request')(_dummy_view)
        with self.assertNoLogs(self.LOGGER, level='WARNING'):
            for _ in range(5):
                self.assertEqual(
                    wrapped(self._get(ip='1.2.3.4')).status_code, 200,
                )

    @with_settings(RATE_LIMIT_IP_ALLOWLIST=['1.2.3.4'],
                   REQUEST_RATE_LIMIT_ENABLED=True,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=1)
    def test_no_warning_on_check_askbot_ratelimit_allowlist_bypass(self):
        with self.assertNoLogs(self.LOGGER, level='WARNING'):
            for _ in range(5):
                self.assertIsNone(check_askbot_ratelimit(
                    self._get(ip='1.2.3.4'), policy='request',
                ))

    @with_settings(RATE_LIMIT_IP_ALLOWLIST=['1.2.3.4'],
                   REQUEST_RATE_LIMIT_ENABLED=True,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=1)
    def test_no_warning_on_is_askbot_ratelimited_allowlist_bypass(self):
        with self.assertNoLogs(self.LOGGER, level='WARNING'):
            for _ in range(5):
                self.assertIs(
                    is_askbot_ratelimited(
                        self._get(ip='1.2.3.4'), policy='request',
                    ),
                    False,
                )

    @with_settings(RATE_LIMIT_IP_ALLOWLIST=[],
                   REQUEST_RATE_LIMIT_ENABLED=False,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=1)
    def test_no_warning_on_decorator_disabled_flag(self):
        wrapped = askbot_ratelimit(policy='request')(_dummy_view)
        with self.assertNoLogs(self.LOGGER, level='WARNING'):
            for _ in range(5):
                self.assertEqual(
                    wrapped(self._get()).status_code, 200,
                )

    @with_settings(RATE_LIMIT_IP_ALLOWLIST=[],
                   REQUEST_RATE_LIMIT_ENABLED=False,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=1)
    def test_no_warning_on_check_askbot_ratelimit_disabled_flag(self):
        with self.assertNoLogs(self.LOGGER, level='WARNING'):
            for _ in range(5):
                self.assertIsNone(check_askbot_ratelimit(
                    self._get(), policy='request',
                ))

    @with_settings(RATE_LIMIT_IP_ALLOWLIST=[],
                   REQUEST_RATE_LIMIT_ENABLED=False,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=1)
    def test_no_warning_on_is_askbot_ratelimited_disabled_flag(self):
        with self.assertNoLogs(self.LOGGER, level='WARNING'):
            for _ in range(5):
                self.assertIs(
                    is_askbot_ratelimited(
                        self._get(), policy='request',
                    ),
                    False,
                )


class ResolveRequestIpTests(TestCase):
    """Direct coverage of ``resolve_request_ip``.

    Catches precedence-discriminator regressions at their source rather
    than via downstream symptoms in subnet/allowlist tests.
    """

    def setUp(self):
        self.factory = RequestFactory()

    def test_unset_meta_key_uses_remote_addr(self):
        request = self.factory.get('/', REMOTE_ADDR='1.2.3.4')
        self.assertEqual(resolve_request_ip(request), '1.2.3.4')

    def test_callable_meta_key_is_invoked(self):
        # `override_settings` is used as a context manager here because
        # `picker` is defined inside the test body, so it isn't in scope
        # at decoration time.
        request = self.factory.get('/', REMOTE_ADDR='10.0.0.1')

        def picker(req):
            return '9.9.9.9'

        with override_settings(RATELIMIT_IP_META_KEY=picker):
            self.assertEqual(resolve_request_ip(request), '9.9.9.9')

    @override_settings(RATELIMIT_IP_META_KEY='myproj.utils.get_ip')
    def test_dotted_path_string_is_imported_and_called(self):
        # The `'.' in ip_meta` discriminator regression test: without
        # the dot test, this branch would silently misroute to META-key
        # lookup. We patch import_string so the branch is exercised
        # deterministically without registering a real importable path.
        request = self.factory.get('/', REMOTE_ADDR='10.0.0.1')

        callable_mock = mock.MagicMock(return_value='5.5.5.5')
        with mock.patch(
            'askbot.utils.ratelimit.import_string',
            return_value=callable_mock,
        ) as import_spy:
            result = resolve_request_ip(request)

        self.assertEqual(result, '5.5.5.5')
        import_spy.assert_called_once_with('myproj.utils.get_ip')
        callable_mock.assert_called_once_with(request)

    @override_settings(RATELIMIT_IP_META_KEY='HTTP_X_FORWARDED_FOR')
    def test_meta_key_string_reads_from_request_meta(self):
        request = self.factory.get(
            '/',
            REMOTE_ADDR='10.0.0.1',
            HTTP_X_FORWARDED_FOR='1.2.3.4',
        )
        self.assertEqual(resolve_request_ip(request), '1.2.3.4')

    @override_settings(RATELIMIT_IP_META_KEY='HTTP_X_FORWARDED_FOR')
    def test_missing_meta_key_returns_empty_string(self):
        # Graceful fallback divergence from _get_ip
        # (which would raise ImproperlyConfigured).
        request = self.factory.get('/', REMOTE_ADDR='10.0.0.1')
        request.META.pop('HTTP_X_FORWARDED_FOR', None)
        self.assertEqual(resolve_request_ip(request), '')

    @override_settings(RATELIMIT_IP_META_KEY='HTTP_X_FORWARDED_FOR')
    def test_multi_hop_xff_returns_first_entry(self):
        request = self.factory.get(
            '/',
            HTTP_X_FORWARDED_FOR='1.2.3.4, 10.0.0.1',
        )
        self.assertEqual(resolve_request_ip(request), '1.2.3.4')

    @override_settings(RATELIMIT_IP_META_KEY='HTTP_X_FORWARDED_FOR')
    def test_single_value_input_unchanged(self):
        request = self.factory.get(
            '/', HTTP_X_FORWARDED_FOR='1.2.3.4',
        )
        self.assertEqual(resolve_request_ip(request), '1.2.3.4')

    @override_settings(RATELIMIT_IP_META_KEY='HTTP_X_FORWARDED_FOR')
    def test_whitespace_is_stripped(self):
        request = self.factory.get(
            '/', HTTP_X_FORWARDED_FOR=' 1.2.3.4 , 10.0.0.1',
        )
        self.assertEqual(resolve_request_ip(request), '1.2.3.4')


class SubnetIpKeyTests(TestCase):
    """Subnet bucketing via ``subnet_ip_key``."""

    def setUp(self):
        caches['default'].clear()
        self.factory = RequestFactory()

    def tearDown(self):
        caches['default'].clear()

    def _attach_browser_state(self, request):
        request.user = AnonymousUser()
        request.session = {}
        return request

    def _get(self, ip='1.2.3.4', **headers):
        request = self.factory.get('/', REMOTE_ADDR=ip, **headers)
        return self._attach_browser_state(request)

    def _post(self, ip='1.2.3.4', **headers):
        request = self.factory.post('/', REMOTE_ADDR=ip, **headers)
        return self._attach_browser_state(request)

    def test_ipv4_24_default_groups_neighbors(self):
        a = subnet_ip_key('grp', self._get(ip='1.2.3.4'))
        b = subnet_ip_key('grp', self._get(ip='1.2.3.5'))
        c = subnet_ip_key('grp', self._get(ip='1.2.4.5'))
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertEqual(a, '1.2.3.0/24')

    def test_ipv6_64_default_groups_neighbors(self):
        a = subnet_ip_key('grp', self._get(ip='2001:db8::1'))
        b = subnet_ip_key('grp', self._get(ip='2001:db8::ffff'))
        c = subnet_ip_key('grp', self._get(ip='2001:db8:1::1'))
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_ipv4_mapped_ipv6_normalized_to_ipv4_width(self):
        # Pin the choice: ::ffff:1.2.3.4 buckets at IPv4 /24, not IPv6.
        mapped = subnet_ip_key('grp', self._get(ip='::ffff:1.2.3.4'))
        plain = subnet_ip_key('grp', self._get(ip='1.2.3.4'))
        self.assertEqual(mapped, plain)
        self.assertEqual(mapped, '1.2.3.0/24')

    def test_unparseable_input_returns_unique_sentinel(self):
        # Both request objects held alive in locals so id() uniqueness
        # is guaranteed for the assertion (regression test for the
        # global-bucket-collapse bug).
        req_a = self._get(ip='garbage')
        req_b = self._get(ip='also-garbage')
        key_a = subnet_ip_key('grp', req_a)
        key_b = subnet_ip_key('grp', req_b)
        self.assertTrue(key_a.startswith('invalid:'))
        self.assertTrue(key_b.startswith('invalid:'))
        self.assertNotEqual(key_a, key_b)

    def test_empty_remote_addr_returns_unique_sentinel(self):
        req_a = self._get(ip='')
        req_b = self._get(ip='')
        key_a = subnet_ip_key('grp', req_a)
        key_b = subnet_ip_key('grp', req_b)
        self.assertTrue(key_a.startswith('invalid:'))
        self.assertTrue(key_b.startswith('invalid:'))
        self.assertNotEqual(key_a, key_b)

    @override_settings(RATELIMIT_IP_META_KEY='HTTP_X_FORWARDED_FOR')
    def test_reverse_proxy_buckets_by_xff_not_remote_addr(self):
        req_a = self._get(
            ip='10.0.0.1', HTTP_X_FORWARDED_FOR='1.2.3.4',
        )
        req_b = self._get(
            ip='10.0.0.2', HTTP_X_FORWARDED_FOR='1.2.3.4',
        )
        self.assertEqual(
            subnet_ip_key('grp', req_a),
            subnet_ip_key('grp', req_b),
        )
        self.assertEqual(
            subnet_ip_key('grp', req_a), '1.2.3.0/24'
        )

    @override_settings(RATELIMIT_IP_META_KEY='HTTP_X_FORWARDED_FOR')
    def test_multi_hop_xff_buckets_by_first_entry(self):
        req = self._get(
            ip='10.0.0.1',
            HTTP_X_FORWARDED_FOR='1.2.3.4, 10.0.0.1',
        )
        self.assertEqual(
            subnet_ip_key('grp', req), '1.2.3.0/24'
        )

    @with_settings(REGISTRATION_RATE_LIMIT_ENABLED=True,
                   REGISTRATION_RATE_LIMIT_MAX_REGISTRATIONS=2)
    def test_registration_policy_with_subnet_key_shares_bucket(self):
        # Two IPs in the same /24 hitting the registration policy
        # share the bucket — mirrors test_same_policy_implies_shared_bucket
        # but exercises the subnet-width property of the policy's key.
        # POSTs are used here to mirror genuine registration attempts;
        # the registration policy itself counts every method.
        wrapped = askbot_ratelimit(policy='registration')(_dummy_view)

        self.assertEqual(
            wrapped(self._post(ip='1.2.3.4')).status_code, 200
        )
        self.assertEqual(
            wrapped(self._post(ip='1.2.3.5')).status_code, 200
        )
        # Third request from a third IP in the same /24 → 429.
        self.assertEqual(
            wrapped(self._post(ip='1.2.3.6')).status_code, 429
        )

    @with_settings(REQUEST_RATE_LIMIT_ENABLED=True,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=2)
    def test_request_policy_with_subnet_key_shares_bucket(self):
        wrapped = askbot_ratelimit(policy='request')(_dummy_view)
        self.assertEqual(
            wrapped(self._get(ip='1.2.3.4')).status_code, 200
        )
        self.assertEqual(
            wrapped(self._get(ip='1.2.3.5')).status_code, 200
        )
        self.assertEqual(
            wrapped(self._get(ip='1.2.3.6')).status_code, 429
        )

class AllowlistTests(TestCase):
    """Coverage for the ``RATE_LIMIT_IP_ALLOWLIST`` livesetting +
    ``ASKBOT_INTERNAL_IPS`` django setting union."""

    def setUp(self):
        caches['default'].clear()
        self.factory = RequestFactory()

    def tearDown(self):
        caches['default'].clear()

    def _attach_browser_state(self, request):
        request.user = AnonymousUser()
        request.session = {}
        return request

    def _get(self, ip='1.2.3.4', **headers):
        request = self.factory.get('/', REMOTE_ADDR=ip, **headers)
        return self._attach_browser_state(request)

    @with_settings(RATE_LIMIT_IP_ALLOWLIST=['1.2.3.4'],
                   REQUEST_RATE_LIMIT_ENABLED=True,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=1)
    def test_plain_ip_entry_bypasses_limit(self):
        wrapped = askbot_ratelimit(policy='request')(_dummy_view)
        for _ in range(10):
            self.assertEqual(
                wrapped(self._get(ip='1.2.3.4')).status_code, 200
            )

    @with_settings(RATE_LIMIT_IP_ALLOWLIST=['1.2.3.0/24'])
    def test_cidr_range_entry_bypasses_limit(self):
        self.assertTrue(is_allowlisted(self._get(ip='1.2.3.99')))
        self.assertFalse(is_allowlisted(self._get(ip='1.2.4.99')))

    @with_settings(RATE_LIMIT_IP_ALLOWLIST=['2001:db8::/32'])
    def test_ipv6_cidr_entry_bypasses_limit(self):
        self.assertTrue(
            is_allowlisted(self._get(ip='2001:db8::1234'))
        )
        self.assertFalse(
            is_allowlisted(self._get(ip='2001:dead::1234'))
        )

    @with_settings(RATE_LIMIT_IP_ALLOWLIST=['1.2.3.0/24', '2001:db8::/32'])
    def test_mixed_ipv4_and_ipv6_entries_coexist(self):
        self.assertTrue(is_allowlisted(self._get(ip='1.2.3.99')))
        self.assertTrue(is_allowlisted(self._get(ip='2001:db8::1')))
        self.assertFalse(is_allowlisted(self._get(ip='5.6.7.8')))

    @with_settings(RATE_LIMIT_IP_ALLOWLIST=[' 1.2.3.4 '])
    def test_whitespace_tolerance(self):
        self.assertTrue(is_allowlisted(self._get(ip='1.2.3.4')))

    @with_settings(RATE_LIMIT_IP_ALLOWLIST=['1.2.3.4'])
    def test_ipv4_mapped_ipv6_request_matches_plain_ipv4_entry(self):
        # Asymmetry guard: admin allowlists 1.2.3.4, traffic arrives as
        # ::ffff:1.2.3.4. Without the ipv4_mapped normalization in
        # is_allowlisted this would silently miss.
        self.assertTrue(
            is_allowlisted(self._get(ip='::ffff:1.2.3.4'))
        )

    @override_settings(RATELIMIT_IP_META_KEY='HTTP_X_FORWARDED_FOR')
    @with_settings(RATE_LIMIT_IP_ALLOWLIST=['1.2.3.4'])
    def test_reverse_proxy_allowlist_match(self):
        request = self._get(
            ip='10.0.0.1', HTTP_X_FORWARDED_FOR='1.2.3.4',
        )
        self.assertTrue(is_allowlisted(request))

    @override_settings(RATELIMIT_IP_META_KEY='HTTP_X_FORWARDED_FOR')
    @with_settings(RATE_LIMIT_IP_ALLOWLIST=['1.2.3.4'])
    def test_multi_hop_xff_allowlist_match(self):
        request = self._get(
            ip='10.0.0.1',
            HTTP_X_FORWARDED_FOR='1.2.3.4, 10.0.0.1',
        )
        self.assertTrue(is_allowlisted(request))

    @override_settings(ASKBOT_INTERNAL_IPS=['10.0.0.1'])
    def test_askbot_internal_ips_plain_ip_bypasses_via_unified_path(self):
        # Semantic-preservation test: ASKBOT_INTERNAL_IPS=['10.0.0.1']
        # continues to bypass via the unified allowlist.
        self.assertTrue(is_allowlisted(self._get(ip='10.0.0.1')))
        self.assertFalse(is_allowlisted(self._get(ip='10.0.0.2')))

    @override_settings(ASKBOT_INTERNAL_IPS=['10.0.0.1'])
    @with_settings(RATE_LIMIT_IP_ALLOWLIST=['5.5.5.5'])
    def test_both_tiers_active_simultaneously(self):
        self.assertTrue(is_allowlisted(self._get(ip='5.5.5.5')))
        self.assertTrue(is_allowlisted(self._get(ip='10.0.0.1')))
        self.assertFalse(is_allowlisted(self._get(ip='8.8.8.8')))

    @with_settings(RATE_LIMIT_IP_ALLOWLIST=['not-an-ip', '1.2.3.4'])
    def test_invalid_entry_logged_and_skipped(self):
        with self.assertLogs(
            'askbot.utils.ratelimit', level='WARNING',
        ) as captured:
            # Valid sibling still applies.
            self.assertTrue(is_allowlisted(self._get(ip='1.2.3.4')))
            # Unrelated IP still rejected.
            self.assertFalse(is_allowlisted(self._get(ip='8.8.8.8')))
        self.assertTrue(any(
            'not-an-ip' in line for line in captured.output
        ))

    @with_settings(RATE_LIMIT_IP_ALLOWLIST=['1.2.3.4'],
                   REQUEST_RATE_LIMIT_ENABLED=True,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=1)
    def test_allowlisted_request_never_touches_cache(self):
        with mock.patch(
            'askbot.utils.ratelimit.is_ratelimited',
        ) as spy:
            wrapped = askbot_ratelimit(policy='request')(_dummy_view)
            for _ in range(5):
                self.assertEqual(
                    wrapped(self._get(ip='1.2.3.4')).status_code, 200
                )
            self.assertEqual(spy.call_count, 0)

    @with_settings(RATE_LIMIT_IP_ALLOWLIST=['1.2.3.4'],
                   REQUEST_RATE_LIMIT_ENABLED=True,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=1)
    def test_is_askbot_ratelimited_respects_allowlist(self):
        # Burn the bucket from a non-allowlisted IP.
        self.assertIs(
            is_askbot_ratelimited(
                self._get(ip='5.6.7.8'),
                policy='request',
            ),
            False,
        )
        # Same policy from an allowlisted IP returns False even
        # under the same bucket (short-circuits before is_ratelimited).
        self.assertIs(
            is_askbot_ratelimited(
                self._get(ip='1.2.3.4'),
                policy='request',
            ),
            False,
        )

class SubnetGranularityTests(TestCase):

    def setUp(self):
        caches['default'].clear()
        self.factory = RequestFactory()

    def tearDown(self):
        caches['default'].clear()

    def _get(self, ip='1.2.3.4', **headers):
        request = self.factory.get('/', REMOTE_ADDR=ip, **headers)
        request.user = AnonymousUser()
        request.session = {}
        return request

    @with_settings(RATE_LIMIT_SUBNET_GRANULARITY='host')
    def test_host_granularity_separates_neighbors(self):
        a = subnet_ip_key('grp', self._get(ip='1.2.3.4'))
        b = subnet_ip_key('grp', self._get(ip='1.2.3.5'))
        self.assertNotEqual(a, b)
        self.assertEqual(a, '1.2.3.4/32')

    @with_settings(RATE_LIMIT_SUBNET_GRANULARITY='region')
    def test_region_granularity_groups_far_neighbors(self):
        a = subnet_ip_key('grp', self._get(ip='1.2.3.4'))
        b = subnet_ip_key('grp', self._get(ip='1.2.99.5'))
        self.assertEqual(a, b)
        self.assertEqual(a, '1.2.0.0/16')

    @with_settings(REQUEST_RATE_LIMIT_ENABLED=True,
                   REQUEST_RATE_LIMIT_MAX_REQUESTS=1)
    def test_switching_granularity_starts_fresh_bucket(self):
        # Same cache-key-invariant property as
        # test_rate_string_reflects_current_max_count above:
        # changing the prefix produces a different cache key, so the
        # old bucket is left behind and a new one starts fresh.
        wrapped = askbot_ratelimit(policy='request')(_dummy_view)
        # Default 'subnet' (/24).
        self.assertEqual(
            wrapped(self._get(ip='1.2.3.4')).status_code, 200
        )
        self.assertEqual(
            wrapped(self._get(ip='1.2.3.4')).status_code, 429
        )

        with livesettings_override(RATE_LIMIT_SUBNET_GRANULARITY='host'):
            # New cache key under /32 → fresh bucket.
            self.assertEqual(
                wrapped(self._get(ip='1.2.3.4')).status_code, 200
            )

    @with_settings(RATE_LIMIT_SUBNET_GRANULARITY='bogus')
    def test_unknown_granularity_falls_back_to_subnet(self):
        # livesettings.StringValue does NOT enforce `choices` at the
        # DB layer (only at the admin-form layer), so update(...) with
        # a bogus value is accepted and exercises the dispatch fallback.
        a = subnet_ip_key('grp', self._get(ip='1.2.3.4'))
        b = subnet_ip_key('grp', self._get(ip='1.2.3.5'))
        # Falls back to default 'subnet' (/24): neighbors share.
        self.assertEqual(a, b)
        self.assertEqual(a, '1.2.3.0/24')


class InternalIpTests(TestCase):
    """Coverage for ``is_internal_ip`` (closed-forum-mode bypass).

    Parallels ``AllowlistTests`` so the new helper has the same shape
    of coverage as its sibling, while also locking the design
    invariants that distinguish the two: no livesetting fold-in, no
    XFF header consultation.
    """

    @override_settings(ASKBOT_INTERNAL_IPS=['10.0.0.1'])
    def test_plain_ipv4_match(self):
        self.assertTrue(is_internal_ip('10.0.0.1'))

    @override_settings(ASKBOT_INTERNAL_IPS=['10.0.0.1'])
    def test_plain_ipv4_miss(self):
        self.assertFalse(is_internal_ip('10.0.0.2'))

    @override_settings(ASKBOT_INTERNAL_IPS=['10.0.0.0/8'])
    def test_cidr_ipv4_match(self):
        self.assertTrue(is_internal_ip('10.0.0.5'))

    @override_settings(ASKBOT_INTERNAL_IPS=['10.0.0.0/8'])
    def test_cidr_ipv4_boundary_miss(self):
        self.assertFalse(is_internal_ip('11.0.0.5'))

    @override_settings(ASKBOT_INTERNAL_IPS=['2001:db8::1'])
    def test_plain_ipv6_match(self):
        self.assertTrue(is_internal_ip('2001:db8::1'))

    @override_settings(ASKBOT_INTERNAL_IPS=['2001:db8::1'])
    def test_plain_ipv6_miss(self):
        self.assertFalse(is_internal_ip('2001:db8::2'))

    @override_settings(ASKBOT_INTERNAL_IPS=['2001:db8::/32'])
    def test_cidr_ipv6_match(self):
        self.assertTrue(is_internal_ip('2001:db8::1234'))

    @override_settings(ASKBOT_INTERNAL_IPS=['2001:db8::/32'])
    def test_cidr_ipv6_boundary_miss(self):
        self.assertFalse(is_internal_ip('2001:dead::1234'))

    @override_settings(ASKBOT_INTERNAL_IPS=['10.0.0.1'])
    def test_ipv4_mapped_ipv6_normalization(self):
        self.assertTrue(is_internal_ip('::ffff:10.0.0.1'))

    @override_settings(ASKBOT_INTERNAL_IPS=[' 10.0.0.1 '])
    def test_whitespace_tolerance(self):
        self.assertTrue(is_internal_ip('10.0.0.1'))

    @override_settings(ASKBOT_INTERNAL_IPS=('10.0.0.1',))
    def test_tuple_typed_setting(self):
        # intranet-setup.rst documents the value as a tuple — the
        # iteration must accept it.
        self.assertTrue(is_internal_ip('10.0.0.1'))

    @override_settings(ASKBOT_INTERNAL_IPS=['10.0.0.1'])
    def test_empty_raw_ip_returns_false(self):
        self.assertFalse(is_internal_ip(''))
        self.assertFalse(is_internal_ip(None))

    @override_settings(ASKBOT_INTERNAL_IPS=['10.0.0.1'])
    def test_malformed_raw_ip_returns_false(self):
        self.assertFalse(is_internal_ip('not-an-ip'))

    @override_settings(ASKBOT_INTERNAL_IPS=[None, '10.0.0.1'])
    def test_non_string_entry_logged_and_skipped(self):
        with self.assertLogs(
            'askbot.utils.ratelimit', level='WARNING',
        ) as captured:
            self.assertTrue(is_internal_ip('10.0.0.1'))
        self.assertTrue(any(
            'not a string' in line for line in captured.output
        ))

    @override_settings(ASKBOT_INTERNAL_IPS=['not-an-ip', '10.0.0.1'])
    def test_malformed_string_entry_logged_and_skipped(self):
        with self.assertLogs(
            'askbot.utils.ratelimit', level='WARNING',
        ) as captured:
            self.assertTrue(is_internal_ip('10.0.0.1'))
        self.assertTrue(any(
            'not-an-ip' in line for line in captured.output
        ))

    def test_setting_unset_returns_false(self):
        # No override_settings — exercises the
        # ``getattr(..., None) or []`` branch when the setting is not
        # defined in test settings.
        self.assertFalse(is_internal_ip('10.0.0.1'))

    @override_settings(ASKBOT_INTERNAL_IPS=[])
    def test_setting_empty_returns_false(self):
        self.assertFalse(is_internal_ip('10.0.0.1'))

    @override_settings(ASKBOT_INTERNAL_IPS=[])
    @with_settings(RATE_LIMIT_IP_ALLOWLIST=['5.5.5.5'])
    def test_livesetting_does_not_broaden_bypass(self):
        # Design invariant: RATE_LIMIT_IP_ALLOWLIST is for the rate
        # limiter only. It must NEVER bleed into closed-forum-mode
        # bypass.
        self.assertFalse(is_internal_ip('5.5.5.5'))
