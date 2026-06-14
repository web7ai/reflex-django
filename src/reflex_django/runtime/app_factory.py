"""Load Reflex apps and page modules from Django settings."""

from __future__ import annotations

import importlib
import importlib.util
import sys
import types
import warnings
from pathlib import Path
from typing import Any

_SKIP_PAGE_APP_LABELS = frozenset({"reflex_django"})
_CONTRIB_APP_PREFIX = "django."

_APP_INSTANCE: Any | None = None
_IMPORTED_VIEW_MODULES: set[str] = set()
_ENTRY_MODULE_PENDING_PAGES: list[tuple[Any, dict[str, Any]]] = []

_REFLEX_APP_MODULE = "reflex_django.runtime.reflex_app"
_APP_MODULE_STUB_MARKER = "reflex-django Django-first app module stub"


def _django_settings() -> Any:
    from django.conf import settings

    return settings


def create_app() -> Any:
    """Built-in factory: return a default :class:`reflex.app.App` for Django-first projects.

    Returns:
        A new Reflex application instance.
    """
    import reflex as rx

    from reflex_django.setup.conf import configure_django

    configure_django()
    return rx.App()


def _resolve_user_create_app() -> Any | None:
    """Return ``rx.App`` from ``RX_CREATE_APP`` when configured."""
    try:
        from django.conf import settings
        from django.utils.module_loading import import_string
    except Exception:
        return None

    dotted = getattr(settings, "RX_CREATE_APP", None)
    if not isinstance(dotted, str) or not dotted.strip():
        return None
    target = import_string(dotted.strip())
    return target()


def get_or_create_app() -> Any:
    """Return the singleton :class:`reflex.app.App` for Django-first projects.

    Honors a pre-set :data:`reflex_django.runtime.reflex_app._app`, then
    :data:`~django.conf.settings.RX_CREATE_APP`, else ``rx.App()``.
    """
    global _APP_INSTANCE
    import reflex_django.runtime.reflex_app as reflex_app_module

    if reflex_app_module._app is not None:
        _APP_INSTANCE = reflex_app_module._app
        return reflex_app_module._app

    if _APP_INSTANCE is not None:
        reflex_app_module._app = _APP_INSTANCE
        return _APP_INSTANCE

    user_app = _resolve_user_create_app()
    created = user_app if user_app is not None else create_app()
    if reflex_app_module._app is not None:
        app = reflex_app_module._app
    else:
        app = created
    reflex_app_module._app = app
    _APP_INSTANCE = app
    from reflex_django.mount.config import resolve_app_name

    app_name = resolve_app_name()
    ensure_reflex_app_module_stub(app_name=app_name)
    import_app_entry_module(app_name=app_name)
    _flush_pending_entry_module_pages(app)
    register_reflex_app_module(app_name, app)
    _apply_django_integration_to_app(app)
    return app


def _apply_django_integration_to_app(app: Any) -> None:
    """Attach Django ASGI dispatch and optional Reflex API routes to *app*."""
    from reflex_django.bootstrap.app_setup import apply_reflex_plugins_to_app

    apply_reflex_plugins_to_app(app)
    _ensure_optional_api_endpoints(app)


def reflex_app_module_name(app_name: str) -> str:
    """Return the Reflex app module path (``{app_name}.{app_name}``)."""
    return f"{app_name}.{app_name}"


def reflex_app_module_import() -> str:
    """Dotted import path Reflex uses for ``app`` in Django-first mode."""
    from reflex_django.mount.config import resolve_app_name

    return reflex_app_module_name(resolve_app_name())


def django_led_app_module_import() -> str:
    """Deprecated alias for :func:`reflex_app_module_import`."""
    return reflex_app_module_import()


