"""Smoke tests against installed artifacts; all remote login calls are mocked."""

import unittest
from importlib.metadata import metadata, version
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import django
from django.conf import settings
from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, override_settings

settings.configure(
    SECRET_KEY="packaging-tests-only",
    INSTALLED_APPS=["django.contrib.auth", "django.contrib.contenttypes"],
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    LOGIN_SERVICE_SESSION_ENDPOINT="https://login.example.test/session/",
    LOGIN_SERVICE_TOKEN_ENDPOINT="https://login.example.test/token/",
    LOGIN_SERVICE_TOKEN="application-token",
    MIDDLEWARE=[],
)
django.setup()

from rest_framework.exceptions import AuthenticationFailed

import login_backend
from login_backend.middleware import (
    DuplicateSessionCookieMiddleware,
    LoginServiceAuthenticationMiddleware,
)
from login_backend.rest_framework.authentication import (
    LoginServiceTokenAuthentication,
)
from login_backend.sessions import SessionStore
from login_backend.utils import InvalidSessionCacheTimeoutException


class InstalledBackendTests(unittest.TestCase):
    def setUp(self):
        cache.clear()

    def test_package_metadata_and_install_location(self):
        self.assertEqual(version("login-service-backend"), login_backend.__version__)
        self.assertIn("site-packages", Path(login_backend.__file__).parts)
        package = metadata("login-service-backend")
        self.assertEqual(package["Requires-Python"], ">=3.10")
        self.assertEqual(package["Description-Content-Type"], "text/markdown")
        self.assertIn("drf", package.get_all("Provides-Extra"))

    @patch("login_backend.sessions.requests.get")
    def test_remote_session_load(self, get):
        get.return_value = Mock(content=b"json", json=lambda: {"example": "value"})
        session = SessionStore("valid-session-key")
        self.assertEqual(session.load(), {"example": "value"})
        get.assert_called_once_with(
            "https://login.example.test/session/valid-session-key/",
            data=None,
            headers={"Authorization": "Token application-token"},
        )

    @patch("login_backend.sessions.requests.get")
    def test_rejected_session_is_cleared(self, get):
        import requests

        get.return_value.raise_for_status.side_effect = requests.HTTPError("expired")
        session = SessionStore("valid-session-key")
        self.assertEqual(session.load(), {})
        self.assertIsNone(session.session_key)

    @patch("login_backend.sessions.requests.get")
    def test_session_cache_disabled_by_default(self, get):
        get.return_value = Mock(content=b"json", json=lambda: {"example": "value"})
        SessionStore("valid-session-key").load()
        SessionStore("valid-session-key").load()
        self.assertEqual(get.call_count, 2)

    @override_settings(LOGIN_SERVICE_CACHE_TIMEOUT=10)
    @patch("login_backend.sessions.requests.delete")
    @patch("login_backend.sessions.requests.get")
    def test_opt_in_cache_invalidated_on_delete(self, get, delete):
        get.return_value = Mock(content=b"json", json=lambda: {"example": "value"})
        delete.return_value = Mock(content=b"")
        SessionStore("valid-session-key").load()
        self.assertEqual(SessionStore("valid-session-key").load(), {"example": "value"})
        self.assertEqual(get.call_count, 1)
        SessionStore("valid-session-key").delete()
        SessionStore("valid-session-key").load()
        self.assertEqual(get.call_count, 2)

    def test_anonymous_middleware_request(self):
        request = SimpleNamespace(session={})
        middleware = LoginServiceAuthenticationMiddleware(lambda request: request)
        self.assertTrue(middleware(request).user.is_anonymous)

    @patch("login_backend.rest_framework.authentication.get_login_user")
    @patch("login_backend.rest_framework.authentication.requests.get")
    def test_token_authentication(self, get, get_user):
        data = {"user": {"username": "tester"}}
        get.return_value.json.return_value = data
        get_user.return_value = SimpleNamespace(is_active=True)
        user, token = LoginServiceTokenAuthentication().authenticate_credentials("test-token")
        self.assertIs(user, get_user.return_value)
        self.assertEqual(token, data)
        get.assert_called_once_with(
            "https://login.example.test/token/test-token/",
            data=None,
            headers={"Authorization": "Token application-token"},
        )

    @patch.object(LoginServiceTokenAuthentication, "_request", return_value=None)
    def test_invalid_token_rejected(self, request):
        with self.assertRaises(AuthenticationFailed):
            LoginServiceTokenAuthentication().authenticate_credentials("invalid")

    @patch("login_backend.rest_framework.authentication.get_login_user")
    @patch.object(LoginServiceTokenAuthentication, "_request", return_value={"user": {}})
    def test_inactive_user_rejected(self, request, get_user):
        get_user.return_value = SimpleNamespace(is_active=False)
        with self.assertRaises(AuthenticationFailed):
            LoginServiceTokenAuthentication().authenticate_credentials("inactive")


