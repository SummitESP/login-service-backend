# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import hashlib
from http import cookies as http_cookies
from importlib import import_module

from django.conf import settings
from django.core.cache import cache
from django.utils.functional import SimpleLazyObject

import logging
logger = logging.getLogger("login_backend")

from .utils import (
    CACHE_KEY_PREFIX_DUPLICATE_SESSION,
    MAX_DUPLICATE_SESSION_COOKIE_CANDIDATES,
    get_duplicate_session_cache_timeout,
    get_login_user,
)

try:
    from django.utils.deprecation import MiddlewareMixin
except ImportError:
    MiddlewareMixin = object


class LoginServiceAuthenticationMiddleware(MiddlewareMixin):
    def process_request(self, request):
        logger.debug("Processing login service authentication")
        assert hasattr(request, 'session'), (
            "The authentication middleware requires session middleware "
            "to be installed. Edit your MIDDLEWARE%s setting to insert "
            "'django.contrib.sessions.middleware.SessionMiddleware' before "
            "'%s'."
        ) % ("_CLASSES" if settings.MIDDLEWARE is None else '', type(self))
        user = request.session.get('_user')
        request.user = SimpleLazyObject(lambda: get_login_user(user))


def get_cookie_values(cookie_header, name):
    """Return every value of cookie ``name`` in header order.

    Parses the header the same way as ``django.http.cookie.parse_cookie`` so the values
    compare equal to ``request.COOKIES``, which keeps only the last value.
    """
    values = []
    for chunk in cookie_header.split(';'):
        if '=' in chunk:
            key, value = chunk.split('=', 1)
        else:
            key, value = '', chunk
        if key.strip() == name:
            values.append(http_cookies._unquote(value.strip()))
    return values


class DuplicateSessionCookieMiddleware(MiddlewareMixin):
    """Choose the session cookie that has a session when the browser sends several.

    Browsers send every cookie whose domain matches, so a host such as
    ``app.test.example.com`` can receive ``sessionid`` set for both ``.example.com`` and
    ``.test.example.com``. Django keeps the last one, which may belong to another
    environment. This middleware selects the first value whose session exists in the
    configured session engine. It must run before ``SessionMiddleware``.
    """

    def process_request(self, request):
        name = settings.SESSION_COOKIE_NAME
        header = request.META.get('HTTP_COOKIE', '')
        if name not in header:
            return

        values = get_cookie_values(header, name)
        candidates = list(dict.fromkeys(value for value in values if value))
        if len(candidates) < 2:
            return

        store = import_module(settings.SESSION_ENGINE).SessionStore()
        checked = candidates[:MAX_DUPLICATE_SESSION_COOKIE_CANDIDATES]
        for session_key in checked:
            if self.session_exists(store, session_key):
                logger.warning(
                    "Request sent %d %s cookies; using the one at index %d",
                    len(values), name, values.index(session_key),
                )
                request.COOKIES[name] = session_key
                return

        logger.warning(
            "Request sent %d %s cookies; none of the %d checked has a session, "
            "keeping the last one",
            len(values), name, len(checked),
        )

    def session_exists(self, store, session_key):
        timeout = get_duplicate_session_cache_timeout()
        cache_key = self.get_cache_key(session_key)
        if timeout:
            exists = cache.get(cache_key)
            if exists is not None:
                return exists

        try:
            exists = bool(store.exists(session_key))
        except Exception as error:  # noqa: BLE001 - any engine failure means "not usable"
            # The exception text may contain the session key (e.g. in a request URL).
            logger.warning(
                "Checking a duplicate %s cookie failed: %s",
                settings.SESSION_COOKIE_NAME, type(error).__name__,
            )
            return False

        if timeout:
            cache.set(cache_key, exists, timeout)
        return exists

    def get_cache_key(self, session_key):
        digest = hashlib.sha256(f'{settings.SESSION_ENGINE}:{session_key}'.encode()).hexdigest()
        return f'{CACHE_KEY_PREFIX_DUPLICATE_SESSION}:{digest}'
