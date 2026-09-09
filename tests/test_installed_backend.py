"""Smoke tests against installed artifacts; all remote login calls are mocked."""

import unittest
from importlib.metadata import metadata, version
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import django
from django.conf import settings
from django.core.cache import cache
from django.test import override_settings

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
from login_backend.middleware import LoginServiceAuthenticationMiddleware
from login_backend.rest_framework.authentication import (
    LoginServiceTokenAuthentication,
)
from login_backend.sessions import SessionStore


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


if __name__ == "__main__":
    unittest.main()
