"""App config that imports @page views during ``ready()`` (simsimai-style ordering)."""

from __future__ import annotations

from django.apps import AppConfig


class TestEarlyPageImportAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "reflex_django_tests.test_early_page_import_app"
    label = "test_early_page_import"

    def ready(self) -> None:
        from reflex_django_tests import test_early_page_import_views  # noqa: F401
