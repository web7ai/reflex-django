"""Public exports for reactive model state and CRUD mixins."""

from __future__ import annotations

from typing import ClassVar, Generic, TypeVar

from django.db import models

from reflex_django.state.views.crud import ModelCRUDView
from reflex_django.states import AppState

M = TypeVar("M", bound=models.Model)


class ModelState(AppState, ModelCRUDView, Generic[M]):
    """Reactive CRUD state for one Django model (includes :class:`~reflex_django.states.AppState`).

    Declare once per model::

        class ProductState(ModelState):
            model = Product
            fields = ["name", "price", "is_active"]

    Optional: ``ModelState[Product]`` sets ``model`` from the type argument if you omit
    ``model`` in the class body (typing aid only).

    Use :meth:`refresh`, :meth:`load`, :meth:`save`, :meth:`create`, :meth:`delete`,
    :meth:`filter`, :meth:`paginate`, and related helpers in ``@rx.event`` handlers.

    Override hooks (``get_queryset``, ``validate_state``, …) or replace any generated
    handler by defining the same method on the subclass.
    """

    model: ClassVar[type[models.Model] | None] = None
    fields: ClassVar[tuple[str, ...] | list[str]] = ()


__all__ = ["M", "ModelCRUDView", "ModelState"]
