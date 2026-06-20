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
RX_PERFORMANCE_PRESET = "lean"
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
```

## Bridge tuning

| Need | Setting |
|:---|:---|
| Skip middleware on UI-only state | `bridge.mode = "smart"` or `_rx_bridge = "none"` on one class |
| Full middleware (default) | `bridge.mode = "full"` |

```python
class FilterState(rx.State):
    _rx_bridge = "none"
```

## Production checklist

1. Build SPA in CI with `reflex export`
2. Set `redis_url` when running multiple Reflex workers
3. Use cache-backed sessions so Django and Reflex agree on login
4. Proxy WebSocket on `/_event` with long idle timeout

See [Deploy](deployment.md) for the build pipeline.
