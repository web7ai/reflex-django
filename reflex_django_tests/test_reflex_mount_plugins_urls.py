"""URLconf that registers a Reflex plugin via reflex_mount()."""

from __future__ import annotations

from reflex_base.plugins.base import Plugin

from reflex_django.urls import reflex_mount


class MountTestPlugin(Plugin):
    """Marker plugin for mount-time registration tests."""

    marker = "mount_test"


urlpatterns = [
    reflex_mount(
        app_name="testfrontend",
        plugins=[MountTestPlugin()],
        rx_config={"frontend_port": 3100},
    ),
]
