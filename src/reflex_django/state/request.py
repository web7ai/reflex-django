"""Django request + response view for model state hooks."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from django.contrib.auth.models import AnonymousUser  # noqa: F401
    from django.http import HttpResponse


def _anonymous_user() -> Any:
    from reflex_django.bridge.context import anonymous_user

    return anonymous_user()


class DjangoStateRequest:
    """Per-event view of the bridged Django request and middleware response.

    Use :attr:`user` for the live auth user on the synthetic request.
    :attr:`response` exposes the :class:`django.http.HttpResponse` produced by
    the ``settings.MIDDLEWARE`` chain for the current event (``None`` if the
    chain is disabled). :attr:`messages` is a JSON-safe list of Django messages
    captured for the current event, and :attr:`csrf_token` is the CSRF token
    bound to the synthetic request (helpful for non-Reflex forms in your SPA).
    """

    __slots__ = ("_http", "_response")

    def __init__(
        self,
        http_request: Any | None,
        response: HttpResponse | None = None,
    ) -> None:
        self._http = http_request
        self._response = response

    @property
    def django_request(self) -> Any | None:
        """Underlying :class:`django.http.HttpRequest` from the event bridge."""
        return self._http

    @property
    def django_response(self) -> HttpResponse | None:
        """Middleware-chain :class:`django.http.HttpResponse`, if any."""
        return self._response

    @property
    def response(self) -> HttpResponse | None:
        """Alias for :attr:`django_response`."""
        return self._response

    @property
    def user(self) -> Any:
        """Authenticated user from the synthetic request (or anonymous)."""
        if self._http is None:
            return _anonymous_user()
        user = getattr(self._http, "user", None)
        return user if user is not None else _anonymous_user()

    @property
    def resolver_match(self) -> Any | None:
        """Best-effort :class:`django.urls.ResolverMatch` for the event path."""
        return getattr(self._http, "resolver_match", None) if self._http else None

    @property
    def messages(self) -> list[dict[str, Any]]:
        """JSON-safe Django messages for the active event (may be empty)."""
        from reflex_django.bridge.context import current_messages

        return current_messages()

    @property
    def csrf_token(self) -> str:
        """CSRF token bound to the synthetic request (empty if unavailable)."""
        from reflex_django.bridge.context import current_csrf_token

        return current_csrf_token()

    def __getattr__(self, name: str) -> Any:
        if self._http is not None:
            return getattr(self._http, name)
        msg = f"{type(self).__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)

    def __bool__(self) -> bool:
        return self._http is not None


__all__ = ["DjangoStateRequest"]
