"""Base Reflex state classes for reflex-django apps."""

from __future__ import annotations

from abc import ABC

import reflex as rx

__all__ = ["AppState"]


class AppState(rx.State, ABC):
    """Domain or routing state.

    Subclass this for app-wide fields (navigation, feature flags, etc.).
    Do not subclass :class:`reflex_django.DjangoUserState` here — use
    :class:`~reflex_django.DjangoUserState` (or :class:`~reflex_django.DjangoAuthState`)
    for auth snapshots and mixins such as ``crud_mixin(..., base=AppState)``.
    """
