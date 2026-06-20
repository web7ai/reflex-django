# Integrated production rxconfig.py (Option 1)
import reflex as rx
from reflex_django.plugins import ReflexDjangoPlugin

config = rx.Config(
    app_name="shop",
    redis_url="redis://localhost:6379/0",
    plugins=[
        ReflexDjangoPlugin(
            config={
                "settings_module": "config.production",
                "profile": "integrated",
            }
        ),
    ],
)
