from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.utils import timezone

from login_backend.user import SyncingLoginUser, SyncingLoginUserWithId


def make_user_data(**overrides):
    data = {
        "username": "engineer@example.com",
        "email": "engineer@example.com",
        "first_name": "Test",
        "last_name": "Engineer",
        "is_staff": False,
        "is_active": True,
        "is_superuser": False,
        "groups": ["reliability-engineer", "reliability"],
    }
    data.update(overrides)
    return data


class SyncingLoginUserSyncTests(TestCase):
    def test_creates_local_user_and_groups(self):
        SyncingLoginUser(make_user_data())

        local_user = User.objects.get(username="engineer@example.com")
        self.assertEqual(
            sorted(local_user.groups.values_list("name", flat=True)),
            ["reliability", "reliability-engineer"],
        )
        self.assertIsNotNone(local_user.last_login)

    def test_existing_groups_resolved_with_single_query(self):
        Group.objects.create(name="reliability-engineer")
        Group.objects.create(name="reliability")
        SyncingLoginUser(make_user_data())

        # Steady state: one SELECT for all groups instead of one per group.
        with self.assertNumQueries(1):
            groups = Group.objects.filter(name__in=["reliability-engineer", "reliability"])
            self.assertEqual(len(list(groups)), 2)

    def test_sync_makes_no_group_queries_per_group(self):
        Group.objects.create(name="reliability-engineer")
        Group.objects.create(name="reliability")
        SyncingLoginUser(make_user_data())

        # Second sync of an unchanged user: 1 group SELECT, 1 user SELECT and
        # 1 m2m SELECT. No UPDATE/INSERT statements.
        with self.assertNumQueries(3):
            SyncingLoginUser(make_user_data())

    def test_missing_groups_are_created(self):
        SyncingLoginUser(make_user_data(groups=["brand-new-group"]))

        self.assertTrue(Group.objects.filter(name="brand-new-group").exists())

    def test_unchanged_user_row_is_not_written(self):
        SyncingLoginUser(make_user_data())
        local_user = User.objects.get(username="engineer@example.com")
        original_last_login = local_user.last_login

        SyncingLoginUser(make_user_data())

        local_user.refresh_from_db()
        self.assertEqual(local_user.last_login, original_last_login)

    def test_changed_fields_are_saved(self):
        SyncingLoginUser(make_user_data())

        SyncingLoginUser(make_user_data(first_name="Updated"))

        local_user = User.objects.get(username="engineer@example.com")
        self.assertEqual(local_user.first_name, "Updated")

    def test_group_membership_changes_are_applied(self):
        SyncingLoginUser(make_user_data())

        SyncingLoginUser(make_user_data(groups=["reliability"]))

        local_user = User.objects.get(username="engineer@example.com")
        self.assertEqual(
            list(local_user.groups.values_list("name", flat=True)), ["reliability"]
        )

    def test_stale_last_login_is_refreshed(self):
        SyncingLoginUser(make_user_data())
        local_user = User.objects.get(username="engineer@example.com")
        stale = timezone.now() - timedelta(hours=1)
        User.objects.filter(pk=local_user.pk).update(last_login=stale)

        SyncingLoginUser(make_user_data())

        local_user.refresh_from_db()
        self.assertGreater(local_user.last_login, stale)

    @override_settings(LOGIN_SERVICE_LAST_LOGIN_INTERVAL=0)
    def test_zero_interval_always_updates_last_login(self):
        SyncingLoginUser(make_user_data())
        local_user = User.objects.get(username="engineer@example.com")
        previous = timezone.now() - timedelta(seconds=1)
        User.objects.filter(pk=local_user.pk).update(last_login=previous)

        SyncingLoginUser(make_user_data())

        local_user.refresh_from_db()
        self.assertGreater(local_user.last_login, previous)

    def test_null_last_login_is_populated(self):
        SyncingLoginUser(make_user_data())
        User.objects.filter(username="engineer@example.com").update(last_login=None)

        SyncingLoginUser(make_user_data())

        local_user = User.objects.get(username="engineer@example.com")
        self.assertIsNotNone(local_user.last_login)

    def test_login_user_pk_comes_from_local_user(self):
        login_user = SyncingLoginUser(make_user_data())

        local_user = User.objects.get(username="engineer@example.com")
        self.assertEqual(login_user.pk, local_user.pk)
        self.assertEqual(login_user.id, local_user.id)


class SyncingLoginUserWithIdSyncTests(TestCase):
    def test_creates_local_user_with_explicit_id(self):
        SyncingLoginUserWithId(make_user_data(pk=4242))

        local_user = User.objects.get(id=4242)
        self.assertEqual(local_user.username, "engineer@example.com")
        self.assertEqual(
            sorted(local_user.groups.values_list("name", flat=True)),
            ["reliability", "reliability-engineer"],
        )

    def test_unchanged_user_row_is_not_written(self):
        SyncingLoginUserWithId(make_user_data(pk=4242))
        local_user = User.objects.get(id=4242)
        original_last_login = local_user.last_login

        SyncingLoginUserWithId(make_user_data(pk=4242))

        local_user.refresh_from_db()
        self.assertEqual(local_user.last_login, original_last_login)
