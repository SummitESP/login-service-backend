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
CACHE_KEY_PREFIX_TOKEN = 'login_service_token'
DEFAULT_CACHE_TIMEOUT = 300


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
