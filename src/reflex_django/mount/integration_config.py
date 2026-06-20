"""Unified four-pillar integration config for reflex-django."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from reflex_django.core.settings_names import (
    SETTING_AUTO_MOUNT,
    SETTING_EVENT_BRIDGE_MODE,
    SETTING_EVENT_BRIDGE_RESOLVER,
    SETTING_PROXY_SERVER,
    SETTING_RUN_MIDDLEWARE_CHAIN,
    SETTING_SEPARATE_DEV_PORTS,
)
from reflex_django.setup.errors import ConfigurationError

logger = logging.getLogger("reflex_django.mount.integration_config")

VALID_BRIDGE_MODES = frozenset({"full", "smart", "none"})
VALID_PROFILES = frozenset({"integrated", "split_dev", "reflex_only"})

ALLOWED_TOP_LEVEL_KEYS = frozenset(
    {
        "settings_module",
        "profile",
        "embed",
        "mount",
        "proxy",
        "bridge",
        # legacy flat keys
        "django_prefix",
        "mount_prefix",
        "auto_mount",
    }
)

ALLOWED_EMBED_KEYS = frozenset({"enabled"})
ALLOWED_MOUNT_KEYS = frozenset({"enabled", "mount_prefix", "django_prefix"})
ALLOWED_PROXY_KEYS = frozenset({"enabled", "server", "separate_dev_ports"})
ALLOWED_BRIDGE_KEYS = frozenset(
    {"enabled", "mode", "run_middleware_chain", "resolver"}
)

_INTEGRATION_CONFIG: IntegrationConfig | None = None


@dataclass(frozen=True)
class EmbedConfig:
    """In-process Django HTTP ASGI inside the Reflex backend (``make_dispatcher``)."""

    enabled: bool = True


@dataclass(frozen=True)
class MountConfig:
    """SPA catch-all URL registration via ``reflex_mount`` / auto-mount."""

    enabled: bool = True
    mount_prefix: str | None = None
    django_prefix: tuple[str, ...] | None = None


@dataclass(frozen=True)
class ProxyConfig:
    """Dev Vite proxy and optional external Django HTTP server."""

    enabled: bool = True
    server: str = ""
    separate_dev_ports: bool | None = None


@dataclass(frozen=True)
class BridgeConfig:
    """Django middleware and request context on Reflex ``/_event`` handlers."""

    enabled: bool = True
    mode: str = "full"
    run_middleware_chain: bool = True
    resolver: str | None = None


@dataclass(frozen=True)
class IntegrationConfig:
    """Resolved four-pillar integration settings."""

    embed: EmbedConfig
    mount: MountConfig
    proxy: ProxyConfig
    bridge: BridgeConfig

    @classmethod
    def from_plugin(cls, plugin: Any) -> IntegrationConfig:
        """Resolve integration config from a :class:`~reflex_django.plugins.ReflexDjangoPlugin`."""
        raw = dict(getattr(plugin, "config", None) or {})
        profile_name = str(raw.get("profile") or "integrated").strip() or "integrated"
        if profile_name not in VALID_PROFILES:
            msg = (
                f"Unsupported ReflexDjangoPlugin profile {profile_name!r}. "
                f"Allowed: {sorted(VALID_PROFILES)}"
            )
            raise ValueError(msg)

        profile = _profile_defaults(profile_name)

        embed = _resolve_embed(raw, profile.embed)
        mount = _resolve_mount(raw, profile.mount)
        proxy = _resolve_proxy(raw, profile.proxy, embed=embed)
        bridge = _resolve_bridge(raw, profile.bridge)

        return cls(embed=embed, mount=mount, proxy=proxy, bridge=bridge)

    def validate(self, *, runtime: bool = False) -> None:
        """Raise :class:`~reflex_django.setup.errors.ConfigurationError` when invalid."""
        if self.bridge.mode not in VALID_BRIDGE_MODES:
            msg = (
                f"Invalid bridge.mode {self.bridge.mode!r}. "
                f"Allowed: {sorted(VALID_BRIDGE_MODES)}"
            )
            raise ConfigurationError(msg)

        if (
            runtime
            and not self.embed.enabled
            and self.proxy.enabled
            and not self.proxy.server
        ):
            raise ConfigurationError(
                "embed.enabled=False with proxy.enabled=True requires proxy.server "
                "(or RX_PROXY_SERVER / RX_PROXY_SERVER env).\n"
                "Start Django separately, for example:\n"
                "    python manage.py runserver\n"
                "Then set in rxconfig.py:\n"
                '    ReflexDjangoPlugin(config={"embed": {"enabled": False}, '
                '"proxy": {"server": "http://127.0.0.1:8000"}})\n'
                "Or set RX_PROXY_SERVER in settings.py."
            )

        if runtime and self.embed.enabled and self.proxy.server:
            logger.warning(
                "reflex-django: embed.enabled=True but proxy.server is set (%s). "
                "In-process Django HTTP takes precedence; proxy.server is used only "
                "when embed.enabled=False.",
                self.proxy.server,
            )

        if runtime and not self.bridge.enabled:
            logger.warning(
                "reflex-django: bridge.enabled=False — Reflex events will not run "
                "Django middleware or bind self.request/self.user on AppState."
            )

    def summary(self) -> str:
        """Return a one-line pillar summary for bootstrap logging."""
        embed = "on" if self.embed.enabled else "off"
        proxy = self.proxy.server or ("on" if self.proxy.enabled else "off")
        mount = "on" if self.mount.enabled else "off"
        bridge = "off" if not self.bridge.enabled else self.bridge.mode
        return f"embed={embed} proxy={proxy} mount={mount} bridge={bridge}"


def _profile_defaults(name: str) -> IntegrationConfig:
    if name == "split_dev":
        return IntegrationConfig(
            embed=EmbedConfig(enabled=False),
            mount=MountConfig(enabled=True),
            proxy=ProxyConfig(enabled=True),
            bridge=BridgeConfig(enabled=True),
        )
    if name == "reflex_only":
        return IntegrationConfig(
            embed=EmbedConfig(enabled=False),
            mount=MountConfig(enabled=False),
            proxy=ProxyConfig(enabled=True),
            bridge=BridgeConfig(enabled=False),
        )
    return IntegrationConfig(
        embed=EmbedConfig(enabled=True),
        mount=MountConfig(enabled=True),
        proxy=ProxyConfig(enabled=True),
        bridge=BridgeConfig(enabled=True),
    )


def _pillar_block(raw: Mapping[str, Any], key: str) -> dict[str, Any]:
    block = raw.get(key)
    if block is None:
        return {}
    if not isinstance(block, Mapping):
        msg = f"ReflexDjangoPlugin config[{key!r}] must be a mapping."
        raise TypeError(msg)
    return dict(block)


def _validate_pillar_keys(block: Mapping[str, Any], *, pillar: str, allowed: frozenset[str]) -> None:
    unknown = set(block) - allowed
    if unknown:
        msg = (
            f"Unsupported ReflexDjangoPlugin config[{pillar!r}] keys: {sorted(unknown)}. "
            f"Allowed: {sorted(allowed)}"
        )
        raise ValueError(msg)


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no"}
    return bool(value)


def _coerce_django_prefix(value: Any) -> tuple[str, ...] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return (value,) if value.strip() else ()
    return tuple(str(p) for p in value if str(p).strip())


def _resolve_embed(raw: Mapping[str, Any], profile: EmbedConfig) -> EmbedConfig:
    block = _pillar_block(raw, "embed")
    _validate_pillar_keys(block, pillar="embed", allowed=ALLOWED_EMBED_KEYS)

    enabled = profile.enabled
    if "enabled" in block:
        enabled = _coerce_bool(block["enabled"], default=profile.enabled)
    elif _proxy_server_from_settings_or_env():
        # Legacy: RX_PROXY_SERVER implies embed off when plugin omits embed block.
        enabled = False

    return EmbedConfig(enabled=enabled)


def _resolve_mount(raw: Mapping[str, Any], profile: MountConfig) -> MountConfig:
    block = _pillar_block(raw, "mount")
    _validate_pillar_keys(block, pillar="mount", allowed=ALLOWED_MOUNT_KEYS)

    enabled = profile.enabled
    if "enabled" in block:
        enabled = _coerce_bool(block["enabled"], default=profile.enabled)
    elif "auto_mount" in raw:
        enabled = _coerce_bool(raw["auto_mount"], default=profile.enabled)
    elif _auto_mount_from_settings_or_env() is not None:
        enabled = _auto_mount_from_settings_or_env()  # type: ignore[assignment]

    if not enabled:
        return MountConfig(enabled=False, mount_prefix=None, django_prefix=None)

    mount_prefix = profile.mount_prefix
    if "mount_prefix" in block:
        mount_prefix = block["mount_prefix"]
    elif "mount_prefix" in raw:
        mount_prefix = raw["mount_prefix"]

    django_prefix = profile.django_prefix
    if "django_prefix" in block:
        django_prefix = _coerce_django_prefix(block["django_prefix"])
    elif "django_prefix" in raw:
        django_prefix = _coerce_django_prefix(raw["django_prefix"])

    return MountConfig(
        enabled=enabled,
        mount_prefix=mount_prefix,
        django_prefix=django_prefix,
    )


def _resolve_proxy(
    raw: Mapping[str, Any],
    profile: ProxyConfig,
    *,
    embed: EmbedConfig,
) -> ProxyConfig:
    block = _pillar_block(raw, "proxy")
    _validate_pillar_keys(block, pillar="proxy", allowed=ALLOWED_PROXY_KEYS)

    enabled = profile.enabled
    if "enabled" in block:
        enabled = _coerce_bool(block["enabled"], default=profile.enabled)

    server = profile.server
    if "server" in block and block["server"]:
        server = str(block["server"]).strip().rstrip("/")
    else:
        settings_server = _proxy_server_from_settings_or_env()
        if settings_server:
            server = settings_server

    separate_dev_ports = profile.separate_dev_ports
    if "separate_dev_ports" in block:
        separate_dev_ports = _coerce_bool(
            block["separate_dev_ports"],
            default=True,
        )

    if not embed.enabled and enabled and not server:
        # split_dev profile expects server; validation catches missing value.
        pass

    return ProxyConfig(
        enabled=enabled,
        server=server,
        separate_dev_ports=separate_dev_ports,
    )


def _resolve_bridge(raw: Mapping[str, Any], profile: BridgeConfig) -> BridgeConfig:
    block = _pillar_block(raw, "bridge")
    _validate_pillar_keys(block, pillar="bridge", allowed=ALLOWED_BRIDGE_KEYS)

    enabled = profile.enabled
    if "enabled" in block:
        enabled = _coerce_bool(block["enabled"], default=profile.enabled)

    mode = profile.mode
    if "mode" in block:
        mode = str(block["mode"]).strip().lower()
    elif not block:
        settings_mode = _bridge_mode_from_settings()
        if settings_mode:
            mode = settings_mode

    run_middleware_chain = profile.run_middleware_chain
    if "run_middleware_chain" in block:
        run_middleware_chain = _coerce_bool(
            block["run_middleware_chain"],
            default=profile.run_middleware_chain,
        )
    elif not block:
        settings_chain = _run_middleware_chain_from_settings()
        if settings_chain is not None:
            run_middleware_chain = settings_chain

    resolver = profile.resolver
    if "resolver" in block and block["resolver"]:
        resolver = str(block["resolver"]).strip()
    elif not block:
        settings_resolver = _bridge_resolver_from_settings()
        if settings_resolver:
            resolver = settings_resolver

    return BridgeConfig(
        enabled=enabled,
        mode=mode,
        run_middleware_chain=run_middleware_chain,
        resolver=resolver,
    )


def _proxy_server_from_settings_or_env() -> str:
    env_value = os.environ.get("RX_PROXY_SERVER", "").strip()
    if env_value:
        return env_value.rstrip("/")
    try:
        from django.conf import settings

        if settings.configured:
            settings_value = str(
                getattr(settings, SETTING_PROXY_SERVER, "") or ""
            ).strip()
            if settings_value:
                return settings_value.rstrip("/")
    except Exception:
        pass
    return ""


def _auto_mount_from_settings_or_env() -> bool | None:
    env = os.environ.get("RX_AUTO_MOUNT")
    if env is not None:
        return str(env).strip().lower() not in {"0", "false", "no"}
    try:
        from django.conf import settings

        if settings.configured and hasattr(settings, SETTING_AUTO_MOUNT):
            return bool(getattr(settings, SETTING_AUTO_MOUNT))
    except Exception:
        pass
    return None


def _bridge_mode_from_settings() -> str | None:
    try:
        from django.conf import settings

        if settings.configured and hasattr(settings, SETTING_EVENT_BRIDGE_MODE):
            value = str(getattr(settings, SETTING_EVENT_BRIDGE_MODE, "") or "").strip()
            if value:
                return value.lower()
    except Exception:
        pass
    return None


def _run_middleware_chain_from_settings() -> bool | None:
    try:
        from django.conf import settings

        if settings.configured and hasattr(settings, SETTING_RUN_MIDDLEWARE_CHAIN):
            return bool(getattr(settings, SETTING_RUN_MIDDLEWARE_CHAIN))
    except Exception:
        pass
    return None


def _bridge_resolver_from_settings() -> str | None:
    try:
        from django.conf import settings

        if settings.configured:
            value = getattr(settings, SETTING_EVENT_BRIDGE_RESOLVER, None)
            if isinstance(value, str) and value.strip():
                return value.strip()
    except Exception:
        pass
    return None


def _separate_dev_ports_from_settings() -> bool | None:
    try:
        from django.conf import settings

        if settings.configured and hasattr(settings, SETTING_SEPARATE_DEV_PORTS):
            return bool(getattr(settings, SETTING_SEPARATE_DEV_PORTS))
    except Exception:
        pass
    return None


def validate_plugin_config_keys(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    """Validate top-level plugin config keys and return a copy."""
    if not raw:
        return {}
    if not isinstance(raw, Mapping):
        msg = "ReflexDjangoPlugin config must be a mapping."
        raise TypeError(msg)
    unknown = set(raw) - ALLOWED_TOP_LEVEL_KEYS
    if unknown:
        msg = (
            f"Unsupported ReflexDjangoPlugin config keys: {sorted(unknown)}. "
            f"Allowed: {sorted(ALLOWED_TOP_LEVEL_KEYS)}"
        )
        raise ValueError(msg)
    return dict(raw)


def integration_config_is_cached() -> bool:
    """Return whether bootstrap has cached integration config."""
    return _INTEGRATION_CONFIG is not None


def set_integration_config(config: IntegrationConfig) -> None:
    """Store resolved integration config (called during plugin bootstrap)."""
    global _INTEGRATION_CONFIG
    _INTEGRATION_CONFIG = config


def get_integration_config() -> IntegrationConfig:
    """Return cached integration config or sensible defaults when unset."""
    if _INTEGRATION_CONFIG is not None:
        return _INTEGRATION_CONFIG
    return IntegrationConfig(
        embed=EmbedConfig(enabled=True),
        mount=MountConfig(enabled=True),
        proxy=ProxyConfig(enabled=True),
        bridge=BridgeConfig(enabled=True),
    )


def clear_integration_config() -> None:
    """Clear cached integration config (tests only)."""
    global _INTEGRATION_CONFIG
    _INTEGRATION_CONFIG = None


def resolve_and_cache_integration_config(plugin: Any) -> IntegrationConfig:
    """Resolve, validate, apply bridge settings, cache, and return config."""
    config = IntegrationConfig.from_plugin(plugin)
    config.validate(runtime=True)
    _apply_bridge_settings(config.bridge)
    set_integration_config(config)
    return config


def _apply_bridge_settings(bridge: BridgeConfig) -> None:
    """Sync resolved bridge config onto Django settings for bridge internals."""
    if not bridge.enabled:
        return
    try:
        from django.conf import settings
    except Exception:
        return
    if not settings.configured:
        return

    setattr(settings, SETTING_EVENT_BRIDGE_MODE, bridge.mode)
    setattr(settings, SETTING_RUN_MIDDLEWARE_CHAIN, bridge.run_middleware_chain)
    if bridge.resolver:
        setattr(settings, SETTING_EVENT_BRIDGE_RESOLVER, bridge.resolver)


def mount_enabled() -> bool:
    """Return whether auto-mount / SPA catch-all registration is enabled."""
    if _INTEGRATION_CONFIG is not None:
        return _INTEGRATION_CONFIG.mount.enabled
    env = os.environ.get("RX_AUTO_MOUNT")
    if env is not None:
        return str(env).strip().lower() not in {"0", "false", "no"}
    settings_val = _auto_mount_from_settings_or_env()
    if settings_val is not None:
        return settings_val
    return True


def proxy_server_url() -> str:
    """Return external Django HTTP server URL for dev proxy."""
    cached = get_integration_config().proxy.server
    if cached:
        return cached
    return _proxy_server_from_settings_or_env()


def proxy_separate_dev_ports() -> bool | None:
    """Return separate dev ports flag from integration config or settings."""
    cfg = get_integration_config().proxy.separate_dev_ports
    if cfg is not None:
        return cfg
    return _separate_dev_ports_from_settings()


def vite_proxy_patching_enabled() -> bool:
    """Return whether reflex-django should write Vite dev proxy rules."""
    return get_integration_config().proxy.enabled


__all__ = [
    "ALLOWED_TOP_LEVEL_KEYS",
    "BridgeConfig",
    "EmbedConfig",
    "IntegrationConfig",
    "MountConfig",
    "ProxyConfig",
    "VALID_BRIDGE_MODES",
    "VALID_PROFILES",
    "clear_integration_config",
    "get_integration_config",
    "integration_config_is_cached",
    "mount_enabled",
    "proxy_separate_dev_ports",
    "vite_proxy_patching_enabled",
    "proxy_server_url",
    "resolve_and_cache_integration_config",
    "set_integration_config",
    "validate_plugin_config_keys",
]
