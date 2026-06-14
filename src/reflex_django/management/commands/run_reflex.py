"""``manage.py run_reflex`` entry module.

Django 6 discovers management commands from ``*.py`` modules only, not
subpackages. The implementation lives in :mod:`reflex_django.management.commands._run_reflex`.
"""

from __future__ import annotations

from reflex_django.management.commands._run_reflex import Command, _parse_asgi_target
from reflex_django.management.commands._run_reflex import asgi_helpers

__all__ = ["Command", "_parse_asgi_target", "asgi_helpers"]
