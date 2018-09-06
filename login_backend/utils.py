# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib.auth.models import AnonymousUser
from django.utils.module_loading import import_string
from django.conf import settings


def get_login_user(user_data):
    if user_data:
        user = import_string(settings.LOGIN_SERVICE_USER_CLASS)(user_data)
        return user
    return AnonymousUser()
