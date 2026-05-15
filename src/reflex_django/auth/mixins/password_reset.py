"""Password reset mixin using Django's token generator and email."""

from __future__ import annotations

import inspect
import sys
import types
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import reflex as rx
from asgiref.sync import sync_to_async
from django.conf import settings as django_settings
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from reflex_django.auth.settings import AuthSettings
from reflex_django.context import current_request
from reflex_django.mixins.session_auth import _defer_nav_js


@dataclass(frozen=True)
class PasswordResetConfig:
    """Password reset routes and copy."""

    password_reset_url: str = "/password-reset"
    password_reset_confirm_url: str = "/password-reset/confirm/[uid]/[token]"
    login_url: str = "/login"
    error_var: str = "reset_error"
    success_var: str = "reset_success"
    email_sent_var: str = "reset_email_sent"
    confirm_valid_var: str = "reset_link_valid"
    request_event: str = "submit_password_reset_request"
    confirm_event: str = "submit_password_reset_confirm"
    on_load_confirm_event: str = "on_load_password_reset_confirm"
    state_class_name: str = "DjangoAuthState"
    messages: dict[str, str] | None = None

    @classmethod
    def from_auth_settings(cls, auth: AuthSettings) -> PasswordResetConfig:
        return cls(
            password_reset_url=auth.password_reset_url,
            password_reset_confirm_url=auth.password_reset_confirm_url,
            login_url=auth.login_url,
            messages=auth.messages,
        )


def _msg(cfg: PasswordResetConfig, key: str, default: str) -> str:
    if cfg.messages and key in cfg.messages:
        return cfg.messages[key]
    return default


def _confirm_path_for(uid: str, token: str, template: str) -> str:
    return (
        template.replace("[uid]", uid)
        .replace("[token]", token)
        .replace("{uid}", uid)
        .replace("{token}", token)
    )


def _page_params(state: Any) -> dict[str, Any]:
    page = getattr(getattr(state, "router", None), "page", None)
    params = getattr(page, "params", None)
    if isinstance(params, dict):
        return params
    return {}


def password_reset_mixin(
    cfg: PasswordResetConfig,
    *,
    base: type[rx.State],
    state_module: str | None = None,
) -> type[rx.State]:
    """Extend ``base`` with password reset request and confirm handlers."""
    frame = inspect.currentframe()
    try:
        if state_module is not None:
            state_mod = state_module
        elif frame is None or frame.f_back is None:
            state_mod = __name__
        else:
            state_mod = str(frame.f_back.f_globals.get("__name__", __name__))
    finally:
        del frame

    e_var = cfg.error_var
    s_var = cfg.success_var
    sent_var = cfg.email_sent_var
    valid_var = cfg.confirm_valid_var
    login_url = cfg.login_url
    confirm_template = cfg.password_reset_confirm_url
    cls_name = cfg.state_class_name

    def exec_body(ns: dict[str, Any]) -> None:
        ns["__module__"] = state_mod
        ann = dict(getattr(base, "__annotations__", {}))
        ann[e_var] = str
        ann[s_var] = bool
        ann[sent_var] = bool
        ann[valid_var] = bool
        ns["__annotations__"] = ann
        ns[e_var] = ""
        ns[s_var] = False
        ns[sent_var] = False
        ns[valid_var] = False

        async def submit_password_reset_request_impl(
            self: Any,
            form_data: dict[str, Any],
        ) -> Any:
            setattr(self, e_var, "")
            setattr(self, sent_var, False)
            email = str(form_data.get("email", "")).strip()
            request = current_request()

            def _send() -> None:
                from django.contrib.auth import get_user_model as _get_user_model

                user_model = _get_user_model()
                users = list(user_model.objects.filter(email__iexact=email))
                if not users:
                    return
                user = users[0]
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                path = _confirm_path_for(uid, token, confirm_template)
                if request is not None and hasattr(request, "build_absolute_uri"):
                    reset_url = request.build_absolute_uri(path)
                else:
                    origin = str(
                        getattr(django_settings, "REFLEX_DJANGO_SITE_ORIGIN", "")
                    ).rstrip("/")
                    reset_url = urljoin(origin + "/", path.lstrip("/")) if origin else path
                subject = "Password reset"
                body = (
                    f"Use the link below to reset your password:\n\n{reset_url}\n\n"
                    "If you did not request this, you can ignore this email."
                )
                send_mail(
                    subject,
                    body,
                    django_settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )

            await sync_to_async(_send)()
            setattr(self, sent_var, True)

        ns[cfg.request_event] = rx.event(submit_password_reset_request_impl)

        async def on_load_password_reset_confirm_impl(self: Any) -> Any:
            setattr(self, e_var, "")
            setattr(self, valid_var, False)
            raw_params = _page_params(self)
            uid = str(raw_params.get("uid", "") or "")
            token = str(raw_params.get("token", "") or "")

            def _check() -> bool:
                from django.contrib.auth import get_user_model
                from django.utils.http import urlsafe_base64_decode

                user_model = get_user_model()
                try:
                    pk = urlsafe_base64_decode(uid).decode()
                    user = user_model.objects.get(pk=pk)
                except (TypeError, ValueError, OverflowError, user_model.DoesNotExist):
                    return False
                return default_token_generator.check_token(user, token)

            ok = bool(uid and token and await sync_to_async(_check)())
            setattr(self, valid_var, ok)
            if not ok:
                setattr(
                    self,
                    e_var,
                    _msg(
                        cfg,
                        "reset_invalid_link",
                        "This reset link is invalid or has expired.",
                    ),
                )

        ns[cfg.on_load_confirm_event] = rx.event(on_load_password_reset_confirm_impl)

        async def submit_password_reset_confirm_impl(
            self: Any,
            form_data: dict[str, Any],
        ) -> Any:
            setattr(self, e_var, "")
            setattr(self, s_var, False)
            if not getattr(self, valid_var, False):
                return

            raw_params = _page_params(self)
            uid = str(raw_params.get("uid", "") or "")
            token = str(raw_params.get("token", "") or "")
            password = str(form_data.get("new_password", ""))
            confirm = str(form_data.get("confirm_password", ""))

            def _confirm() -> str | None:
                from django.contrib.auth import get_user_model
                from django.utils.http import urlsafe_base64_decode

                user_model = get_user_model()
                try:
                    pk = urlsafe_base64_decode(uid).decode()
                    user = user_model.objects.get(pk=pk)
                except (TypeError, ValueError, OverflowError, user_model.DoesNotExist):
                    return _msg(
                        cfg,
                        "reset_invalid_link",
                        "This reset link is invalid or has expired.",
                    )
                if not default_token_generator.check_token(user, token):
                    return _msg(
                        cfg,
                        "reset_invalid_link",
                        "This reset link is invalid or has expired.",
                    )
                form = SetPasswordForm(
                    user,
                    data={
                        "new_password1": password,
                        "new_password2": confirm,
                    },
                )
                if not form.is_valid():
                    return " ".join(
                        err for errs in form.errors.values() for err in errs
                    )
                form.save()
                return None

            err = await sync_to_async(_confirm)()
            if err:
                setattr(self, e_var, err)
                return
            setattr(self, s_var, True)
            return rx.call_script(_defer_nav_js(login_url))

        ns[cfg.confirm_event] = rx.event(submit_password_reset_confirm_impl)

    cls = types.new_class(cls_name, (base,), {}, exec_body)
    mod_obj = sys.modules.get(state_mod)
    if mod_obj is not None:
        setattr(mod_obj, cls.__name__, cls)
    return cls


__all__ = ["PasswordResetConfig", "password_reset_mixin"]
