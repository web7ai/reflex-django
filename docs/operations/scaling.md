---
level: advanced
tags: [performance, deployment, settings]
---

# Scaling and performance

**What you will learn:** How to tune reflex-django as a **Django + realtime UI stack** from `settings.py` alone  -  bridge tiers, cache, lean WebSocket deltas, and production topology.

**When you need this:**

- High event volume (filters, live dashboards, typing indicators).
- Multi-worker Reflex backends or split Django / Reflex processes.
- You want performance knobs without reading bridge source.

!!! tip "Defaults are safe"
    Out of the box, `RX_EVENT_BRIDGE_MODE = "full"`  -  the same behavior as before tiered bridges. Enable `"smart"` and `"lean"` only when you need them.

---

## Cheatsheet (`settings.py`)

Copy-paste starting point for a large app (all opt-in):

```python
import os

# Bridge: skip middleware for plain rx.State; full chain for AppState / ModelState
RX_EVENT_BRIDGE_MODE = "smart"

# Smaller WebSocket deltas when mirror toggles still match library defaults
RX_PERFORMANCE_PRESET = "lean"

# Multi-worker Reflex state (required when running >1 Reflex backend worker)
RX_CONFIG = {
    "redis_url": os.environ["REDIS_URL"],
}

# Session cache between events (choose backend via CACHES)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ["REDIS_URL"],
    },
    "reflex_events": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ["REDIS_URL"],
        "KEY_PREFIX": "rxdj",
    },
}
RX_EVENT_CACHE = "reflex_events"
RX_EVENT_CACHE_TTL = 60

# Production sessions at scale
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

# Optional: log bridge phase timings at DEBUG
# RX_EVENT_METRICS = True
```

See [Settings reference](../reference/settings.md) for every knob and default.

---

## When to use what

| Traffic | Where it runs | Tune with |
|:---|:---|:---|
| REST / admin HTTP | Django ASGI | Normal Django: DB pooling, `CACHES`, CDN for `/static/` |
| Button clicks, form edits | Reflex `/_event` | `RX_EVENT_BRIDGE_MODE`, per-State override |
| File uploads | Reflex `/_upload` | Always at least `auth_only` tier (session + auth) |
| UI-only state (theme, modals) | Reflex `/_event` | `_rx_bridge = "none"` or `"smart"` mode |

Django developers configure; reflex-django executes. No hidden env vars unless documented as overrides (for example `RX_PROXY_SERVER` for split-process dev).

---

## Production topology

```text
Browser -> CDN (/static/) -> reverse proxy
              ├── Django ASGI  (admin, API, SPA shell via reflex_mount)
              └── Reflex backend (/_event, /_upload)
                        └── Redis (Reflex state + optional event cache + sessions)
                        └── PostgreSQL (shared with Django)
```

Checklist:

1. **Build SPA in CI**  -  do not rely on `RX_AUTO_EXPORT_ON_START` in production.
2. **Redis** for `RX_CONFIG["redis_url"]` when multiple Reflex workers serve the same app.
3. **Sessions**  -  prefer `cached_db` or cache-backed sessions so Django and Reflex agree on login state.
4. **Proxy**  -  WebSocket upgrade on `/_event`, idle timeout >= 300s, `X-Forwarded-Proto` for HTTPS.
5. **Workers**  -  start with 2–4 Django ASGI workers; scale Reflex workers with Redis state.

Reference compose layout: `docs/examples/docker-compose.scaling.yml` in the repository.

---

## Override precedence

Documented everywhere; highest wins:

```text
1. RX_EVENT_BRIDGE_RESOLVER   (your callable  -  full control)
2. State._rx_bridge             (per-class: "full" | "auth_only" | "none")
3. RX_EVENT_BRIDGE_MODE        (project default: "full" | "smart" | "none")
4. Built-in smart rules                   (AppState -> full, plain rx.State -> none)
```

!!! warning "Use `_rx_bridge`, not `reflex_django_bridge`"
    Reflex treats public class attributes as state vars. Prefix with `_` so the tier string is not serialized to the client:

```python
class FilterState(rx.State):
    _rx_bridge = "none"
```

---

## Bridge tiers

| Tier | Middleware | Auth snapshot sync |
|:---|:---|:---|
| `full` | Full `MIDDLEWARE` (minus skip list) | Yes |
| `auth_only` | `RX_AUTH_ONLY_MIDDLEWARE` | Only for `DjangoUserState` handlers |
| `none` | Skipped | No |

### Project default

```python
RX_EVENT_BRIDGE_MODE = "full"   # legacy default
RX_EVENT_BRIDGE_MODE = "smart"  # plain rx.State -> none; AppState -> full
RX_EVENT_BRIDGE_MODE = "none"   # skip chain unless overridden
```

