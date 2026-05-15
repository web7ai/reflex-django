"""Tests for :mod:`reflex_django.states`."""

from __future__ import annotations

from abc import ABC

import reflex as rx

from reflex_django.states import AppState


def test_app_state_is_rx_state_subclass() -> None:
    assert issubclass(AppState, rx.State)
    assert issubclass(AppState, ABC)


def test_app_state_can_be_subclassed() -> None:
    class MyAppState(AppState):
        pass

    assert issubclass(MyAppState, AppState)
    assert issubclass(MyAppState, rx.State)
