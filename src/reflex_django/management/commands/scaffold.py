"""``reflex django scaffold <app.Model>`` - generate CRUD state + pages.

Introspects a Django model and emits a runnable Reflex views module containing
a typed ``ModelState``, an optional serializer, and list/form/detail page
components.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError

from reflex_django.scaffold import render_scaffold


class Command(BaseCommand):
    """Generate a Reflex CRUD views module from a Django model."""

    help = "Generate a Reflex ModelState and list/form pages for a Django model."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "model",
            help="Target model as 'app_label.ModelName' (e.g. 'shop.Product').",
        )
        parser.add_argument(
            "--fields",
            default="",
            help="Comma-separated editable fields to expose (default: all editable).",
        )
        parser.add_argument(
            "--serializer",
            action="store_true",
            help="Emit an explicit ReflexDjangoModelSerializer class.",
        )
        parser.add_argument(
            "--paginate-by",
            type=int,
            default=20,
            help="Page size for the list view (use 0 to disable pagination).",
        )
        parser.add_argument(
            "--search",
            default="",
            help="Comma-separated search fields (default: text fields).",
        )
        parser.add_argument(
            "--route",
            default="",
            help="Page route (default: pluralized model name).",
        )
        parser.add_argument(
            "-o",
            "--output",
            default="",
            help="Write to this file path instead of stdout.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite the output file if it already exists.",
        )

    def _resolve_model(self, label: str) -> type[Any]:
        if "." not in label:
            msg = "Model must be given as 'app_label.ModelName', got {label!r}."
            raise CommandError(msg.format(label=label))
        app_label, _, model_name = label.partition(".")
        try:
            return apps.get_model(app_label, model_name)
        except LookupError as exc:
            raise CommandError(str(exc)) from exc

    @staticmethod
    def _split(value: str) -> list[str] | None:
        parts = [part.strip() for part in value.split(",") if part.strip()]
        return parts or None

    def handle(self, *args: Any, **options: Any) -> None:
        model = self._resolve_model(options["model"])
        paginate_by = options["paginate_by"] or None
        try:
            source = render_scaffold(
                model,
                fields=self._split(options["fields"]),
                include_serializer=options["serializer"],
                paginate_by=paginate_by,
                search_fields=self._split(options["search"]),
                route=options["route"].strip() or None,
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        output = options["output"].strip()
        if not output:
            self.stdout.write(source)
            return

        path = Path(output)
        if path.exists() and not options["force"]:
            raise CommandError(f"{path} already exists. Pass --force to overwrite.")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
        self.stdout.write(
            self.style.SUCCESS(f"Wrote {model._meta.label} scaffold to {path}")
        )


__all__ = ["Command"]
