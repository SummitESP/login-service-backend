# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django
from typing import List, Optional
from django.conf import settings
from django.contrib.auth.models import User, Group
from django.utils import timezone

import logging
logger = logging.getLogger("login_backend")

# How often (in seconds) a synced user's last_login is refreshed. Syncing user
# classes run on every request, and an unconditional last_login write forced a
# user-row UPDATE (and row lock) per request. Set to 0 to update on every
# request.
DEFAULT_LAST_LOGIN_INTERVAL = 300


def _resolve_groups(group_names) -> "List[Group]":
    """
    Return Group objects for the given names using a single query.

    Missing groups are created individually, but only when they don't already
    exist; the previous per-name ``get_or_create`` loop issued one query per
    group on every request (the N+1 flagged by Sentry).
    """
    group_names = list(group_names)
    if not group_names:
        return []
    groups = {group.name: group for group in Group.objects.filter(name__in=group_names)}
    for name in group_names:
        if name not in groups:
            groups[name] = Group.objects.get_or_create(name=name)[0]
    return [groups[name] for name in group_names]


def _sync_local_user(lookup: dict, defaults: dict, groups: "List[Group]") -> User:
    """
    Create or update the local ``auth.User`` while avoiding writes when
    nothing changed.

    ``update_or_create`` runs SELECT FOR UPDATE plus an UPDATE inside a
    transaction on every request, which locks the user row and produces
    constant write traffic. Instead, read the user, save only changed fields,
    and refresh ``last_login`` at most every LOGIN_SERVICE_LAST_LOGIN_INTERVAL
    seconds.
    """
    try:
        local_user = User.objects.get(**lookup)
    except User.DoesNotExist:
        # Rare path; update_or_create keeps creation race-safe.
        local_user, _ = User.objects.update_or_create(
            defaults=dict(defaults, last_login=timezone.now()), **lookup
        )
        local_user.groups.set(groups)
        return local_user

    changed_fields = [
        field for field, value in defaults.items() if getattr(local_user, field) != value
    ]
    for field in changed_fields:
        setattr(local_user, field, defaults[field])

    last_login_interval = getattr(
        settings, "LOGIN_SERVICE_LAST_LOGIN_INTERVAL", DEFAULT_LAST_LOGIN_INTERVAL
    )
    now = timezone.now()
    if (
        local_user.last_login is None
        or (now - local_user.last_login).total_seconds() >= last_login_interval
    ):
        local_user.last_login = now
        changed_fields.append("last_login")

    if changed_fields:
        local_user.save(update_fields=changed_fields)

    # ``groups.set`` reads the existing m2m rows and only writes the
    # difference, so it is a single SELECT when the groups are unchanged.
    local_user.groups.set(groups)
    return local_user


class LoginUser(object):
    def __init__(self, user_data):
        self.groups = Group.objects.filter(name__in=user_data.pop('groups', []))
        for key, value in user_data.items():
            setattr(self, key, value)

    def get_group_permissions(self, obj=None):
        logger.debug(f"Getting group permissions: {obj}")
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

    _cached_django_user = None

    def __init__(self, user_data):
        """
        Creates/updates a corresponding local auth.User object during __init__
        """

        # Missing Groups needs to exist before calling super.__init__
        groups = _resolve_groups(user_data.get("groups", []))

        super(SyncingLoginUser, self).__init__(user_data)
        local_user = _sync_local_user(
            lookup={"username": self.username},
            defaults={
                "email": self.email,
                "first_name": self.first_name,
                "last_name": self.last_name,
                "is_staff": self.is_staff,
                "is_active": self.is_active,
                "is_superuser": self.is_superuser,
            },
            groups=groups,
        )

        # cache the local user
        self._cached_django_user = local_user

    def _load_django_user(self) -> None:
        """Load the synced Django user into cache."""
        if self._cached_django_user is None and self.username:
            try:
                self._cached_django_user = User.objects.get(username=self.username)
            except User.DoesNotExist:
                logger.error(f"Django User not found for username: {self.username}")
                self._cached_django_user = None
                raise

    @property
    def django_user(self) -> Optional[User]:
        """Return the synced Django auth.User if available."""
        if self._cached_django_user is None:
            self._load_django_user()
        return self._cached_django_user

    @property
    def id(self) -> Optional[int]:
        """
        Return ONLY the ID of the synced Django user for admin compatibility.
        Never returns the login service user ID.
        """
        django_user = self.django_user
        if django_user:
            return django_user.id
        return None

    @id.setter
    def id(self, value: int) -> None:
        """Prevent setting id - it's read-only from synced Django User."""
        pass

    @property
    def pk(self) -> Optional[int]:
        """
        Alias for id to ensure Django admin compatibility.
        Never returns the login service user ID.
        """
        return self.id

    @pk.setter
    def pk(self, value: int) -> None:
        """Prevent setting pk - it's read-only from synced Django User."""
        pass


class SyncingLoginUserWithId(LoginUser):
    def __init__(self, user_data):
        """
        Creates/updates a corresponding local auth.User object during __init__
        This class sets the id explicitly based on the id from login service.
        """
        # Missing Groups needs to exist before calling super.__init__
        groups = _resolve_groups(user_data.get("groups", []))

        super(SyncingLoginUserWithId, self).__init__(user_data)
        _sync_local_user(
            lookup={"id": self.pk},
            defaults={
                "username": self.username,
                "email": self.email,
                "first_name": self.first_name,
                "last_name": self.last_name,
                "is_staff": self.is_staff,
                "is_active": self.is_active,
                "is_superuser": self.is_superuser,
            },
            groups=groups,
        )
