"""Django-first ``@page`` registration and decorated pages."""

from __future__ import annotations

import importlib
from typing import Any


def _reflex_page_namespace() -> Any | None:
    """Return :class:`reflex.page.PageNamespace` (not the lazy ``rx.page`` function)."""
    try:
        return importlib.import_module("reflex.page")
    except ImportError:
        return None


def _patch_reflex_page() -> None:
    """Bucket ``@page`` / ``@template`` under the mount ``app_name``, not ``""``."""
    page_module = _reflex_page_namespace()
    if page_module is None:
        return

    if getattr(page_module, "_reflex_django_page_patched", False):
        return

    original_page = page_module.page

    def patched_page(*args: Any, **kwargs: Any) -> Any:
        def decorator(render_fn: Any) -> Any:
            from reflex_base.config import get_config

            page_kwargs: dict[str, Any] = {}
            if args:
                page_kwargs["route"] = args[0]
            page_kwargs.update(kwargs)
            if "route" in page_kwargs and page_kwargs["route"] is None:
                page_kwargs.pop("route", None)

            bucket = _resolve_decorated_pages_app_name()
            page_module.DECORATED_PAGES[bucket].append((render_fn, page_kwargs))
            return render_fn

        return decorator

    page_module.page = patched_page  # type: ignore[assignment]
    page_module._reflex_django_page_patched = True
    page_module._reflex_django_page_original = original_page


def _resolve_decorated_pages_app_name() -> str:
    """Return the ``DECORATED_PAGES`` key for Django-first page registration."""
    from reflex_base.config import get_config

    try:
        from reflex_django.mount.config import has_mount_rx_config, resolve_app_name

        if has_mount_rx_config():
            return resolve_app_name()
    except ImportError:
        pass
    return str(get_config().app_name or "")


def _patch_apply_decorated_pages() -> None:
    """Apply decorated pages under the Django ``app_name`` from ``reflex_mount()``."""
    try:
        import reflex.app as reflex_app_module
    except ImportError:
        return

    if getattr(reflex_app_module.App, "_reflex_django_apply_pages_patched", False):
        return

    original = reflex_app_module.App._apply_decorated_pages

    def _apply_decorated_pages(self) -> None:  # noqa: ANN001
        from reflex_django.runtime.app_factory import (
            import_app_entry_module,
            prepare_pages_for_compile,
        )

        import_app_entry_module()
        if getattr(self, "_reflex_django_decorated_pages_applied", False):
            return

        prepare_pages_for_compile()
        self._reflex_django_decorated_pages_applied = True  # type: ignore[attr-defined]

    reflex_app_module.App._apply_decorated_pages = _apply_decorated_pages
    reflex_app_module.App._reflex_django_apply_pages_patched = True
    reflex_app_module.App._reflex_django_apply_pages_original = original
