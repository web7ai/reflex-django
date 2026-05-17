"""Base class for canned, subclassable auth pages."""

from __future__ import annotations

from typing import Any, ClassVar

import reflex as rx

from reflex_django.auth.pages.components import (
    auth_card,
    auth_page_shell,
    error_callout,
    success_callout,
)
from reflex_django.auth.settings import AuthSettings, get_auth_settings


class _LazyOnLoad:
    """Resolve a state ``on_load`` handler after :func:`~reflex_django.conf.configure_django`."""

    __slots__ = ("_method_name",)

    def __init__(self, method_name: str) -> None:
        self._method_name = method_name

    def __get__(self, obj: object, owner: type | None = None) -> Any:
        if owner is None:
            msg = "_LazyOnLoad must be accessed on a page class"
            raise AttributeError(msg)
        return getattr(owner.get_state(), self._method_name)


class AuthPageMeta(type):
    """Make ``LoginPage()`` return a component (Reflex calls page callables with ``()``)."""

    def __call__(cls, *args: object, **kwargs: object) -> rx.Component:
        if not args and not kwargs:
            return cls.render()
        return super().__call__(*args, **kwargs)


class BaseAuthPage(metaclass=AuthPageMeta):
    """Page type for ``app.add_page(LoginPage, ...)`` and incremental UI overrides.

    Reflex evaluates pages by calling the registered callable with no arguments.
    Subclass hook methods (``heading``, ``form_fields``, …) or :meth:`render` to
    customize layout and copy. Set :attr:`state_cls` to a custom auth state class
    that exposes the same event handlers (``submit_login_form``, etc.).
    """

    default_title: ClassVar[str] = ""
    default_on_load: ClassVar[Any] = None
    state_cls: ClassVar[type | None] = None

    @classmethod
    def auth_settings(cls) -> AuthSettings:
        """Resolved Django auth settings (override in tests if needed)."""
        return get_auth_settings()

    @classmethod
    def message(cls, key: str) -> str:
        """User-facing string from ``REFLEX_DJANGO_AUTH`` ``MESSAGES``."""
        return cls.auth_settings().messages[key]

    @classmethod
    def get_state(cls) -> type:
        """Auth state class used for form handlers and error vars."""
        if cls.state_cls is not None:
            return cls.state_cls
        from reflex_django.auth.state import DjangoAuthState

        return DjangoAuthState

    @classmethod
    def shell(cls, content: rx.Component) -> rx.Component:
        """Outer page layout."""
        return auth_page_shell(content)

    @classmethod
    def card(cls, *children: rx.Component, **props: object) -> rx.Component:
        """Centered card wrapper."""
        return auth_card(*children, **props)

    @classmethod
    def auth_form(
        cls,
        *children: rx.Component,
        on_submit: Any,
        **props: object,
    ) -> rx.Component:
        """Standard full-width auth form."""
        return rx.form(*children, on_submit=on_submit, width="100%", **props)

    @classmethod
    def error_for(cls, message: rx.Var | str) -> rx.Component:
        """Error callout when ``message`` is non-empty (caller wraps in ``rx.cond``)."""
        return error_callout(message)

    @classmethod
    def success_for(cls, message: rx.Var | str) -> rx.Component:
        """Success callout."""
        return success_callout(message)

    @classmethod
    def render(cls) -> rx.Component:
        """Build the page component. Override in subclasses."""
        msg = f"{cls.__name__}.render() is not implemented"
        raise NotImplementedError(msg)
