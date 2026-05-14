"""Per-event Django request context for reflex-django.

Reflex events arrive over Socket.IO without an HTTP request object, but Reflex
exposes ``router_data`` containing the cookie, headers, and client IP from the
WebSocket upgrade. :class:`DjangoEventBridge` synthesizes a Django HTTP request
from that data and stashes it on a :class:`contextvars.ContextVar` so user
state code can call :func:`current_user`, :func:`current_session`,
:func:`current_language`, or :func:`current_request` from any event handler.

Template ``TEMPLATES`` context processors can be reused for Reflex (see
:mod:`reflex_django.reflex_context`), but the active values are still keyed off
the synthetic request for the current Reflex event, not a template render.
"""

from __future__ import annotations

import contextvars
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
    from django.contrib.sessions.backends.base import SessionBase
    from django.http import HttpRequest


_request_var: contextvars.ContextVar[HttpRequest | None] = contextvars.ContextVar(
    "reflex_django.current_request", default=None
)

_reset_token_var: contextvars.ContextVar[
    contextvars.Token[HttpRequest | None] | None
] = contextvars.ContextVar("reflex_django._request_reset_token", default=None)


def set_current_request(
    request: HttpRequest | None,
) -> contextvars.Token[HttpRequest | None]:
    """Bind a Django request to the current async/sync task.

    Args:
        request: The :class:`django.http.HttpRequest` to bind, or ``None`` to
            clear.

    Returns:
        A reset token; pass it to :func:`reset_current_request` to undo.
    """
    return _request_var.set(request)


def reset_current_request(
    token: contextvars.Token[HttpRequest | None],
) -> None:
    """Undo a previous :func:`set_current_request` call.

    Args:
        token: The token returned by :func:`set_current_request`.
    """
    _request_var.reset(token)


def end_event_request() -> None:
    """Reset the bound Django request for the current task, if any.

    Clears the token produced by the last :func:`begin_event_request` in this
    context. Safe to call multiple times.
    """
    t = _reset_token_var.get()
    if t is not None:
        reset_current_request(t)
        _reset_token_var.set(None)


def begin_event_request(request: HttpRequest) -> None:
    """Bind ``request`` for the current task and remember the reset token.

    Calls :func:`end_event_request` first so nested or leaked bindings are
    cleared.

    Args:
        request: The synthetic Django request for this Reflex event.
    """
    end_event_request()
    token = set_current_request(request)
    _reset_token_var.set(token)


def current_request() -> HttpRequest | None:
    """Return the Django request bound to the active Reflex event, if any.

    Returns:
        The bound :class:`django.http.HttpRequest`, or ``None`` when called
        outside an event with the bridge installed.
    """
    return _request_var.get()


def current_user() -> AbstractBaseUser | AnonymousUser:
    """Return the authenticated user for the active Reflex event.

    Falls back to :class:`django.contrib.auth.models.AnonymousUser` when no
    request is bound or no user is present on the request.

    Returns:
        The Django user object.
    """
    from django.contrib.auth.models import AnonymousUser

    request = current_request()
    if request is None:
        return AnonymousUser()
    return getattr(request, "user", None) or AnonymousUser()


def current_session() -> SessionBase | None:
    """Return the Django session associated with the active Reflex event.

    Returns:
        The :class:`django.contrib.sessions.backends.base.SessionBase`
        instance, or ``None`` when no request is bound.
    """
    request = current_request()
    if request is None:
        return None
    return getattr(request, "session", None)


def current_language() -> str:
    """Return the active Django language code for this task.

    After :class:`reflex_django.middleware.DjangoEventBridge` runs, this matches
    ``request.LANGUAGE_CODE`` and :func:`django.utils.translation.get_language`.

    Returns:
        A language string such as ``en`` or ``de``. Falls back to Django's
        ``LANGUAGE_CODE`` setting when nothing is activated.
    """
    from django.conf import settings
    from django.utils import translation

    request = current_request()
    if request is not None:
        from_cookie = getattr(request, "LANGUAGE_CODE", None)
        if from_cookie:
            return str(from_cookie)
    active = translation.get_language()
    if active:
        return str(active)
    return str(getattr(settings, "LANGUAGE_CODE", "en") or "en")


__all__ = [
    "begin_event_request",
    "current_language",
    "current_request",
    "current_session",
    "current_user",
    "end_event_request",
    "reset_current_request",
    "set_current_request",
]
