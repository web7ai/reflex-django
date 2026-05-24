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


def import_page_packages() -> list[str]:
    """Import discovered page modules so ``@template`` / ``@page`` decorators run.

    Returns:
        Dotted module paths that were imported successfully.
    """
    imported: list[str] = []
    for dotted in resolve_page_packages():
        importlib.import_module(dotted)
        imported.append(dotted)
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
    import_page_packages()
    app = load_app_factory()
    if hasattr(app, "_apply_decorated_pages"):
        app._apply_decorated_pages()
    return app


def reset_app_factory_cache() -> None:
    """Clear cached app instance (tests only)."""
    global _APP_INSTANCE
    _APP_INSTANCE = None
    import reflex_django.django_led_app as django_led_app

    django_led_app._app = None
