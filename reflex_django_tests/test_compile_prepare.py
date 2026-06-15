"""Tests for compile-time page preparation."""

from __future__ import annotations

from unittest import mock

from reflex_django.runtime.app_factory import prepare_pages_for_compile


def test_prepare_pages_for_compile_migrates_and_imports() -> None:
    with mock.patch(
        "reflex_django.runtime.app_factory.migrate_decorated_pages_app_name"
    ) as migrate_mock, mock.patch(
        "reflex_django.runtime.app_factory.import_page_packages",
        return_value=[],
    ) as import_mock, mock.patch(
        "reflex_django.runtime.app_factory.load_app_factory",
    ) as load_mock:
        prepare_pages_for_compile()
        assert migrate_mock.call_count >= 2
        import_mock.assert_called_once()
        load_mock.assert_called_once()
