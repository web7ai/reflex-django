"""Typed descriptors for editable vars on :class:`~reflex_django.state.views.crud.ModelCRUDView`."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

TVar = TypeVar("TVar")
TPython = TypeVar("TPython")

Validator = Callable[[Any], str | None]


@dataclass(frozen=True)
class StateField(Generic[TVar, TPython]):
    """Maps a Reflex state var to a Python value for ORM writes."""

    name: str
    var_type: type
    required: bool = False
    validators: tuple[Validator, ...] = field(default_factory=tuple)

    def to_python(self, raw: TVar) -> TPython:
        return raw  # type: ignore[return-value]

    def to_var(self, value: TPython | None) -> TVar:
        if value is None:
            return self.var_type()  # type: ignore[call-arg]
        return self.var_type(value)  # type: ignore[call-arg, return-value]

    def validate_value(self, value: TPython) -> str | None:
        for validator in self.validators:
            err = validator(value)
            if err:
                return err
        return None


@dataclass(frozen=True)
class StrStateField(StateField[str, str]):
    var_type: type = str

    def to_python(self, raw: str) -> str:
        return str(raw).strip()

    def to_var(self, value: str | None) -> str:
        if value is None:
            return ""
        return str(value)


@dataclass(frozen=True)
class IntStateField(StateField[int, int]):
    var_type: type = int

    def to_python(self, raw: int) -> int:
        return int(raw)

    def to_var(self, value: int | None) -> int:
        return 0 if value is None else int(value)


@dataclass(frozen=True)
class BoolStateField(StateField[bool, bool]):
    var_type: type = bool

    def to_python(self, raw: bool) -> bool:
        return bool(raw)

    def to_var(self, value: bool | None) -> bool:
        return False if value is None else bool(value)


def state_field_for_name(name: str, *, required: bool = False) -> StateField[Any, Any]:
    """Default field descriptor (string var)."""
    return StrStateField(name=name, required=required)


def build_state_fields(
    names: Sequence[str],
    *,
    required_fields: frozenset[str],
) -> tuple[StateField[Any, Any], ...]:
    return tuple(
        state_field_for_name(n, required=n in required_fields) for n in names
    )


__all__ = [
    "BoolStateField",
    "IntStateField",
    "StateField",
    "StrStateField",
    "build_state_fields",
    "state_field_for_name",
]
