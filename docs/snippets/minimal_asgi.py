import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from reflex_django.asgi.entry import application  # noqa: E402,F401
