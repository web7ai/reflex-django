"""Public exports for reactive model state and CRUD mixins."""

from __future__ import annotations

from typing import Any, ClassVar, Generic, TypeVar

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
            paginate_by = 20
            search_fields = ("name",)

    Optional: ``ModelState[Product]`` sets ``model`` from the type argument if you omit
    ``model`` in the class body (typing aid only).

    **IDE / UI:** default list vars are typed below (``data``, ``error``, ``search``, …).
    Use them in components, e.g. ``rx.foreach(ProductState.data, row)``. Override names
    with ``list_var`` / ``search_var`` on the class body or ``Meta``.

    Use :meth:`refresh`, :meth:`load`, :meth:`save`, :meth:`create`, :meth:`delete`,
    :meth:`filter`, :meth:`paginate`, and related helpers in ``@rx.event`` handlers.
    """

    model: ClassVar[type[models.Model] | None] = None
    fields: ClassVar[tuple[str, ...] | list[str]] = ()

    # Default reactive vars for :class:`ModelState` (assembly may add or rename via Meta).
    data: list[dict[str, Any]] = []
    error: str = ""
    search: str = ""
    editing_id: int = -1
    form_reset_key: int = 0
    total_count: int = 0
    page_count: int = 0
    page: int = 1
    # Set by assembly from ``Meta.paginate_by`` when pagination is enabled.
    page_size: int = 0
    field_errors: dict[str, str] = {}


__all__ = ["M", "ModelCRUDView", "ModelState"]
