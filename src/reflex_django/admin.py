"""Thin wrappers over :mod:`django.contrib.admin` for reflex-django.

Importing :mod:`reflex_django.admin` triggers Django setup so registering
models at module top-level is safe.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from reflex_django.conf import configure_django

configure_django()

from django.contrib import admin as _admin  # noqa: E402

if TYPE_CHECKING:
    from django.db.models import Model

# Re-export the configured admin site so user code can do
# ``from reflex_django.admin import site`` and add custom views.
site = _admin.site


def register(
    model: type[Model],
    admin_class: type[_admin.ModelAdmin] | None = None,
    **options: Any,
) -> type[_admin.ModelAdmin]:
    """Register ``model`` on the default admin site.

    A drop-in helper for :func:`django.contrib.admin.site.register` that
    returns the registered admin class (or a generated default) so callers can
    keep a reference.

    Args:
        model: The Django model class to register.
        admin_class: Optional :class:`django.contrib.admin.ModelAdmin`
            subclass. When ``None``, a minimal default is generated.
        **options: Additional class attributes applied to the generated admin
            (ignored when ``admin_class`` is supplied).

    Returns:
        The :class:`django.contrib.admin.ModelAdmin` subclass used for the
        registration.
    """
    if admin_class is None:
        admin_class = type(
            f"{model.__name__}Admin",
            (_admin.ModelAdmin,),
            dict(options),
        )
    site.register(model, admin_class)
    return admin_class


__all__ = ["register", "site"]
