"""Per-event Django request context for reflex-django.

Reflex events arrive over Socket.IO without an HTTP request object, but Reflex
exposes ``router_data`` containing the cookie, headers, and client IP from the
WebSocket upgrade. :class:`DjangoEventBridge` synthesizes a Django HTTP request
from that data and stashes it on a :class:`contextvars.ContextVar` so user
state code can call :func:`current_user`, :func:`current_session`,
:func:`current_language`, or :func:`current_request` from any event handler.
"""

from __future__ import annotations

import contextvars
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
    from django.contrib.sessions.backends.base import SessionBase
    from django.http import HttpRequest, HttpResponse


_request_var: contextvars.ContextVar[HttpRequest | None] = contextvars.ContextVar(
    "reflex_django.current_request", default=None
)

# Response produced by the Django middleware chain for the active event.
# Populated by :class:`~reflex_django.bridge.django_event.DjangoEventBridge` after it
# runs ``settings.MIDDLEWARE`` against the synthetic request; reset when the
# event finishes.
_response_var: contextvars.ContextVar[HttpResponse | None] = contextvars.ContextVar(
    "reflex_django.current_response", default=None
)


class _StandInAnonymousUser:
    """Lightweight anonymous user before Django apps are ready or outside events."""

    is_authenticated = False
    is_staff = False
    is_superuser = False
    pk = None
    email = ""
    username = ""
    first_name = ""
    last_name = ""

    def get_username(self) -> str:
        return ""


def _django_apps_ready() -> bool:
    try:
        from django.apps import apps

        return bool(apps.ready)
    except Exception:
        return False


def anonymous_user() -> Any:
    """Return an anonymous user without touching the app registry when not ready."""
    if not _django_apps_ready():
        return _StandInAnonymousUser()
    from django.contrib.auth.models import AnonymousUser

    return AnonymousUser()


_reset_token_var: contextvars.ContextVar[
    contextvars.Token[HttpRequest | None] | None
] = contextvars.ContextVar("reflex_django._request_reset_token", default=None)

_response_reset_token_var: contextvars.ContextVar[
    contextvars.Token[HttpResponse | None] | None
] = contextvars.ContextVar("reflex_django._response_reset_token", default=None)


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


def set_current_response(
    response: HttpResponse | None,
) -> contextvars.Token[HttpResponse | None]:
    """Bind a Django response to the current async/sync task.

    Args:
        response: The :class:`django.http.HttpResponse` to bind, or ``None``
            to clear.

    Returns:
        A reset token; pass it to :func:`reset_current_response` to undo.
    """
    return _response_var.set(response)


def reset_current_response(
    token: contextvars.Token[HttpResponse | None],
) -> None:
    """Undo a previous :func:`set_current_response` call."""
    _response_var.reset(token)


def end_event_response() -> None:
    """Reset the bound Django response for the current task, if any."""
    t = _response_reset_token_var.get()
    if t is not None:
        reset_current_response(t)
        _response_reset_token_var.set(None)


def begin_event_response(response: HttpResponse | None) -> None:
    """Bind ``response`` for the current task and remember the reset token.

    Args:
        response: The middleware-chain response for this Reflex event, or
            ``None`` if no middleware response should be exposed (e.g.
            when ``RX_RUN_MIDDLEWARE_CHAIN`` is disabled).
    """
    end_event_response()
    token = set_current_response(response)
    _response_reset_token_var.set(token)


def current_response() -> HttpResponse | None:
    """Return the Django response bound to the active Reflex event, if any.

    Returns:
        The :class:`django.http.HttpResponse` produced by
        ``settings.MIDDLEWARE`` for the current event, or ``None`` when no
        middleware chain has run.
    """
    return _response_var.get()


def current_request() -> HttpRequest | None:
    """Return the Django request bound to the active Reflex event, if any.

    Returns:
        The bound :class:`django.http.HttpRequest`, or ``None`` when called
        outside an event with the bridge installed.
    """
    return _request_var.get()


def current_user() -> AbstractBaseUser | AnonymousUser:
    """Return the authenticated user for the active Reflex event.

    Falls back to an anonymous user when no request is bound or no user is on
    the request. Before :func:`django.apps.apps` is ready (for example during
    ``views.py`` import), returns :class:`_StandInAnonymousUser` instead of
    importing Django auth models.

    Returns:
        The Django user object.
    """
    request = current_request()
    if request is None:
        return anonymous_user()
    user = getattr(request, "user", None)
    return user if user is not None else anonymous_user()


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

    After :class:`reflex_django.bridge.django_event.DjangoEventBridge` runs, this matches
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


def current_messages() -> list[dict[str, Any]]:
    """Return a JSON-safe list of Django messages for the active event.

    Reads :func:`django.contrib.messages.get_messages` against the current
    request (after ``MessageMiddleware`` has populated the storage). Each
    message becomes a dict with ``level`` (int), ``level_tag`` (str),
    ``message`` (str), ``tags`` (str), and ``extra_tags`` (str).

    Returns an empty list when no request is bound, when the messages
    framework is not installed, or when reading the storage raises.
    """
    request = current_request()
    if request is None:
        return []
    try:
        from django.contrib.messages import get_messages
    except ImportError:
        return []
    try:
        storage = get_messages(request)
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for msg in storage:
        try:
            out.append(
                {
                    "level": int(getattr(msg, "level", 0) or 0),
                    "level_tag": str(getattr(msg, "level_tag", "") or ""),
                    "message": str(getattr(msg, "message", "") or ""),
                    "tags": str(getattr(msg, "tags", "") or ""),
                    "extra_tags": str(getattr(msg, "extra_tags", "") or ""),
                }
            )
        except Exception:
            continue
    return out


def current_csrf_token() -> str:
    """Return the CSRF token bound to the active Reflex event request.

    Calls :func:`django.middleware.csrf.get_token` against the bound
    request, which both reads the existing cookie value and sets a fresh
    one when missing. Useful when Reflex needs to surface a CSRF token to
    the browser for non-Reflex form submissions or fetch calls.

    Returns:
        The CSRF token string, or an empty string when no request is bound
        or CSRF support is not installed.
    """
    request = current_request()
    if request is None:
        return ""
    try:
        from django.middleware.csrf import get_token
    except ImportError:
        return ""
    try:
        return str(get_token(request) or "")
    except Exception:
        return ""


__all__ = [
    "anonymous_user",
    "begin_event_request",
    "begin_event_response",
    "current_csrf_token",
    "current_language",
    "current_messages",
    "current_request",
    "current_response",
    "current_session",
    "current_user",
    "end_event_request",
    "end_event_response",
    "reset_current_request",
    "reset_current_response",
    "set_current_request",
    "set_current_response",
]