VALID_KEY = "validtestsessionkey"
STALE_KEY = "staleprodsessionkey"
SESSION_ENDPOINT = "https://login.example.test/session/"


def login_service_get(url, data=None, headers=None):
    """Fake login-service session API that only knows VALID_KEY."""
    import requests

    response = Mock(content=b"json", json=lambda: {"_user": {"username": "tester"}})
    if url != f"{SESSION_ENDPOINT}{VALID_KEY}/":
        response.status_code = 404
        response.raise_for_status.side_effect = requests.HTTPError(f"404 for url: {url}")
    return response


@override_settings(SESSION_ENGINE="login_backend.sessions")
@patch("login_backend.sessions.requests.get", side_effect=login_service_get)
class DuplicateSessionCookieTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def process(self, cookie_header):
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.http import HttpResponse

        request = RequestFactory().get("/", HTTP_COOKIE=cookie_header)
        django_choice = request.COOKIES.get("sessionid")

        def view(request):
            request.django_choice = django_choice
            request.selected = request.session.session_key
            request.loaded = request.session.get("_user")
            return HttpResponse()

        chain = DuplicateSessionCookieMiddleware(SessionMiddleware(view))
        chain(request)
        return request

    def test_valid_cookie_first(self, get):
        request = self.process(f"sessionid={VALID_KEY}; csrftoken=x; sessionid={STALE_KEY}")
        self.assertEqual(request.django_choice, STALE_KEY)
        self.assertEqual(request.selected, VALID_KEY)
        self.assertEqual(request.loaded, {"username": "tester"})

    def test_valid_cookie_last(self, get):
        request = self.process(f"sessionid={STALE_KEY}; sessionid={VALID_KEY}")
        self.assertEqual(request.selected, VALID_KEY)
        self.assertEqual(request.loaded, {"username": "tester"})
        checked = [call.args[0] for call in get.call_args_list]
        self.assertEqual(
            checked[:2], [f"{SESSION_ENDPOINT}{STALE_KEY}/", f"{SESSION_ENDPOINT}{VALID_KEY}/"]
        )

    def test_no_valid_cookie_keeps_django_choice(self, get):
        request = RequestFactory().get("/", HTTP_COOKIE="sessionid=unknownkey1; sessionid=unknownkey2")
        DuplicateSessionCookieMiddleware(lambda request: request)(request)
        self.assertEqual(request.COOKIES["sessionid"], "unknownkey2")
        self.assertEqual(get.call_count, 2)

    def test_single_cookie_makes_no_lookup(self, get):
        for header in (f"sessionid={STALE_KEY}", f"sessionid={STALE_KEY}; sessionid={STALE_KEY}",
                       "csrftoken=x", ""):
            request = RequestFactory().get("/", HTTP_COOKIE=header)
            before = dict(request.COOKIES)
            DuplicateSessionCookieMiddleware(lambda request: request)(request)
            self.assertEqual(request.COOKIES, before)
        get.assert_not_called()

    def test_similar_cookie_names_are_not_duplicates(self, get):
        request = RequestFactory().get("/", HTTP_COOKIE=f"xsessionid=a; sessionid={STALE_KEY}")
        DuplicateSessionCookieMiddleware(lambda request: request)(request)
        self.assertEqual(request.COOKIES["sessionid"], STALE_KEY)
        get.assert_not_called()

    def test_results_are_cached(self, get):
        header = f"sessionid={STALE_KEY}; sessionid={VALID_KEY}"
        for _ in range(3):
            request = RequestFactory().get("/", HTTP_COOKIE=header)
            DuplicateSessionCookieMiddleware(lambda request: request)(request)
            self.assertEqual(request.COOKIES["sessionid"], VALID_KEY)
        self.assertEqual(get.call_count, 2)
        self.assertFalse(any(STALE_KEY in str(key) for key in cache._cache))

    @override_settings(LOGIN_SERVICE_DUPLICATE_SESSION_CACHE_TIMEOUT=0)
    def test_cache_can_be_disabled(self, get):
        header = f"sessionid={STALE_KEY}; sessionid={VALID_KEY}"
        for _ in range(2):
            request = RequestFactory().get("/", HTTP_COOKIE=header)
            DuplicateSessionCookieMiddleware(lambda request: request)(request)
        self.assertEqual(get.call_count, 4)

    @override_settings(LOGIN_SERVICE_DUPLICATE_SESSION_CACHE_TIMEOUT=None)
    def test_unbounded_cache_rejected(self, get):
        request = RequestFactory().get("/", HTTP_COOKIE="sessionid=unknownkey1; sessionid=k2key2k2")
        with self.assertRaises(InvalidSessionCacheTimeoutException):
            DuplicateSessionCookieMiddleware(lambda request: request)(request)

    def test_candidates_are_capped(self, get):
        header = "; ".join(f"sessionid=unknownkey{index}" for index in range(5))
        request = RequestFactory().get("/", HTTP_COOKIE=f"{header}; sessionid={VALID_KEY}")
        DuplicateSessionCookieMiddleware(lambda request: request)(request)
        self.assertEqual(get.call_count, 3)
        self.assertEqual(request.COOKIES["sessionid"], VALID_KEY)

    def test_logs_never_include_cookie_values(self, get):
        with self.assertLogs("login_backend", level="DEBUG") as logs:
            self.process(f"sessionid={STALE_KEY}; sessionid={VALID_KEY}")
        output = "\n".join(logs.output)
        self.assertIn("2 sessionid cookies; using the one at index 1", output)
        self.assertNotIn(STALE_KEY, output)
        self.assertNotIn(VALID_KEY, output)

    def test_lookup_error_is_treated_as_missing(self, get):
        import requests

        get.side_effect = requests.ConnectionError(f"failed url: {STALE_KEY}")
        request = RequestFactory().get("/", HTTP_COOKIE=f"sessionid={STALE_KEY}; sessionid=other-key")
        with self.assertLogs("login_backend", level="WARNING") as logs:
            DuplicateSessionCookieMiddleware(lambda request: request)(request)
        self.assertEqual(request.COOKIES["sessionid"], "other-key")
        self.assertNotIn(STALE_KEY, "\n".join(logs.output))
        self.assertIn("ConnectionError", "\n".join(logs.output))

    @override_settings(SESSION_ENGINE="django.contrib.sessions.backends.cache")
    def test_other_session_engines(self, get):
        from django.contrib.sessions.backends.cache import SessionStore as CacheSessionStore

        session = CacheSessionStore()
        session["_user"] = {"username": "cached"}
        session.create()
        request = self.process(f"sessionid={session.session_key}; sessionid={STALE_KEY}")
        self.assertEqual(request.selected, session.session_key)
        self.assertEqual(request.loaded, {"username": "cached"})
        get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
