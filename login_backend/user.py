# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib.auth.models import Group


class LoginUser(object):
    is_authenticated = True
    is_anonymous = False
    is_active = True

    def __init__(self, user_data):
        self.groups = Group.objects.filter(name__in=user_data.pop('groups', []))
        for key, value in user_data.items():
            setattr(self, key, value)

    def get_group_permissions(self, obj=None):
        if not hasattr(self, '_group_permissions'):
            self._group_permissions = set(
                '{}.{}'.format(app, codename)
                for group in self.groups
                for app, codename in group.permissions.values_list(
                    'content_type__app_label', 'codename')
            )
        return self._group_permissions

    def get_all_permissions(self, obj=None):
        return self.get_group_permissions(obj)

    def has_perm(self, perm, obj=None):
        if self.is_active and self.is_superuser:
            return True
        return perm in self.get_all_permissions()

    def has_perms(self, perm_list, obj=None):
        return all(self.has_perm(perm, obj) for perm in perm_list)

    def has_module_perms(self, app_label):
        if self.is_active and self.is_superuser:
            return True
        for perm in self.get_all_permissions():
            if perm[:perm.index('.')] == app_label:
                return True
        return False