def register_reflex_app_module(app_name: str, app: Any) -> str:
    """Expose *app* on ``sys.modules`` so Reflex can import ``{app_name}.{app_name}:app``.

    Args:
        app_name: Reflex app label from :func:`reflex_django.mount.config.resolve_app_name`.
        app: The Reflex app instance.

    Returns:
        The registered module name.
    """
    module_name = reflex_app_module_name(app_name)
    module = sys.modules.get(module_name)
    if module is None:
        module = types.ModuleType(module_name)
        sys.modules[module_name] = module
    module.app = app  # type: ignore[attr-defined]
    return module_name


def _format_app_module_stub() -> str:
    return f'''"""Reflex app entry for Django-first projects (auto-maintained by reflex-django).

Pages and state belong in Django ``views.py`` modules. Do not add UI logic here.
"""
# {_APP_MODULE_STUB_MARKER}

from reflex_django.runtime.reflex_app import app

__all__ = ["app"]
'''


def ensure_reflex_app_module_stub(*, app_name: str | None = None) -> Path | None:
    """Materialize ``{app_name}/{app_name}.py`` so Reflex can import the app module.

    Reflex validates ``app_module_import`` with :func:`reflex.utils.misc.get_module_path`,
    which requires a file on disk. Django-first projects use a thin stub that re-exports
    the shared :data:`reflex_django.runtime.reflex_app.app` singleton.

    User-owned ``{app_name}/{app_name}.py`` files are never overwritten once they exist.
    """
    from reflex_django.mount.config import resolve_app_name

    name = (app_name or resolve_app_name()).strip()
    if not name:
        return None

    module_name = reflex_app_module_name(name)
    package, _, module_file = module_name.partition(".")
    if not module_file or package != module_file:
        return None

    settings = _django_settings()
    base = getattr(settings, "BASE_DIR", None)
    root = Path(str(base)).resolve() if base else Path.cwd().resolve()

    package_dir = root / package
    target = package_dir / f"{module_file}.py"
    body = _format_app_module_stub()

    if target.is_file():
        return target

    package_dir.mkdir(parents=True, exist_ok=True)
    init_py = package_dir / "__init__.py"
    if not init_py.is_file():
        init_py.write_text("", encoding="utf-8")
    target.write_text(body, encoding="utf-8")
    return target


def import_app_entry_module(*, app_name: str | None = None) -> types.ModuleType:
    """Import and execute ``{app_name}/{app_name}.py`` from disk.

    A synthetic placeholder in ``sys.modules`` (no ``__file__``) is removed first
    so Python runs the on-disk entry module on cold start instead of returning an
    empty cached module.

    While the singleton app exists, ``app.add_page`` calls are queued and flushed
    via :func:`_flush_pending_entry_module_pages` so entry-module routes register
    on the same pre-compile path as ``@page`` in ``views.py``.
    """
    from reflex_django.mount.config import resolve_app_name

    name = (app_name or resolve_app_name()).strip()
    module_name = reflex_app_module_name(name)
    ensure_reflex_app_module_stub(app_name=name)

    cached = sys.modules.get(module_name)
    if cached is not None and not getattr(cached, "__file__", None):
        del sys.modules[module_name]

    import reflex_django.runtime.reflex_app as reflex_app_module

    app = reflex_app_module._app
    original_add_page = None
    if app is not None and hasattr(app, "add_page"):
        original_add_page = app.add_page

        def queued_add_page(component: Any, **kwargs: Any) -> None:
            _ENTRY_MODULE_PENDING_PAGES.append((component, dict(kwargs)))

        app.add_page = queued_add_page  # type: ignore[method-assign]

    try:
        return importlib.import_module(module_name)
    finally:
        if app is not None and original_add_page is not None:
            app.add_page = original_add_page  # type: ignore[method-assign]


def _route_registration_rank(route: str | None) -> tuple[int, int, str]:
    """Return a sort key where lower values register first (dynamic before static)."""
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


def clear_entry_module_pending_pages() -> None:
    """Clear the entry-module page queue (tests only)."""
    _ENTRY_MODULE_PENDING_PAGES.clear()


