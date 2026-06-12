"""Legacy make_dispatcher was removed in v1.0."""

from __future__ import annotations

import pytest

from reflex_django.asgi.app import make_dispatcher
from reflex_django.setup.errors import DeprecationRemovedError


def test_make_dispatcher_removed() -> None:
    with pytest.raises(DeprecationRemovedError):
        make_dispatcher(lambda s, r, sn: None, backend_prefixes=("/admin",))