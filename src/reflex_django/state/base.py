"""Core types for the model state CBV stack."""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from typing import Any, ClassVar

from django.db import models

from reflex_django.serializers import ReflexDjangoModelSerializer
from reflex_django.state.options import ModelStateOptions


@dataclass
class ActionContext:
    """Per-event context passed through hooks and backends."""

    action: str
    state: Any
    user: Any | None
    pk: int | None
    options: ModelStateOptions
    backend: Any
    request: Any | None = None


class BaseModelState(ABC):
    """Base hooks shared by all model state mixins."""

    serializer_class: ClassVar[type[ReflexDjangoModelSerializer] | None] = None
    model: ClassVar[type[models.Model] | None] = None
    ordering: ClassVar[tuple[str, ...]] = ("-created_at",)
    permission_classes: ClassVar[tuple[type, ...]] = ()
    login_required: ClassVar[bool] = True
    state_validators: ClassVar[tuple[Any, ...]] = ()

    _model_state_options: ClassVar[ModelStateOptions | None] = None

    @property
    def request(self) -> Any:
        """Bridged request for the current event (not a Reflex var)."""
        try:
            return object.__getattribute__(self, "_rd_request")
        except AttributeError:
            return None

    @property
    def django_request(self) -> Any:
        """Raw :class:`django.http.HttpRequest` for the current event."""
        try:
            return object.__getattribute__(self, "_rd_django_request")
        except AttributeError:
            return None

    @classmethod
    def get_options(cls) -> ModelStateOptions:
        opts = cls._model_state_options
        if opts is None:
            msg = f"{cls.__name__} has no resolved ModelStateOptions."
            raise RuntimeError(msg)
        return opts

    def get_backend(self) -> Any:
        opts = self.get_options()
        return opts.backend_class(self)

    def setup(self, action: str) -> None:
        """Pre-action hook (override in subclasses)."""

    def teardown(self, action: str) -> None:
        """Clear per-event request bindings."""
        self._clear_request_bindings()

    async def bind_request_context(self) -> None:
        """Attach :attr:`request` and :attr:`django_request` for this event."""
        from reflex_django.bridge.context import current_request
        from reflex_django.state.request import DjangoStateRequest

        http_request = current_request()
        wrapper = DjangoStateRequest(http_request)
        object.__setattr__(self, "_rd_request", wrapper)
        object.__setattr__(self, "_rd_django_request", http_request)

    def _clear_request_bindings(self) -> None:
        object.__setattr__(self, "_rd_request", None)
        object.__setattr__(self, "_rd_django_request", None)

    def _resolve_action_request(self) -> Any | None:
        """Return a bridged request when one is bound to the current event."""
        from reflex_django.bridge.context import current_request
        from reflex_django.state.request import DjangoStateRequest

        http = current_request()
        if http is None:
            return None
        return DjangoStateRequest(http)

    def build_context(self, action: str, **kwargs: Any) -> ActionContext:
        pk = kwargs.get("pk")
        if pk is not None:
            pk = int(pk)
        user = None
        if self.login_required and action in self.get_options().login_required_actions:
            from reflex_django.auth.shortcuts import require_login_user

            user = require_login_user()
        return ActionContext(
            action=action,
            state=self,
            user=user,
            pk=pk,
            options=self.get_options(),
            backend=self.get_backend(),
            request=self._resolve_action_request(),
        )

    def handle_exception(self, ctx: ActionContext, exc: BaseException) -> None:
        opts = ctx.options
        setattr(self, opts.error_var, str(exc))

    def get_error_message(self, field: str, code: str) -> str:
        return f"{field}: {code}"


__all__ = ["ActionContext", "BaseModelState"]
