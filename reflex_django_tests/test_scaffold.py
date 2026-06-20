"""Tests for `reflex django scaffold` code generation and management command."""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import models

from reflex_django.setup.conf import configure_django

configure_django()

from reflex_django.management.commands.scaffold import Command as ScaffoldCommand  # noqa: E402
from reflex_django.scaffold import editable_fields, render_scaffold  # noqa: E402


class ScProduct(models.Model):
    name = models.CharField(max_length=100, verbose_name="name")
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    quantity = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "reflex_django_tests"


def test_editable_fields_skips_pk_and_auto_timestamps() -> None:
    names = [f.name for f in editable_fields(ScProduct)]
    assert names == ["name", "description", "price", "quantity", "is_active"]


def test_editable_fields_widget_mapping() -> None:
    by = {f.name: f for f in editable_fields(ScProduct)}
    assert by["name"].widget == "text"
    assert by["description"].widget == "textarea"
    assert by["price"].widget == "number"
    assert by["quantity"].widget == "number"
    assert by["is_active"].widget == "bool"


def test_render_scaffold_is_valid_python() -> None:
    src = render_scaffold(ScProduct)
    compile(src, "<scaffold>", "exec")


def test_render_scaffold_contains_state_and_pages() -> None:
    src = render_scaffold(ScProduct, paginate_by=20)
    assert "class ScProductState(ModelState):" in src
    assert "model = ScProduct" in src
    assert 'fields = ["name", "description", "price", "quantity", "is_active"]' in src
    assert "paginate_by = 20" in src
    assert "def scproduct_row(row: dict)" in src
    assert "def scproduct_form()" in src
    assert "def scproduct_list()" in src
    assert "def scproduct_page()" in src
    assert 'search_fields = ("name", "description")' in src


def test_render_scaffold_with_explicit_fields_and_serializer() -> None:
    src = render_scaffold(
        ScProduct,
        fields=["name", "price"],
        include_serializer=True,
    )
    compile(src, "<scaffold>", "exec")
    assert "class ScProductSerializer(ReflexDjangoModelSerializer):" in src
    assert 'fields = ("id", "name", "price")' in src
    assert "serializer = ScProductSerializer" in src
    assert 'fields = ["name", "price"]' in src


def test_render_scaffold_widgets_present() -> None:
    src = render_scaffold(ScProduct)
    assert "rx.checkbox(" in src
    assert "rx.text_area(" in src
    assert 'type="number"' in src


def test_render_scaffold_no_pagination_omits_controls() -> None:
    src = render_scaffold(ScProduct, paginate_by=None)
    assert "paginate_by" not in src
    assert '"Prev"' not in src


def test_render_scaffold_unknown_field_raises() -> None:
    with pytest.raises(ValueError):
        render_scaffold(ScProduct, fields=["does_not_exist"])


def test_scaffold_command_prints_for_installed_model() -> None:
    out = StringIO()
    call_command(ScaffoldCommand(), "auth.Group", stdout=out)
    src = out.getvalue()
    assert "class GroupState(ModelState):" in src
    compile(src, "<scaffold>", "exec")


def test_scaffold_command_writes_file(tmp_path) -> None:
    target = tmp_path / "group_views.py"
    out = StringIO()
    call_command(
        ScaffoldCommand(),
        "auth.Group",
        "--output",
        str(target),
        stdout=out,
    )
    assert target.exists()
    compile(target.read_text(encoding="utf-8"), "<scaffold>", "exec")


def test_scaffold_command_refuses_overwrite_without_force(tmp_path) -> None:
    target = tmp_path / "group_views.py"
    target.write_text("# existing", encoding="utf-8")
    with pytest.raises(CommandError):
        call_command(ScaffoldCommand(), "auth.Group", "--output", str(target))


def test_scaffold_command_bad_model_raises() -> None:
    with pytest.raises(CommandError):
        call_command(ScaffoldCommand(), "auth.DoesNotExist")

    with pytest.raises(CommandError):
        call_command(ScaffoldCommand(), "NoDotHere")
