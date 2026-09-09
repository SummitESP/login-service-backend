Login Service Backend
---------------------

This session and authentication backend is intended specifically for use with the
[login-service](https://github.com/SummitESP/login-service).

Usage
=====

```sh
python -m pip install "login-service-backend @ git+https://github.com/SummitESP/login-service-backend.git@<commit-or-tag>"
```

Requires Python 3.10+ and Django 3.2+. Django and `requests` are installed as
runtime dependencies. For the Django REST Framework integration, install the
`drf` extra (`login-service-backend[drf] @ git+https://...`).

### Building and validating a release

Packaging uses PEP 517/621 and an isolated setuptools build backend. No Django
settings, application imports, system `distutils`, or preinstalled setuptools
are required to build the package. Keep pip build isolation enabled.

```sh
python -m venv .venv
.venv/bin/python -m pip install --upgrade pip build
.venv/bin/python script/check_packaging.py
```

The check builds an sdist and then a wheel from that sdist, installs each in a
separate environment seeded with pip 25.2 and setuptools 57.5.0 (the legacy
deployment toolchain), checks dependency consistency, and exercises the installed
session, middleware, and DRF modules outside the source tree. On Python 3.14 this
also verifies that the build does not depend on the host's broken legacy
setuptools/distutils installation. CI runs this against Python/Django
3.10/3.2, 3.12/4.2, and 3.14/5.2.

For a release, update `login_backend.__version__`, pass the packaging checks,
merge, and tag that commit as `v<version>`. Consumers can pin the reviewed commit
SHA before the release tag is available. Version 1.3.3 corrects the stale 1.3.1
package metadata in the existing v1.3.2 tag and modernizes packaging; it retains
the runtime code from v1.3.2, including its session-cache behavior (disabled by
default). SK deployments must also upgrade their pip bootstrap to match CI.

### Django Settings

    SESSION_ENGINE = 'login_backend.sessions'
    LOGIN_SERVICE_USER_CLASS = 'login_backend.user.LoginUser'
    LOGIN_SERVICE_SESSION_ENDPOINT = 'https://login.example.com/api/v1/session/'

You MUST remove `django.contrib.auth.middleware.AuthenticationMiddleware` from the MIDDLEWARE
setting and replace it with `login_backend.middleware.LoginServiceAuthenticationMiddleware`.

NOTE: This modified middleware will ignore the AUTHENTICATION_BACKENDS setting and assumes it
is the only authentication backend.

#### Authenticating your app with Login Service

When connecting to a Login Service using token-based authentication, you must create a user in the
Login Service for your application to connect as. Once you've created the user, you can use the
Admin to create an auth token. You can then add that token to your apps settings using the setting
below.

    LOGIN_SERVICE_TOKEN = '<generated token from login service>'

You should also create an auth group in the Login Service for authenticated apps to use. This group
should have the following permissions:

* view access for users.user
* view, add, change and delete access for sessions.session
* view access for authtoken.token

#### Caching

To improve performance and reduce network calls to the Login Service, session data can be cached. You can configure the cache timeout using the following setting:

    LOGIN_SERVICE_CACHE_TIMEOUT = 10  # seconds (default: 0)

This setting controls how long session and token data is cached before making another request to the Login Service. The default is 0 seconds, effectively disabling the cache.

The backend uses Django's cache framework, so ensure you have a cache backend configured in your Django settings. For production use, consider using Redis or Memcached instead of the default local-memory cache.

#### Django Rest Framework

The login service can also handle Token authentication for Django Rest Framework. Be sure to add
the following setting.

    LOGIN_SERVICE_TOKEN_ENDPOINT = 'https://login.example.com/api/v1/token/'

And add `login_backend.rest_framework.authentication.LoginServiceTokenAuthentication` to the
`REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES']` setting of the authentication_classes attribute
of the specific view you intend on using it with.

### Extending

You may create a customer user class by extending `login_backend.user.LoginUser` and replacing it
in the settings.

    class CustomUser(LoginUser):
        def __init__(self, user_data):
            super().__init__(user_data)
            self.person = self.get_person(user_data)

        def get_person(self, user_data):
            person, created = Person.objects.get_or_create(identified=user_data['identifier'])
            person.sync_attrs(user_data)  # update first_name, last_name, email, etc.
            return person

#### SyncingLoginUser

The `login_backend.user.SyncingLoginUser` class provides an alternative user class that automatically syncs user data and groups to local Django `auth.User` and `auth.Group` models.

    LOGIN_SERVICE_USER_CLASS = 'login_backend.user.SyncingLoginUser'

When using `SyncingLoginUser`:

* User records are created or updated on every authenticated request
* Groups are automatically created if they don't exist
* User group memberships are synced on every request
* User attributes (username, email, first_name, last_name, is_staff, is_active, is_superuser) are kept in sync with the Login Service
* The `last_login` timestamp is updated on every request

This is useful when you need local Django user records for foreign key relationships or when integrating with Django apps that expect standard Django users. Note that this approach makes additional database queries on each request, so consider the performance implications for high-traffic applications.
