"""Legacy make_dispatcher tests — dispatcher removed in v1.0.

Routing behavior is covered by test_django_outer_dispatcher.py.
"""

from __future__ import annotations

import pytest

from reflex_django.asgi import make_dispatcher
from reflex_django.errors import DeprecationRemovedError


def test_make_dispatcher_raises_deprecation() -> None:
    with pytest.raises(DeprecationRemovedError):
        make_dispatcher(lambda s, r, sn: None, backend_prefixes=("/admin",))