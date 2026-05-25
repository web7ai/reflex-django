"""Load Reflex apps and page modules from Django settings."""

from __future__ import annotations

import importlib
import importlib.util
import sys
import types
from typing import Any

_SKIP_PAGE_APP_LABELS = frozenset({"reflex_django"})
_CONTRIB_APP_PREFIX = "django."

_APP_INSTANCE: Any | None = None
_IMPORTED_VIEW_MODULES: set[str] = set()

_DJANGO_LED_APP_MODULE = "reflex_django.django_led_app"


def _django_settings() -> Any:
    from django.conf import settings

    return settings


def create_app() -> Any:
    """Built-in factory: return a default :class:`reflex.app.App` for Django-first projects.

    Returns:
        A new Reflex application instance.
    """
    import reflex as rx

    from reflex_django.conf import configure_django

    configure_django()
    return rx.App()


def reflex_app_module_name(app_name: str) -> str:
    """Return the Reflex app module path (``{app_name}.{app_name}``)."""
    return f"{app_name}.{app_name}"


def django_led_app_module_import() -> str:
    """Dotted import path Reflex uses for ``app`` in Django-first mode."""
    return _DJANGO_LED_APP_MODULE


def register_reflex_app_module(app_name: str, app: Any) -> str:
    """Expose *app* on ``sys.modules`` so Reflex can import ``{app_name}.{app_name}:app``.

    Args:
        app_name: Reflex app label from :func:`reflex_django.mount_config.resolve_app_name`.
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

    Override with ``REFLEX_DJANGO_PAGE_PACKAGES`` in settings when needed.
    """
    settings = _django_settings()
    explicit = getattr(settings, "REFLEX_DJANGO_PAGE_PACKAGES", None)
    if explicit:
        return list(explicit)

    if not getattr(settings, "REFLEX_DJANGO_AUTO_DISCOVER_PAGES", True):
        from reflex_django.mount_config import ensure_mount_config_loaded, resolve_app_name

        ensure_mount_config_loaded()
        return [_page_module_name(resolve_app_name(), "views")]

    module_suffix = getattr(settings, "REFLEX_DJANGO_PAGE_MODULE", "views")
    allowlist = getattr(settings, "REFLEX_DJANGO_PAGE_APPS", None)
    from reflex_django.mount_config import ensure_mount_config_loaded, resolve_app_name

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
    from reflex.utils import format as route_format

    from reflex_django.mount_config import resolve_app_name

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
        unevaluated = getattr(app, "_unevaluated_pages", {})
        if DECORATED_PAGES is not None:
            for render, kwargs in DECORATED_PAGES.get(app_name, ()):
                route = kwargs.get("route")
                if route is not None:
                    formatted = route_format.format_route(str(route))
                    if formatted in unevaluated:
                        continue
                app.add_page(render, **kwargs)
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
        from reflex_django.mount_config import resolve_app_name
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
    """Register :data:`~reflex_django.decorators.PAGE_REGISTRY` pages on *app*."""
    from reflex.utils import format as route_format
    from reflex_django.decorators import PAGE_REGISTRY

    for registration in PAGE_REGISTRY:
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

    from reflex_django.mount_config import resolve_app_name

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
    from reflex_django.mount_config import resolve_app_name

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
    from reflex_django.mount_config import ensure_mount_config_loaded, resolve_app_name

    ensure_mount_config_loaded()
    try:
        from reflex_django.rxconfig_bridge import ensure_rxconfig_from_django

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
    """Load :class:`reflex.app.App` via :func:`create_app` and register ``{app}.{app}:app``.

    Returns:
        The Reflex app instance.

    """
    global _APP_INSTANCE
    if _APP_INSTANCE is not None:
        return _APP_INSTANCE

    from reflex_django.mount_config import ensure_mount_config_loaded, resolve_app_name

    ensure_mount_config_loaded()
    app_name = resolve_app_name()

    app = create_app()
    register_reflex_app_module(app_name, app)
    _APP_INSTANCE = app
    return app


def ensure_django_led_app_ready() -> Any:
    """Import pages, build :class:`reflex.app.App`, and apply decorated pages.

    Does not write ``{app_name}/{app_name}.py``; Reflex
    loads :data:`reflex_django.django_led_app.app` instead.

    Returns:
        The configured Reflex app.
    """
    _ensure_runtime_state_classes_registered()
    import_page_packages()
    app = load_app_factory()
    from reflex_django.integration import _ensure_runtime_event_patches
    from reflex_django.mount_config import resolve_app_name
    from reflex_django.plugin import apply_reflex_plugins_to_app

    _ensure_runtime_event_patches()
    apply_reflex_plugins_to_app(app)
    if hasattr(app, "_apply_decorated_pages"):
        migrate_decorated_pages_app_name(resolve_app_name())
        app._apply_decorated_pages()
    sync_page_load_events(app)
    _ensure_optional_api_endpoints(app)
    return app


def _ensure_runtime_state_classes_registered() -> None:
    """Eagerly import substates that the middleware would otherwise register late.

    Some ``reflex_django`` state classes — most notably
    :class:`~reflex_django.reflex_context.DjangoContextState` — are exposed via
    :pep:`562` lazy attribute access on the package and are first imported by
    :func:`reflex_django.state.auth_bridge.maybe_sync_django_context_state`
    when the first WebSocket event fires. That late import registers the class
    as a new substate **after** the Reflex SPA has been compiled, leaving the
    bundle without a matching React dispatcher entry. The next delta the
    server sends for the substate then trips
    ``TypeError: h[<state>] is not a function`` in
    ``.web/build/client/assets/theme-*.js`` and the page is stuck on the
    loading skeleton.

    Pre-importing the affected classes here, before Reflex walks the state
    tree, makes the frontend codegen and the runtime see the same set of
    substates. Each import is best-effort and gated on the same settings the
    runtime checks, so disabling a feature (e.g.
    ``REFLEX_DJANGO_AUTO_LOAD_CONTEXT = False``) still skips the registration.
    """
    try:
        from django.conf import settings
    except Exception:  # noqa: BLE001 — Django may not be configured yet.
        return

    if getattr(settings, "REFLEX_DJANGO_AUTO_LOAD_CONTEXT", True) or getattr(
        settings, "REFLEX_DJANGO_CONTEXT_PROCESSORS", None
    ):
        try:
            from reflex_django.reflex_context import DjangoContextState  # noqa: F401
        except Exception:  # noqa: BLE001 — never fail boot on optional substates.
            import logging

            logging.getLogger("reflex_django.app_factory").exception(
                "Could not pre-register DjangoContextState; the SPA bundle may "
                "be missing a dispatcher entry and trigger "
                "`TypeError: h[...] is not a function` on the first delta."
            )


def _ensure_optional_api_endpoints(app: Any) -> None:
    """Register Reflex's optional Starlette routes (``/_upload``, …) on ``app._api``.

    :meth:`reflex.app.App._add_optional_endpoints` is normally called from
    :func:`reflex.compiler.compiler.compile_app`, which only runs inside the
    SPA export subprocess. In the Django-outer ASGI process we build a fresh
    :class:`~reflex.app.App` via :func:`ensure_django_led_app_ready` without
    compiling it (the SPA is already on disk), so those routes are missing
    from ``app._api`` and ``POST /_upload`` returns ``404 Not Found`` through
    the :class:`~reflex_django.django_outer_dispatcher.DjangoOuterDispatcher`.

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

        logging.getLogger("reflex_django.app_factory").exception(
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
    import reflex_django.django_led_app as django_led_app

    django_led_app._app = None
