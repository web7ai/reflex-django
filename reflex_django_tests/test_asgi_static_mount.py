"""Static mount websocket safety — covered by django_outer dispatcher tests."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="make_dispatcher removed; mount-only architecture")