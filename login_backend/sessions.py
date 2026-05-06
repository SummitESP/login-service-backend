# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import requests
from django.conf import settings
from django.core.cache import cache
from django.contrib.sessions.backends.base import CreateError, SessionBase
from .utils import CACHE_KEY_PREFIX_SESSION, DEFAULT_CACHE_TIMEOUT

import logging
logger = logging.getLogger("login_backend")

try:
    from django.contrib.sessions.backends.base import UpdateError
except ImportError:
    class UpdateError(Exception):
        pass


class SessionStore(SessionBase):
    def load(self):
        if self.session_key:
            cache_key = self.get_cache_key(self.session_key)
            session_data = cache.get(cache_key)
            if session_data is not None:
                return session_data

        session_data = self._request(requests.get, self.get_endpoint(self.session_key))
        if session_data is not None:
            if self.session_key:
                timeout = getattr(settings, 'LOGIN_SERVICE_CACHE_TIMEOUT', DEFAULT_CACHE_TIMEOUT)
                cache.set(self.get_cache_key(self.session_key), session_data, timeout)
            return session_data
        self._session_key = None
        return {}

    def create(self):
        self.save(create=True)

    def save(self, create=False):
        if create or self.session_key is None:
            method = requests.post
            endpoint = self.get_endpoint()
            error = CreateError
        else:
            method = requests.patch
            endpoint = self.get_endpoint(self.session_key)
            error = UpdateError
        session_data = self._request(method, endpoint, data=self._get_session(no_load=True))
        if session_data is None:
            logger.error("Session data is empty.")
            raise error

        self._session_key = session_data['_session_key']
        self._session_cache.update(session_data)

        timeout = getattr(settings, 'LOGIN_SERVICE_CACHE_TIMEOUT', DEFAULT_CACHE_TIMEOUT)
        cache.set(self.get_cache_key(self._session_key), session_data, timeout)

    def exists(self, session_key):
        cache_key = self.get_cache_key(session_key)
        if cache.get(cache_key) is not None:
            return True

        session_data = self._request(requests.get, self.get_endpoint(session_key))
        if session_data:
            timeout = getattr(settings, 'LOGIN_SERVICE_CACHE_TIMEOUT', DEFAULT_CACHE_TIMEOUT)
            cache.set(cache_key, session_data, timeout)
            return True
        return False

    def delete(self, session_key=None):
        if session_key is None:
            if self.session_key is None:
                return
            session_key = self.session_key
        self._request(requests.delete, self.get_endpoint(session_key))

        cache.delete(self.get_cache_key(session_key))

    @classmethod
    def clear_expired(cls):
        pass

    def get_cache_key(self, session_key):
        return '{}:{}'.format(CACHE_KEY_PREFIX_SESSION, session_key)

    def get_endpoint(self, session_key=None):
        if session_key:
            return '{}{}/'.format(
                settings.LOGIN_SERVICE_SESSION_ENDPOINT,
                session_key,
            )
        else:
            return settings.LOGIN_SERVICE_SESSION_ENDPOINT

    def get_headers(self, headers):
        if not headers or not isinstance(headers, dict):
            headers = dict()
        token = getattr(settings, 'LOGIN_SERVICE_TOKEN', None)
        if token:
            headers['Authorization'] = 'Token {}'.format(token)
        return headers

    def _request(self, method, url, data=None, headers=None):
        logger.debug("Requesting session data")
        headers = self.get_headers(headers)
        resp = method(url, data=data, headers=headers)
        session_data = None
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            err_message = str(e)
            logger.error(f"HTTP error occurred: {err_message}")
        else:
            if resp.content:
                session_data = resp.json()
        return session_data
