"""Django request + context-processor view for model state hooks."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from django.contrib.auth.models import AnonymousUser


def _anonymous_user() -> Any:
    from reflex_django.context import anonymous_user

    return anonymous_user()


class DjangoStateRequest:
    """Per-event view of the bridged Django request and processor context.

    Access template-style keys from context processors via attribute lookup
    (for example ``self.request.LANGUAGE_CODE``). Use :attr:`user` for the live
    auth user on the synthetic request (not the JSON ``user`` snapshot from
    processors unless you read ``self.request.context["user"]``).
    """

    __slots__ = ("_http", "_context")

    def __init__(
        self,
        http_request: Any | None,
        context: dict[str, Any] | None = None,
    ) -> None:
        self._http = http_request
        self._context = dict(context or {})

    @property
    def django_request(self) -> Any | None:
        """Underlying :class:`django.http.HttpRequest` from the event bridge."""
        return self._http

    @property
    def context(self) -> dict[str, Any]:
        """Shallow copy of merged context-processor output."""
        return dict(self._context)

    @property
    def user(self) -> Any:
        """Authenticated user from the synthetic request (or anonymous)."""
        if self._http is None:
            return _anonymous_user()
        user = getattr(self._http, "user", None)
        return user if user is not None else _anonymous_user()

    def __getattr__(self, name: str) -> Any:
        if name in self._context:
            return self._context[name]
        if self._http is not None:
            return getattr(self._http, name)
        msg = f"{type(self).__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)

    def __bool__(self) -> bool:
        return self._http is not None


__all__ = ["DjangoStateRequest"]