def _flush_pending_entry_module_pages(app: Any) -> None:
    """Register queued entry-module ``app.add_page`` calls on *app*."""
    if not _ENTRY_MODULE_PENDING_PAGES or not hasattr(app, "add_page"):
        clear_entry_module_pending_pages()
        return

    from reflex.utils import format as route_format

    unevaluated = getattr(app, "_unevaluated_pages", {})
    for render, kwargs in _sort_page_entries(list(_ENTRY_MODULE_PENDING_PAGES)):
        route = kwargs.get("route")
        if route is not None:
            formatted = route_format.format_route(str(route))
            if formatted in unevaluated:
                continue
        app.add_page(render, **kwargs)
        unevaluated = getattr(app, "_unevaluated_pages", {})
    clear_entry_module_pending_pages()


def _apply_decorated_pages_to_app(
    app: Any,
    *,
    app_name: str,
    decorated_pages: Any,
) -> None:
    """Apply ``DECORATED_PAGES[app_name]`` in Reflex route registration order."""
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


def _page_module_name(app_label: str, module_suffix: str) -> str:
    return f"{app_label}.{module_suffix}"


def _views_module_exists(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ModuleNotFoundError, ValueError):
        return False


def _app_label_from_installed_entry(entry: str) -> str | None:
    """Resolve an ``INSTALLED_APPS`` entry to an app label (package name)."""
    if entry in _SKIP_PAGE_APP_LABELS or entry.startswith(_CONTRIB_APP_PREFIX):
        return None
    try:
        from django.apps import AppConfig
        from django.utils.module_loading import import_string

        suffix = entry.rsplit(".", 1)[-1]
        if "." in entry and suffix[:1].isupper():
            cfg_cls = import_string(entry)
            if isinstance(cfg_cls, type) and issubclass(cfg_cls, AppConfig):
                return cfg_cls.name
    except Exception:
        pass
    return entry


def _iter_installed_app_labels() -> list[str]:
    settings = _django_settings()
    labels: list[str] = []
    seen: set[str] = set()
    for entry in getattr(settings, "INSTALLED_APPS", ()):
        label = _app_label_from_installed_entry(str(entry))
        if label and label not in seen:
            labels.append(label)
            seen.add(label)
    return labels


def discover_page_modules() -> list[str]:
    """Discover ``{app}.views`` modules across ``INSTALLED_APPS`` for ``@template`` / ``@page``.

    Scans project apps (skips ``django.*`` and ``reflex_django``). Importing each module
    runs decorators and registers Reflex routes — no ``urls.py`` imports or ``rxconfig.py``
    page list required.

    Deprecated: import page modules explicitly in ``urls.py`` or use
    ``from reflex_django import app`` with ``app.add_page()``. Auto-discovery will be
    removed in a future major release.
    """
    settings = _django_settings()
    explicit = getattr(settings, "RX_PAGE_PACKAGES", None)
    if explicit:
        return list(explicit)

    if getattr(settings, "RX_AUTO_DISCOVER_PAGES", True):
        warnings.warn(
            "RX_AUTO_DISCOVER_PAGES is deprecated; import page modules "
            "explicitly in urls.py (e.g. `import myapp.views  # noqa: F401`) or "
            "register pages with `from reflex_django import app` and app.add_page(). "
            "Auto-discovery will be removed in a future major release.",
            DeprecationWarning,
            stacklevel=2,
        )

    if not getattr(settings, "RX_AUTO_DISCOVER_PAGES", True):
        from reflex_django.mount.config import ensure_mount_config_loaded, resolve_app_name

        ensure_mount_config_loaded()
        return [_page_module_name(resolve_app_name(), "views")]

    module_suffix = getattr(settings, "RX_PAGE_MODULE", "views")
    allowlist = getattr(settings, "RX_PAGE_APPS", None)
    from reflex_django.mount.config import ensure_mount_config_loaded, resolve_app_name

    ensure_mount_config_loaded()
    primary_app = resolve_app_name()
    primary_module = (
        _page_module_name(primary_app, module_suffix) if primary_app else None
    )

    discovered: list[str] = []
    seen: set[str] = set()

    if primary_module and _views_module_exists(primary_module):
        discovered.append(primary_module)
        seen.add(primary_module)

    for app_label in sorted(_iter_installed_app_labels()):
        if allowlist is not None and app_label not in allowlist:
            continue

        module_name = _page_module_name(app_label, module_suffix)
        if module_name in seen or not _views_module_exists(module_name):
            continue
        discovered.append(module_name)
        seen.add(module_name)

    return discovered


