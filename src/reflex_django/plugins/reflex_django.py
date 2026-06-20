"""Reflex-first integration plugin for existing Reflex projects."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from reflex_base.plugins.base import Plugin

logger = logging.getLogger("reflex_django.plugins")

PLUGIN_MARKER = "reflex_django"

# Backward-compatible export; see integration_config.ALLOWED_TOP_LEVEL_KEYS.
ALLOWED_PLUGIN_CONFIG_KEYS = frozenset(
    {
        "settings_module",
        "profile",
        "embed",
        "mount",
        "proxy",
        "bridge",
        "django_prefix",
        "mount_prefix",
        "auto_mount",
    }
)


def _coerce_plugin_config(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    from reflex_django.mount.integration_config import (
        IntegrationConfig,
        validate_plugin_config_keys,
    )

    config = validate_plugin_config_keys(raw)
    if config:
        IntegrationConfig.from_plugin(_ConfigHolder(config)).validate()
    return config


class _ConfigHolder:
    """Minimal stand-in for plugin during early config validation."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config


def is_reflex_django_plugin(plugin: Any) -> bool:
    """Return whether *plugin* is a :class:`ReflexDjangoPlugin` instance."""
    return (
        isinstance(plugin, ReflexDjangoPlugin)
        or getattr(plugin, "PLUGIN_MARKER", None) == PLUGIN_MARKER
    )


class ReflexDjangoPlugin(Plugin):
    """Mount Django inside a native Reflex project via ``rxconfig.py`` plugins."""

    PLUGIN_MARKER = PLUGIN_MARKER

    def __init__(
        self,
        *,
        config: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        from reflex_django.mount.integration_config import (
            IntegrationConfig,
            validate_plugin_config_keys,
        )

        merged = validate_plugin_config_keys(config)
        if kwargs:
            merged = {**merged, **validate_plugin_config_keys(kwargs)}
        if merged:
            IntegrationConfig.from_plugin(_ConfigHolder(merged)).validate()
        self.config = merged

    def pre_compile(self, **context: Any) -> None:
        """Bootstrap Django integration and patch Vite for two-port dev."""
        self._ensure_bootstrap()
        from reflex_django.mount.integration_config import get_integration_config

        if not get_integration_config().proxy.enabled:
            logger.info(
                "reflex-django: proxy.enabled=False — skipping Vite proxy patch."
            )
            try:
                from reflex_django.dev.vite_proxy import finalize_web_dev_layout

                finalize_web_dev_layout(force=True)
            except Exception as exc:
                logger.warning(
                    "reflex-django: could not strip Vite proxy rules: %r", exc
                )
            return
        try:
            from reflex_django.dev.vite_proxy import (
                ensure_vite_django_dev_proxy_from_config,
            )

            ensure_vite_django_dev_proxy_from_config()
        except Exception as exc:
            logger.warning("reflex-django: Vite proxy setup failed: %r", exc)

    def post_compile(self, app: Any = None, **context: Any) -> None:
        """Wire Django ASGI dispatch and the event bridge on the native App."""
        self._ensure_bootstrap()
        if app is None:
            return
        from reflex_django.bootstrap.app_setup import apply_django_integration

        apply_django_integration(app)

    def post_build(self, static_dir: Any = None, **context: Any) -> None:
        """Ensure Django bootstrap completed before static export finishes."""
        self._ensure_bootstrap()

    def _ensure_bootstrap(self) -> None:
        from reflex_django.runtime.integration import install_plugin_integration
        from reflex_django.runtime.integration.registry import is_installed

        if is_installed():
            return
        install_plugin_integration(self)


RXDJANGOPLUGIN = ReflexDjangoPlugin

__all__ = [
    "ALLOWED_PLUGIN_CONFIG_KEYS",
    "PLUGIN_MARKER",
    "RXDJANGOPLUGIN",
    "ReflexDjangoPlugin",
    "is_reflex_django_plugin",
]
