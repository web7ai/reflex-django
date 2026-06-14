"""Django-style ``request`` proxy for Reflex event handlers.

Use inside ``@rx.event`` handlers after :class:`~reflex_django.bridge.event.DjangoEventBridge`
has bound the synthetic :class:`django.http.HttpRequest`::

    from reflex_django import request

    @rx.event
    async def my_handler(self):
        if request.user.is_authenticated:
            ...
        page = request.GET.get("page")

Do **not** use ``request.user`` in **class-level** state defaults (for example
``message: str = f"Hi {request.user}"``) — that runs at import time before
Django is ready. Set values in ``@rx.event`` handlers (``on_load``) instead.

Do **not** pass ``request.user`` (a Django model) into ``rx.text`` / components.
For UI labels use :class:`~reflex_django.states.auth.DjangoUserState` /
:class:`~reflex_django.states.AppState`` vars (``username``, ``is_authenticated``)
or the primitive helpers ``request.username`` / ``request.is_authenticated``.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

from reflex_django.bridge.context import current_request, current_session, current_user
from reflex_django.core.users import username_str

_REFLEX_HEADERS_ATTR = "_reflex_django_headers"


class RequestHeaders(Mapping[str, str]):
    """Case-insensitive header mapping for the active bridged request."""

    def __init__(self, http_request: Any | None) -> None:
        self._http = http_request
        raw = getattr(http_request, _REFLEX_HEADERS_ATTR, None) if http_request else None
        self._direct: dict[str, str] = dict(raw) if raw else {}

    def _meta_headers(self) -> dict[str, str]:
        if self._http is None:
            return {}
        meta = getattr(self._http, "META", None) or {}
        out: dict[str, str] = {}
        for key, value in meta.items():
            if key.startswith("HTTP_"):
                name = key[5:].replace("_", "-").title()
                out[name] = str(value)
        return out

    def _lookup(self, key: str) -> str | None:
        if not key:
            return None
        lower = key.lower()
        for name, value in self._direct.items():
            if name.lower() == lower:
                return value
        meta = self._meta_headers()
        for name, value in meta.items():
            if name.lower() == lower:
                return value
        return None

    def __getitem__(self, key: str) -> str:
        value = self._lookup(key)
        if value is None:
            raise KeyError(key)
        return value

    def __iter__(self) -> Iterator[str]:
        seen: set[str] = set()
        for name in self._direct:
            lower = name.lower()
            if lower not in seen:
                seen.add(lower)
                yield name
        for name in self._meta_headers():
            lower = name.lower()
            if lower not in seen:
                seen.add(lower)
                yield name

    def __len__(self) -> int:
        return len(set(k.lower() for k in self))

    def get(self, key: str, default: str | None = None) -> str | None:
        value = self._lookup(key)
        return value if value is not None else default


class RequestProxy:
    """Module-level proxy to the Django request for the active Reflex event."""

    @property
    def django_request(self) -> Any | None:
        """Underlying :class:`django.http.HttpRequest`, or ``None`` outside an event."""
        return current_request()

    @property
    def user(self) -> Any:
        """Authenticated user (or :class:`~django.contrib.auth.models.AnonymousUser`).

        For authorization in handlers only — not valid as a Reflex component child.
        """
        return current_user()

    @property
    def username(self) -> str:
        """Username string (safe for display); empty when anonymous."""
        user = current_user()
        if getattr(user, "is_authenticated", False):
            return username_str(user)
        return ""

    @property
    def is_authenticated(self) -> bool:
        """Whether the bridged request has an authenticated user."""
        return bool(getattr(current_user(), "is_authenticated", False))

    @property
    def email(self) -> str:
        """User email string; empty when anonymous or unset."""
        user = current_user()
        if getattr(user, "is_authenticated", False):
            return str(getattr(user, "email", "") or "")
        return ""

    @property
    def session(self) -> Any | None:
        """Django session store for this event, if the bridge ran."""
        return current_session()

    @property
    def GET(self) -> Any:
        """Query parameters (:class:`django.http.QueryDict`)."""
        from django.http import QueryDict

        http = current_request()
        if http is not None:
            get = getattr(http, "GET", None)
            if get is not None:
                return get
        return QueryDict()

    @property
    def headers(self) -> RequestHeaders:
        """Request headers (case-insensitive)."""
        return RequestHeaders(current_request())

    @property
    def COOKIES(self) -> dict[str, str]:
        http = current_request()
        if http is not None:
            return dict(getattr(http, "COOKIES", {}) or {})
        return {}

    @property
    def META(self) -> dict[str, Any]:
        http = current_request()
        if http is not None:
            return dict(getattr(http, "META", {}) or {})
        return {}

    @property
    def method(self) -> str:
        http = current_request()
        if http is not None:
            return str(getattr(http, "method", "GET") or "GET")
        return "GET"

    @property
    def path(self) -> str:
        http = current_request()
        if http is not None:
            return str(getattr(http, "path", "/") or "/")
        return "/"

    def __getattr__(self, name: str) -> Any:
        http = current_request()
        if http is not None:
            return getattr(http, name)
        msg = (
            f"No active Reflex event request (attribute {name!r}). "
            "Ensure install_reflex_django_integration() is enabled (via manage.py run_reflex)."
        )
        raise AttributeError(msg)

    def __bool__(self) -> bool:
        return current_request() is not None


request = RequestProxy()

__all__ = ["RequestHeaders", "RequestProxy", "request"]
