from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import Group

UserModel = get_user_model()


# Syncs m2m field with existing and incoming values
def sync_m2m_field(obj, attr_name, existing, incoming):
    existing = set(existing)
    incoming = set(incoming)
    attr = getattr(obj, attr_name, None)
    if not attr:
        raise FieldError('{} was not found for {} {}'.format(
            attr_name, type(obj), obj))
    attr.add(*(incoming - existing))
    attr.remove(*(existing - incoming))


class LoginServiceBackend(ModelBackend):
    """
    This backend is to be used in conjunction with the ``RemoteLoginServiceUserMiddleware``
    found in the middleware module of this package, and is used when the server
    is handling authentication to the login service.

    By default, the ``authenticate`` method creates ``User`` objects for
    usernames that don't already exist in the database.  Subclasses can disable
    this behavior by setting the ``create_unknown_user`` attribute to
    ``False``.
    """

    create_unknown_user = True
    # Fields that are synced on initial save of the user
    configure_fields = ('first_name', 'last_name', 'email', 'groups',)
    # Fields that are synced every time a user authenticates
    sync_fields = ('email', 'groups', 'is_active', 'is_staff',)

    def authenticate(self, request, h_number=None):
        """
        The username passed as ``h_number`` is considered trusted. Return
        the ``User`` object with the given h_number. Create a new ``User``
        object if ``create_unknown_user`` is ``True``.

        Return None if ``create_unknown_user`` is ``False`` and a ``User``
        object with the given h_number is not found in the database.

        Always sync
        """
        if not h_number:
            return
        user = None
        username = self.clean_username(h_number)

        # Note that this could be accomplished in one try-except clause, but
        # instead we use get_or_create when creating unknown users since it has
        # built-in safeguards for multiple threads.
        user_data = request.session['_user']
        if self.create_unknown_user:
            # TODO: specify a different field constant to match with h_number?
            user, created = UserModel._default_manager.get_or_create(**{
                UserModel.USERNAME_FIELD: username
            })
            if created:
                user = self.configure_user(user, user_data=user_data)
        else:
            try:
                user = UserModel._default_manager.get_by_natural_key(username)
            except UserModel.DoesNotExist:
                pass

        if not user:
            return None

        # Sync user fields before attempting to check auth
        user = self.sync_user(user, user_data)
        # Always save the user before attempting auth due to changes that can happen
        # in configure_user and sync_user.
        user.save()
        return user if self.user_can_authenticate(user) else None

    def sync_user_fields(self, user, fields, data):
        # optionally sync groups if present
        sync_groups = 'groups' in fields
        groups = data.pop('groups', None)
        if sync_groups:
            sync_m2m_field(user, 'groups', user.groups.all(), Group.objects.filter(name__in=groups))
            # Take 'groups' off fields
            fields = set(fields) - set(('groups',))

        for attr, value in data.items():
            if attr in fields:
                setattr(user, attr, value)
        return user

    def sync_user(self, user, data):
        """
        Sync groups and other items
        """
        return self.sync_user_fields(user, self.sync_fields, data)

    def clean_username(self, h_number):
        """
        Make sure h_number is uppercase
        """
        return h_number.upper()

    def configure_user(self, user, user_data=dict()):
        """
        Configure a user after creation and return the updated user.
        This should be used to add custom profile models or other user fields.
        """
        user.set_unusable_password()
        user = self.sync_user_fields(user, self.configure_fields, user_data)
        return user
