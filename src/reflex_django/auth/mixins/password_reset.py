"""Password reset mixin using Django's token generator and email."""

from __future__ import annotations

import inspect
import re
import sys
import types
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, unquote, urljoin

import reflex as rx
from asgiref.sync import sync_to_async
from django.conf import settings as django_settings
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from reflex_django.auth.settings import AuthSettings
from reflex_django.context import current_request
from reflex_django.mixins.session_auth import _defer_nav_js


@dataclass(frozen=True)
class PasswordResetConfig:
    """Password reset routes and copy."""

    password_reset_url: str = "/password-reset"
    password_reset_confirm_url: str = "/password-reset/confirm/[uid]/[key]"
    login_url: str = "/login"
    error_var: str = "reset_error"
    success_var: str = "reset_success"
    email_sent_var: str = "reset_email_sent"
    confirm_valid_var: str = "reset_link_valid"
    confirm_loaded_var: str = "reset_confirm_loaded"
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
    uid_seg = quote(uid, safe="")
    token_seg = quote(token, safe="")
    return (
        template.replace("[uid]", uid_seg)
        .replace("[token]", token_seg)
        .replace("[key]", token_seg)
        .replace("{uid}", uid_seg)
        .replace("{token}", token_seg)
        .replace("{key}", token_seg)
    )


def _reset_uid_and_token(params: dict[str, Any]) -> tuple[str, str]:
    """Return ``(uid, token)`` from route params.

    Prefer ``key`` over ``token`` because Reflex uses a top-level ``token`` router
    field for the websocket session id, which can shadow dynamic ``[token]`` args.
    """
    uid = str(params.get("uid", "") or "")
    reset_token = str(
        params.get("key", "") or params.get("token", "") or params.get("reset_token", "") or ""
    )
    return uid, reset_token


def _params_from_confirm_path(path: str, template: str) -> dict[str, str]:
    """Parse uid and reset token from the current pathname."""
    path = unquote(path.split("?", 1)[0].rstrip("/") or "/")
    template_path = template.split("?", 1)[0].rstrip("/") or "/"
    if not template_path.startswith("/"):
        template_path = "/" + template_path

    pattern = re.escape(template_path)
    for placeholder, group in (
        ("[uid]", "uid"),
        ("{uid}", "uid"),
        ("[key]", "key"),
        ("{key}", "key"),
        ("[token]", "token"),
        ("{token}", "token"),
        ("[reset_token]", "reset_token"),
        ("{reset_token}", "reset_token"),
    ):
        pattern = pattern.replace(re.escape(placeholder), rf"(?P<{group}>[^/]+)")

    match = re.match(rf"^{pattern}/?$", path)
    if not match:
        return {}

    groups = {k: unquote(v) for k, v in match.groupdict().items() if v}
    uid = groups.get("uid", "")
    reset_token = groups.get("key") or groups.get("token") or groups.get("reset_token") or ""
    if uid and reset_token:
        return {"uid": uid, "key": reset_token}
    return {}


def _page_params(state: Any, *, confirm_template: str | None = None) -> dict[str, str]:
    """Collect dynamic route params from router query, state, and pathname."""
    params: dict[str, str] = {}

    page = getattr(getattr(state, "router", None), "page", None)
    raw_page_params = getattr(page, "params", None)
    if isinstance(raw_page_params, dict):
        params.update({str(k): str(v) for k, v in raw_page_params.items() if v is not None})

    router_data = getattr(state, "router_data", None) or {}
    query = router_data.get("query")
    if isinstance(query, dict):
        for key, value in query.items():
            if value is not None and str(key) not in params:
                params[str(key)] = str(value)

    for name in ("uid", "key", "token", "reset_token"):
        if name in params:
            continue
        value = getattr(state, name, None)
        if value is not None and str(value).strip() != "":
            params[name] = str(value)

    uid, reset_token = _reset_uid_and_token(params)
    if (not uid or not reset_token) and confirm_template:
        path = ""
        if page is not None:
            path = str(getattr(page, "path", "") or "")
        if not path:
            path = str(router_data.get("pathname", "") or router_data.get("path", "") or "")
        parsed = _params_from_confirm_path(path, confirm_template)
        for key, value in parsed.items():
            if key not in params and value:
                params[key] = value

    return params


def _decode_uid(uid: str) -> str:
    return force_str(urlsafe_base64_decode(uid))


def populate_password_reset_state(
    ns: dict[str, Any],
    cfg: PasswordResetConfig,
    *,
    cls_name: str,
    annotations: dict[str, type],
) -> None:
    """Add password reset fields and handlers to ``ns`` (flat state build)."""
    e_var = cfg.error_var
    s_var = cfg.success_var
    sent_var = cfg.email_sent_var
    valid_var = cfg.confirm_valid_var
    loaded_var = cfg.confirm_loaded_var
    login_url = cfg.login_url
    confirm_template = cfg.password_reset_confirm_url

    annotations[e_var] = str
    annotations[s_var] = bool
    annotations[sent_var] = bool
    annotations[valid_var] = bool
    annotations[loaded_var] = bool
    ns[e_var] = ""
    ns[s_var] = False
    ns[sent_var] = False
    ns[valid_var] = False
    ns[loaded_var] = False

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
        setattr(self, loaded_var, False)
        raw_params = _page_params(self, confirm_template=confirm_template)
        uid, token = _reset_uid_and_token(raw_params)
        uid = unquote(uid)
        token = unquote(token)

        def _check() -> bool:
            from django.contrib.auth import get_user_model

            user_model = get_user_model()
            try:
                pk = _decode_uid(uid)
                user = user_model.objects.get(pk=pk)
            except (TypeError, ValueError, OverflowError, user_model.DoesNotExist):
                return False
            return default_token_generator.check_token(user, token)

        ok = bool(uid and token and await sync_to_async(_check)())
        setattr(self, valid_var, ok)
        setattr(self, loaded_var, True)
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

        raw_params = _page_params(self, confirm_template=confirm_template)
        uid, token = _reset_uid_and_token(raw_params)
        uid = unquote(uid)
        token = unquote(token)
        password = str(form_data.get("new_password", ""))
        confirm = str(form_data.get("confirm_password", ""))

        def _confirm() -> str | None:
            from django.contrib.auth import get_user_model

            user_model = get_user_model()
            try:
                pk = _decode_uid(uid)
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

    cls_name = cfg.state_class_name

    def exec_body(ns: dict[str, Any]) -> None:
        ns["__module__"] = state_mod
        annotations = dict(getattr(base, "__annotations__", {}))
        populate_password_reset_state(
            ns,
            cfg,
            cls_name=cls_name,
            annotations=annotations,
        )
        ns["__annotations__"] = annotations

    cls = types.new_class(cls_name, (base,), {}, exec_body)
    mod_obj = sys.modules.get(state_mod)
    if mod_obj is not None:
        setattr(mod_obj, cls.__name__, cls)
    return cls


__all__ = [
    "PasswordResetConfig",
    "password_reset_mixin",
    "populate_password_reset_state",
]
