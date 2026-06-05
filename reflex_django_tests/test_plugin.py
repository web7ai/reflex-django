"""Plugin tests: ReflexDjangoPlugin.post_compile mutates App.api_transformer."""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable, MutableMapping, Sequence
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from reflex_django.plugin import ReflexDjangoPlugin, _as_sequence


@pytest.fixture(autouse=True)
def _clear_prefix_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate prefix resolution from prior tests' environment exports."""
    monkeypatch.delenv("REFLEX_DJANGO_API_PREFIX", raising=False)
    monkeypatch.delenv("REFLEX_DJANGO_ADMIN_PREFIX", raising=False)


class _StubApp:
    """Stand-in for reflex.app.App with just the fields the plugin touches."""

    def __init__(self) -> None:
        self.api_transformer: Any = None
        self.middlewares: list[Any] = []

    def add_middleware(self, middleware: Any) -> None:
        self.middlewares.append(middleware)


def _patch_django_build(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Make plugin._configure cheap by stubbing django setup and ASGI build.

    Args:
        monkeypatch: Pytest's monkeypatch fixture.

    Returns:
        The fake django ASGI app installed on the plugin.
    """

    async def _fake_django_asgi(  # noqa: RUF029
        scope: MutableMapping[str, Any],
        receive: Callable[[], Awaitable[MutableMapping[str, Any]]],
        send: Callable[[MutableMapping[str, Any]], Awaitable[None]],
    ) -> None:
        return None

    monkeypatch.setattr("reflex_django.plugin.configure_django", lambda *a, **k: "stub")
    monkeypatch.setattr(
        "reflex_django.plugin.build_django_asgi", lambda: _fake_django_asgi
    )
    return _fake_django_asgi


def test_post_compile_assigns_api_transformer_when_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_django_build(monkeypatch)
    monkeypatch.setattr(
        "reflex_django.plugin.ReflexDjangoPlugin._warn_if_using_auto_settings",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "reflex_django.middleware.DjangoEventBridge.__init__",
        lambda self: None,
    )

    app = _StubApp()
    plugin = ReflexDjangoPlugin()

    plugin.post_compile(app=app)

    assert isinstance(app.api_transformer, tuple)
    assert len(app.api_transformer) == 1
    transformer = app.api_transformer[0]
    assert callable(transformer)
    assert transformer.backend_prefixes == ("/admin",)  # pyright: ignore[reportFunctionMemberAccess]

    # The bridge is installed by default.
    assert len(app.middlewares) == 1


def test_post_compile_applies_frontend_stability_patches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_django_build(monkeypatch)
    monkeypatch.setattr(
        "reflex_django.plugin.ReflexDjangoPlugin._warn_if_using_auto_settings",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "reflex_django.middleware.DjangoEventBridge.__init__",
        lambda self: None,
    )
    monkeypatch.setattr(
        "reflex_django.plugin.ReflexDjangoPlugin._ensure_vite_dev_proxy_on_disk",
        lambda self: None,
    )
    monkeypatch.setattr(
        "reflex_django.plugin.ReflexDjangoPlugin._warn_if_frontend_dispatchers_out_of_sync",
        lambda self: None,
    )

    calls: list[Path | None] = []

    def _fake_apply(web_dir: Path | None = None) -> list[str]:
        calls.append(web_dir)
        return ["utils/context.js"]

    monkeypatch.setattr(
        "reflex_django.frontend_stability.apply_frontend_stability_after_compile",
        _fake_apply,
    )

    app = _StubApp()
    ReflexDjangoPlugin().post_compile(app=app)

    assert len(calls) == 1
    assert calls[0] is None


def test_post_compile_chains_with_existing_transformer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_django_build(monkeypatch)
    monkeypatch.setattr(
        "reflex_django.plugin.ReflexDjangoPlugin._warn_if_using_auto_settings",
        lambda *_a, **_k: None,
    )

    def existing(asgi: Any) -> Any:
        return asgi

    app = _StubApp()
    app.api_transformer = existing
    plugin = ReflexDjangoPlugin(install_event_bridge=False)

    plugin.post_compile(app=app)

    assert isinstance(app.api_transformer, tuple)
    assert app.api_transformer[0] is existing
    assert len(app.api_transformer) == 2
    assert app.middlewares == []


def test_post_compile_appends_after_existing_sequence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_django_build(monkeypatch)
    monkeypatch.setattr(
        "reflex_django.plugin.ReflexDjangoPlugin._warn_if_using_auto_settings",
        lambda *_a, **_k: None,
    )

    first = lambda asgi: asgi  # noqa: E731
    second = lambda asgi: asgi  # noqa: E731

    app = _StubApp()
    app.api_transformer = (first, second)
    plugin = ReflexDjangoPlugin(install_event_bridge=False)

    plugin.post_compile(app=app)

    assert isinstance(app.api_transformer, tuple)
    assert app.api_transformer[0] is first
    assert app.api_transformer[1] is second
    assert callable(app.api_transformer[2])


def test_pre_compile_skips_vite_proxy_in_django_outer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two-port / single-port DJANGO_OUTER must not inject Vite→Django proxies."""
    _patch_django_build(monkeypatch)
    modify_tasks: list[tuple[str, object]] = []

    plugin = ReflexDjangoPlugin(
        backend_prefix="/api",
        django_prefix=("/billing",),
        install_event_bridge=False,
    )
    plugin.pre_compile(
        add_modify_task=lambda path, fn: modify_tasks.append((path, fn)),
        add_save_task=lambda *a, **k: None,
        radix_themes_plugin=None,
        unevaluated_pages=[],
    )

    assert modify_tasks == []


def test_pre_compile_registers_vite_proxy_modify_task_for_django_led(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_django_build(monkeypatch)
    monkeypatch.setattr(
        "reflex_django.plugin.resolve_url_routing",
        lambda: __import__(
            "reflex_django.routing", fromlist=["UrlRoutingMode"]
        ).UrlRoutingMode.DJANGO_LED,
    )
    modify_tasks: list[tuple[str, object]] = []

    plugin = ReflexDjangoPlugin(
        backend_prefix="/api",
        django_prefix=("/billing",),
        install_event_bridge=False,
    )
    plugin.pre_compile(
        add_modify_task=lambda path, fn: modify_tasks.append((path, fn)),
        add_save_task=lambda *a, **k: None,
        radix_themes_plugin=None,
        unevaluated_pages=[],
    )

    assert len(modify_tasks) == 1
    assert modify_tasks[0][0] == "vite.config.js"
    patched = modify_tasks[0][1](  # type: ignore[operator]
        "export default defineConfig({ plugins: [reactRouter()], server: { port: 1, }, });"
    )
    assert "reflex-django-proxy" in patched
    assert "reflexDjangoProxyPlugin()" in patched
    assert '"/api":' in patched
    assert '"/admin":' in patched
    assert '"/billing":' in patched


def test_post_compile_django_prefix_propagate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_django_build(monkeypatch)
    monkeypatch.setattr(
        "reflex_django.plugin.ReflexDjangoPlugin._warn_if_using_auto_settings",
        lambda *_a, **_k: None,
    )

    app = _StubApp()
    plugin = ReflexDjangoPlugin(
        django_prefix=("/billing", "/auth"),
        install_event_bridge=False,
    )

    plugin.post_compile(app=app)

    transformer = app.api_transformer[0]
    assert transformer.backend_prefixes == (  # pyright: ignore[reportFunctionMemberAccess]
        "/billing",
        "/auth",
        "/admin",
    )


def test_post_compile_requires_app_in_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_django_build(monkeypatch)
    plugin = ReflexDjangoPlugin()

    with pytest.raises(RuntimeError, match="requires the Reflex App"):
        plugin.post_compile()


def test_post_compile_rejects_reserved_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_django_build(monkeypatch)
    monkeypatch.setattr(
        "reflex_django.plugin.ReflexDjangoPlugin._warn_if_using_auto_settings",
        lambda *_a, **_k: None,
    )

    app = _StubApp()
    plugin = ReflexDjangoPlugin(backend_prefix="/_event")

    with pytest.raises(ValueError, match="reserved endpoint"):
        plugin.post_compile(app=app)


def test_post_compile_warns_when_using_bundled_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_django_build(monkeypatch)
    warn_mock = mock.Mock()
    monkeypatch.setattr("reflex_base.utils.console.warn", warn_mock)

    fake_settings = mock.Mock(
        REFLEX_DJANGO_AUTO_SETTINGS=True,
        INSTALLED_APPS=[],
        STATIC_URL=None,
    )
    monkeypatch.setattr("django.conf.settings", fake_settings)

    app = _StubApp()
    plugin = ReflexDjangoPlugin(install_event_bridge=False)
    plugin.post_compile(app=app)

    assert warn_mock.call_count == 1
    assert "bundled default settings" in warn_mock.call_args.args[0]


def test_post_compile_routes_static_url_when_staticfiles_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When staticfiles is in INSTALLED_APPS, STATIC_URL is forwarded to Django."""
    _patch_django_build(monkeypatch)
    monkeypatch.setattr(
        "reflex_django.plugin.ReflexDjangoPlugin._warn_if_using_auto_settings",
        lambda *_a, **_k: None,
    )
    fake_settings = mock.Mock(
        INSTALLED_APPS=["django.contrib.staticfiles"],
        STATIC_URL="/static/",
    )
    monkeypatch.setattr("django.conf.settings", fake_settings)

    app = _StubApp()
    plugin = ReflexDjangoPlugin(install_event_bridge=False)
    plugin.post_compile(app=app)

    transformer = app.api_transformer[0]
    assert transformer.backend_prefixes == ("/admin", "/static")  # pyright: ignore[reportFunctionMemberAccess]


def test_post_compile_skips_static_when_staticfiles_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without staticfiles installed, STATIC_URL is not added to prefixes."""
    _patch_django_build(monkeypatch)
    monkeypatch.setattr(
        "reflex_django.plugin.ReflexDjangoPlugin._warn_if_using_auto_settings",
        lambda *_a, **_k: None,
    )
    fake_settings = mock.Mock(
        INSTALLED_APPS=["django.contrib.auth", "django.contrib.admin"],
        STATIC_URL="/static/",
    )
    monkeypatch.setattr("django.conf.settings", fake_settings)

    app = _StubApp()
    plugin = ReflexDjangoPlugin(install_event_bridge=False)
    plugin.post_compile(app=app)

    transformer = app.api_transformer[0]
    assert transformer.backend_prefixes == ("/admin",)  # pyright: ignore[reportFunctionMemberAccess]


def test_post_compile_skips_static_when_absolute_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A CDN-style STATIC_URL (absolute URL) is not added to the dispatcher."""
    _patch_django_build(monkeypatch)
    monkeypatch.setattr(
        "reflex_django.plugin.ReflexDjangoPlugin._warn_if_using_auto_settings",
        lambda *_a, **_k: None,
    )
    fake_settings = mock.Mock(
        INSTALLED_APPS=["django.contrib.staticfiles"],
        STATIC_URL="https://cdn.example.com/static/",
    )
    monkeypatch.setattr("django.conf.settings", fake_settings)

    app = _StubApp()
    plugin = ReflexDjangoPlugin(install_event_bridge=False)
    plugin.post_compile(app=app)

    transformer = app.api_transformer[0]
    assert transformer.backend_prefixes == ("/admin",)  # pyright: ignore[reportFunctionMemberAccess]


def test_post_compile_optional_backend_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``backend_prefix`` is set, it is forwarded before ``admin_prefix``."""
    _patch_django_build(monkeypatch)
    monkeypatch.setattr(
        "reflex_django.plugin.ReflexDjangoPlugin._warn_if_using_auto_settings",
        lambda *_a, **_k: None,
    )

    app = _StubApp()
    plugin = ReflexDjangoPlugin(backend_prefix="/api", install_event_bridge=False)
    plugin.post_compile(app=app)

    transformer = app.api_transformer[0]
    assert transformer.backend_prefixes == ("/api", "/admin")  # pyright: ignore[reportFunctionMemberAccess]


def test_plugin_init_calls_configure_django(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reflex loads ``rxconfig`` before the app module; bootstrap runs in ``__post_init__``."""
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def track(*args: Any, **kwargs: Any) -> str:
        calls.append((args, kwargs))
        return "stubbed.settings"

    monkeypatch.setattr("reflex_django.plugin.configure_django", track)
    ReflexDjangoPlugin(settings_module="reflex_django.default_settings")
    assert len(calls) == 1
    assert calls[0][0] == ("reflex_django.default_settings",)


def test_as_sequence_normalizes_inputs() -> None:
    assert _as_sequence(None) == ()

    def callable_transformer(asgi: Any) -> Any:
        return asgi

    assert _as_sequence(callable_transformer) == (callable_transformer,)

    seq: Sequence[Any] = (callable_transformer, callable_transformer)
    assert _as_sequence(seq) == tuple(seq)
