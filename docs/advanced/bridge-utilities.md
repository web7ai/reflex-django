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

## Request lifecycle helpers

These helpers are used by the bridge and are available for custom integrations/tests:

```python
from reflex_django import (
    begin_event_request,
    begin_event_response,
    end_event_request,
    end_event_response,
)
```

They bind/unbind the current synthetic `HttpRequest` and response with `contextvars`. Prefer `current_request()` and `current_response()` in application code.

## Bridge module exports

```python
from reflex_django.bridge import (
    DjangoEventBridge,
    bind_django_request_for_handler_state,
    bridge_request_for_state,
    invalidate_event_cache,
    resolve_bridge_tier,
)
```

| API | Purpose |
|:---|:---|
| `resolve_bridge_tier(state_cls, event)` | Return `full`, `auth_only`, or `none` |
| `invalidate_event_cache(request_or_session)` | Drop cached auth/session event context |
| `bridge_request_for_state(state)` | Read the bound bridge request for a state |
| `bind_django_request_for_handler_state(...)` | Bind request/response to the handler state branch |
| `DjangoEventBridge` | Event preprocess/postprocess bridge class |

## Run middleware manually

```python
from reflex_django import run_middleware_chain

response = await run_middleware_chain(request)
```

Rare outside the bridge. Useful in tests or custom ASGI wiring.

When `RX_AUTO_REDIRECT_FROM_MIDDLEWARE=True`, middleware 3xx responses are converted into Reflex redirects during normal event processing.

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

See [Bridge](../learn/bridge.md) for resolver precedence, the `auth_only` tier, and upload tier floors.

**Next:** [i18n](i18n.md) for locale snapshots.
