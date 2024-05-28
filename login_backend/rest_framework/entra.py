import requests
from django.contrib.auth import get_user_model

from rest_framework import authentication
from django.conf import settings
from rest_framework.authentication import get_authorization_header


class EntraTokenAuthentication(authentication.TokenAuthentication):
    def authenticate(self, request):
        # grab entra bearer token
        auth = get_authorization_header(request).split()

        if not auth or auth[0].lower() != b'bearer':
            return None

        if len(auth) == 1:
            return None
        elif len(auth) > 2:
            return None

        try:
            token = auth[1].decode()
        except UnicodeError:
            return None

        # ask login service for user data
        response = requests.post(
            f"{settings.LOGIN_SERVICE_TOKEN_ENDPOINT}m2m/",
            headers={"Authorization": f"Token {settings.LOGIN_SERVICE_TOKEN}"},
            data={"token": token},
        )

        # check if response is valid
        if response.status_code != 200:
            return None

        # return user and token
        username = response.json().get('username')
        User = get_user_model()
        user = User.objects.filter(username=username)

        if user.exists():
            user = user.first()
        else:
            return None

        return user, None
