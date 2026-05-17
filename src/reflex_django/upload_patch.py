"""Inject ``router_data`` into Reflex upload handler events.

Reflex's ``/_upload`` endpoint builds handler :class:`~reflex_base.event.Event`
objects without ``router_data``, so :class:`~reflex_django.middleware.DjangoEventBridge`
cannot read session cookies. This module patches the upload helpers once to
attach cookies and routing metadata from the Starlette upload request at
enqueue time (reliable even when the handler event is processed on a worker task).
"""

from __future__ import annotations

import contextvars
import dataclasses
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

from reflex_django.middleware import _router_data_from_starlette_request

if TYPE_CHECKING:
    from reflex_base.event import Event
    from starlette.requests import Request

    from reflex.app import App

_upload_patch_applied = False
_upload_router_data: contextvars.ContextVar[dict[str, Any] | None] = (
    contextvars.ContextVar("reflex_django_upload_router_data", default=None)
)


def _event_has_session_cookie(event: Any) -> bool:
    raw = getattr(event, "router_data", None)
    if not isinstance(raw, dict):
        return False
    return bool((raw.get("headers") or {}).get("cookie"))


def inject_router_data_into_event(event: Any, router_data: dict[str, Any]) -> Any:
    """Return ``event`` with upload HTTP ``router_data`` merged in when cookies are missing.

    Args:
        event: The Reflex event about to be enqueued.
        router_data: Metadata from the Starlette ``/_upload`` request.

    Returns:
        The same event, or a copy with merged ``router_data``.
    """
    if _event_has_session_cookie(event):
        return event

    from reflex_base.event import Event as ReflexEvent

    if not isinstance(event, ReflexEvent):
        return event

    existing: dict[str, Any] = (
        event.router_data if isinstance(event.router_data, dict) else {}
    )
    merged: dict[str, Any] = {**router_data, **existing}
    headers: dict[str, str] = dict(router_data.get("headers") or {})
    headers.update(existing.get("headers") or {})
    cookie = headers.get("cookie") or (router_data.get("headers") or {}).get(
        "cookie", ""
    )
    if cookie:
        headers["cookie"] = cookie
    merged["headers"] = headers
    return dataclasses.replace(event, router_data=merged)


def _wrap_event_processor_enqueue(processor: Any) -> None:
    """Patch ``enqueue`` / ``enqueue_stream_delta`` to inject upload ``router_data``."""
    if getattr(processor, "_reflex_django_upload_wrapped", False):
        return

    orig_stream = processor.enqueue_stream_delta
    orig_enqueue = processor.enqueue

    async def enqueue_stream_delta(
        token: str,
        event: Event,
    ) -> AsyncGenerator[Any, None]:
        router_data = _upload_router_data.get()
        patched = (
            inject_router_data_into_event(event, router_data)
            if router_data is not None
            else event
        )
        async for delta in orig_stream(token, patched):
            yield delta

    async def enqueue(
        token: str,
        event: Event,
        ev_ctx: Any = None,
    ) -> Any:
        router_data = _upload_router_data.get()
        patched = (
            inject_router_data_into_event(event, router_data)
            if router_data is not None
            else event
        )
        return await orig_enqueue(token, patched, ev_ctx)

    processor.enqueue_stream_delta = enqueue_stream_delta  # type: ignore[method-assign]
    processor.enqueue = enqueue  # type: ignore[method-assign]
    processor._reflex_django_upload_wrapped = True  # noqa: SLF001


async def _patched_upload_buffered_file(
    request: Request,
    app: App,
    *,
    token: str,
    handler_name: str,
    handler_upload_param: tuple[str, Any],
) -> Any:
    import reflex_components_core.core._upload as upload_mod

    router_data = _router_data_from_starlette_request(request)
    _wrap_event_processor_enqueue(app.event_processor)
    ctx_token = _upload_router_data.set(router_data)
    try:
        return await upload_mod._upload_buffered_file__orig__(
            request,
            app,
            token=token,
            handler_name=handler_name,
            handler_upload_param=handler_upload_param,
        )
    finally:
        _upload_router_data.reset(ctx_token)


async def _patched_upload_chunk_file(
    request: Request,
    app: App,
    *,
    token: str,
    handler_name: str,
    handler_upload_param: tuple[str, Any],
    acknowledge_on_upload_endpoint: bool,
) -> Any:
    import reflex_components_core.core._upload as upload_mod

    router_data = _router_data_from_starlette_request(request)
    _wrap_event_processor_enqueue(app.event_processor)
    ctx_token = _upload_router_data.set(router_data)
    try:
        return await upload_mod._upload_chunk_file__orig__(
            request,
            app,
            token=token,
            handler_name=handler_name,
            handler_upload_param=handler_upload_param,
            acknowledge_on_upload_endpoint=acknowledge_on_upload_endpoint,
        )
    finally:
        _upload_router_data.reset(ctx_token)


def apply_upload_router_data_patch() -> None:
    """Patch Reflex upload handlers to populate ``event.router_data`` (idempotent)."""
    global _upload_patch_applied  # noqa: PLW0603

    if _upload_patch_applied:
        return

    import reflex_components_core.core._upload as upload_mod

    if not hasattr(upload_mod, "_upload_buffered_file__orig__"):
        upload_mod._upload_buffered_file__orig__ = upload_mod._upload_buffered_file
        upload_mod._upload_chunk_file__orig__ = upload_mod._upload_chunk_file

    upload_mod._upload_buffered_file = _patched_upload_buffered_file
    upload_mod._upload_chunk_file = _patched_upload_chunk_file
    _upload_patch_applied = True
