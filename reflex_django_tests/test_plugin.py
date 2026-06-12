"""Tests for removed ReflexDjangoPlugin stub."""

from __future__ import annotations

import pytest

from reflex_django.setup.errors import DeprecationRemovedError
from reflex_django.setup.plugin import ReflexDjangoPlugin, make_dispatcher


def test_plugin_constructor_raises() -> None:
    with pytest.raises(DeprecationRemovedError):
        ReflexDjangoPlugin()


def test_make_dispatcher_returns_transformer() -> None:
    from reflex_django.asgi.app import make_dispatcher

    calls: list[str] = []

    async def django_asgi(scope, receive, send):  # noqa: ANN001
        calls.append("django")

    async def reflex_asgi(scope, receive, send):  # noqa: ANN001
        calls.append("reflex")

    transformer = make_dispatcher(django_asgi, backend_prefixes=("/admin",))
    dispatch = transformer(reflex_asgi)
    assert callable(dispatch)