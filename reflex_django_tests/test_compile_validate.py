"""Tests for frontend dispatcher validation."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from reflex_django.runtime.compile_validate import (
    dispatch_keys_from_context_js,
    expected_dispatch_keys_from_app,
    filter_delta_to_compiled_dispatch_keys,
    missing_frontend_dispatchers,
)


def test_dispatch_keys_from_context_js_extracts_dispatcher_map(tmp_path: Path) -> None:
    context = tmp_path / "context.js"
    context.write_text(
        """
export function StateProvider({ children }) {
  const dispatchers = useMemo(() => ({
    "reflex___state____state": dispatch_reflex___state____state,
    "reflex___state____state.demo___views____home_state": dispatch_home,
  }), [])
}
""",
        encoding="utf-8",
    )
    keys = dispatch_keys_from_context_js(context)
    assert "reflex___state____state" in keys
    assert "reflex___state____state.demo___views____home_state" in keys


def test_missing_frontend_dispatchers_reports_backend_only_states(
    tmp_path: Path, monkeypatch
) -> None:
    context = tmp_path / "context.js"
    context.write_text(
        '"reflex___state____state": dispatch_root,',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "reflex.state.all_base_state_classes",
        {
            "reflex___state____state": None,
            "reflex___state____state.demo___views____home_state": None,
        },
    )
    expected = {
        "reflex___state____state": None,
        "reflex___state____state.demo___views____home_state": None,
    }
    missing = missing_frontend_dispatchers(
        context,
        expected_keys=set(expected),
    )
    assert missing == ["reflex___state____state.demo___views____home_state"]


def test_missing_frontend_dispatchers_with_explicit_expected_keys(
    tmp_path: Path,
) -> None:
    context = tmp_path / "context.js"
    context.write_text(
        '"reflex___state____state": dispatch_root,',
        encoding="utf-8",
    )
    expected = {
        "reflex___state____state",
        "reflex___state____state.demo___views____home_state",
    }
    missing = missing_frontend_dispatchers(context, expected_keys=expected)
    assert missing == ["reflex___state____state.demo___views____home_state"]


def test_expected_dispatch_keys_from_app_returns_sorted_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "reflex.compiler.utils.compile_state",
        lambda _state: {
            "reflex___state____state": {},
            "reflex___state____state.demo___views____home_state": {},
        },
    )
    import reflex_django.runtime.compile_validate as cv

    keys = cv.expected_dispatch_keys_from_app(mock.Mock(_state=object))
    assert keys == {
        "reflex___state____state",
        "reflex___state____state.demo___views____home_state",
    }
