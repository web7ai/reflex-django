"""Ordered, idempotent patch application for Reflex integration."""

from __future__ import annotations


def apply_post_rxconfig_patches() -> None:
    """Apply compile and page patches after rxconfig is materialized."""
    from reflex_django.runtime.integration.registry import install_post_rxconfig_patches

    install_post_rxconfig_patches()


__all__ = ["apply_post_rxconfig_patches"]