def resolve_page_packages() -> list[str]:
    """Return page modules to import for decorator registration."""
    return discover_page_modules()


def prepare_pages_for_compile() -> None:
    """Import page modules and bucket decorated pages under the mount ``app_name``.

    Call before Reflex compile so ``DECORATED_PAGES`` and backend substates match
    the compiled ``.web/utils/context.js`` dispatch map (avoids
    ``dispatch is not a function`` in the browser).

    Adds only routes not already present on the app, so calling this after
    :func:`ensure_django_led_app_ready` (or repeatedly during Reflex plugin
    ``post_compile`` hooks) does not emit ``Page X is being redefined with
    the same component.`` warnings from :meth:`reflex.app.App.add_page`.
    """
    from reflex_django.mount.config import resolve_app_name

    migrate_decorated_pages_app_name(resolve_app_name())
    _ensure_runtime_state_classes_registered()
    from reflex_django.auth.registry import ensure_auth_pages_registered

    ensure_auth_pages_registered()
    import_page_packages()
    app = load_app_factory()
    import_app_entry_module()
    _flush_pending_entry_module_pages(app)
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


def migrate_decorated_pages_app_name(app_name: str | None = None) -> str:
    """Move pages registered under the wrong ``DECORATED_PAGES`` key to *app_name*.

    ``@page`` / ``@template`` call :func:`reflex.page`, which buckets decorators
    by :func:`reflex_base.config.get_config`.app_name at import time. In
    Django-first projects that name is often still ``""`` when ``urls.py`` imports
    ``views.py``, so pages land in ``DECORATED_PAGES[""]`` while compile later
    reads ``DECORATED_PAGES["demo"]`` — resulting in a blank UI and
    ``dispatch is not a function`` frontend errors.
    """
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
    """Register :data:`~reflex_django.pages.decorators.PAGE_REGISTRY` pages on *app*."""
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
    """Ensure ``app._load_events`` matches ``on_load`` from decorated pages.

    Reflex stores page ``on_load`` handlers when :meth:`reflex.app.App.add_page`
    runs during compile. In Django-first mode the app can be prepared before
    compile or decorated pages can be registered after an early ``add_page``
    pass; this syncs ``DECORATED_PAGES`` metadata onto the live app instance.
    """
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
    """Import ``{app_name}.views`` during ``reflex_mount()`` without re-importing urls."""
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
    """Import discovered page modules so ``@template`` / ``@page`` decorators run.

    Returns:
        Dotted module paths that were imported successfully.
    """
    from reflex_django.mount.config import ensure_mount_config_loaded, resolve_app_name

    ensure_mount_config_loaded()
    try:
        from reflex_django.setup.rxconfig_bridge import ensure_rxconfig_from_django

        ensure_rxconfig_from_django()
    except Exception:
        pass

    imported: list[str] = []
    for dotted in resolve_page_packages():
        if dotted in _IMPORTED_VIEW_MODULES:
            continue
        importlib.import_module(dotted)
        _IMPORTED_VIEW_MODULES.add(dotted)
        imported.append(dotted)
    migrate_decorated_pages_app_name(resolve_app_name())
    return imported


def load_app_factory() -> Any:
    """Load :class:`reflex.app.App` via :func:`get_or_create_app`.

    Returns:
        The Reflex app instance.

    """
    from reflex_django.mount.config import ensure_mount_config_loaded

    ensure_mount_config_loaded()
    return get_or_create_app()


