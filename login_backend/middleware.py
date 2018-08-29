# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.utils.functional import SimpleLazyObject
from django.utils.module_loading import import_string

try:
    from django.utils.deprecation import MiddlewareMixin
except ImportError:
    MiddlewareMixin = object


class LoginServiceAuthenticationMiddleware(MiddlewareMixin):
    def process_request(self, request):
        assert hasattr(request, 'session'), (
            "The authentication middleware requires session middleware "
            "to be installed. Edit your MIDDLEWARE%s setting to insert "
            "'django.contrib.sessions.middleware.SessionMiddleware' before "
            "'%s'."
        ) % ("_CLASSES" if settings.MIDDLEWARE is None else '', type(self))
        request.user = SimpleLazyObject(lambda: self.get_user(request))

    def get_user(self, request):
        user_data = request.session.get('_user')
        if user_data:
            user = import_string(settings.LOGIN_SERVICE_USER_CLASS)(user_data)
            return user
        from django.contrib.auth.models import AnonymousUser
        return AnonymousUser()
