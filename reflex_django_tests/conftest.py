"""Shared fixtures for reflex-django unit tests.

Assign ``DJANGO_SETTINGS_MODULE`` here (not ``setdefault``) before any test
module imports :mod:`reflex_django` for the first time. That overrides a stale
value from the developer's shell. Using a test-specific settings module keeps
test databases isolated and avoids littering the cwd with sqlite files when the
bundled defaults are used.
"""

from __future__ import annotations

import os

# Always use the test settings module so a developer shell's
# ``DJANGO_SETTINGS_MODULE`` cannot shadow the assignment above.
os.environ["DJANGO_SETTINGS_MODULE"] = "reflex_django_tests.django_settings"
