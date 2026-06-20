# Devtools

reflex-django includes opt-in development inspectors for bridge tier, event timing, SQL query count, bound request/user summary, and state-tree snapshots.

Enable only in development:

```python
RX_DEVTOOLS = True
```

or:

```bash
RX_DEVTOOLS=1 reflex run
```

## Overlay

Add the overlay to a page:

```python
import reflex as rx
import reflex_django.devtools as devtools


def index() -> rx.Component:
    return rx.fragment(
        page_content(),
        devtools.dev_inspector_overlay(),
    )
```

The overlay uses `DjangoDevToolsState` and shows the latest captured tier, handler, duration, query count, user, and path. Click refresh to snapshot current diagnostics into state vars.

## Event inspection

The bridge automatically calls `start_event_capture` and `finish_event_capture` around events when devtools are enabled.

```python
from reflex_django.devtools import collect_inspection_summary

summary = collect_inspection_summary()
```

Summary keys:

| Key | Meaning |
|:---|:---|
| `tier` | Resolved bridge tier |
| `handler` | Handler name |
| `duration_ms` | Event wall-clock time |
| `query_count` | Captured SQL count |
| `total_query_ms` | Sum of captured SQL durations |
| `user` | Bound user display |
| `authenticated` | Bound user auth status |
| `session_key` | Bound session key |
| `path` | Synthetic request path |

Outside an event, summaries return safe defaults.

## Programmatic API

```python
from reflex_django.devtools import (
    EventInspection,
    QueryRecord,
    bound_request_summary,
    capture_queries,
    collect_inspection_summary,
    current_inspection,
    devtools_enabled,
    finish_event_capture,
    start_event_capture,
    state_tree_snapshot,
)
```

| API | Purpose |
|:---|:---|
| `devtools_enabled()` | Reads `RX_DEVTOOLS` env/settings |
| `current_inspection()` | Current event record or `None` |
| `capture_queries()` | Context manager for sync query capture |
| `start_event_capture()` / `finish_event_capture()` | Low-level event capture hooks |
| `bound_request_summary()` | Summarize current request/user/session/path |
| `state_tree_snapshot(state)` | JSON-ish Reflex substate tree snapshot |
| `EventInspection` | Mutable event record |
| `QueryRecord` | Captured SQL + duration |

`capture_queries()` is fully reliable for synchronous queries executed inside the block. Async ORM may run on another connection, so per-event bridge capture is usually more useful.

## State snapshots

```python
snapshot = state_tree_snapshot(self, max_depth=4)
```

Snapshots include public reactive vars with JSON-friendly values and recurse through substates up to `max_depth`. They are defensive against Reflex internal shape changes and omit underscore-prefixed vars.

## When to use

| Question | Signal |
|:---|:---|
| Is this event using `full`, `auth_only`, or `none`? | Bridge tier |
| Did a handler add unexpected ORM work? | Query count and total query ms |
| Is the right request/user bound? | Request summary |
| Which state branch is active? | State tree snapshot |

Do not enable `RX_DEVTOOLS` in production; it captures diagnostics intended for local debugging.

**Next:** [Bridge](../learn/bridge.md), [Scaling](scaling.md), and [Troubleshooting](troubleshooting.md).
