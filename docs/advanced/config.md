# Config reference

Integration config lives in **`ReflexDjangoPlugin`** inside **`rxconfig.py`**. Django **`settings.py`** holds Django apps, auth, cache, sessions, event bridge tuning, and deployment toggles.

## Policy

Use plugin config for the four integration pillars:

- `embed`: run Django HTTP inside the Reflex backend during dev/integrated runs
- `mount`: decide which paths Django owns and where the SPA catch-all lives
- `proxy`: configure Vite/dev proxy wiring
- `bridge`: configure Django request context on Reflex events

Use Django settings for auth pages, caches, sessions, event cache, security, mirrors, and deployment behavior.

## `rx.Config`

| Field | Purpose |
|:---|:---|
| `app_name` | Matches `{app_name}/{app_name}.py` |
| `frontend_port` / `backend_port` | Dev ports, usually `3000` / `8000` |
| `redis_url` | Required for multi-worker Reflex state |
| `plugins` | Include `ReflexDjangoPlugin` |

## `ReflexDjangoPlugin`

```python
ReflexDjangoPlugin(config={
    "settings_module": "config.settings",
    "profile": "integrated",
    "mount": {"django_prefix": ("/admin", "/api")},
    "bridge": {"mode": "smart"},
})
```

| Key | Purpose |
|:---|:---|
| `settings_module` | Django settings module path |
| `profile` | `integrated`, `split_dev`, or `reflex_only` |
| `embed` | `{enabled: bool}` |
| `mount` | `{enabled, mount_prefix, django_prefix}` |
| `proxy` | `{enabled, server, separate_dev_ports}` |
| `bridge` | `{enabled, mode, run_middleware_chain, resolver}` |

Explicit pillar blocks override profile defaults.

| Profile | embed | mount | proxy | bridge |
|:---|:---|:---|:---|:---|
| `integrated` | on | on | on | on |
| `split_dev` | off | on | on | on |
| `reflex_only` | off | off | on | off |

Legacy flat plugin keys (`auto_mount`, `mount_prefix`, `django_prefix`) are still accepted for upgrades. New projects should use nested `mount` and profile config.

When no explicit `embed` block is supplied, setting `RX_PROXY_SERVER` for split development implies Django is external and embed should be off. Prefer explicit `profile: "split_dev"` plus `proxy.server` for clarity.

## Required Django settings

| Setting | Purpose |
|:---|:---|
| `INSTALLED_APPS` | Include `reflex_django` or `reflex_django.django.apps.ReflexDjangoConfig` |
| `MIDDLEWARE` | Put `reflex_django.bridge.streaming.AsyncStreamingMiddleware` last |
| `DJANGO_SETTINGS_MODULE` | Use your real settings module outside local fallback mode |

## Auth and sessions

| Setting | Default | Purpose |
|:---|:---|:---|
| `RX_AUTH` | built-in dict | Auth page routes, fields, messages, redirects, branding, page classes |
| `RX_AUTH_AUTO_SYNC` | `True` | Refresh auth snapshot vars after bridge events |
| `RX_USER_SNAPSHOT_INCLUDE_GROUPS` | `False` | Include group names in the user snapshot |
| `RX_LOGOUT_PRESERVE_SESSION_KEYS` | `("theme",)` | Session keys copied across logout |
| `RX_SITE_ORIGIN` | unset | Password-reset origin when no request is bound |
| `SESSION_COOKIE_HTTPONLY` | `False` in fallback settings | Enables JavaScript session cookie sync after Reflex login/logout |

See [Auth](auth.md) and [Security](security.md) before changing cookie behavior.

## Bridge and performance

| Setting | Default | Purpose |
|:---|:---|:---|
| `RX_EVENT_BRIDGE_MODE` | `full` | Global mode: `full`, `smart`, or `none` |
| `RX_RUN_MIDDLEWARE_CHAIN` | `True` | Run Django middleware on event requests |
| `RX_AUTH_ONLY_MIDDLEWARE` | session + auth | Middleware subset for the `auth_only` tier |
| `RX_EVENT_MIDDLEWARE_SKIP` | CSRF + streaming | Middleware skipped on synthetic event requests |
| `RX_EVENT_BRIDGE_RESOLVER` | unset | Dotted callable `(state_cls, event) -> "full"|"auth_only"|"none"` |
| `RX_EVENT_RESOLVE_URL` | `True` | Populate `request.resolver_match` on synthetic requests |
| `RX_EVENT_POST_FROM_PAYLOAD` | `False` | Copy event handler kwargs into synthetic `request.POST` |
| `RX_AUTO_REDIRECT_FROM_MIDDLEWARE` | `True` | Convert middleware 3xx responses into `rx.redirect` |
| `RX_EVENT_CACHE` | `default` | Django cache alias for event context |
| `RX_EVENT_CACHE_TTL` | `60` | Event cache TTL in seconds; `0` disables |
| `RX_EVENT_CACHE_KEY_PREFIX` | `rx:event:` | Cache key prefix |
| `RX_EVENT_CACHE_FAST_AUTH` | `False` | Reuse cached auth snapshot for `auth_only` tier within TTL |
| `RX_EVENT_METRICS` | `False` | Log bridge timing at DEBUG |
| `RX_EVENT_METRICS_LOGGER` | unset | Logger name for bridge timing |
| `RX_BRIDGE_DEBUG` | `False` | Log tracebacks for swallowed bridge hot-path exceptions |
| `RX_DEVTOOLS` | `False` | Enable dev-only query/timing/state inspectors |
| `RX_PERFORMANCE_PRESET` | `default` | `lean` trims mirror deltas when settings still match defaults |

