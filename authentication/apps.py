from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    # keep module name as-is, but give the app a custom label so it doesn't
    # collide with Django's built-in 'auth' app
    name = 'authentication'
