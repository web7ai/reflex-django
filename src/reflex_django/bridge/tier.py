"""Resolve event-bridge tiers for Reflex handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

BridgeTier = Literal["full", "auth_only", "none"]

if TYPE_CHECKING:
    from reflex_base.event import Event

_VALID_TIERS = frozenset({"full", "auth_only", "none"})
_BRIDGE_MODE_SETTINGS_KEY: str | None = None
_BRIDGE_MODE = "full"


def _global_bridge_mode() -> str:
    global _BRIDGE_MODE_SETTINGS_KEY, _BRIDGE_MODE
    try:
        from django.conf import settings

        settings_key = str(getattr(settings, "SETTINGS_MODULE", "") or "")
        if settings_key != _BRIDGE_MODE_SETTINGS_KEY:
            mode_raw = getattr(settings, "RX_EVENT_BRIDGE_MODE", "full")
            _BRIDGE_MODE = (
                str(mode_raw).strip().lower()
                if isinstance(mode_raw, str)
                else "full"
            )
            _BRIDGE_MODE_SETTINGS_KEY = settings_key
    except Exception:
        _BRIDGE_MODE = "full"
        _BRIDGE_MODE_SETTINGS_KEY = ""
    return _BRIDGE_MODE


def _normalize_tier(value: object) -> BridgeTier | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized in _VALID_TIERS:
        return normalized  # type: ignore[return-value]
    return None


def _class_bridge_override(handler_state_cls: type | None) -> BridgeTier | None:
    if handler_state_cls is None:
        return None
    for key in ("_rx_bridge", "rx_bridge"):
        raw = handler_state_cls.__dict__.get(key)
        tier = _normalize_tier(raw)
        if tier is not None:
            return tier
    return None


def _is_upload_event(event: Event | None) -> bool:
    if event is None:
        return False
    name = str(getattr(event, "name", "") or "").lower()
    if "upload" in name:
        return True
    router_data = getattr(event, "router_data", None)
    if isinstance(router_data, dict):
        pathname = str(router_data.get("pathname") or "")
        if pathname.startswith("/_upload"):
            return True
    return False


def _is_django_aware_state(handler_state_cls: type | None) -> bool:
    if handler_state_cls is None:
        return False
    try:
        from reflex_django.states import AppState
        from reflex_django.auth_state import DjangoUserState
    except Exception:
        return False
    try:
        if issubclass(handler_state_cls, AppState):
            return True
    except TypeError:
        pass
    try:
        if issubclass(handler_state_cls, DjangoUserState):
            return True
    except TypeError:
        pass
    try:
        from reflex_django.state.model_state import ModelState

        if issubclass(handler_state_cls, ModelState):
            return True
    except (ImportError, TypeError):
        pass
    return False


def _smart_tier(
    handler_state_cls: type | None,
    event: Event | None,
) -> BridgeTier:
    if _is_upload_event(event):
        return "auth_only"
    if _is_django_aware_state(handler_state_cls):
        return "full"
    return "none"


def _raise_minimum_tier(current: BridgeTier, minimum: BridgeTier) -> BridgeTier:
    order = {"none": 0, "auth_only": 1, "full": 2}
    if order[minimum] > order[current]:
        return minimum
    return current


def resolve_bridge_tier(
    handler_state_cls: type | None,
    event: Event | None = None,
) -> BridgeTier:
    """Return the bridge tier for *handler_state_cls* and *event*."""
    from reflex_django.bridge.registry import call_custom_bridge_resolver

    custom = call_custom_bridge_resolver(handler_state_cls, event)
    if custom is not None:
        tier = _normalize_tier(custom)
        if tier is not None:
            if _is_upload_event(event):
                return _raise_minimum_tier(tier, "auth_only")
            return tier

    class_tier = _class_bridge_override(handler_state_cls)
    if class_tier is not None:
        if _is_upload_event(event):
            return _raise_minimum_tier(class_tier, "auth_only")
        return class_tier

    mode = _global_bridge_mode()

    if mode == "full":
        tier: BridgeTier = "full"
    elif mode == "none":
        tier = "none"
    elif mode == "smart":
        tier = _smart_tier(handler_state_cls, event)
    else:
        tier = "full"

    if _is_upload_event(event):
        return _raise_minimum_tier(tier, "auth_only")
    return tier


def tier_needs_auth_sync(
    tier: BridgeTier,
    handler_state_cls: type | None,
) -> bool:
    """Return whether auth snapshot sync should run for this tier."""
    if tier == "full":
        return True
    if tier != "auth_only" or handler_state_cls is None:
        return False
    from reflex_django.state.auth_bridge import _is_django_user_handler_cls

    return _is_django_user_handler_cls(handler_state_cls)


__all__ = [
    "BridgeTier",
    "resolve_bridge_tier",
    "tier_needs_auth_sync",
]