def ensure_django_led_app_ready() -> Any:
    """Import pages, build :class:`reflex.app.App`, and apply decorated pages.

    Does not write ``{app_name}/{app_name}.py``; Reflex
    loads :data:`reflex_django.runtime.reflex_app.app` instead.

    Returns:
        The configured Reflex app.
    """
    from reflex_django.runtime.integration import _ensure_runtime_event_patches
    from reflex_django.bootstrap.app_setup import apply_reflex_plugins_to_app

    _ensure_runtime_event_patches()
    # prepare_pages_for_compile deduplicates routes already registered by
    # @page / @template at import time (avoids "Page X is being redefined").
    prepare_pages_for_compile()
    app = load_app_factory()
    apply_reflex_plugins_to_app(app)
    _ensure_optional_api_endpoints(app)
    return app


def _ensure_runtime_state_classes_registered() -> None:
    """Eagerly import substates that the middleware would otherwise register late.

    Pre-importing affected classes before Reflex walks the state tree keeps the
    frontend codegen and runtime in sync (avoids missing dispatcher entries).
    """
    try:
        from reflex_django.auth.state_builders import get_or_create_django_auth_state

        get_or_create_django_auth_state()
    except Exception:  # noqa: BLE001 — never fail boot on optional substates.
        import logging

        logging.getLogger("reflex_django.runtime.app_factory").exception(
            "Could not pre-register DjangoAuthState; auth pages may fail to hydrate."
        )


def _ensure_optional_api_endpoints(app: Any) -> None:
    """Register Reflex's optional Starlette routes (``/_upload``, …) on ``app._api``.

    :meth:`reflex.app.App._add_optional_endpoints` is normally called from
    :func:`reflex.compiler.compiler.compile_app`, which only runs inside the
    SPA export subprocess. In the Django-outer ASGI process we build a fresh
    :class:`~reflex.app.App` via :func:`ensure_django_led_app_ready` without
    compiling it (the SPA is already on disk), so those routes are missing
    from ``app._api`` and ``POST /_upload`` returns ``404 Not Found`` through
    the :class:`~reflex_django.asgi.django_outer.DjangoOuterDispatcher`.

    The check ``Upload.is_used or upload_is_used_marker.exists()`` makes the
    method a no-op when no page uses :func:`rx.upload`, so it is safe to
    always invoke. A per-app guard keeps it idempotent across repeat calls
    (e.g. plugin ``post_compile`` re-invocations during dev).
    """
    if app is None:
        return
    if getattr(app, "_reflex_django_optional_endpoints_applied", False):
        return
    add = getattr(app, "_add_optional_endpoints", None)
    if not callable(add):
        return
    try:
        add()
    except Exception:  # noqa: BLE001 — optional endpoints must not fail boot.
        import logging

        logging.getLogger("reflex_django.runtime.app_factory").exception(
            "Failed to register Reflex optional API endpoints (`/_upload`, …) — "
            "uploads and codespace auth may return 404."
        )
        return
    app._reflex_django_optional_endpoints_applied = True  # type: ignore[attr-defined]


def reset_app_factory_cache() -> None:
    """Clear cached app instance (tests only)."""
    global _APP_INSTANCE
    if _APP_INSTANCE is not None:
        if hasattr(_APP_INSTANCE, "_reflex_django_decorated_pages_applied"):
            delattr(_APP_INSTANCE, "_reflex_django_decorated_pages_applied")
    _APP_INSTANCE = None
    _IMPORTED_VIEW_MODULES.clear()
    clear_entry_module_pending_pages()
    import reflex_django.runtime.reflex_app as reflex_app

    reflex_app._app = None
    try:
        from reflex_django.mount.config import resolve_app_name

        module_name = reflex_app_module_name(resolve_app_name())
        sys.modules.pop(module_name, None)
    except Exception:  # noqa: BLE001 — test cleanup only.
        pass
    from reflex_django.mount.auto import clear_auto_mount_state

    clear_auto_mount_state()
