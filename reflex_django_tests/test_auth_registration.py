"""Tests for registration mixin handlers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from reflex_django.setup.conf import configure_django

configure_django()

from reflex_django.auth.mixins.registration import (  # noqa: E402
    RegistrationConfig,
    registration_mixin,
)
from reflex_django.states.auth import DjangoUserState  # noqa: E402


class _Base(DjangoUserState):
    is_hydrated: bool = True


def _make_reg_state(suffix: str):
    cfg = RegistrationConfig(
        signup_redirect_url="/login",
        email_required=False,
        password_min_length=4,
        state_class_name=f"TestRegistrationState{suffix}",
    )
    return registration_mixin(cfg, base=_Base, state_module=__name__)


def _fake_sync_to_async(fn):
    async def _call(*_args, **_kwargs):
        return fn()

    return _call


@pytest.mark.asyncio
async def test_registration_rejects_duplicate_username() -> None:
    Cls = _make_reg_state("Dup")
    state = Cls()
    mock_request = MagicMock()

    with patch(
        "reflex_django.auth.mixins.registration.current_request",
        return_value=mock_request,
    ):
        with patch(
            "reflex_django.auth.mixins.registration.sync_to_async",
            side_effect=_fake_sync_to_async,
        ):
            with patch(
                "reflex_django.auth.mixins.registration.get_user_model",
            ) as gum:
                user_model = MagicMock()
                user_model.objects.filter.return_value.exists = MagicMock(
                    return_value=True
                )
                gum.return_value = user_model
                await state.handle_registration(
                    {
                        "username": "taken",
                        "password": "secret1234",
                        "confirm_password": "secret1234",
                    }
                )

    assert "taken" in state.registration_error.lower()


@pytest.mark.asyncio
async def test_registration_success_navigates() -> None:
    Cls = _make_reg_state("New")
    state = Cls()
    mock_request = MagicMock()
    mock_request.session.asave = AsyncMock()
    created_user = MagicMock()

    with patch(
        "reflex_django.auth.mixins.registration.current_request",
        return_value=mock_request,
    ):
        with patch(
            "reflex_django.auth.mixins.registration._sync_session_cookie_then_nav",
            return_value="nav",
        ) as nav:
            with patch(
                "reflex_django.auth.mixins.registration.validate_password",
            ):
                with patch(
                    "reflex_django.auth.mixins.registration.alogin",
                    new_callable=AsyncMock,
                ):
                    with patch(
                        "reflex_django.auth.mixins.registration.get_user_model",
                    ) as gum:
                        user_model = MagicMock()
                        user_model.objects.filter.return_value.exists = MagicMock(
                            return_value=False
                        )
                        gum.return_value = user_model

                        def _fake_sync(fn):
                            async def _call(*_a, **_k):
                                if fn.__name__ == "_create_user":
                                    return created_user
                                return fn()

                            return _call

                        with patch(
                            "reflex_django.auth.mixins.registration.sync_to_async",
                            side_effect=_fake_sync,
                        ):
                            with patch.object(
                                Cls,
                                "refresh_django_user_fields",
                                new_callable=AsyncMock,
                            ):
                                result = await state.handle_registration(
                                    {
                                        "username": "newbie",
                                        "email": "new@example.com",
                                        "password": "secret1234",
                                        "confirm_password": "secret1234",
                                    }
                                )

    assert result == "nav"
    nav.assert_called_once()


def test_registration_mixin_exposes_handler() -> None:
    Cls = _make_reg_state("Meta")
    assert hasattr(Cls, "handle_registration")
    assert hasattr(Cls, "on_load_register")
