"""Load Reflex apps and page modules for plugin-only integration."""

from __future__ import annotations

import importlib
import importlib.util
import sys
import types
from typing import Any

_IMPORTED_VIEW_MODULES: set[str] = set()


def create_app() -> Any:
    """Return a default :class:`reflex.app.App` after configuring Django."""
    import reflex as rx

    from reflex_django.setup.conf import configure_django

    configure_django()
    return rx.App()


def _page_module_name(app_label: str, module_suffix: str) -> str:
    return f"{app_label}.{module_suffix}"


def _views_module_exists(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ModuleNotFoundError, ValueError):
        return False


def discover_page_modules() -> list[str]:
    """Return page modules to import for ``@page`` / ``@template`` registration."""
    from reflex_django.mount.config import resolve_app_name

    module_suffix = "views"
    try:
        from django.conf import settings

        module_suffix = getattr(settings, "RX_PAGE_MODULE", "views")
    except Exception:
        pass

    primary_app = resolve_app_name()
    if not primary_app:
        return []
    primary_module = _page_module_name(primary_app, module_suffix)
    if _views_module_exists(primary_module):
        return [primary_module]
    return []


def resolve_page_packages() -> list[str]:
    """Return page modules to import for decorator registration."""
    return discover_page_modules()


def _route_registration_rank(route: str | None) -> tuple[int, int, str]:
    if not route:
        return (2, 0, "")
    route_str = str(route)
    if "[..." in route_str or "[[..." in route_str:
        kind = 1
    elif "[" in route_str:
        kind = 0
    else:
        kind = 2
    return (kind, -len(route_str), route_str)


def _sort_page_entries(
    entries: list[tuple[Any, dict[str, Any]]],
) -> list[tuple[Any, dict[str, Any]]]:
    return sorted(
        entries,
        key=lambda item: _route_registration_rank(item[1].get("route")),
    )


def _apply_decorated_pages_to_app(
    app: Any,
    *,
    app_name: str,
    decorated_pages: Any,
) -> None:
    from reflex.utils import format as route_format

    unevaluated = getattr(app, "_unevaluated_pages", {})
    entries = _sort_page_entries(list(decorated_pages.get(app_name, ())))
    for render, kwargs in entries:
        route = kwargs.get("route")
        if route is not None:
            formatted = route_format.format_route(str(route))
            if formatted in unevaluated:
                continue
        app.add_page(render, **kwargs)
        unevaluated = getattr(app, "_unevaluated_pages", {})


def migrate_decorated_pages_app_name(app_name: str | None = None) -> str:
    """Move pages registered under the wrong ``DECORATED_PAGES`` key to *app_name*."""
    try:
        from reflex.page import DECORATED_PAGES
        from reflex_django.mount.config import resolve_app_name
    except ImportError:
        return app_name or ""

    target = (app_name or resolve_app_name()).strip()
    if not target:
        return target

    target_pages = DECORATED_PAGES[target]
    seen_routes: set[str | None] = {
        kwargs.get("route") for _render, kwargs in target_pages
    }

    for key in list(DECORATED_PAGES.keys()):
        if key == target:
            continue
        for entry in DECORATED_PAGES.pop(key, []):
            route = entry[1].get("route")
            if route in seen_routes:
                continue
            target_pages.append(entry)
            seen_routes.add(route)

    deduped: list[tuple[Any, dict[str, Any]]] = []
    seen_routes.clear()
    for entry in target_pages:
        route = entry[1].get("route")
        if route in seen_routes:
            continue
        deduped.append(entry)
        seen_routes.add(route)
    DECORATED_PAGES[target] = deduped

    return target


def apply_page_registry_to_app(app: Any) -> None:
    from reflex.utils import format as route_format
    from reflex_django.pages.decorators import PAGE_REGISTRY

    registrations = sorted(
        PAGE_REGISTRY,
        key=lambda registration: _route_registration_rank(
            registration.route or registration.kwargs.get("route")
        ),
    )
    for registration in registrations:
        route = registration.route or registration.kwargs.get("route")
        if route:
            formatted = route_format.format_route(str(route))
            if formatted in getattr(app, "_unevaluated_pages", {}):
                continue
        app.add_page(registration.render_fn, **registration.kwargs)


def sync_page_load_events(app: Any) -> None:
    try:
        from reflex.page import DECORATED_PAGES
        from reflex.utils import format
        from reflex_base.config import get_config
    except ImportError:
        return

    from reflex_django.mount.config import resolve_app_name

    app_name = migrate_decorated_pages_app_name(resolve_app_name())
    try:
        config_name = get_config().app_name
        if config_name:
            app_name = str(config_name)
    except Exception:
        pass
    for _render, kwargs in DECORATED_PAGES.get(app_name, ()):
        route = kwargs.get("route")
        on_load = kwargs.get("on_load")
        if not route or on_load is None:
            continue
        formatted = format.format_route(str(route))
        handlers = on_load if isinstance(on_load, list) else [on_load]
        if not app._load_events.get(formatted):
            app._load_events[formatted] = list(handlers)


