# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib.auth.models import AnonymousUser
from django.conf import settings

try:
    from django.utils.module_loading import import_string
except ImportError:
    # Django < 1.7
    from django.utils.module_loading import import_by_path as import_string


def get_login_user(user_data):
    if user_data:
        UserClass = import_string(getattr(
            settings, 'LOGIN_SERVICE_USER_CLASS', 'login_backend.user.LoginUser'))
        user = UserClass(user_data)
        return user
    return AnonymousUser()
