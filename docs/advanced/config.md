# Config reference

Integration config lives in **`ReflexDjangoPlugin`** inside **`rxconfig.py`**. Django **`settings.py`** holds app setup and performance tuning.

**Policy:** Use the plugin for embed, mount, proxy, and bridge pillars. Use Django settings for auth branding, cache, sessions, and mirror toggles. Prefer plugin `mount` / `proxy` blocks over duplicate flat env keys when both exist.

## rx.Config

| Field | Purpose |
|:---|:---|
| `app_name` | Matches `{app_name}/{app_name}.py` |
| `frontend_port` / `backend_port` | Dev ports (default 3000 / 8000) |
| `redis_url` | Required for multi-worker Reflex |
| `plugins` | Include `ReflexDjangoPlugin` |

## ReflexDjangoPlugin

| Key | Purpose |
|:---|:---|
| `settings_module` | Django settings module path |
| `profile` | `integrated`, `split_dev`, or `reflex_only` |
| `embed` | `{enabled: bool}` |
| `mount` | `{enabled, mount_prefix, django_prefix}` |
| `proxy` | `{enabled, server, separate_dev_ports}` |
| `bridge` | `{enabled, mode, run_middleware_chain, resolver}` |

### Profiles

| Profile | embed | mount | proxy | bridge |
|:---|:---|:---|:---|:---|
| `integrated` | on | on | on | on |
| `split_dev` | off | on | on | on |
| `reflex_only` | off | off | on | off |

### Example

```python
ReflexDjangoPlugin(config={
    "settings_module": "config.settings",
    "profile": "integrated",
    "mount": {"django_prefix": ("/admin", "/api")},
    "bridge": {"mode": "smart"},
})
```

Override any piece after choosing a profile. Explicit pillar blocks win over profile defaults.

## Django settings (required)

| Setting | Purpose |
|:---|:---|
| `INSTALLED_APPS` | Include `reflex_django` |
| `MIDDLEWARE` | `AsyncStreamingMiddleware` last |

## Django settings (auth and mirrors)

| Setting | Default | Purpose |
|:---|:---|:---|
| `RX_AUTH` | built-in dict | Auth page routes, fields, branding, page classes |
| `RX_AUTH_AUTO_SYNC` | `True` | Refresh auth snapshot vars after events |
| `RX_USER_SNAPSHOT_INCLUDE_GROUPS` | `False` | Include group names in snapshot |
| `RX_LOGOUT_PRESERVE_SESSION_KEYS` | `("theme",)` | Session keys kept on logout |
| `RX_MIRROR_MESSAGES` | `True` | Mirror Django messages |
| `RX_MIRROR_CSRF` | `True` | Mirror CSRF token |
| `RX_MIRROR_LANGUAGE` | `True` | Mirror locale |

## Django settings (bridge and performance)

| Setting | Default | Purpose |
|:---|:---|:---|
| `RX_EVENT_BRIDGE_MODE` | `full` | `full`, `smart`, or `none` (prefer plugin `bridge.mode`) |
| `RX_RUN_MIDDLEWARE_CHAIN` | `True` | Run full middleware on events |
| `RX_EVENT_MIDDLEWARE_SKIP` | CSRF + streaming | Middleware skipped on synthetic requests |
| `RX_EVENT_CACHE` | `default` | Cache alias for event context |
| `RX_EVENT_CACHE_TTL` | `60` | Cache TTL (seconds) |
| `RX_EVENT_CACHE_KEY_PREFIX` | `rx:event:` | Cache key prefix |
| `RX_EVENT_METRICS` | `False` | Log bridge timing |
| `RX_PERFORMANCE_PRESET` | `default` | `lean` disables heavy mirrors |
| `RX_AUTO_REDIRECT_FROM_MIDDLEWARE` | `True` | Turn 3xx middleware into `rx.redirect` |

## Django settings (mount and dev)

Prefer plugin config for these when possible. Settings exist for env overrides and bundled defaults.

| Setting | Purpose |
|:---|:---|
| `RX_PAGE_MODULE` | Page module suffix (default `views`) |
| `RX_AUTO_MOUNT` | Auto-append SPA catch-all |
| `RX_MOUNT_PREFIX` | SPA mount prefix |
| `RX_DJANGO_PREFIX` | Django-owned URL prefixes |
| `RX_DEV_PROXY` | Proxy to Vite in DEBUG |
| `RX_SEPARATE_DEV_PORTS` | Two-port dev layout |
| `RX_SERVE_FROM_BUILD` | Serve pre-built bundle |
| `RX_AUTO_EXPORT_ON_START` | Build at startup (off in production) |
| `RX_RENDER_SPA_VIA_TEMPLATE_ENGINE` | Render SPA shell via Django templates |

### Environment variables

Common env overrides: `RX_PROXY_SERVER`, `RX_DEV_PROXY`, `RX_FRONTEND_PORT`, `RX_BACKEND_PORT`, `RX_DATABASE_URL`, `RX_SECRET_KEY`, `RX_DEBUG`. See `reflex_django.core.settings_names` for the full list.

See [Scaling](scaling.md) for cache and bridge tuning together.

Learn what each integration piece does: [Learn path](../learn/index.md).
