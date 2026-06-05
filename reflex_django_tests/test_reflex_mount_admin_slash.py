"""Ensure /admin without trailing slash is not swallowed by reflex_mount."""

from __future__ import annotations

import pytest
from django.test import Client
from django.urls import clear_url_caches

from reflex_django.conf import configure_django


@pytest.fixture
def django_client(monkeypatch: pytest.MonkeyPatch) -> Client:
    configure_django()
    monkeypatch.setattr(
        "django.conf.settings.ROOT_URLCONF",
        "reflex_django_tests.test_reflex_mount_admin_urls",
        raising=False,
    )
    clear_url_caches()
    return Client(HTTP_HOST="localhost")


def test_admin_without_slash_redirects_not_mount(django_client: Client) -> None:
    response = django_client.get("/admin")
    assert response.status_code in (301, 302)
    assert response["Location"].startswith("/admin/")
    assert b"Reflex application" not in response.content


def test_bare_admin_segment_not_caught_by_mount_regex() -> None:
    """Root resolver passes ``admin`` (no slash) to included patterns."""
    import re

    from reflex_django.prefixes import resolve_prefixes
    from reflex_django.urls import _catchall_regex

    config = resolve_prefixes(django_prefix=("/admin",))
    pattern = _catchall_regex(
        config.mount_prefix,
        config.reserved_paths_for_catchall(),
    )
    assert re.match(pattern, "admin") is None
    assert re.match(pattern, "/admin") is None


def test_site_root_not_caught_when_separate_dev_ports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two-port dev: ``/`` is owned by Django, not the SPA catch-all."""
    import re

    from reflex_django.prefixes import resolve_prefixes
    from reflex_django.urls import _catchall_regex

    monkeypatch.setattr("reflex_django.dev_proxy.dev_uses_separate_ports", lambda: True)
    config = resolve_prefixes(django_prefix=("/admin", "/api"))
    pattern = _catchall_regex(
        config.mount_prefix,
        config.reserved_paths_for_catchall(),
    )
    assert re.match(pattern, "") is None
    assert re.match(pattern, "/") is None
    assert re.match(pattern, "login") is not None


def test_admin_with_slash_reaches_login(django_client: Client) -> None:
    response = django_client.get("/admin/")
    assert response.status_code in (301, 302)
    assert "login" in response["Location"]
