Login Service Backend
---------------------

This session and authentication backend is intended specifically for use with the
[login-service](https://github.com/SummitESP/login-service).

Usage
=====

pip install ...

### Django Settings

    SESSION_ENGINE = 'login_backend.sessions'
    LOGIN_SERVICE_USER_CLASS = 'login_backend.user.LoginUser'
    LOGIN_SERVICE_SESSION_ENDPOINT = 'https://login.example.com/api/v1/session/'

You MUST remove `django.contrib.auth.middleware.AuthenticationMiddleware` from the MIDDLEWARE
setting and replace it with `login_backend.middleware.LoginServiceAuthenticationMiddleware`.

NOTE: This modified middleware will ignore the AUTHENTICATION_BACKENDS setting and assumes it 
is the only authentication backend.


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
