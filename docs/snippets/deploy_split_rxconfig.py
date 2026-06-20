# Split production rxconfig.py (Reflex worker - Option 2)
import os
import reflex as rx
from reflex_django.plugins import ReflexDjangoPlugin

config = rx.Config(
    app_name="shop",
    redis_url=os.environ["REDIS_URL"],
    plugins=[
        ReflexDjangoPlugin(
            config={
                "settings_module": "config.production",
                "embed": {"enabled": False},
                "mount": {"enabled": True},
                "proxy": {"enabled": False},
                "bridge": {"enabled": True, "mode": "full"},
            }
        ),
    ],
)
