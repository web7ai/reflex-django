"""Settings hooks and resolver registry for the event bridge."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from reflex_base.event import Event

_resolver_cache: Any | None = None
_resolver_dotted: str | None = None


def _load_custom_resolver() -> Any | None:
    global _resolver_cache, _resolver_dotted
    try:
        from django.conf import settings
    except Exception:
        return None

    dotted = getattr(settings, "RX_EVENT_BRIDGE_RESOLVER", None)
    if not isinstance(dotted, str) or not dotted.strip():
        _resolver_cache = None
        _resolver_dotted = None
        return None

    dotted = dotted.strip()
    if _resolver_dotted == dotted and _resolver_cache is not None:
        return _resolver_cache

    from django.utils.module_loading import import_string

    _resolver_cache = import_string(dotted)
    _resolver_dotted = dotted
    return _resolver_cache


def call_custom_bridge_resolver(
    handler_state_cls: type | None,
    event: Event | None,
) -> str | None:
    """Invoke ``RX_EVENT_BRIDGE_RESOLVER`` when configured."""
    resolver = _load_custom_resolver()
    if resolver is None:
        return None
    result = resolver(handler_state_cls, event)
    if result is None:
        return None
    return str(result)


def reset_bridge_resolver_cache() -> None:
    """Clear cached resolver (tests only)."""
    global _resolver_cache, _resolver_dotted
    _resolver_cache = None
    _resolver_dotted = None


__all__ = [
    "call_custom_bridge_resolver",
    "reset_bridge_resolver_cache",
]