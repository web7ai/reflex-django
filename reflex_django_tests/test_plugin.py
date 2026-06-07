"""Tests for removed ReflexDjangoPlugin stub."""

from __future__ import annotations

import pytest

from reflex_django.errors import DeprecationRemovedError
from reflex_django.plugin import ReflexDjangoPlugin, make_dispatcher


def test_plugin_constructor_raises() -> None:
    with pytest.raises(DeprecationRemovedError):
        ReflexDjangoPlugin()


def test_make_dispatcher_raises() -> None:
    with pytest.raises(DeprecationRemovedError):
        make_dispatcher(None, backend_prefixes=("/admin",))