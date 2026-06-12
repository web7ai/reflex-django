"""Django AppConfig for the reflex_django built-in app."""

from __future__ import annotations

from django.apps import AppConfig


class ReflexDjangoConfig(AppConfig):
    """Built-in Django app shipped with reflex-django.

    Registered automatically by :mod:`reflex_django.setup.default_settings`; users
    with their own settings module can add ``"reflex_django"`` to
    ``INSTALLED_APPS`` to opt in to admin auto-discovery and serializer
    registration.
    """

    name = "reflex_django"
    label = "reflex_django"
    verbose_name = "Reflex Django"
    default_auto_field = "django.db.models.BigAutoField"  # pyright: ignore[reportAssignmentType]

    def ready(self) -> None:
        from reflex_django.mount.auto import schedule_auto_mount_after_admin

        schedule_auto_mount_after_admin()
