"""Django bootstrap helpers for reflex-django.

Provides :func:`configure_django`, an idempotent wrapper around
:func:`django.setup` that honors ``DJANGO_SETTINGS_MODULE`` from the environment
and falls back to :mod:`reflex_django.setup.default_settings` when the user did not
configure a project of their own.
"""

from __future__ import annotations

import os
import threading

_DEFAULT_SETTINGS_MODULE = "reflex_django.setup.default_settings"
# Re-entrant: ``django.setup()`` triggers admin autodiscover which can import
# user modules that call ``configure_django()`` again from the same thread.
# A plain ``Lock`` would deadlock; ``RLock`` lets the recursive call return
# after the inner ``apps.loading`` short-circuit below.
_SETUP_LOCK = threading.RLock()
_SETUP_DONE = False


def _settings_already_set() -> bool:
    return bool(os.environ.get("DJANGO_SETTINGS_MODULE"))


def configure_django(settings_module: str | None = None) -> str:
    """Configure Django and return the settings module that was activated.

    The function is idempotent and thread-safe — it can be called from any
    plugin hook or test fixture; repeated calls after the first one are no-ops
    that simply return the already-active settings module.

    Resolution order:

    1. If ``DJANGO_SETTINGS_MODULE`` is already set in the environment, respect
       it (typical for production deployments where the user owns
       ``manage.py`` / ``asgi.py``). ``settings_module`` is ignored in this
       case.
    2. Else, discover from the nearest ``manage.py`` via
       :func:`reflex_django.setup.project.discover_settings_module`.
    3. Else, if ``settings_module`` is provided by the caller, use it.
    4. Else, fall back to :mod:`reflex_django.setup.default_settings`.

    Args:
        settings_module: Optional dotted path to a Django settings module.

    Returns:
        The dotted path of the settings module that was activated.
    """
    global _SETUP_DONE

    with _SETUP_LOCK:
        if not _settings_already_set():
            from reflex_django.setup.project import discover_settings_module

            discovered = discover_settings_module()
            os.environ["DJANGO_SETTINGS_MODULE"] = (
                discovered or settings_module or _DEFAULT_SETTINGS_MODULE
            )

        active = os.environ["DJANGO_SETTINGS_MODULE"]

        # Detect a reentrant call coming from inside ``django.apps.populate()``.
        # This happens when admin autodiscover (or any AppConfig.ready hook)
        # imports a user module that itself calls ``configure_django()`` — the
        # outer call is still in the middle of ``django.setup()`` so
        # ``_SETUP_DONE`` is False, but ``apps.loading`` (or ``apps.ready``)
        # tells us setup is already in flight. This check runs *before* the
        # ``_SETUP_DONE`` short-circuit so reentrant calls don't trigger a
        # nested ``django.setup()`` and a "populate() isn't reentrant" error.
        try:
            from django.apps import apps as _django_apps

            if _django_apps.ready or _django_apps.loading:
                return active
        except Exception:
            pass

        if _SETUP_DONE:
            return active

        from reflex_django.setup.project import ensure_django_project_on_path

        ensure_django_project_on_path()

        import django

        django.setup()
        _SETUP_DONE = True
        try:
            from reflex_django.setup.performance import apply_performance_preset

            apply_performance_preset()
        except Exception:
            pass
        _bootstrap_reflex_integration_for_plugin()
        return active


def _bootstrap_reflex_integration_for_plugin() -> None:
    """Install plugin integration when ``rxconfig`` is loaded in worker processes."""
    try:
        from reflex_django.runtime.integration import install_reflex_django_integration

        install_reflex_django_integration()
    except Exception as ex:
        import warnings

        warnings.warn(
            f"reflex-django integration bootstrap failed: {ex!r}",
            stacklevel=2,
        )


def is_configured() -> bool:
    """Return whether :func:`configure_django` has run successfully.

    Returns:
        True if Django has been set up in the current process.
    """
    return _SETUP_DONE
