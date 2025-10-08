# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.utils.functional import SimpleLazyObject

import logging
logger = logging.getLogger("login_backend")

from .utils import get_login_user

try:
    from django.utils.deprecation import MiddlewareMixin
except ImportError:
    MiddlewareMixin = object


class LoginServiceAuthenticationMiddleware(MiddlewareMixin):
    def process_request(self, request):
        logging.debug(f"Processing login service authentication, request: {request}")
        assert hasattr(request, 'session'), (
            "The authentication middleware requires session middleware "
            "to be installed. Edit your MIDDLEWARE%s setting to insert "
            "'django.contrib.sessions.middleware.SessionMiddleware' before "
            "'%s'."
        ) % ("_CLASSES" if settings.MIDDLEWARE is None else '', type(self))
        logging.debug(f"Getting _user from request.session: {request.session}")
        user = request.session.get('_user')
        request.user = SimpleLazyObject(lambda: get_login_user(user))
