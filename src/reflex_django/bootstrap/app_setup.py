"""Apply Reflex plugins and middleware after the app factory builds rx.App."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from reflex.app import App


def apply_reflex_plugins_to_app(app: App) -> None:
    """Install DjangoEventBridge and run user plugin post_compile hooks."""
    from reflex_base.config import get_config

    from reflex_django.rxconfig_bridge import ensure_rxconfig_from_django

    ensure_rxconfig_from_django()
    _ensure_event_bridge(app)

    for plugin in get_config().plugins or ():
        post_compile = getattr(plugin, "post_compile", None)
        if callable(post_compile):
            post_compile(app=app)


def _ensure_event_bridge(app: Any) -> None:
    from reflex_django.middleware import DjangoEventBridge

    middlewares = getattr(app, "_middlewares", ())
    if any(type(m).__name__ == "DjangoEventBridge" for m in middlewares):
        return
    app.add_middleware(DjangoEventBridge())


__all__ = ["apply_reflex_plugins_to_app"]