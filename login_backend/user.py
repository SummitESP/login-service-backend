# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django
from django.utils import timezone
from django.contrib.auth.models import User, Group


class LoginUser(object):
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

    @property
    def is_authenticated(self):
        if django.VERSION < (1, 10):
            return lambda: True
        return True

    @property
    def is_anonymous(self):
        if django.VERSION < (1, 10):
            return lambda: False
        return False

    def get_username(self):
        return getattr(self, 'username', '')

    def get_full_name(self):
        """
        Return the first_name plus the last_name, with a space in between.
        """
        full_name = '%s %s' % (getattr(self, 'first_name', ''), getattr(self, 'last_name', ''))
        return full_name.strip()

    def get_short_name(self):
        """Return the short name for the user."""
        return getattr(self, 'first_name', '')


class SyncingLoginUser(LoginUser):
    def __init__(self, user_data):
        """
        Creates/updates a corresponding local auth.User object during __init__
        """
        # Missing Groups needs to exist before calling super.__init__
        for group_name in user_data.get('groups', []):
            Group.objects.get_or_create(name=group_name)

        super(SyncingLoginUser, self).__init__(user_data)
        local_user, _ = User.objects.update_or_create(
            username=self.username,
            defaults={
                "email": self.email,
                "first_name": self.first_name,
                "last_name": self.last_name,
                "is_staff": self.is_staff,
                "is_active": self.is_active,
                "is_superuser": self.is_superuser,
                "last_login": timezone.now()
            })

        # Sync the pk, so the request.user is using the correct PK.
        self.pk = local_user.pk