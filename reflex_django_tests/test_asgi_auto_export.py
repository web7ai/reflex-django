"""Tests for the ASGI startup "build SPA if missing" hook.

Covers :func:`reflex_django.asgi.entry._maybe_auto_export_spa` and its
helpers, which let a raw ``uvicorn ...:application`` deploy build the SPA
bundle once at boot instead of 404ing with "Reflex SPA bundle not found".
"""

from __future__ import annotations

import os
from unittest import mock

import pytest

import reflex_django.asgi.entry as asgi_entry


@pytest.fixture(autouse=True)
def _clear_auto_export_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the env toggles don't leak between tests."""
    monkeypatch.delenv("REFLEX_DJANGO_AUTO_EXPORT_ON_START", raising=False)
    monkeypatch.delenv("REFLEX_DJANGO_DEV_PROXY", raising=False)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0", False),
        ("false", False),
        ("False", False),
        ("no", False),
        ("1", True),
        ("true", True),
        ("yes", True),
    ],
)
def test_enabled_env_overrides(
    monkeypatch: pytest.MonkeyPatch, value: str, expected: bool
) -> None:
    """The env var wins over any setting and parses truthy/falsy values."""
    monkeypatch.setenv("REFLEX_DJANGO_AUTO_EXPORT_ON_START", value)
    assert asgi_entry._auto_export_on_start_enabled() is expected


def test_enabled_defaults_true_without_env_or_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no env and no Django configured, default to enabled."""
    # Force the settings lookup to raise so we exercise the fallback.
    monkeypatch.setattr(
        "django.conf.settings",
        mock.Mock(spec=[]),  # no REFLEX_DJANGO_AUTO_EXPORT_ON_START attr
    )
    assert asgi_entry._auto_export_on_start_enabled() is True


def test_spa_bundle_missing_true_when_index_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "reflex_django.views.mount._resolve_spa_index", lambda: None
    )
    assert asgi_entry._spa_bundle_missing() is True


def test_spa_bundle_missing_false_when_index_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "reflex_django.views.mount._resolve_spa_index",
        lambda: "/some/index.html",
    )
    assert asgi_entry._spa_bundle_missing() is False


def test_maybe_auto_export_skips_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REFLEX_DJANGO_AUTO_EXPORT_ON_START", "0")
    called = mock.Mock()
    monkeypatch.setattr("django.core.management.call_command", called)
    # Even if a bundle were missing, disabled means no build.
    monkeypatch.setattr(asgi_entry, "_spa_bundle_missing", lambda: True)

    asgi_entry._maybe_auto_export_spa()

    called.assert_not_called()


def test_maybe_auto_export_skips_when_bundle_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REFLEX_DJANGO_AUTO_EXPORT_ON_START", "1")
    called = mock.Mock()
    monkeypatch.setattr("django.core.management.call_command", called)
    monkeypatch.setattr(asgi_entry, "_spa_bundle_missing", lambda: False)

    asgi_entry._maybe_auto_export_spa()

    called.assert_not_called()


def test_maybe_auto_export_builds_when_enabled_and_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REFLEX_DJANGO_AUTO_EXPORT_ON_START", "1")
    called = mock.Mock()
    monkeypatch.setattr("django.core.management.call_command", called)
    monkeypatch.setattr(asgi_entry, "_spa_bundle_missing", lambda: True)

    asgi_entry._maybe_auto_export_spa()

    called.assert_called_once_with(
        "export_reflex",
        frontend_only=True,
        no_zip=True,
        stage_to_static_root=True,
        env="prod",
    )


def test_maybe_auto_export_swallows_build_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing export must not crash server startup."""
    monkeypatch.setenv("REFLEX_DJANGO_AUTO_EXPORT_ON_START", "1")
    monkeypatch.setattr(asgi_entry, "_spa_bundle_missing", lambda: True)

    def _boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("node missing")

    monkeypatch.setattr("django.core.management.call_command", _boom)

    # Should return cleanly (best-effort), not raise.
    asgi_entry._maybe_auto_export_spa()


# --- startup dev-proxy probe -------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [("1", True), ("true", True), ("yes", True), ("on", True),
     ("0", False), ("false", False), ("", False)],
)
def test_dev_proxy_explicitly_enabled(
    monkeypatch: pytest.MonkeyPatch, value: str, expected: bool
) -> None:
    if value == "":
        monkeypatch.delenv("REFLEX_DJANGO_DEV_PROXY", raising=False)
    else:
        monkeypatch.setenv("REFLEX_DJANGO_DEV_PROXY", value)
    assert asgi_entry._dev_proxy_explicitly_enabled() is expected


def test_probe_disables_proxy_when_vite_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DEBUG-default proxy + no Vite listening -> proxy disabled for process."""
    monkeypatch.setattr(
        "reflex_django.dev.proxy._dev_vite_target_or_none",
        lambda: "http://127.0.0.1:3000",
    )
    monkeypatch.setattr(asgi_entry, "_vite_target_reachable", lambda target: False)

    asgi_entry._maybe_disable_dev_proxy_without_vite()

    assert os.environ.get("REFLEX_DJANGO_DEV_PROXY") == "0"


def test_probe_keeps_proxy_when_vite_reachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "reflex_django.dev.proxy._dev_vite_target_or_none",
        lambda: "http://127.0.0.1:3000",
    )
    monkeypatch.setattr(asgi_entry, "_vite_target_reachable", lambda target: True)

    asgi_entry._maybe_disable_dev_proxy_without_vite()

    assert os.environ.get("REFLEX_DJANGO_DEV_PROXY") is None


def test_probe_skipped_when_explicitly_forced_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_reflex forces DEV_PROXY=1; the probe must not run a reachability check."""
    monkeypatch.setenv("REFLEX_DJANGO_DEV_PROXY", "1")
    monkeypatch.setattr(
        "reflex_django.dev.proxy._dev_vite_target_or_none",
        lambda: "http://127.0.0.1:3000",
    )
    probe = mock.Mock()
    monkeypatch.setattr(asgi_entry, "_vite_target_reachable", probe)

    asgi_entry._maybe_disable_dev_proxy_without_vite()

    probe.assert_not_called()
    assert os.environ.get("REFLEX_DJANGO_DEV_PROXY") == "1"


def test_probe_noop_when_proxy_already_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No dev target (proxy off / prod) -> nothing to probe or change."""
    monkeypatch.setattr(
        "reflex_django.dev.proxy._dev_vite_target_or_none", lambda: None
    )
    probe = mock.Mock()
    monkeypatch.setattr(asgi_entry, "_vite_target_reachable", probe)

    asgi_entry._maybe_disable_dev_proxy_without_vite()

    probe.assert_not_called()
