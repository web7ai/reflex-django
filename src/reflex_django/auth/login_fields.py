"""Login identifier configuration (username, email, or both)."""

from __future__ import annotations

from typing import Any

from asgiref.sync import sync_to_async
from django.contrib.auth import aauthenticate

SUPPORTED_LOGIN_FIELDS = frozenset({"username", "email"})
DEFAULT_LOGIN_FIELDS = ("username",)


def normalize_login_fields(raw: Any) -> tuple[str, ...]:
    """Parse ``LOGIN_FIELDS`` from Django settings into an ordered tuple.

    Args:
        raw: A sequence of field names (e.g. ``["username", "email"]``), a single
            string (``"email"``), or ``None`` for the default (username only).

    Returns:
        Normalized field names, each in ``SUPPORTED_LOGIN_FIELDS``.

    Raises:
        ValueError: If ``raw`` is empty or contains no supported fields.
    """
    if raw is None:
        return DEFAULT_LOGIN_FIELDS
    if isinstance(raw, str):
        items = [raw]
    elif isinstance(raw, (list, tuple)):
        items = list(raw)
    else:
        msg = (
            "LOGIN_FIELDS must be a string or sequence of 'username' and/or 'email', "
            f"got {type(raw).__name__}"
        )
        raise ValueError(msg)

    out: list[str] = []
    for item in items:
        key = str(item).strip().lower()
        if key in SUPPORTED_LOGIN_FIELDS and key not in out:
            out.append(key)
    if not out:
        msg = (
            "LOGIN_FIELDS must include at least one of 'username' or 'email', "
            f"got {raw!r}"
        )
        raise ValueError(msg)
    return tuple(out)


def login_identifier_label(login_fields: tuple[str, ...]) -> str:
    """Human-readable label for the login identifier input."""
    labels = {"username": "Username", "email": "Email"}
    parts = [labels[f] for f in login_fields if f in labels]
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} or {parts[1].lower()}"
    return "Login"


def login_identifier_placeholder(login_fields: tuple[str, ...]) -> str:
    """Placeholder text for the login identifier input."""
    return login_identifier_label(login_fields)


def login_identifier_autocomplete(login_fields: tuple[str, ...]) -> str:
    """HTML autocomplete value for the login identifier input."""
    if login_fields == ("email",):
        return "email"
    if login_fields == ("username",):
        return "username"
    return "username email"


def default_invalid_credentials_message(login_fields: tuple[str, ...]) -> str:
    """Default error copy when authentication fails."""
    if login_fields == ("email",):
        return "Invalid email or password."
    if "username" in login_fields and "email" in login_fields:
        return "Invalid username, email, or password."
    return "Invalid username or password."


async def aauthenticate_login_fields(
    request: Any,
    identifier: str,
    password: str,
    login_fields: tuple[str, ...],
) -> Any | None:
    """Authenticate using the configured login identifier fields.

    Django's :func:`~django.contrib.auth.aauthenticate` only accepts ``username``.
    When ``email`` is enabled, the user is looked up by email (case-insensitive)
    and authentication proceeds with their username.

    Args:
        request: Current Django/ASGI request from :func:`reflex_django.bridge.context.current_request`.
        identifier: Value entered in the login form (username and/or email).
        password: Password from the login form.
        login_fields: Normalized tuple from :func:`normalize_login_fields`.

    Returns:
        Authenticated user, or ``None`` if credentials are invalid.
    """
    identifier = identifier.strip()
    if not identifier or not password:
        return None

    if "username" in login_fields:
        user = await aauthenticate(
            request,
            username=identifier,
            password=password,
        )
        if user is not None:
            return user

    if "email" not in login_fields:
        return None

    def _username_for_email() -> str | None:
        from django.contrib.auth import get_user_model

        user_model = get_user_model()
        matches = list(user_model.objects.filter(email__iexact=identifier))
        if len(matches) != 1:
            return None
        return str(matches[0].get_username())

    username = await sync_to_async(_username_for_email)()
    if not username:
        return None
    return await aauthenticate(request, username=username, password=password)


__all__ = [
    "DEFAULT_LOGIN_FIELDS",
    "SUPPORTED_LOGIN_FIELDS",
    "aauthenticate_login_fields",
    "default_invalid_credentials_message",
    "login_identifier_autocomplete",
    "login_identifier_label",
    "login_identifier_placeholder",
    "normalize_login_fields",
]
