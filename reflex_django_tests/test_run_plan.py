"""Tests for dev.run_plan."""

from __future__ import annotations

from reflex_django.dev.run_plan import build_run_plan, resolve_from_build


def test_resolve_from_build_env_dev_is_false():
    assert resolve_from_build({"env": "dev"}) is False


def test_resolve_from_build_env_prod_is_true():
    assert resolve_from_build({"env": "prod"}) is True


def test_build_run_plan_single_port_dev():
    plan = build_run_plan({"env": "dev"})
    assert plan.is_single_port_dev is True
    assert plan.serve_from_disk is True