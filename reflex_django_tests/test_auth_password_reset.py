"""Tests for password reset mixin."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from reflex_django.conf import configure_django

configure_django()

from reflex_django.auth.mixins.password_reset import (  # noqa: E402
    PasswordResetConfig,
    _page_params,
    _params_from_confirm_path,
    _reset_uid_and_token,
    password_reset_mixin,
)
from reflex_django.auth_state import DjangoUserState  # noqa: E402


class _Base(DjangoUserState):
    is_hydrated: bool = True


def _make_reset_state(suffix: str):
    cfg = PasswordResetConfig(
        password_reset_confirm_url="/password-reset/confirm/[uid]/[key]",
        login_url="/login",
        state_class_name=f"TestPasswordResetState{suffix}",
    )
    return password_reset_mixin(cfg, base=_Base, state_module=__name__)


def _fake_sync_to_async(fn):
    async def _call(*_args, **_kwargs):
        return fn()

    return _call


@pytest.mark.asyncio
async def test_password_reset_request_sets_sent_flag() -> None:
    Cls = _make_reset_state("Send")
    state = Cls()
    mock_request = MagicMock()
    mock_request.build_absolute_uri = lambda p: f"http://test{p}"

    with patch(
        "reflex_django.auth.mixins.password_reset.current_request",
        return_value=mock_request,
    ):
        with patch(
            "reflex_django.auth.mixins.password_reset.sync_to_async",
            side_effect=_fake_sync_to_async,
        ):
            with patch("reflex_django.auth.mixins.password_reset.send_mail") as send_mail:
                with patch(
                    "reflex_django.auth.mixins.password_reset.default_token_generator.make_token",
                    return_value="tok",
                ):
                    with patch(
                        "django.contrib.auth.get_user_model",
                    ) as gum:
                        user = MagicMock(pk=1, email="reset@example.com")
                        gum.return_value.objects.filter.return_value = [user]
                        await state.submit_password_reset_request(
                            {"email": "reset@example.com"}
                        )

    assert state.reset_email_sent is True
    send_mail.assert_called_once()


def test_page_params_prefers_key_over_session_token() -> None:
    """Route param must not be confused with Reflex's websocket ``token`` field."""
    class _RouterPage:
        params: dict[str, str] = {}

    class _Router:
        page = _RouterPage()

    class _State:
        router = _Router()
        router_data = {
            "pathname": "/password-reset/confirm/MQ/reset-tok",
            "query": {"uid": "MQ", "key": "reset-tok", "token": "client-ws-token"},
            "token": "client-ws-token",
        }
        token = "client-ws-token"

    params = _page_params(
        _State(),
        confirm_template="/password-reset/confirm/[uid]/[key]",
    )
    uid, tok = _reset_uid_and_token(params)
    assert uid == "MQ"
    assert tok == "reset-tok"


def test_params_from_confirm_path_parses_pathname() -> None:
    parsed = _params_from_confirm_path(
        "/password-reset/confirm/MQ/abc-def",
        "/password-reset/confirm/[uid]/[key]",
    )
    assert parsed == {"uid": "MQ", "key": "abc-def"}


@pytest.mark.asyncio
async def test_password_reset_confirm_invalid_token() -> None:
    Cls = _make_reset_state("Bad")
    state = Cls()

    with patch(
        "reflex_django.auth.mixins.password_reset._page_params",
        return_value={"uid": "bad", "key": "bad"},
    ):
        with patch(
            "reflex_django.auth.mixins.password_reset.sync_to_async",
            side_effect=_fake_sync_to_async,
        ):
            with patch(
                "reflex_django.auth.mixins.password_reset.default_token_generator.check_token",
                return_value=False,
            ):
                await state.on_load_password_reset_confirm()

    assert state.reset_link_valid is False
    assert state.reset_confirm_loaded is True
    assert state.reset_error != ""


@pytest.mark.asyncio
async def test_password_reset_confirm_valid_token() -> None:
    Cls = _make_reset_state("Ok")
    state = Cls()

    with patch(
        "reflex_django.auth.mixins.password_reset._page_params",
        return_value={"uid": "MQ", "key": "abc"},
    ):

        def _sync(fn):
            async def _call(*_a, **_k):
                if getattr(fn, "__name__", "") == "_check":
                    return True
                return fn()

            return _call

        with patch(
            "reflex_django.auth.mixins.password_reset.sync_to_async",
            side_effect=_sync,
        ):
            await state.on_load_password_reset_confirm()

    assert state.reset_link_valid is True
    assert state.reset_confirm_loaded is True


@pytest.mark.asyncio
async def test_password_reset_confirm_valid_token_from_pathname() -> None:
    from django.contrib.auth import get_user_model
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="pathuser",
        email="path@example.com",
        password="oldpass123",
    )
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    reset_token = default_token_generator.make_token(user)

    Cls = _make_reset_state("Path")
    state = Cls()

    class _RouterPage:
        params: dict[str, str] = {}

    class _Router:
        page = _RouterPage()

    state.router = _Router()
    state.router_data = {
        "pathname": f"/password-reset/confirm/{uid}/{reset_token}",
        "query": {},
        "token": "client-ws-token",
    }

    await state.on_load_password_reset_confirm()

    assert state.reset_link_valid is True
    assert state.reset_confirm_loaded is True
