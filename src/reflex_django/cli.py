"""Reflex CLI integration for reflex-django.

Registers a ``django`` command group on Reflex's ``reflex`` CLI (via an import
hook installed from a ``.pth`` file in the wheel) and exposes the standalone
``reflex-django`` console script.

- ``reflex django <django-args>`` — forwards to Django's management runner.
- ``reflex-django …`` — same forwarding as ``reflex django``.
"""

from __future__ import annotations

import sys
from typing import ClassVar

import click

from reflex_django.conf import configure_django
from reflex_django.integration import install_reflex_django_integration


def _load_rxconfig() -> None:
    """Import the user's ``rxconfig`` so plugin side-effects run.

    ``ReflexDjangoPlugin.__post_init__`` exports ``DJANGO_SETTINGS_MODULE``
    and the API/admin path prefixes into the environment when the plugin is
    instantiated. Loading ``rxconfig`` triggers that instantiation so
    subsequent calls to :func:`configure_django` see the user's settings
    module — without this step, the CLI would fall back to
    :mod:`reflex_django.default_settings`.

    Failures are swallowed so the standalone ``reflex-django`` console
    script keeps working in directories that are not Reflex projects.
    """
    try:
        from reflex_base.config import get_config

        get_config()
    except Exception:
        pass


def _execute(argv: list[str], prog_name: str) -> None:
    """Run a Django management command via ``execute_from_command_line``.

    Args:
        argv: Arguments to forward (e.g. ``["migrate", "--fake-initial"]``).
        prog_name: Name to display in Django help text and error output.
    """
    install_reflex_django_integration()
    _load_rxconfig()
    configure_django()
    from django.core.management import execute_from_command_line

    execute_from_command_line([prog_name, *argv])


def _make_django_forward_command(cmd_name: str) -> click.Command:
    """Build a Click command that forwards ``cmd_name`` to Django."""

    @click.command(
        name=cmd_name,
        context_settings={
            "ignore_unknown_options": True,
            "allow_extra_args": True,
            "help_option_names": ["--reflex-help"],
        },
        add_help_option=False,
    )
    @click.argument("tail", nargs=-1, type=click.UNPROCESSED)
    def _forward(tail: tuple[str, ...]) -> None:
        argv = [cmd_name, *list(tail)] if tail else [cmd_name]
        _execute(argv, prog_name="reflex django")

    return _forward


class DjangoCliGroup(click.Group):
    """``django`` group that forwards unknown subcommands to Django management."""

    _forward_cache: ClassVar[dict[str, click.Command]] = {}

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        rv = super().get_command(ctx, cmd_name)
        if rv is not None:
            return rv
        if cmd_name and not cmd_name.startswith("-"):
            cached = self._forward_cache.get(cmd_name)
            if cached is None:
                cached = _make_django_forward_command(cmd_name)
                self._forward_cache[cmd_name] = cached
            return cached
        return None


@click.group(
    "django",
    cls=DjangoCliGroup,
    invoke_without_command=True,
    short_help="Run Django management commands with your Reflex rxconfig settings.",
)
@click.pass_context
def django_cli_group(ctx: click.Context) -> None:
    """Forward subcommands to Django (``migrate``, ``shell``, …)."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def register_django_cli_group_if_needed(
    reflex_cli: click.Group | None = None,
) -> None:
    """Attach ``django_cli_group`` to Reflex's top-level ``reflex`` CLI (idempotent).

    Args:
        reflex_cli: Optional pre-imported Reflex CLI group. When omitted,
            :mod:`reflex.reflex` is imported for its ``cli`` object.
    """
    if reflex_cli is None:
        from reflex.reflex import cli as reflex_cli

    if reflex_cli.commands.get("django") is not None:
        return
    reflex_cli.add_command(django_cli_group)


# Backward-compatible name (historically a single forwarding command).
django_cli = django_cli_group


def main() -> None:
    """Entry point for the ``reflex-django`` console script."""
    argv = sys.argv[1:]
    if not argv:
        argv = ["help"]
    _execute(argv, prog_name="reflex-django")
