# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import requests
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

from ..utils import get_login_user


class LoginServiceTokenAuthentication(TokenAuthentication):
    def authenticate_credentials(self, key):
        data = self._request(self.get_endpoint(key))
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
