"""Tests for :mod:`reflex_django.mount.spa_template` — Django-templated SPA shell."""

from __future__ import annotations

from unittest import mock

import pytest

from reflex_django.setup.conf import configure_django

configure_django()

from django.contrib.auth.models import AnonymousUser  # noqa: E402
from django.http import FileResponse, HttpResponse  # noqa: E402
from django.test import RequestFactory  # noqa: E402

from reflex_django.mount.spa_template import (  # noqa: E402
    _render_via_template_engine_enabled,
    _response_is_html,
    maybe_render_spa_html,
)


@pytest.fixture
def html_request():
    request = RequestFactory().get("/")
    # The ``django.template.context_processors.auth`` processor expects
    # ``request.user`` to exist; the bridge populates this in real life but
    # for the unit test we attach an AnonymousUser explicitly.
    request.user = AnonymousUser()  # type: ignore[attr-defined]
    return request


def test_render_substitutes_user_and_messages(html_request) -> None:
    body = (
        "<!doctype html><html><body>"
        "<p data-user='{{ user.is_authenticated }}'>x</p>"
        "</body></html>"
    )
    response = HttpResponse(body, content_type="text/html; charset=utf-8")
    out = maybe_render_spa_html(html_request, response)
    assert b"data-user='False'" in out.content
    assert out["Content-Type"].startswith("text/html")


def test_render_skips_non_html(html_request) -> None:
    response = HttpResponse(b"console.log({{ user }});", content_type="application/javascript")
    out = maybe_render_spa_html(html_request, response)
    assert out is response
    assert b"{{ user }}" in out.content


def test_render_passes_through_when_disabled_via_env(
    monkeypatch: pytest.MonkeyPatch,
    html_request,
) -> None:
    monkeypatch.setenv("REFLEX_DJANGO_RENDER_SPA_VIA_TEMPLATE_ENGINE", "0")
    response = HttpResponse(
        b"<p>{{ user.is_authenticated }}</p>",
        content_type="text/html",
    )
    out = maybe_render_spa_html(html_request, response)
    assert out is response
    assert b"{{ user.is_authenticated }}" in out.content


def test_render_falls_back_on_template_syntax_error(html_request) -> None:
    # ``{% something %}`` is not a real template tag — Django raises
    # ``TemplateSyntaxError`` during compilation. The helper must return the
    # original response untouched rather than 500ing the page.
    body = b"<p>{% bogus-tag %}</p>"
    response = HttpResponse(body, content_type="text/html")
    out = maybe_render_spa_html(html_request, response)
    assert out is response
    assert out.content == body


def test_render_skips_streaming_bodies(html_request) -> None:
    # FileResponse is streaming → the helper must leave it alone, otherwise
    # large JS/CSS assets would be buffered into memory by the template
    # engine.
    response = FileResponse(b"\x00\x01\x02", content_type="text/html")
    response.streaming = True  # ensure the streaming flag is on
    out = maybe_render_spa_html(html_request, response)
    assert out is response


def test_response_is_html_accepts_charset_suffix() -> None:
    response = HttpResponse(b"<p>hi</p>", content_type="text/html; charset=utf-8")
    assert _response_is_html(response)


def test_response_is_html_rejects_other_types() -> None:
    response = HttpResponse(b"{}", content_type="application/json")
    assert not _response_is_html(response)


def test_env_var_overrides_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REFLEX_DJANGO_RENDER_SPA_VIA_TEMPLATE_ENGINE", "false")
    assert _render_via_template_engine_enabled() is False
    monkeypatch.setenv("REFLEX_DJANGO_RENDER_SPA_VIA_TEMPLATE_ENGINE", "1")
    assert _render_via_template_engine_enabled() is True


def test_setting_used_when_env_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REFLEX_DJANGO_RENDER_SPA_VIA_TEMPLATE_ENGINE", raising=False)
    from django.conf import settings

    with mock.patch.object(
        settings,
        "REFLEX_DJANGO_RENDER_SPA_VIA_TEMPLATE_ENGINE",
        False,
        create=True,
    ):
        assert _render_via_template_engine_enabled() is False
