Login Service Backend
---------------------

This session and authentication backend is intended specifically for use with the
[login-service](https://github.com/SummitESP/login-service).

Usage
=====

pip install -e git+https://github.com/SummitESP/login-service-backend

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
