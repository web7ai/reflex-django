"""Reflex :class:`reflex.state.State` helpers for Django's active locale."""

from __future__ import annotations

import reflex as rx
from reflex_django.context import current_language, current_request


class DjangoI18nState(rx.State):
    """Snapshot of Django's active language for Reflex UI (selectors, labels).

    Call :meth:`sync_from_django` from ``on_load`` or after changing locale
    (e.g. after returning from Django's ``set_language`` view).
    """

    django_language_code: str = ""
    django_language_bidi: bool = False

    async def refresh_django_i18n_fields(self) -> None:
        """Update language fields from :func:`~reflex_django.current_language`.

        Callable from any coroutine while the event bridge has bound a request.
        """
        from django.utils import translation

        req = current_request()
        lc = getattr(req, "LANGUAGE_CODE", None) if req is not None else None
        if lc:
            self.django_language_code = str(lc)
        else:
            self.django_language_code = current_language()
        self.django_language_bidi = translation.get_language_bidi()

    @rx.event
    async def sync_from_django(self) -> None:
        """Refresh :attr:`django_language_code` and :attr:`django_language_bidi`."""
        await self.refresh_django_i18n_fields()


__all__ = ["DjangoI18nState"]
