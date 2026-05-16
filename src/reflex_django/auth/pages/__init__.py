"""Canned auth page components."""

from reflex_django.auth.pages.base import AuthPageMeta, BaseAuthPage
from reflex_django.auth.pages.login import LoginPage, login_page
from reflex_django.auth.pages.password_reset import (
    PasswordResetConfirmPage,
    PasswordResetPage,
    password_reset_confirm_page,
    password_reset_page,
)
from reflex_django.auth.pages.register import RegisterPage, register_page

__all__ = [
    "AuthPageMeta",
    "BaseAuthPage",
    "LoginPage",
    "PasswordResetConfirmPage",
    "PasswordResetPage",
    "RegisterPage",
    "login_page",
    "password_reset_confirm_page",
    "password_reset_page",
    "register_page",
]
