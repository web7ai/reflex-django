"""Canonical ORM API handler assembly (load, save, refresh, etc.)."""

from __future__ import annotations

from typing import Any

from reflex_django.state.constants import (
    ACTION_DELETE,
    ACTION_LOAD_LIST,
    ACTION_SAVE,
    ACTION_START_EDIT,
)
from reflex_django.state.options import ModelStateOptions

from reflex_django.state.assembly.meta import bind_event


def _assemble_orm_api_handlers(
    namespace: dict[str, Any],
    options: ModelStateOptions,
    *,
    qualname: str,
) -> None:
    """Register canonical ORM API handlers (load, save, refresh, etc.)."""
    lr_save = ACTION_SAVE in options.login_required_actions
    lr_delete = ACTION_DELETE in options.login_required_actions
    lr_start = ACTION_START_EDIT in options.login_required_actions
    lr_load = ACTION_LOAD_LIST in options.login_required_actions

    if "load" not in namespace:

        async def load_impl(self: Any, pk: int) -> None:
            await self.dispatch(ACTION_START_EDIT, pk=int(pk))

        load_impl.__name__ = "load"
        load_impl.__qualname__ = f"{qualname}.load"
        namespace["load"] = bind_event(load_impl, login_required=lr_start)

    if "save" not in namespace:

        async def save_impl(self: Any) -> None:
            await self.dispatch(ACTION_SAVE)

        save_impl.__name__ = "save"
        save_impl.__qualname__ = f"{qualname}.save"
        namespace["save"] = bind_event(save_impl, login_required=lr_save)

    if "create" not in namespace:

        async def create_impl(self: Any) -> None:
            setattr(self, options.editing_var, -1)
            await self.dispatch(ACTION_SAVE)

        create_impl.__name__ = "create"
        create_impl.__qualname__ = f"{qualname}.create"
        namespace["create"] = bind_event(create_impl, login_required=lr_save)

    if "delete" not in namespace:

        async def delete_impl(self: Any, pk: int | None = None) -> None:
            resolved = pk
            if resolved is None:
                resolved = getattr(self, options.editing_var, -1)
            if resolved is None or int(resolved) < 0:
                return
            await self.dispatch(ACTION_DELETE, pk=int(resolved))

        delete_impl.__name__ = "delete"
        delete_impl.__qualname__ = f"{qualname}.delete"
        namespace["delete"] = bind_event(delete_impl, login_required=lr_delete)

    if "refresh" not in namespace:

        async def refresh_impl(self: Any) -> None:
            await self.dispatch(ACTION_LOAD_LIST)

        refresh_impl.__name__ = "refresh"
        refresh_impl.__qualname__ = f"{qualname}.refresh"
        namespace["refresh"] = bind_event(refresh_impl, login_required=lr_load)

    if "filter" not in namespace:

        async def filter_impl(self: Any, **kwargs: Any) -> None:
            self._queryset_filter = dict(kwargs)
            await self.dispatch(ACTION_LOAD_LIST)

        filter_impl.__name__ = "filter"
        filter_impl.__qualname__ = f"{qualname}.filter"
        namespace["filter"] = bind_event(filter_impl, login_required=lr_load)

    if "clear_filter" not in namespace:

        async def clear_filter_impl(self: Any) -> None:
            self._queryset_filter = None
            await self.dispatch(ACTION_LOAD_LIST)

        clear_filter_impl.__name__ = "clear_filter"
        clear_filter_impl.__qualname__ = f"{qualname}.clear_filter"
        namespace["clear_filter"] = bind_event(clear_filter_impl, login_required=lr_load)

    if "paginate" not in namespace:

        async def paginate_impl(
            self: Any,
            *,
            page: int | None = None,
            page_size: int | None = None,
        ) -> None:
            opts = self.get_options()
            if opts.paginate_by is None:
                await self.dispatch(ACTION_LOAD_LIST)
                return
            if page_size is not None:
                clamped = min(max(1, int(page_size)), opts.max_page_size)
                setattr(self, opts.page_size_var, clamped)
            if page is not None:
                setattr(self, opts.page_var, max(1, int(page)))
                self.on_page_change(int(page))
            await self.dispatch(ACTION_LOAD_LIST)

        paginate_impl.__name__ = "paginate"
        paginate_impl.__qualname__ = f"{qualname}.paginate"
        namespace["paginate"] = bind_event(paginate_impl, login_required=lr_load)
