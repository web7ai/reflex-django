"""Reflex plugin that wires a Django ASGI backend into a Reflex App."""

from __future__ import annotations

import dataclasses
import os
import warnings
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from reflex_base.plugins.base import Plugin
from reflex_base.utils import console

from reflex_django.asgi import build_django_asgi, make_dispatcher
from reflex_django.conf import configure_django
from reflex_django.prefixes import export_prefix_env, resolve_prefixes
from reflex_django.routing import UrlRoutingMode, resolve_url_routing

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
            **Deprecated** — use ``manage.py`` / ``DJANGO_SETTINGS_MODULE`` or
            manage.py discovery instead.
        backend_prefix: Optional path prefix forwarded to Django for your own
            HTTP routes (e.g. ``"/api"`` when ``ROOT_URLCONF`` includes
            ``path("api/", ...)``). Defaults to ``""`` (no extra prefix).
            List in ``django_prefix`` on :func:`reflex_django.urls.reflex_mount` too.
        admin_prefix: Path prefix for Django Admin (``rxconfig.py`` / plugin only).
            Defaults to ``"/admin"``.
        django_prefix: Path prefixes routed to Django (e.g. ``("/billing", "/api")``).
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
    django_prefix: tuple[str, ...] = ()
    install_event_bridge: bool = True
    install_auth_pages: bool = False

    def __post_init__(self) -> None:
        """Export Django env vars and run :func:`configure_django` when the plugin is built."""
        if self.settings_module is not None:
            warnings.warn(
                "ReflexDjangoPlugin(settings_module=...) is deprecated. "
                "Set DJANGO_SETTINGS_MODULE via manage.py or environment instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            if not os.environ.get("DJANGO_SETTINGS_MODULE"):
                os.environ["DJANGO_SETTINGS_MODULE"] = self.settings_module

        self._export_prefix_env()
        configure_django(self.settings_module)

    def _prefix_config(self):
        prefixes: list[str] = list(self.django_prefix)
        if self.backend_prefix:
            prefixes.append(self.backend_prefix)
        if self.admin_prefix:
            prefixes.append(self.admin_prefix)
        return resolve_prefixes(
            django_prefix=tuple(dict.fromkeys(prefixes)),
        )

    def _export_prefix_env(self) -> None:
        export_prefix_env(self._prefix_config())

    def _all_prefixes(self) -> tuple[str, ...]:
        return self._prefix_config().backend_prefixes_for_asgi()

    def pre_compile(self, **context: Any) -> None:
        """Import pages and inject Vite dev-server proxy rules for Django prefixes."""
        from reflex_django.app_factory import prepare_pages_for_compile

        prepare_pages_for_compile()

        # DJANGO_OUTER never injects Vite→Django proxies: two-port dev matches
        # native ``reflex run`` (UI on Vite, API on backend); single-port uses
        # Django's reverse-proxy instead.
        if resolve_url_routing() == UrlRoutingMode.DJANGO_OUTER:
            return

        from reflex_base import constants
        from reflex_base.config import get_config

        from reflex_django.vite_proxy import (
            _PROXY_PLUGIN_FILENAME,
            patch_vite_config,
            render_proxy_plugin_js,
        )

        prefixes = self._all_prefixes()
        if not prefixes:
            return

        target = get_config().api_url.rstrip("/")

        def _save_proxy_plugin() -> tuple[str, str]:
            return (
                _PROXY_PLUGIN_FILENAME,
                render_proxy_plugin_js(target=target, prefixes=prefixes),
            )

        context["add_save_task"](_save_proxy_plugin)
        context["add_modify_task"](
            constants.ReactRouter.VITE_CONFIG_FILE,
            lambda content: patch_vite_config(
                content, target=target, prefixes=prefixes
            ),
        )

    def post_compile(self, **context: Any) -> None:
        """Attach the Django dispatcher to ``app.api_transformer``."""
        app: App | None = context.get("app")
        if app is None:
            msg = "ReflexDjangoPlugin requires the Reflex App in post_compile context."
            raise RuntimeError(msg)

        self._configure(app)
        self._ensure_vite_dev_proxy_on_disk()
        self._apply_frontend_stability_patches()
        self._warn_if_frontend_dispatchers_out_of_sync()

    def _warn_if_frontend_dispatchers_out_of_sync(self) -> None:
        """Detect stale ``.web/utils/context.js`` after page/state registration changes."""
        from reflex_django.compile_validate import warn_if_frontend_dispatchers_out_of_sync

        warn_if_frontend_dispatchers_out_of_sync()

    def _ensure_vite_dev_proxy_on_disk(self) -> None:
        """Write Vite ``server.proxy`` rules when missing from ``.web/vite.config.js``."""
        try:
            from reflex_django.vite_proxy import ensure_vite_django_dev_proxy_from_config

            ensure_vite_django_dev_proxy_from_config()
        except Exception as exc:
            console.warn(
                "reflex-django could not patch .web/vite.config.js for Django "
                f"path proxies: {exc}. Use http://localhost:<backend_port>/admin "
                "or re-run `python manage.py run_reflex`."
            )

    def _apply_frontend_stability_patches(self) -> None:
        """Patch generated frontend for EventLoopContext and React dedupe issues."""
        from reflex_django.frontend_stability import apply_frontend_stability_after_compile

        apply_frontend_stability_after_compile()

    def _configure(self, app: App) -> None:
        if getattr(app, "_reflex_django_plugin_configured", False):
            return

        if self.settings_module is not None:
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", self.settings_module)
        self._export_prefix_env()

        active_settings = configure_django(self.settings_module)

        self._warn_if_using_auto_settings(active_settings)

        routing_mode = resolve_url_routing()

        # In ``DJANGO_OUTER`` mode Django is the outer ASGI app
        # (:mod:`reflex_django.asgi_entry`) and the Reflex Starlette is mounted
        # under it via :class:`~reflex_django.django_outer_dispatcher.DjangoOuterDispatcher`.
        # The legacy Reflex-led dispatcher must NOT be attached as an
        # ``api_transformer`` because it would try to mount Django *inside* Reflex,
        # causing infinite-recursion-style routing collisions.
        if routing_mode != UrlRoutingMode.DJANGO_OUTER:
            from reflex_django.asgi import django_asgi_application

            django_asgi = django_asgi_application()
            transformer = make_dispatcher(
                django_asgi,
                backend_prefixes=self._all_prefixes(),
                routing_mode=routing_mode,
            )

            existing = _as_sequence(app.api_transformer)
            app.api_transformer = (*existing, transformer)

        if self.install_event_bridge:
            from reflex_django.middleware import DjangoEventBridge
            from reflex_django.upload_patch import apply_upload_router_data_patch

            apply_upload_router_data_patch()
            if not any(
                isinstance(m, DjangoEventBridge) for m in getattr(app, "_middlewares", ())
            ):
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

        from reflex_django.app_factory import sync_page_load_events

        sync_page_load_events(app)

        app._reflex_django_plugin_configured = True  # type: ignore[attr-defined]

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


def apply_reflex_plugins_to_app(app: App) -> None:
    """Run ``post_compile`` for every plugin on *app* (idempotent for reflex-django).

    Django-first apps load via :mod:`reflex_django.django_led_app` before Reflex
    calls :meth:`reflex.app.App.__call__`. Without this, :class:`DjangoEventBridge`
    is never registered and ``self.request`` stays empty in event handlers.
    """
    from reflex_base.config import get_config

    from reflex_django.rxconfig_bridge import ensure_rxconfig_from_django

    # ``rx.App()`` can reset ``get_config().plugins``; restore Django-first plugins.
    ensure_rxconfig_from_django()

    for plugin in get_config().plugins or ():
        post_compile = getattr(plugin, "post_compile", None)
        if callable(post_compile):
            post_compile(app=app)
