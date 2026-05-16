"""Optional convenience mixins for common scoping patterns."""

from __future__ import annotations

from typing import Any, ClassVar

from django.db.models import QuerySet


class UserScopedMixin:
    """Filter queryset and lookups by a user-related field (opt-in recipe).

    Combine with :class:`~reflex_django.state.views.crud.ModelCRUDView` and
    override ``scope_field`` (default ``"user_id"``). Requires
    :meth:`~reflex_django.state.mixins.auth.LoginRequiredMixin.get_user` on the
    state class (included on :class:`~reflex_django.state.views.crud.ModelCRUDView`).
    """

    scope_field: ClassVar[str] = "user_id"

    def get_queryset(self) -> QuerySet[Any]:
        user = self.get_user()
        return super().get_queryset().filter(**{self.scope_field: user.pk})

    def get_object_lookup(self, pk: int) -> dict[str, Any]:
        lookup = super().get_object_lookup(pk)
        lookup[self.scope_field] = self.get_user().pk
        return lookup

    def get_create_kwargs(self, state_data: dict[str, Any]) -> dict[str, Any]:
        kwargs = super().get_create_kwargs(state_data)
        kwargs[self.scope_field] = self.get_user().pk
        return kwargs


__all__ = ["UserScopedMixin"]