`RX_PERFORMANCE_PRESET="lean"` only changes settings that still have bundled defaults; explicit user overrides win.

The lean preset trims mirror deltas and can disable auth auto-sync when those settings still match bundled defaults.

## Mirrors

| Setting | Default | Purpose |
|:---|:---|:---|
| `RX_MIRROR_MESSAGES` | `True` | Mirror Django messages to `AppState` |
| `RX_MIRROR_CSRF` | `True` | Mirror CSRF token |
| `RX_MIRROR_LANGUAGE` | `True` | Mirror active language |

Disable mirrors you do not render in the UI to reduce event deltas.

## Mount, dev, and SPA serving

| Setting | Default | Purpose |
|:---|:---|:---|
| `RX_PAGE_MODULE` | `views` | Optional decorated-page module suffix auto-imported before compile |
| `RX_CREATE_APP` | unset | Dotted path to a callable returning `rx.App` |
| `RX_AUTO_MOUNT` | `True` | Auto-append SPA catch-all to Django URLConf |
| `RX_MOUNT_PREFIX` | `/` | SPA catch-all prefix |
| `RX_DJANGO_PREFIX` | auto-detected | Django-owned path prefixes |
| `RX_RESERVED_REFLEX_PREFIXES` | `()` | Extra protected Reflex prefixes beyond `/_event`, `/_upload`, etc. |
| `RX_PROXY_SERVER` | unset | External Django server for split dev |
| `RX_DEV_PROXY` | `True` | Proxy catch-all requests to Vite in `DEBUG` |
| `RX_SEPARATE_DEV_PORTS` | `False` | Use native Reflex two-port dev layout |
| `RX_SERVE_FROM_BUILD` | `False` | Serve an existing exported bundle instead of Vite/HMR |
| `RX_AUTO_EXPORT_ON_START` | `False` | Build SPA at startup when none is on disk |
| `RX_RENDER_SPA_VIA_TEMPLATE_ENGINE` | `True` | Optionally post-process only the SPA HTML shell with Django `RequestContext` |
| `RX_SHOW_BUILT_WITH_REFLEX` | `False` | Show Reflex badge in generated SPA |
| `RX_VITE_VERSION` | bundled default | Pin Vite version used by generated frontend |

Dev serving matrix:

| Need | Setting |
|:---|:---|
| Vite HMR in normal dev | `RX_DEV_PROXY=True`, `RX_SERVE_FROM_BUILD=False` |
| Serve an exported bundle from disk | `RX_SERVE_FROM_BUILD=True` |
| Compile-only dev without Vite catch-all | `RX_COMPILE_DEV=1` and `RX_DEV_PROXY=0` |
| Tell Django a frontend is already available | `RX_FRONTEND_PRESENT=1` |
| Native two-port Reflex layout | `RX_SEPARATE_DEV_PORTS=True` or `proxy.separate_dev_ports` |

`RX_RENDER_SPA_VIA_TEMPLATE_ENGINE` only affects HTML shell responses such as exported `index.html` or deep-link HTML files. It does not template Reflex components, JavaScript, CSS, source maps, images, uploads, or event traffic. Set it to `False` when you want Reflex output served exactly as exported and reflex-django to act only as the integration layer.

## Static files and database fallback

| Setting / env | Default | Purpose |
|:---|:---|:---|
| `RX_STATIC_URL` | `/static/` | Django static URL in fallback settings |
| `RX_STATIC_ROOT` | `.reflex-django/staticfiles` | Static root for `collectstatic` |
| `RX_DATABASE_URL` | unset | Database URL used by fallback settings |
| `rx.Config.db_url` | unset | Fallback database URL when `RX_DATABASE_URL` is absent |

If neither database source is set, fallback settings use `sqlite:///reflex.db` in the working directory.

## Environment variables

Common env overrides:

| Env | Purpose |
|:---|:---|
| `RX_PROXY_SERVER` | Split-dev Django server |
| `RX_DEV_PROXY` | Enable/disable Vite catch-all proxy |
| `RX_FRONTEND_PORT` / `RX_BACKEND_PORT` | Dev/prod ports |
| `RX_BACKEND_HOST` | Backend bind host |
| `RX_BACKEND_RELOAD` | Backend reload behavior |
| `RX_COMPILE_DEV` | Compile-only dev serving |
| `RX_FRONTEND_PRESENT` | Treat frontend bundle/server as present |
| `RX_SERVE_FROM_BUILD` | Serve pre-built frontend |
| `RX_AUTO_EXPORT_ON_START` | Export SPA at startup |
| `RX_SECRET_KEY` | Fallback settings secret key |
| `RX_DEBUG` | Fallback `DEBUG` |
| `RX_ALLOWED_HOSTS` | Fallback `ALLOWED_HOSTS` comma list |

## Validation and warnings

The resolver warns for contradictory plugin config, such as `embed.enabled=False` without a `proxy.server` in split dev, or a configured external proxy while embed is still enabled. `bridge.enabled=False` is allowed, but handlers will not receive Django request context.

Production runs also call the insecure-default audit. See [Security](security.md).

**Next:** [Bridge](../learn/bridge.md), [Scaling](scaling.md), and [Deploy](deployment.md).
