"""Tests for reflex_django.reflex_context."""

from __future__ import annotations

from typing import Any, cast
from unittest import mock

from reflex_django.conf import configure_django

configure_django()

from reflex_django.reflex_context import (  # noqa: E402
    builtin_user_context,
    collect_reflex_context,
    reflex_context_processor_paths,
    template_context_processor_paths,
)

_merge_calls: list[str] = []


def _merge_first_processor(_req):
    _merge_calls.append("first")
    return {"a": 1, "b": 2}


def _merge_second_processor(_req):
    _merge_calls.append("second")
    return {"b": 3, "c": 4}


async def test_collect_reflex_context_empty_request() -> None:
    merged = await collect_reflex_context(None)
    assert merged == {}


def test_builtin_user_context_anonymous() -> None:
    ctx = builtin_user_context(mock.Mock())
    assert "user" in ctx
    assert ctx["user"]["is_authenticated"] is False


async def test_collect_reflex_context_merge_order(monkeypatch) -> None:
    from django.conf import settings

    _merge_calls.clear()

    monkeypatch.setattr(
        settings,
        "REFLEX_DJANGO_CONTEXT_PROCESSORS",
        (
            "reflex_django_tests.test_reflex_context._merge_first_processor",
            "reflex_django_tests.test_reflex_context._merge_second_processor",
        ),
        raising=False,
    )
    monkeypatch.setattr(
        settings,
        "REFLEX_DJANGO_USE_TEMPLATE_CONTEXT_PROCESSORS",
        True,
        raising=False,
    )
    merged = await collect_reflex_context(mock.Mock())
    assert _merge_calls == ["first", "second"]
    assert merged == {"a": 1, "b": 3, "c": 4}


def test_template_context_processor_paths_reads_templates() -> None:
    paths = template_context_processor_paths()
    assert paths[0] == "django.contrib.auth.context_processors.auth"
    assert paths[1] == "django.contrib.messages.context_processors.messages"


def test_reflex_context_processor_paths_explicit_wins(monkeypatch) -> None:
    from django.conf import settings

    monkeypatch.setattr(
        settings,
        "REFLEX_DJANGO_CONTEXT_PROCESSORS",
        ("myapp.only",),
        raising=False,
    )
    monkeypatch.setattr(
        settings,
        "REFLEX_DJANGO_USE_TEMPLATE_CONTEXT_PROCESSORS",
        True,
        raising=False,
    )
    assert reflex_context_processor_paths() == ("myapp.only",)


async def test_collect_from_template_context_processors(monkeypatch) -> None:
    from django.conf import settings
    from django.contrib.auth.models import AnonymousUser
    from django.test import RequestFactory

    monkeypatch.setattr(settings, "REFLEX_DJANGO_CONTEXT_PROCESSORS", (), raising=False)
    monkeypatch.setattr(
        settings,
        "REFLEX_DJANGO_USE_TEMPLATE_CONTEXT_PROCESSORS",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        settings,
        "TEMPLATES",
        [
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "DIRS": [],
                "APP_DIRS": True,
                "OPTIONS": {
                    "context_processors": [
                        "django.template.context_processors.request",
                        "django.contrib.auth.context_processors.auth",
                    ],
                },
            }
        ],
        raising=False,
    )

    req = RequestFactory().get("/demo")
    cast(Any, req).user = AnonymousUser()
    merged = await collect_reflex_context(req)
    assert "request" not in merged
    assert "perms" not in merged
    assert merged["user"]["is_authenticated"] is False
