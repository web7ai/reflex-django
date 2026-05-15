"""Tests for password reset mixin."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from reflex_django.conf import configure_django

configure_django()

from reflex_django.auth.mixins.password_reset import (  # noqa: E402
    PasswordResetConfig,
    password_reset_mixin,
)
from reflex_django.auth_state import DjangoUserState  # noqa: E402


class _Base(DjangoUserState):
    is_hydrated: bool = True


def _make_reset_state(suffix: str):
    cfg = PasswordResetConfig(
        password_reset_confirm_url="/password-reset/confirm/[uid]/[token]",
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


@pytest.mark.asyncio
async def test_password_reset_confirm_invalid_token() -> None:
    Cls = _make_reset_state("Bad")
    state = Cls()

    with patch(
        "reflex_django.auth.mixins.password_reset._page_params",
        return_value={"uid": "bad", "token": "bad"},
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
    assert state.reset_error != ""


@pytest.mark.asyncio
async def test_password_reset_confirm_valid_token() -> None:
    Cls = _make_reset_state("Ok")
    state = Cls()

    with patch(
        "reflex_django.auth.mixins.password_reset._page_params",
        return_value={"uid": "MQ", "token": "abc"},
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
