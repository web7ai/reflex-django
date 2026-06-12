"""Django ORM integration for Reflex state.

Exports an abstract :class:`Model` base for users to extend (so their app's
Django models live under ``reflex_django``'s metadata when convenient) and
registers a Reflex serializer that converts a Django ``Model`` instance into a
JSON-friendly dict via :func:`django.forms.models.model_to_dict`.

Importing this module triggers :func:`reflex_django.conf.configure_django` so
:class:`django.db.models.Model` is safe to subclass at module import time.
"""

from __future__ import annotations

from typing import Any

from reflex_base.utils.serializers import serializer

from reflex_django.setup.conf import configure_django

# Importing Django's ORM module requires django.setup() to have run.
configure_django()

from django.db import models  # noqa: E402


class Model(models.Model):
    """Abstract Django Model base for reflex-django apps.

    Subclasses get a ``BigAutoField`` primary key by default and the standard
    Django ORM API. Inherit from this class (or directly from
    :class:`django.db.models.Model`) for new tables, then run
    ``python manage.py makemigrations && migrate`` to apply schema changes.

    Example:
        >>> class Post(Model):
        ...     title = models.CharField(max_length=200)
    """

    class Meta:
        """Django model metadata for the abstract reflex-django base."""

        abstract = True


def _model_to_dict(value: models.Model) -> dict[str, Any]:
    """Serialize a Django Model instance to a JSON-friendly dict.

    Includes non-editable fields (timestamps) omitted by Django 6+
    :func:`~django.forms.models.model_to_dict`, plus the primary key as ``id``.

    Args:
        value: The Django model instance to serialize.

    Returns:
        A dict containing the model's field values and primary key.
    """
    from reflex_django.serializers.core import serialize_model_row

    return serialize_model_row(value, exclude_fields=frozenset())


@serializer(to=dict)
def serialize_django_model(value: models.Model) -> dict[str, Any]:
    """Reflex serializer hook for Django model instances.

    Args:
        value: The Django model instance to serialize.

    Returns:
        A dict suitable for sending to the Reflex frontend.
    """
    return _model_to_dict(value)


__all__ = ["Model", "serialize_django_model"]
