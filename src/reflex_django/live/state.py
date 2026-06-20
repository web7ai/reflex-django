"""``LiveListMixin`` - opt-in live list updates for ``ModelState``.

Mix into a ``ModelState`` and start the ``live_subscribe`` background event, for
example from ``on_load``. The handler subscribes to the model's change stream
and patches the list var in place as rows are created, updated, or deleted by
any connection, reusing the same incremental patch helpers as the local CRUD
path.

Live updates respect the state's scoped queryset, so a user only receives rows
they are allowed to see. User-scoped models therefore require the session's user
to be resolvable in the background task; for request-scoped querysets that need
a bound request, prefer a periodic ``refresh_list`` instead.
"""

from __future__ import annotations

import reflex as rx

from reflex_django.live.broadcaster import live_broadcaster
from reflex_django.live.change import ModelChange
from reflex_django.live.signals import model_label, register_live_model


class LiveListMixin:
    """Adds a background subscription that keeps the list var live."""

    async def apply_live_change(self, change: ModelChange) -> None:
        """Apply a single broadcast change to this state's list var."""
        opts = self.get_options()  # type: ignore[attr-defined]
        if change.is_delete:
            self.remove_list_row(opts, change.pk)  # type: ignore[attr-defined]
            return

        queryset = self.get_scoped_queryset()  # type: ignore[attr-defined]
        instance = await queryset.filter(pk=change.pk).afirst()
        if instance is None:
            # Out of this user's scope (or already gone): ensure it is not shown.
            self.remove_list_row(opts, change.pk)  # type: ignore[attr-defined]
            return

        row = await self.serialize_instance(None, instance)  # type: ignore[attr-defined]
        self.patch_list_row(opts, row, was_create=change.is_create)  # type: ignore[attr-defined]

    @rx.event(background=True)
    async def live_subscribe(self):
        """Background event: stream model changes into the list var.

        Loops for the lifetime of the connection. Reflex cancels the task when
        the client disconnects; the ``finally`` block then unsubscribes.
        """
        opts = self.get_options()  # type: ignore[attr-defined]
        register_live_model(opts.model)
        label = model_label(opts.model)
        broadcaster = live_broadcaster()
        queue = broadcaster.subscribe(label)
        try:
            while True:
                change: ModelChange = await queue.get()
                async with self:
                    await self.apply_live_change(change)
        finally:
            broadcaster.unsubscribe(label, queue)


__all__ = ["LiveListMixin"]
