"""Tests for reflex_django.django.model: the Reflex serializer for Django models."""

from __future__ import annotations

from reflex_django.setup.conf import configure_django

configure_django()

from django.db import models  # noqa: E402
from reflex_django.django.model import Model, serialize_django_model  # noqa: E402


class _Post(Model):
    """Throwaway Django model used only for serializer round-trip tests."""

    title = models.CharField(max_length=200)
    published = models.BooleanField(default=False)  # pyright: ignore[reportArgumentType]

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Django model metadata for the test model."""

        app_label = "reflex_django"


def test_model_subclass_inherits_django_fields() -> None:
    field_names = {
        f.name
        for f in _Post._meta.get_fields()  # pyright: ignore[reportAttributeAccessIssue]
    }
    assert {"id", "title", "published"} <= field_names


def test_serialize_django_model_includes_pk_and_fields() -> None:
    post = _Post(id=42, title="hello", published=True)

    result = serialize_django_model(post)

    assert result["id"] == 42
    assert result["title"] == "hello"
    assert result["published"] is True


def test_serialize_django_model_includes_auto_timestamps() -> None:
    from datetime import datetime

    class _Stamped(Model):
        title = models.CharField(max_length=32)
        created_at = models.DateTimeField(auto_now_add=True)

        class Meta:
            app_label = "reflex_django"

    row = _Stamped(
        id=7,
        title="ts",
        created_at=datetime(2024, 2, 3, 4, 5),
    )
    result = serialize_django_model(row)
    assert result["created_at"] == "2024-02-03 04:05"


def test_serialize_django_model_preserves_pk_when_unsaved() -> None:
    post = _Post(title="draft")

    result = serialize_django_model(post)

    assert result["id"] is None
    assert result["title"] == "draft"


def test_serializer_registered_for_django_model() -> None:
    """The serializer must be discoverable through Reflex's serializer registry."""
    from reflex_base.utils.serializers import has_serializer

    assert has_serializer(_Post)
