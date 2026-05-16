"""Authentication helpers for model state."""

from __future__ import annotations

from typing import Any

from reflex_django.state.base import BaseModelState


class LoginRequiredMixin(BaseModelState):
    """Expose ``get_user`` for scoping overrides."""

    def get_user(self) -> Any:
        req = self.request
        if req is not None and bool(req):
            user = req.user
            if getattr(user, "is_authenticated", False):
                return user
        from reflex_django.auth.shortcuts import require_login_user

        return require_login_user()


__all__ = ["LoginRequiredMixin"]
