"""Public alias for the batteries-included CRUD stack."""

from __future__ import annotations

from reflex_django.state.views.crud import ModelCRUDView

ModelState = ModelCRUDView

__all__ = ["ModelCRUDView", "ModelState"]
