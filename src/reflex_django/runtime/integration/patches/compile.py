"""Compile-time hooks: Vite proxy, in-process compile, validation."""

from __future__ import annotations

from typing import Any

from reflex_django.runtime.integration.registry import (
    get_original_compile_or_validate,
    set_original_compile_or_validate,
)


def _finalize_web_dev_layout_safe(*, force: bool = True) -> None:
    """Apply Vite proxy wiring; log failures instead of failing compile."""
    try:
        from reflex_django.dev.vite_proxy import finalize_web_dev_layout

        finalize_web_dev_layout(force=force)
    except Exception as exc:
        import warnings

        warnings.warn(
            f"reflex-django could not finalize Vite dev proxy layout: {exc!r}",
            stacklevel=3,
        )


def _patch_vite_config_generation() -> None:
    """Inject Django proxy rules when Reflex generates ``vite.config.js``."""
    try:
        import reflex.utils.frontend_skeleton as frontend_skeleton
    except ImportError:
        return

    if getattr(frontend_skeleton, "_reflex_django_vite_config_patched", False):
        return

    original = frontend_skeleton._compile_vite_config

    def _compile_vite_config(config: Any) -> str:
        content = original(config)
        try:
            from reflex_django.dev.proxy import dev_uses_separate_ports
            from reflex_django.dev.vite_proxy import (
                patch_vite_config_content,
                resolve_vite_dev_proxy_routes,
            )

            if not dev_uses_separate_ports():
                return content
            routes = resolve_vite_dev_proxy_routes()
            if routes:
                return patch_vite_config_content(content, routes=routes)
        except Exception as exc:
            import warnings

            warnings.warn(
                f"reflex-django could not patch generated vite.config.js: {exc!r}",
                stacklevel=2,
            )
        return content

    frontend_skeleton._compile_vite_config = _compile_vite_config  # type: ignore[assignment]
    frontend_skeleton._reflex_django_vite_config_patched = True


def _patch_app_compile() -> None:
    """Finalize Vite proxy after every ``App._compile`` (incl. backend hot reload)."""
    try:
        from reflex.app import App
    except ImportError:
        return

    if getattr(App, "_reflex_django_app_compile_patched", False):
        return

    original_compile = App._compile

    def _compile(self: Any, *args: Any, **kwargs: Any) -> Any:
        result = original_compile(self, *args, **kwargs)
        _finalize_web_dev_layout_safe(force=True)
        return result

    App._compile = _compile  # type: ignore[method-assign]
    App._reflex_django_app_compile_patched = True


def _patch_compile_or_validate_app() -> None:
    """Restore Vite proxy wiring after every successful Reflex compile."""
    try:
        import reflex.utils.prerequisites as prerequisites
    except ImportError:
        return

    if getattr(prerequisites, "_reflex_django_compile_or_validate_patched", False):
        return

    set_original_compile_or_validate(prerequisites.compile_or_validate_app)
    original_compile_or_validate = get_original_compile_or_validate()

    def compile_or_validate_app(
        compile: bool = False,
        check_if_schema_up_to_date: bool = False,
        prerender_routes: bool = False,
        **kwargs: Any,
    ) -> bool:
        result = original_compile_or_validate(
            compile=compile,
            check_if_schema_up_to_date=check_if_schema_up_to_date,
            prerender_routes=prerender_routes,
            **kwargs,
        )
        return result

    prerequisites.compile_or_validate_app = compile_or_validate_app  # type: ignore[assignment]
    prerequisites._reflex_django_compile_or_validate_patched = True


def _patch_reflex_compile() -> None:
    """Compile in-process and restore the Vite Django dev proxy after compile."""
    try:
        import reflex.reflex as reflex_module
    except ImportError:
        return

    if getattr(reflex_module, "_reflex_django_compile_patched", False):
        return

    original_compile = reflex_module._compile_app

    def _compile_app(*, avoid_dirty_check: bool = True) -> None:
        from reflex_django.runtime.app_factory import load_app_factory, prepare_pages_for_compile
        from reflex_django.runtime.compile_validate import (
            expected_dispatch_keys_from_app,
            invalidate_stale_context_js,
            missing_frontend_dispatchers,
            warn_if_frontend_dispatchers_out_of_sync,
        )

        prepare_pages_for_compile()
        app = load_app_factory()
        from reflex_django.bootstrap.app_setup import apply_reflex_plugins_to_app

        apply_reflex_plugins_to_app(app)
        expected = expected_dispatch_keys_from_app(app)
        if missing_frontend_dispatchers(expected_keys=expected, app=app):
            invalidate_stale_context_js()
            if hasattr(app, "_reflex_django_decorated_pages_applied"):
                delattr(app, "_reflex_django_decorated_pages_applied")
            prepare_pages_for_compile()
            expected = expected_dispatch_keys_from_app(app)
        original_compile(avoid_dirty_check=False)
        missing = missing_frontend_dispatchers(expected_keys=expected, app=app)
        if missing:
            invalidate_stale_context_js()
            if hasattr(app, "_reflex_django_decorated_pages_applied"):
                delattr(app, "_reflex_django_decorated_pages_applied")
            prepare_pages_for_compile()
            expected = expected_dispatch_keys_from_app(app)
            original_compile(avoid_dirty_check=False)
            missing = missing_frontend_dispatchers(expected_keys=expected, app=app)
        warn_if_frontend_dispatchers_out_of_sync(expected_keys=expected, app=app)
        return None

    reflex_module._compile_app = _compile_app  # type: ignore[assignment]
    reflex_module._reflex_django_compile_patched = True
