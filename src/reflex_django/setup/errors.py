"""Typed exceptions for reflex-django configuration and runtime errors."""

from __future__ import annotations


class ReflexDjangoError(Exception):
    """Base exception for reflex-django."""


class ConfigurationError(ReflexDjangoError):
    """Raised when settings or environment configuration is invalid."""


class SpaNotBuiltError(ReflexDjangoError):
    """Raised when a compiled SPA bundle is required but missing on disk."""


class DeprecationRemovedError(ReflexDjangoError):
    """Raised when a removed API is accessed."""


__all__ = [
    "ConfigurationError",
    "DeprecationRemovedError",
    "ReflexDjangoError",
    "SpaNotBuiltError",
]