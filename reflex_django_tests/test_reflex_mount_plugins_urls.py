"""URLconf that registers a Reflex plugin via reflex_mount()."""

from __future__ import annotations

from reflex_base.plugins.base import Plugin

from reflex_django.django.urls import reflex_mount


class MountTestPlugin(Plugin):
    """Marker plugin for mount-time registration tests."""

    marker = "mount_test"


urlpatterns = [
    reflex_mount(
        plugins=[MountTestPlugin()],
        rx_config={"app_name": "testfrontend", "frontend_port": 3100},
    ),
]
