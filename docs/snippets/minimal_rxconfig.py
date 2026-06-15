import reflex as rx
from reflex_django.plugins import ReflexDjangoPlugin

config = rx.Config(
    app_name="shop",
    frontend_port=3000,
    backend_port=8000,
    plugins=[
        ReflexDjangoPlugin(config={
            "settings_module": "config.settings",
            "django_prefix": ("/admin", "/api"),
            "mount_prefix": "/",
            "auto_mount": True,
        }),
        rx.plugins.RadixThemesPlugin(),
    ],
)
