# Scaling

Tune bridge in the plugin. Tune cache and sessions in Django settings. Defaults are safe for most apps.

## Cheatsheet

**rxconfig.py:**

```python
import os
import reflex as rx
from reflex_django.plugins import ReflexDjangoPlugin

config = rx.Config(
    app_name="shop",
    redis_url=os.environ["REDIS_URL"],
    plugins=[
        ReflexDjangoPlugin(config={
            "settings_module": "config.settings",
            "profile": "integrated",
            "bridge": {"mode": "smart"},
        }),
    ],
)
```

**settings.py:**

```python
CACHES = {
    "reflex_events": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ["REDIS_URL"],
    },
}
RX_EVENT_CACHE = "reflex_events"
RX_EVENT_CACHE_TTL = 60
RX_EVENT_CACHE_FAST_AUTH = False
RX_EVENT_METRICS = True
RX_PERFORMANCE_PRESET = "lean"
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
```

## Bridge tuning

| Need | Setting |
|:---|:---|
| Skip middleware on UI-only state | `bridge.mode = "smart"` or `_rx_bridge = "none"` on one class |
| Full middleware (default) | `bridge.mode = "full"` |
| Reuse cached auth for auth-only events | `RX_EVENT_CACHE_FAST_AUTH = True` |
| Pick tier per state/event | `bridge.resolver` or `RX_EVENT_BRIDGE_RESOLVER` |
| Measure bridge overhead | `RX_EVENT_METRICS = True` or [Devtools](devtools.md) |

```python
class FilterState(rx.State):
    _rx_bridge = "none"
```

`RX_EVENT_CACHE_FAST_AUTH` is opt-in because it trades fewer session/auth middleware calls for a small TTL-bound staleness window. Logout invalidates the event cache.

`RX_PERFORMANCE_PRESET = "lean"` reduces bridge/UI churn by changing mirror and auth-sync defaults only when you have not explicitly overridden them. If you set `RX_AUTH_AUTO_SYNC` or mirror toggles yourself, your values are preserved.

Custom resolver:

```python
def resolve_bridge_tier(handler_state_cls, event):
    if handler_state_cls.__name__.endswith("FilterState"):
        return "none"
    return "full"
```

Configure it:

```python
ReflexDjangoPlugin(config={
    "settings_module": "config.settings",
    "bridge": {"resolver": "shop.performance.resolve_bridge_tier"},
})
```

Upload events are always raised to at least `auth_only`, even if a resolver returns `none`.

## Event cache

Use a shared Django cache when multiple workers process events:

```python
CACHES = {
    "reflex_events": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ["REDIS_URL"],
    },
}
RX_EVENT_CACHE = "reflex_events"
RX_EVENT_CACHE_TTL = 60
```

Set `RX_EVENT_CACHE_TTL = 0` to disable event caching. Keep the TTL short when `RX_EVENT_CACHE_FAST_AUTH=True`.

## Metrics

`RX_EVENT_METRICS=True` logs bridge timing at DEBUG. Set `RX_EVENT_METRICS_LOGGER = "myapp.performance"` to send metrics to a custom logger. For local query counts and tier inspection, use [Devtools](devtools.md).

## Live updates

`LiveListMixin` uses a process-local broadcaster for model-signal fan-out. For multiple workers, add a shared transport such as Redis pub/sub or Postgres `LISTEN/NOTIFY` and publish into each worker with `live_broadcaster().publish(...)`.

```python
from reflex_django.live import ModelChange, live_broadcaster

live_broadcaster().publish(ModelChange("shop.product", "updated", 42))
```

See [Live updates](live-updates.md).

## Production checklist

1. Build SPA in CI with `reflex export`
2. Set `redis_url` when running multiple Reflex workers
3. Use cache-backed sessions so Django and Reflex agree on login
4. Proxy WebSocket on `/_event` with long idle timeout
5. Proxy uploads on `/_upload` to the Reflex backend in split deployments
6. Review [Security](security.md) before production

See [Deploy](deployment.md) for the build pipeline.
