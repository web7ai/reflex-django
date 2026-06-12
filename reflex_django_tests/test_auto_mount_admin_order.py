"""Ensure auto-mount waits for django.contrib.admin autodiscover."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


def test_auto_mount_after_admin_autodiscover_in_subprocess() -> None:
    """Fresh process: reflex_django before admin must still expose admin:app_list."""
    root = Path(__file__).resolve().parent.parent
    script = """
import os
import sys

sys.path.insert(0, {src!r})
sys.path.insert(0, {root!r})
os.environ["DJANGO_SETTINGS_MODULE"] = "reflex_django_tests.test_auto_mount_admin_order_settings"

import django
from django.contrib import admin
from django.contrib.auth.models import User
from django.urls import reverse

django.setup()

if not admin.site.is_registered(User):
    admin.site.register(User)

url = reverse("admin:app_list", kwargs={{"app_label": "auth"}})
assert url == "/admin/auth/", url
print("ok")
""".format(
        src=str(root / "src"),
        root=str(root),
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(root),
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_schedule_auto_mount_patches_admin_when_reflex_listed_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from django.conf import settings
    from django.contrib.admin.apps import AdminConfig

    from reflex_django.mount.auto import (
        clear_auto_mount_state,
        schedule_auto_mount_after_admin,
    )

    clear_auto_mount_state()
    monkeypatch.delattr(AdminConfig, "_reflex_auto_mount_scheduled", raising=False)

    monkeypatch.setattr(
        settings,
        "INSTALLED_APPS",
        [
            "reflex_django",
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.admin",
        ],
        raising=False,
    )
    monkeypatch.setattr(settings, "REFLEX_DJANGO_AUTO_MOUNT", True, raising=False)

    original_ready = AdminConfig.ready
    schedule_auto_mount_after_admin()

    assert getattr(AdminConfig, "_reflex_auto_mount_scheduled", False)
    assert AdminConfig.ready is not original_ready

    clear_auto_mount_state()
    monkeypatch.delattr(AdminConfig, "_reflex_auto_mount_scheduled", raising=False)
    AdminConfig.ready = original_ready
