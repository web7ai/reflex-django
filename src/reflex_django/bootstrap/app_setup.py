"""Apply Reflex plugins and middleware after the app factory builds rx.App."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from reflex.app import App


def _as_api_transformer_sequence(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, Sequence) and not callable(value):
        return tuple(value)
    return (value,)


def apply_django_integration(app: App) -> None:
    """Mount Django ASGI dispatch and the event bridge on *app*."""
    _apply_bridge_settings_from_config()
    _warn_insecure_defaults_for_prod()
    _ensure_django_api_transformer(app)
    _ensure_event_bridge(app)


def _warn_insecure_defaults_for_prod() -> None:
    """Emit a one-time security audit when compiling in a production posture."""
    try:
        from reflex_django.setup.security_check import warn_insecure_defaults

        warn_insecure_defaults()
    except Exception:
        pass


def _apply_bridge_settings_from_config() -> None:
    from reflex_django.mount.integration_config import get_integration_config

    bridge = get_integration_config().bridge
    if not bridge.enabled:
        return
    try:
        from django.conf import settings
    except Exception:
        return
    if not settings.configured:
        return
    from reflex_django.core.settings_names import (
        SETTING_EVENT_BRIDGE_MODE,
        SETTING_EVENT_BRIDGE_RESOLVER,
        SETTING_RUN_MIDDLEWARE_CHAIN,
    )

    settings.RX_EVENT_BRIDGE_MODE = bridge.mode
    settings.RX_RUN_MIDDLEWARE_CHAIN = bridge.run_middleware_chain
    if bridge.resolver:
        settings.RX_EVENT_BRIDGE_RESOLVER = bridge.resolver


def apply_reflex_plugins_to_app(app: App) -> None:
    """Install Django ASGI dispatch, event bridge, and user plugin hooks."""
    from reflex_base.config import get_config

    from reflex_django.plugins.reflex_django import is_reflex_django_plugin

    apply_django_integration(app)

    for plugin in get_config().plugins or ():
        if is_reflex_django_plugin(plugin):
            continue
        post_compile = getattr(plugin, "post_compile", None)
        if callable(post_compile):
            post_compile(app=app)


def _ensure_django_api_transformer(app: App) -> None:
    if getattr(app, "_reflex_django_dispatcher_configured", False):
        return

    from reflex_django.asgi.app import django_asgi_application, make_dispatcher
    from reflex_django.mount.integration_config import get_integration_config
    from reflex_django.mount.prefixes import resolve_prefixes

    if not get_integration_config().embed.enabled:
        return

    prefixes = resolve_prefixes().backend_prefixes_for_asgi()
    if not prefixes:
        return

    transformer = make_dispatcher(
        django_asgi_application(),
        backend_prefixes=prefixes,
    )
    existing = _as_api_transformer_sequence(app.api_transformer)
    app.api_transformer = (*existing, transformer)
    app._reflex_django_dispatcher_configured = True  # type: ignore[attr-defined]


def _ensure_event_bridge(app: Any) -> None:
    from reflex_django.bridge.event import DjangoEventBridge
    from reflex_django.mount.integration_config import get_integration_config

    if not get_integration_config().bridge.enabled:
        return

    middlewares = getattr(app, "_middlewares", ())
    if any(type(m).__name__ == "DjangoEventBridge" for m in middlewares):
        return
    app.add_middleware(DjangoEventBridge())


__all__ = ["apply_django_integration", "apply_reflex_plugins_to_app"]
