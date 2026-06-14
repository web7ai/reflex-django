"""Ordered, idempotent patch application for Reflex integration."""

from __future__ import annotations


def apply_post_rxconfig_patches() -> None:
    """Apply compile and page patches after rxconfig is materialized."""
    from reflex_django.runtime.integration import (
        _patch_app_compile,
        _patch_apply_decorated_pages,
        _patch_assert_in_reflex_dir,
        _patch_compile_or_validate_app,
        _patch_needs_reinit,
        _patch_reflex_compile,
        _patch_reflex_page,
        _patch_vite_config_generation,
    )

    _patch_vite_config_generation()
    _patch_app_compile()
    _patch_compile_or_validate_app()
    _patch_reflex_compile()
    _patch_reflex_page()
    _patch_apply_decorated_pages()
    _patch_assert_in_reflex_dir()
    _patch_needs_reinit()


__all__ = ["apply_post_rxconfig_patches"]
