"""Reflex plugin that wires a Django ASGI backend into a Reflex App."""

from __future__ import annotations

import dataclasses
import os
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from reflex_base.plugins.base import Plugin
from reflex_base.utils import console

from reflex_django.asgi import build_django_asgi, make_dispatcher
from reflex_django.conf import configure_django

if TYPE_CHECKING:
    from reflex.app import App


def _as_sequence(value: Any) -> tuple[Any, ...]:
    """Normalize an api_transformer-shaped value into a flat tuple.

    Args:
        value: ``None``, a single ASGI callable / Starlette app, or a sequence
            of them — matching :attr:`reflex.app.App.api_transformer`'s shape.

    Returns:
        A flat tuple of zero or more transformers.
    """
    if value is None:
        return ()
    if isinstance(value, Sequence) and not callable(value):
        return tuple(value)
    return (value,)


@dataclasses.dataclass(kw_only=True)
class ReflexDjangoPlugin(Plugin):
    """Mount a Django ASGI backend on a Reflex App.

    Attributes:
        settings_module: Optional dotted path to a Django settings module.
            When ``None`` (the default), the plugin uses
            ``reflex_django.default_settings`` unless ``DJANGO_SETTINGS_MODULE``
            is already set in the environment. When you pass a value here, it is
            applied via ``setdefault`` before :func:`reflex_django.conf.configure_django`
            runs in :meth:`__post_init__` (so gettext and other Django imports in
            your Reflex module work at compile time).
        backend_prefix: Optional path prefix forwarded to Django for your own
            HTTP routes (e.g. ``"/api"`` when ``ROOT_URLCONF`` includes
            ``path("api/", ...)``). Defaults to ``""`` (no extra prefix).
        admin_prefix: Path prefix for Django Admin. Defaults to ``"/admin"``.
        extra_prefixes: Additional path prefixes that should be routed to
            Django (e.g. ``("/billing",)``).
        install_event_bridge: Whether to register :class:`DjangoEventBridge`
            as a Reflex event middleware. When ``True`` (the default), Reflex
            Socket.IO events see ``current_user()``, ``current_session()`` etc.
        install_auth_pages: When ``True``, call
            :func:`reflex_django.auth.autoload` during plugin setup so canned
            login/register/reset pages are registered. Prefer calling
            :func:`reflex_django.auth.add_auth_pages` explicitly in your app
            module for clarity.
    """

    settings_module: str | None = None
    backend_prefix: str = ""
    admin_prefix: str = "/admin"
    extra_prefixes: tuple[str, ...] = ()
    install_event_bridge: bool = True
    install_auth_pages: bool = False

    def __post_init__(self) -> None:
        """Export Django env vars and run :func:`configure_django` when the plugin is built.

        ``rxconfig.py`` is imported (and ``Config`` is constructed) before Reflex
        calls :func:`~reflex.utils.prerequisites.get_app`, which imports the
        user's ``<app>.<app>`` module. Calling :func:`configure_django` here lets
        that module use Django APIs such as :func:`django.utils.translation.gettext`
        at import time (including Reflex compile) without a manual bootstrap
        block in application code.
        """
        if self.settings_module is not None:
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", self.settings_module)
        bp = (self.backend_prefix or "").strip()
        if bp:
            os.environ.setdefault("REFLEX_DJANGO_API_PREFIX", bp)
        os.environ.setdefault("REFLEX_DJANGO_ADMIN_PREFIX", self.admin_prefix)
        configure_django(self.settings_module)

    def _all_prefixes(self) -> tuple[str, ...]:
        parts: list[str] = []
        bp = (self.backend_prefix or "").strip()
        if bp:
            parts.append(bp)
        parts.append(self.admin_prefix)
        return (*parts, *self._static_prefixes(), *self.extra_prefixes)

    @staticmethod
    def _static_prefixes() -> tuple[str, ...]:
        """Return ``STATIC_URL`` as a prefix tuple when staticfiles is enabled.

        ``configure_django`` must have run before this is called so
        :mod:`django.conf.settings` is populated. Returns an empty tuple when
        the user disables staticfiles (no ``django.contrib.staticfiles`` in
        ``INSTALLED_APPS``) or sets ``STATIC_URL`` to a fully-qualified URL
        (e.g., a CDN — those are served externally, not by Django).
        """
        try:
            from django.conf import settings
        except Exception:
            return ()

        if "django.contrib.staticfiles" not in getattr(settings, "INSTALLED_APPS", ()):
            return ()

        url = getattr(settings, "STATIC_URL", None)
        if not isinstance(url, str) or not url:
            return ()
        # Skip absolute URLs (CDN-hosted statics) — only forward path prefixes.
        if "://" in url:
            return ()
        return (url,)

    def pre_compile(self, **context: Any) -> None:
        """Inject Vite dev-server proxy rules for Django path prefixes."""
        from reflex_base import constants
        from reflex_base.config import get_config

        from reflex_django.vite_proxy import inject_vite_dev_proxy

        prefixes = self._all_prefixes()
        if not prefixes:
            return

        target = get_config().api_url.rstrip("/")
        context["add_modify_task"](
            constants.ReactRouter.VITE_CONFIG_FILE,
            lambda content: inject_vite_dev_proxy(
                content, target=target, prefixes=prefixes
            ),
        )

    def post_compile(self, **context: Any) -> None:
        """Attach the Django dispatcher to ``app.api_transformer``.

        Runs after :meth:`reflex.app.App._compile` and before
        :meth:`reflex.app.App.__call__` builds the final ASGI app, which is
        when ``api_transformer`` is consulted.

        Args:
            context: Plugin context provided by the Reflex compiler. Expects
                ``context["app"]`` to be the active :class:`reflex.app.App`.

        Raises:
            RuntimeError: If the Reflex app instance is missing from the
                plugin context.
        """
        app: App | None = context.get("app")
        if app is None:
            msg = "ReflexDjangoPlugin requires the Reflex App in post_compile context."
            raise RuntimeError(msg)

        self._configure(app)

    def _configure(self, app: App) -> None:
        # Path prefixes and DJANGO_SETTINGS_MODULE were already exported in
        # __post_init__; redo the setdefaults here so direct callers (tests,
        # custom plugin runners that bypass dataclass init) still get them.
        if self.settings_module is not None:
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", self.settings_module)
        bp = (self.backend_prefix or "").strip()
        if bp:
            os.environ.setdefault("REFLEX_DJANGO_API_PREFIX", bp)
        os.environ.setdefault("REFLEX_DJANGO_ADMIN_PREFIX", self.admin_prefix)

        active_settings = configure_django(self.settings_module)

        self._warn_if_using_auto_settings(active_settings)

        django_asgi = build_django_asgi()
        transformer = make_dispatcher(
            django_asgi,
            backend_prefixes=self._all_prefixes(),
        )

        existing = _as_sequence(app.api_transformer)
        app.api_transformer = (*existing, transformer)

        if self.install_event_bridge:
            from reflex_django.middleware import DjangoEventBridge
            from reflex_django.upload_patch import apply_upload_router_data_patch

            apply_upload_router_data_patch()
            app.add_middleware(DjangoEventBridge())

        if self.install_auth_pages:
            try:
                from reflex_django.auth import autoload

                autoload()
            except Exception as exc:
                console.warn(
                    "reflex-django install_auth_pages=True but autoload failed: "
                    f"{exc}. Call add_auth_pages(app) in your app module instead."
                )

    @staticmethod
    def _warn_if_using_auto_settings(settings_module: str) -> None:
        try:
            from django.conf import settings

            auto = getattr(settings, "REFLEX_DJANGO_AUTO_SETTINGS", False)
        except Exception:
            return

        if auto:
            console.warn(
                "reflex-django is using bundled default settings "
                f"({settings_module!r}). Set DJANGO_SETTINGS_MODULE to your "
                "own settings module (with a stable SECRET_KEY) before "
                "deploying to production."
            )
