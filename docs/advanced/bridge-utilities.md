# Bridge utilities

Low-level helpers for reading Django context outside `AppState` fields, or inside plain functions called from handlers.

For the integration overview, see [Bridge](../learn/bridge.md).

## Context accessors

Available while an event is running (after bridge middleware):

```python
from reflex_django import (
    current_request,
    current_user,
    current_session,
    current_messages,
    current_language,
    current_csrf_token,
    current_response,
)
```

| Function | Returns |
|:---|:---|
| `current_request()` | Synthetic `HttpRequest` for this event |
| `current_user()` | Django user (anonymous when logged out) |
| `current_session()` | Session store |
| `current_messages()` | Django messages list |
| `current_language()` | Active locale code |
| `current_csrf_token()` | CSRF token string |
| `current_response()` | Response from middleware chain (if any) |

Module-level `request` is a lazy proxy to `current_request()`.

## Run middleware manually

```python
from reflex_django import run_middleware_chain

response = await run_middleware_chain(request)
```

Rare outside the bridge. Useful in tests or custom ASGI wiring.

## Mirror settings

Control what AppState syncs into reactive vars (`settings.py`):

| Setting | Default | Purpose |
|:---|:---|:---|
| `RX_AUTH_AUTO_SYNC` | `True` | Refresh auth snapshot after events |
| `RX_MIRROR_MESSAGES` | `True` | Django messages in state |
| `RX_MIRROR_CSRF` | `True` | CSRF token in state |
| `RX_MIRROR_LANGUAGE` | `True` | Locale in state |

Set to `False` with `RX_PERFORMANCE_PRESET = "lean"` for hot UI-only pages. See [Scaling](scaling.md).

## Session cookie JS

After programmatic login/logout, the browser may need cookie updates (Reflex events do not run `SessionMiddleware` on the real HTTP response):

```python
from reflex_django.bridge.session_js import (
    session_cookie_set_js,
    session_cookie_clear_js,
)
```

Built-in auth pages handle this automatically.

## Plugin bridge keys

In `ReflexDjangoPlugin`:

| Key | Purpose |
|:---|:---|
| `bridge.mode` | `full`, `smart`, or `none` |
| `bridge.run_middleware_chain` | Run full `MIDDLEWARE` on events |
| `bridge.resolver` | Callable to pick tier per event |

Per-state override: `_rx_bridge = "none"` on the class body.

**Next:** [i18n](i18n.md) for locale snapshots.
