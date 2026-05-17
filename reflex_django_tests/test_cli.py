"""Tests for ``reflex_django.cli`` — the Django management passthrough."""

from __future__ import annotations

from unittest import mock

import click
from click.testing import CliRunner

from reflex_django import cli as cli_module
from reflex_django.cli import django_cli, main, register_django_cli_group_if_needed


def test_django_cli_forwards_args_verbatim(
    monkeypatch,
) -> None:
    """``reflex django migrate`` calls execute_from_command_line with migrate."""
    sentinel = mock.Mock()
    monkeypatch.setattr("django.core.management.execute_from_command_line", sentinel)

    runner = CliRunner()
    result = runner.invoke(django_cli, ["migrate", "--fake-initial"])

    assert result.exit_code == 0, result.output
    sentinel.assert_called_once_with(["reflex django", "migrate", "--fake-initial"])


def test_django_cli_help_when_no_subcommand(monkeypatch) -> None:
    """Bare ``reflex django`` prints the Click group help (does not call Django)."""
    sentinel = mock.Mock()
    monkeypatch.setattr("django.core.management.execute_from_command_line", sentinel)

    runner = CliRunner()
    result = runner.invoke(django_cli, [])

    assert result.exit_code == 0, result.output
    sentinel.assert_not_called()
    assert "Django" in result.output


def test_django_cli_passes_through_dash_help(monkeypatch) -> None:
    """``--help`` is forwarded to Django so per-command help works."""
    sentinel = mock.Mock()
    monkeypatch.setattr("django.core.management.execute_from_command_line", sentinel)

    runner = CliRunner()
    result = runner.invoke(django_cli, ["migrate", "--help"])

    assert result.exit_code == 0, result.output
    sentinel.assert_called_once_with(["reflex django", "migrate", "--help"])


def test_django_cli_configures_django_before_dispatch(monkeypatch) -> None:
    """configure_django() must run before execute_from_command_line()."""
    order: list[str] = []
    monkeypatch.setattr(
        cli_module, "configure_django", lambda: order.append("configured")
    )
    monkeypatch.setattr(
        "django.core.management.execute_from_command_line",
        lambda argv: order.append(f"exec:{argv[1]}"),
    )

    runner = CliRunner()
    result = runner.invoke(django_cli, ["migrate"])

    assert result.exit_code == 0, result.output
    assert order == ["configured", "exec:migrate"]


def test_main_console_script_forwards_sys_argv(monkeypatch) -> None:
    """``reflex-django migrate`` console-script entry calls execute_from_command_line."""
    sentinel = mock.Mock()
    monkeypatch.setattr("django.core.management.execute_from_command_line", sentinel)
    monkeypatch.setattr("sys.argv", ["reflex-django", "migrate", "--verbosity=2"])

    main()

    sentinel.assert_called_once_with(["reflex-django", "migrate", "--verbosity=2"])


def test_main_console_script_help_when_no_args(monkeypatch) -> None:
    """Bare ``reflex-django`` forwards ``help`` to Django."""
    sentinel = mock.Mock()
    monkeypatch.setattr("django.core.management.execute_from_command_line", sentinel)
    monkeypatch.setattr("sys.argv", ["reflex-django"])

    main()

    sentinel.assert_called_once_with(["reflex-django", "help"])


def test_register_django_cli_group_if_needed_idempotent() -> None:
    """Registering twice on a synthetic group does not duplicate ``django``."""
    cli = click.Group()

    register_django_cli_group_if_needed(cli)
    assert "django" in cli.commands

    register_django_cli_group_if_needed(cli)
    assert len([n for n in cli.commands if n == "django"]) == 1

