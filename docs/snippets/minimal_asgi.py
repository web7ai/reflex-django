import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from reflex_django.asgi_entry import application  # noqa: E402,F401
