"""List feature assembly: pagination, search, and ordering handlers."""

from __future__ import annotations

from typing import Any

from reflex_django.state.constants import ACTION_LOAD_LIST
from reflex_django.state.options import ModelStateOptions

from reflex_django.state.assembly.meta import bind_event, inject_var_default


def _assemble_list_features(
    namespace: dict[str, Any],
    options: ModelStateOptions,
    *,
    bases: tuple[Any, ...],
    qualname: str,
) -> None:
    """Inject pagination, search, and ordering vars/events when enabled in Meta."""
    annotations = dict(namespace.get("__annotations__", {}))
    lr_load = ACTION_LOAD_LIST in options.login_required_actions

    if options.paginate_by is not None:
        inject_var_default(namespace, annotations, bases, options.page_var, int, 1)
        # Always seed page_size from ``paginate_by`` on the concrete class (``ModelState``
        # declares ``page_size = 0`` for typing; skipping here left page size at 1).
        if options.page_size_var not in namespace:
            annotations[options.page_size_var] = int
        namespace[options.page_size_var] = options.paginate_by
        inject_var_default(namespace, annotations, bases, options.total_count_var, int, 0)
        inject_var_default(namespace, annotations, bases, options.page_count_var, int, 0)

    if options.search_fields:
        inject_var_default(namespace, annotations, bases, options.search_var, str, "")

    if options.allow_dynamic_ordering:
        default_order = options.ordering[0] if options.ordering else ""
        inject_var_default(
            namespace, annotations, bases, options.ordering_var, str, default_order
        )

    namespace["__annotations__"] = annotations

    async def reload_list(self: Any) -> None:
        await getattr(self, options.load_method)()

    if options.paginate_by is not None:

        if "next_page" not in namespace:

            async def next_page_impl(self: Any) -> None:
                opts = self.get_options()
                page = int(getattr(self, opts.page_var))
                page_count = int(getattr(self, opts.page_count_var))
                if page < page_count:
                    setattr(self, opts.page_var, page + 1)
                    self.on_page_change(page + 1)
                    await reload_list(self)

            next_page_impl.__name__ = "next_page"
            next_page_impl.__qualname__ = f"{qualname}.next_page"
            namespace["next_page"] = bind_event(next_page_impl, login_required=lr_load)

        if "prev_page" not in namespace:

            async def prev_page_impl(self: Any) -> None:
                opts = self.get_options()
                page = int(getattr(self, opts.page_var))
                if page > 1:
                    setattr(self, opts.page_var, page - 1)
                    self.on_page_change(page - 1)
                    await reload_list(self)

            prev_page_impl.__name__ = "prev_page"
            prev_page_impl.__qualname__ = f"{qualname}.prev_page"
            namespace["prev_page"] = bind_event(prev_page_impl, login_required=lr_load)

        if "go_to_page" not in namespace:

            async def go_to_page_impl(self: Any, page: int) -> None:
                opts = self.get_options()
                page_count = max(1, int(getattr(self, opts.page_count_var)))
                clamped = max(1, min(int(page), page_count))
                setattr(self, opts.page_var, clamped)
                self.on_page_change(clamped)
                await reload_list(self)

            go_to_page_impl.__name__ = "go_to_page"
            go_to_page_impl.__qualname__ = f"{qualname}.go_to_page"
            namespace["go_to_page"] = bind_event(go_to_page_impl, login_required=lr_load)

        if "set_page_size" not in namespace:

            async def set_page_size_impl(self: Any, size: int) -> None:
                opts = self.get_options()
                clamped = min(max(1, int(size)), opts.max_page_size)
                setattr(self, opts.page_size_var, clamped)
                setattr(self, opts.page_var, 1)
                self.on_page_change(1)
                await reload_list(self)

            set_page_size_impl.__name__ = "set_page_size"
            set_page_size_impl.__qualname__ = f"{qualname}.set_page_size"
            namespace["set_page_size"] = bind_event(set_page_size_impl, login_required=lr_load)

    if options.search_fields:
        set_search_name = f"set_{options.search_var}"

        if set_search_name not in namespace:

            async def set_search_impl(self: Any, value: str) -> None:
                setattr(self, options.search_var, str(value))
                self.reset_page()
                await reload_list(self)

            set_search_impl.__name__ = set_search_name
            set_search_impl.__qualname__ = f"{qualname}.{set_search_name}"
            namespace[set_search_name] = bind_event(set_search_impl, login_required=lr_load)

        clear_search_name = f"clear_{options.search_var}"

        if clear_search_name not in namespace:

            async def clear_search_impl(self: Any) -> None:
                setattr(self, options.search_var, "")
                self.reset_page()
                await reload_list(self)

            clear_search_impl.__name__ = clear_search_name
            clear_search_impl.__qualname__ = f"{qualname}.{clear_search_name}"
            namespace[clear_search_name] = bind_event(clear_search_impl, login_required=lr_load)

    if options.allow_dynamic_ordering:
        set_ordering_name = f"set_{options.ordering_var}"

        if set_ordering_name not in namespace:

            async def set_ordering_impl(self: Any, value: str) -> None:
                setattr(self, options.ordering_var, str(value).strip())
                self.reset_page()
                await reload_list(self)

            set_ordering_impl.__name__ = set_ordering_name
            set_ordering_impl.__qualname__ = f"{qualname}.{set_ordering_name}"
            namespace[set_ordering_name] = bind_event(set_ordering_impl, login_required=lr_load)
