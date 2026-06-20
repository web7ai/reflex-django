import reflex as rx
from reflex_django.plugins import ReflexDjangoPlugin

config = rx.Config(
    app_name="shop",
    plugins=[
        ReflexDjangoPlugin(config={
            "settings_module": "config.settings",
            "profile": "integrated",
        }),
    ],
)