### Per-class override

```python
class TelemetryState(rx.State):
    _rx_bridge = "none"
```

### Custom resolver (full control)

```python
# myapp/performance.py
def resolve_bridge_tier(handler_state_cls, event):
    if handler_state_cls.__name__.endswith("TelemetryState"):
        return "none"
    return "full"
```

```python
# settings.py
RX_EVENT_BRIDGE_RESOLVER = "myapp.performance.resolve_bridge_tier"
```

Upload events always run at least `auth_only`, even when the resolver returns `"none"`.

---

## Event cache (Django `CACHES`)

Store **post-middleware auth metadata** in Django's cache framework. The cache is **write-only** after middleware runs  -  it does not bypass session or auth middleware on the next event. Set `RX_EVENT_CACHE_TTL = 0` to disable writes.

```python
RX_EVENT_CACHE = "reflex_events"  # CACHES alias; "default" when unset
RX_EVENT_CACHE_TTL = 60           # 0 = disabled
RX_EVENT_CACHE_KEY_PREFIX = "rx:event:"
```

Invalidate on logout (also wired from built-in auth logout):

```python
from reflex_django.bridge import invalidate_event_cache

invalidate_event_cache(session_key=request.session.session_key)
```

Optional signal hook:

```python
from reflex_django.signals import event_bridge_cache_invalidated

event_bridge_cache_invalidated.connect(my_handler)
```

---

## Lean preset (smaller deltas)

When `RX_PERFORMANCE_PRESET = "lean"` and mirror settings still match library defaults, reflex-django disables:

| Setting | Lean value |
|:---|:---|
| `RX_AUTH_AUTO_SYNC` | `False` |
| `RX_MIRROR_MESSAGES` | `False` |
| `RX_MIRROR_CSRF` | `False` |
| `RX_MIRROR_LANGUAGE` | `False` |

Explicit values in `settings.py` always win over the preset.

---

## Dev-only: skip in-process Django mount

When `RX_PROXY_SERVER` points at a separate `runserver`, reflex-django skips `make_dispatcher` on the Reflex backend (saves memory). Production still uses your edge proxy; this is a dev layout only. See [Local development](../getting-started/local_development.md).

---

## Observability

```python
RX_EVENT_METRICS = True
# RX_EVENT_METRICS_LOGGER = "myapp.performance"
```

When enabled, bridge phases log timing at DEBUG. Zero overhead when `False`.

---

## Override quick reference

| Need | Setting / hook |
|:---|:---|
| Project-wide bridge behavior | `RX_EVENT_BRIDGE_MODE` |
| Full custom tier logic | `RX_EVENT_BRIDGE_RESOLVER` |
| One hot state class | `_rx_bridge = "none"` |
| Skip heavy middleware on events | `RX_EVENT_MIDDLEWARE_SKIP` |
| Auth-only middleware list | `RX_AUTH_ONLY_MIDDLEWARE` |
| Disable middleware entirely | `RX_RUN_MIDDLEWARE_CHAIN = False` |
| Smaller WebSocket deltas | `RX_PERFORMANCE_PRESET = "lean"` |
| Session cache between events | `RX_EVENT_CACHE` + `CACHES` + TTL |
| Flush cache on logout | `invalidate_event_cache()` |
| Multi-worker Reflex | `RX_CONFIG["redis_url"]` |
| Skip URL resolve on events | `RX_EVENT_RESOLVE_URL = False` |
| Debug timings | `RX_EVENT_METRICS = True` |

---

## Anti-patterns

- **Debouncing in Python only**  -  still ships a delta; debounce in the UI or batch server-side.
- **Huge lists in reactive state**  -  paginate; every row can cross the WebSocket.
- **Blocking ORM in async handlers**  -  use async ORM or `sync_to_async`.
- **Authorizing from `self.user` snapshot**  -  check `self.request.user` in handlers.
- **Running Celery tasks inside `@rx.event`**  -  enqueue and return; see background-job patterns in Django docs.

---

## Background jobs (v1: docs only)

Long work belongs in Celery, RQ, or Django Q  -  not in the event loop:

```python
@rx.event
async def submit(self):
    from myapp.tasks import process_order
    process_order.delay(self.order_id)
    self.status = "queued"
```

---

## What just happened?

You have a settings-first cheatsheet for scaling Django + Reflex: tiers, cache, lean preset, Redis, and production topology.

## Next up

[Deployment ->](deployment.md) for build and proxy detail, or [Custom middleware in events ->](../guides/middleware.md) for tier internals.