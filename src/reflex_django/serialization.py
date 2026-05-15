"""JSON-friendly serialization of Django model instances for Reflex state."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.db import models
from django.forms.models import model_to_dict
from django.utils import timezone


def _json_friendly_value(
    val: Any,
    *,
    datetime_format: str,
    date_format: str,
) -> Any:
    """Convert a single field value to a Reflex/JSON-safe representation."""
    if val is None:
        return None
    if isinstance(val, datetime):
        if timezone.is_aware(val):
            val = timezone.localtime(val)
        return val.strftime(datetime_format)
    if isinstance(val, date):
        return val.strftime(date_format)
    if isinstance(val, Decimal):
        return str(val)
    if isinstance(val, UUID):
        return str(val)
    return val


def serialize_model_row(
    instance: models.Model,
    *,
    exclude_fields: frozenset[str],
    datetime_format: str = "%Y-%m-%d %H:%M",
    date_format: str = "%Y-%m-%d",
) -> dict[str, Any]:
    """Build a JSON-friendly row dict for a Django model instance.

    Django 6+ :func:`~django.forms.models.model_to_dict` omits non-editable fields
    (e.g. ``auto_now_add`` / ``auto_now`` timestamps). This helper merges those
    from ``instance._meta.concrete_fields`` and normalizes datetimes for the UI.

    Args:
        instance: Django model row to serialize.
        exclude_fields: Field names to omit (e.g. owner FK).
        datetime_format: ``strftime`` format for :class:`datetime.datetime` values.
        date_format: ``strftime`` format for :class:`datetime.date` values.

    Returns:
        Dict suitable for Reflex state / ``rx.foreach`` row data.
    """
    data = model_to_dict(instance, exclude=list(exclude_fields))
    data["id"] = instance.pk
    for field in instance._meta.concrete_fields:
        if field.name in exclude_fields or field.name in data:
            continue
        data[field.name] = field.value_from_object(instance)
    for key, val in list(data.items()):
        data[key] = _json_friendly_value(
            val,
            datetime_format=datetime_format,
            date_format=date_format,
        )
    return data


__all__ = ["serialize_model_row"]
