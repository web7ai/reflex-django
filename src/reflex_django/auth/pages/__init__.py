"""Canned auth page components."""

from reflex_django.auth.pages.login import login_page
from reflex_django.auth.pages.password_reset import (
    password_reset_confirm_page,
    password_reset_page,
)
from reflex_django.auth.pages.register import register_page

__all__ = [
    "login_page",
    "password_reset_confirm_page",
    "password_reset_page",
    "register_page",
]