def import_mount_app_views(app_name: str | None = None) -> list[str]:
    from reflex_django.mount.config import resolve_app_name

    name = (app_name or resolve_app_name()).strip()
    if not name:
        return []

    module_name = _page_module_name(name, "views")
    imported: list[str] = []
    if _views_module_exists(module_name):
        if module_name not in _IMPORTED_VIEW_MODULES:
            importlib.import_module(module_name)
            _IMPORTED_VIEW_MODULES.add(module_name)
        imported.append(module_name)
    migrate_decorated_pages_app_name(name)
    return imported


def import_page_packages() -> list[str]:
    from reflex_django.mount.config import ensure_mount_config_loaded, resolve_app_name

    ensure_mount_config_loaded()
    imported: list[str] = []
    for dotted in resolve_page_packages():
        if dotted in _IMPORTED_VIEW_MODULES:
            continue
        importlib.import_module(dotted)
        _IMPORTED_VIEW_MODULES.add(dotted)
        imported.append(dotted)
    migrate_decorated_pages_app_name(resolve_app_name())
    return imported


def _resolve_app_module_import(*, app_name: str | None = None) -> str:
    """Return the dotted path to the on-disk Reflex app module."""
    from reflex_base.config import get_config
    from reflex_django.mount.config import resolve_app_name

    config = get_config()
    module_path = getattr(config, "module", None) or getattr(
        config, "app_module_import", None
    )
    if isinstance(module_path, str) and module_path.strip():
        return module_path.strip()
    name = (app_name or resolve_app_name()).strip()
    if not name:
        msg = "Cannot resolve Reflex app module path (missing app_name in rx.Config)."
        raise RuntimeError(msg)
    return f"{name}.{name}"


def import_app_entry_module(*, app_name: str | None = None) -> types.ModuleType:
    """Import the on-disk Reflex app module so ``app.add_page`` calls run at compile time."""
    from reflex_django.mount.config import ensure_mount_config_loaded

    ensure_mount_config_loaded()
    module_path = _resolve_app_module_import(app_name=app_name)
    cached = sys.modules.get(module_path)
    if cached is not None and not getattr(cached, "__file__", None):
        del sys.modules[module_path]
    return importlib.import_module(module_path)


def load_native_reflex_app() -> Any:
    """Load :class:`reflex.app.App` from the on-disk app module in ``rx.Config``."""
    module = import_app_entry_module()
    app = getattr(module, "app", None)
    if app is None:
        module_path = _resolve_app_module_import()
        msg = f"Module {module_path!r} has no 'app' attribute."
        raise RuntimeError(msg)
    return app


def load_app_factory() -> Any:
    """Load :class:`reflex.app.App` from the user's on-disk app module."""
    from reflex_django.mount.config import ensure_mount_config_loaded

    ensure_mount_config_loaded()
    return load_native_reflex_app()


def _ensure_runtime_state_classes_registered() -> None:
    try:
        from reflex_django.auth.state_builders import get_or_create_django_auth_state

        get_or_create_django_auth_state()
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger("reflex_django.runtime.app_factory").exception(
            "Could not pre-register DjangoAuthState; auth pages may fail to hydrate."
        )


def prepare_pages_for_compile() -> None:
    """Import page modules and register decorated pages on the app."""
    from reflex_django.mount.config import resolve_app_name

    migrate_decorated_pages_app_name(resolve_app_name())
    _ensure_runtime_state_classes_registered()
    import_page_packages()
    app = load_app_factory()
    app_name = migrate_decorated_pages_app_name(resolve_app_name())
    if hasattr(app, "add_page"):
        try:
            from reflex.page import DECORATED_PAGES
        except ImportError:
            DECORATED_PAGES = None  # type: ignore[assignment]
        if DECORATED_PAGES is not None:
            _apply_decorated_pages_to_app(
                app, app_name=app_name, decorated_pages=DECORATED_PAGES
            )
        apply_page_registry_to_app(app)
        app._reflex_django_decorated_pages_applied = True  # type: ignore[attr-defined]
    sync_page_load_events(app)


def ensure_reflex_app_ready() -> Any:
    """Import pages, load the app, and apply Django integration."""
    from reflex_django.bootstrap.app_setup import apply_reflex_plugins_to_app
    from reflex_django.runtime.integration import _ensure_runtime_event_patches

    _ensure_runtime_event_patches()
    prepare_pages_for_compile()
    app = load_app_factory()
    apply_reflex_plugins_to_app(app)
    _ensure_optional_api_endpoints(app)
    return app


def _ensure_optional_api_endpoints(app: Any) -> None:
    if app is None:
        return
    if getattr(app, "_reflex_django_optional_endpoints_applied", False):
        return
    add = getattr(app, "_add_optional_endpoints", None)
    if not callable(add):
        return
    try:
        add()
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger("reflex_django.runtime.app_factory").exception(
            "Failed to register Reflex optional API endpoints (`/_upload`, …)."
        )
        return
    app._reflex_django_optional_endpoints_applied = True  # type: ignore[attr-defined]


def reset_app_factory_cache() -> None:
    """Clear import caches (tests only)."""
    _IMPORTED_VIEW_MODULES.clear()
    from reflex_django.mount.config import clear_mount_registration

    clear_mount_registration()
