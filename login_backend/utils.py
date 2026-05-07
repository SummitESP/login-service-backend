# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib.auth.models import AnonymousUser
from django.conf import settings

import logging
logger = logging.getLogger("login_backend")

try:
    from django.utils.module_loading import import_string
except ImportError:
    # Django < 1.7
    from django.utils.module_loading import import_by_path as import_string

# Cache configuration
CACHE_KEY_PREFIX_SESSION = 'login_service_session'
# `0` is the secure default. Effectively disables caching. THIS VALUE CAN NEVER BE None.
# If the value is None then the cache doesn't expire and this whole session backend plugin breaks.
DEFAULT_CACHE_TIMEOUT = 0
# Max timeout is ten seconds. 10 seconds is enough to cut out almost all chatter to the
# login-service while maintain only a 10 seconds lag if permissions change for a user on the
# identity provider or login-service itself.
MAX_CACHE_TIMEOUT = 10


class InvalidSessionCacheTimeoutException(Exception):
    """Raised with the cache timeout value is None"""
    pass


def get_login_service_cache_timeout():
    timeout = getattr(settings, 'LOGIN_SERVICE_CACHE_TIMEOUT', DEFAULT_CACHE_TIMEOUT)
    if timeout is None or timeout > MAX_CACHE_TIMEOUT:
        raise InvalidSessionCacheTimeoutException(
            f"Cache timeout cannot be greater than {MAX_CACHE_TIMEOUT} or None"
        )
    return timeout


def get_login_user(user_data):
    logger.debug(f"Getting login user: {user_data}")
    if user_data:
        UserClass = import_string(getattr(
            settings, 'LOGIN_SERVICE_USER_CLASS', 'login_backend.user.LoginUser'))
        user = UserClass(user_data)
        logger.debug(f"Created user: {user}")
        return user
    logger.debug("No user data found, returning AnonymousUser.")
    return AnonymousUser()
