"""A small dev overlay showing the bridge tier, query count, and bound user.

Usage in a Reflex app::

    import reflex_django.devtools as devtools

    def index() -> rx.Component:
        return rx.fragment(
            my_page(),
            devtools.dev_inspector_overlay(),
        )

Trigger ``DjangoDevToolsState.capture`` from an event (or ``on_mount``) to
refresh the panel with the most recent event's diagnostics.
"""

from __future__ import annotations

import reflex as rx

from reflex_django.devtools.report import collect_inspection_summary


class DjangoDevToolsState(rx.State):
    """Holds the latest captured event diagnostics for the overlay."""

    tier: str = ""
    handler: str = ""
    duration_ms: float = 0.0
    query_count: int = 0
    user: str = "AnonymousUser"
    authenticated: bool = False
    path: str = ""
    visible: bool = True

    @rx.event
    def capture(self) -> None:
        """Snapshot the current event's bridge diagnostics into overlay vars."""
        summary = collect_inspection_summary()
        self.tier = str(summary["tier"]) or "none"
        self.handler = str(summary["handler"])
        self.duration_ms = float(summary["duration_ms"])
        self.query_count = int(summary["query_count"])
        self.user = str(summary["user"])
        self.authenticated = bool(summary["authenticated"])
        self.path = str(summary["path"])

    @rx.event
    def toggle(self) -> None:
        self.visible = not self.visible


def _row(label: str, value: rx.Var | str) -> rx.Component:
    return rx.hstack(
        rx.text(label, size="1", weight="bold", color="gray"),
        rx.spacer(),
        rx.text(value, size="1", font_family="monospace"),
        width="100%",
        spacing="3",
    )


def dev_inspector_overlay() -> rx.Component:
    """A fixed-position overlay with the latest bridge-tier diagnostics."""
    state = DjangoDevToolsState
    return rx.cond(
        state.visible,
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.text("reflex-django devtools", size="1", weight="bold"),
                    rx.spacer(),
                    rx.button("x", size="1", variant="ghost", on_click=state.toggle),
                    width="100%",
                ),
                _row("tier", state.tier),
                _row("queries", state.query_count.to_string()),
                _row("duration ms", state.duration_ms.to_string()),
                _row("user", state.user),
                _row("path", state.path),
                rx.button(
                    "refresh",
                    size="1",
                    width="100%",
                    on_click=state.capture,
                ),
                spacing="1",
                width="100%",
            ),
            position="fixed",
            bottom="1rem",
            right="1rem",
            width="16rem",
            padding="0.75rem",
            border_radius="0.5rem",
            border="1px solid var(--gray-5)",
            background="var(--color-panel-solid, white)",
            box_shadow="0 4px 16px rgba(0,0,0,0.15)",
            z_index="9999",
        ),
        rx.box(
            rx.button("devtools", size="1", on_click=state.toggle),
            position="fixed",
            bottom="1rem",
            right="1rem",
            z_index="9999",
        ),
    )


__all__ = ["DjangoDevToolsState", "dev_inspector_overlay"]
