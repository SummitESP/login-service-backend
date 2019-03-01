# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django import VERSION
from django.conf import settings
from django.contrib import auth
from django.contrib.auth.middleware import RemoteUserMiddleware
from django.core.exceptions import ImproperlyConfigured
from django.utils.functional import SimpleLazyObject

from .utils import get_login_user
from .user import LoginUser

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
        request.user = SimpleLazyObject(lambda: get_login_user(request.session.get('_user')))


class RemoteLoginServiceUserMiddleware(RemoteUserMiddleware):
    """
    Used in place of the above LoginServiceAuthenticationMiddleware in cases where you need to save
    A new user model if an account doesn't exist locally for that user.
    """

    force_logout_if_no_session = True

    def is_authenticated(self, request):
        """Handle user is_auth propery"""
        if VERSION >= (1, 10):
            # Django 1.10 onwards `is_authenticated` is a property
            return request.user.is_authenticated
        return request.user.is_authenticated()

    def process_request(self, request):
        # AuthenticationMiddleware is required so that request.user exists.
        if not hasattr(request, 'user'):
            raise ImproperlyConfigured(
                "The Django remote user auth middleware requires the"
                " authentication middleware to be installed.  Edit your"
                " MIDDLEWARE setting to insert"
                " 'django.contrib.auth.middleware.AuthenticationMiddleware'"
                " before the RemoteLoginServiceUserMiddleware class.")

        assert not isinstance(request.user, LoginUser), "request.user must not be a LoginUser"

        assert hasattr(request, 'session'), (
            "The authentication middleware requires session middleware "
            "to be installed. Edit your MIDDLEWARE%s setting to insert "
            "'django.contrib.sessions.middleware.SessionMiddleware' before "
            "'%s'."
        ) % ("_CLASSES" if settings.MIDDLEWARE is None else '', type(self))

        try:
            h_number = request.session['_user']['h_number']
        except KeyError:
            # If specified session doesn't exist then remove any existing
            # authenticated remote-user, or return (leaving request.user set to
            # AnonymousUser by the AuthenticationMiddleware).
            if self.force_logout_if_no_session and self.is_authenticated(request):
                self._remove_invalid_user(request)
            return
        # If the user is already authenticated and that user is the user we are
        # getting passed in the headers, then the correct user is already
        # persisted in the session and we don't need to continue.

        if self.is_authenticated(request):
            if request.user.get_username() == self.clean_username(h_number, request):
                return
            else:
                # An authenticated user is associated with the request, but
                # it does not match the authorized user in the login service session.
                self._remove_invalid_user(request)

        # We are seeing this user for the first time in this session, attempt
        # to authenticate the user.
        user = auth.authenticate(request=request, h_number=h_number)
        if user:
            # User is valid.  Set request.user and persist user in the session
            # by logging the user in.
            request.user = user
            # FIX: This is cycling session keys
            auth.login(request, user)
