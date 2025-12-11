# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import requests
from django.conf import settings
from django.core.cache import cache

from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

from ..utils import get_login_user, CACHE_KEY_PREFIX_TOKEN, DEFAULT_CACHE_TIMEOUT

try:
    # ugettext_lazy was deprecated in Django 2.2
    from django.utils.translation import ugettext_lazy as _
except ImportError:
    from django.utils.translation import gettext_lazy as _


class LoginServiceTokenAuthentication(TokenAuthentication):
    def authenticate_credentials(self, key):
        cache_key = self.get_cache_key(key)
        data = cache.get(cache_key)

        if data is None:
            data = self._request(self.get_endpoint(key))
            if data:
                timeout = getattr(settings, 'LOGIN_SERVICE_CACHE_TIMEOUT', DEFAULT_CACHE_TIMEOUT)
                cache.set(cache_key, data, timeout)

        if not data:
            raise AuthenticationFailed(_('Invalid token.'))

        user = get_login_user(data.get('user'))

        if not user.is_active:
            raise AuthenticationFailed(_('User inactive or deleted.'))

        return (user, data)

    def get_endpoint(self, key):
        return '{}{}/'.format(
            settings.LOGIN_SERVICE_TOKEN_ENDPOINT,
            key,
        )

    def get_cache_key(self, key):
        return '{}:{}'.format(CACHE_KEY_PREFIX_TOKEN, key)

    def get_headers(self, headers):
        if not headers or not isinstance(headers, dict):
            headers = dict()
        token = getattr(settings, 'LOGIN_SERVICE_TOKEN', None)
        if token:
            headers['Authorization'] = 'Token {}'.format(token)
        return headers

    def _request(self, url, data=None, headers=None):
        headers = self.get_headers(headers)
        resp = requests.get(url, data=data, headers=headers)
        try:
            resp.raise_for_status()
        except requests.HTTPError:
            session_data = None
        else:
            session_data = resp.json()
        return session_data
