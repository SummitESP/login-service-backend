# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import requests
from django.conf import settings
from django.contrib.sessions.backends.base import CreateError, SessionBase

try:
    from django.contrib.sessions.backends.base import UpdateError
except ImportError:
    class UpdateError(Exception):
        pass


class SessionStore(SessionBase):
    def load(self):
        session_data = self._request(requests.get, self.get_endpoint(self.session_key))
        if session_data is not None:
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
            raise error

        self._session_key = session_data['_session_key']
        self._session_cache.update(session_data)

    def exists(self, session_key):
        if self._request(requests.get, self.get_endpoint(session_key)):
            return True
        return False

    def delete(self, session_key=None):
        if session_key is None:
            if self.session_key is None:
                return
            session_key = self.session_key
        self._request(requests.delete, self.get_endpoint(session_key))

    @classmethod
    def clear_expired(cls):
        pass

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
        headers = self.get_headers(headers)
        resp = method(url, data=data, headers=headers)
        try:
            resp.raise_for_status()
        except requests.HTTPError:
            session_data = None
        else:
            session_data = resp.json()
        return session_data
