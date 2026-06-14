# `REFLEX_DJANGO_*` settings

**What you will learn:** Every configuration knob reflex-django exposes, with defaults and when to change them.

**When you need this:**

- You are tuning routing, dev ports, or event middleware.
- You need the exact env var name for CI or Docker.

For narrative setup, see [Configuration](configuration.md) and [The three knobs](mental_model.md).

Most projects change zero settings. The defaults are tuned for v1.0.

---

## Routing and proxy

| Setting | Type | Default | Purpose |
|:---|:---|:---|:---|
| `RXDJANGO_PROXY_SERVER` | `str` | `""` | Optional. Base URL of a **separate** Django HTTP server for Vite dev proxy. When unset, Django prefixes are served from the Reflex backend. Env: `RXDJANGO_PROXY_SERVER`. |
| `REFLEX_DJANGO_MOUNT_PREFIX` | `str` | `"/"` | Catch-all mount prefix. Env: `REFLEX_DJANGO_MOUNT_PREFIX`. |
| `REFLEX_DJANGO_AUTO_MOUNT` | `bool` | `True` | Append SPA catch-all at startup. Env: `REFLEX_DJANGO_AUTO_MOUNT=0`. |
| `REFLEX_DJANGO_RESERVED_REFLEX_PREFIXES` | `tuple[str, ...]` | `()` | Extra Reflex path prefixes for dev proxy routing. |

Deprecated: `REFLEX_DJANGO_HTTP_UPSTREAM` maps to `RXDJANGO_PROXY_SERVER` with a warning.

Removed in v3: `REFLEX_DJANGO_URL_ROUTING`, `REFLEX_DJANGO_HTTP_SUBPROCESS`, `REFLEX_DJANGO_HTTP_PORT`.

---

## Serving and dev ports

How the SPA is built, proxied in dev, and served in production.

| Setting | Type | Default | Purpose |
|:---|:---|:---|:---|
| `REFLEX_DJANGO_SERVE_FROM_BUILD` | `bool` | `False` | Serve compiled bundle from disk instead of Vite (`--from-build`). |
| `REFLEX_DJANGO_AUTO_EXPORT_ON_START` | `bool` | `True` | Build missing SPA at ASGI boot. Set `False` in production CI builds. Env: `REFLEX_DJANGO_AUTO_EXPORT_ON_START=0`. |
| `REFLEX_DJANGO_RENDER_SPA_VIA_TEMPLATE_ENGINE` | `bool` | `True` | Run `index.html` through Django templates (`{% csrf_token %}`, etc.). |
| `REFLEX_DJANGO_SHOW_BUILT_WITH_REFLEX` | `bool` | `False` | Show or hide the Reflex footer. |
| `REFLEX_DJANGO_FRONTEND_PORT` | `int` | `3000` | Vite port. Prefer `REFLEX_DJANGO_RX_CONFIG["frontend_port"]`. Env: `REFLEX_DJANGO_FRONTEND_PORT`. |
| `REFLEX_DJANGO_BACKEND_PORT` | `int` | `8000` | ASGI port. Prefer `REFLEX_DJANGO_RX_CONFIG["backend_port"]`. Env: `REFLEX_DJANGO_BACKEND_PORT`. |
| `REFLEX_DJANGO_COMPILE_DEV` | env | unset | Set to `1` by `run_reflex --env dev`. Compile-only dev on backend port. |

### `REFLEX_DJANGO_SEPARATE_DEV_PORTS`

| | |
|:---|:---|
| **Type** | `bool` |
| **Default in settings** | `False` |
| **Default when `run_reflex` runs** | `True` (env `REFLEX_DJANGO_SEPARATE_DEV_PORTS=1`) |
| **Env** | `REFLEX_DJANGO_SEPARATE_DEV_PORTS` |

Two-port dev: browse Vite on the frontend port for the SPA; backend port serves admin, API, and `/_event`. Default `run_reflex` sets this automatically.

Set `False` together with `REFLEX_DJANGO_DEV_PROXY=1` if you want single-origin HMR on `:8000` (Django reverse-proxies Vite). See [Local development](local_development.md).

### `REFLEX_DJANGO_DEV_PROXY`

| | |
|:---|:---|
| **Type** | `bool` |
| **Default in settings** | `True` |
| **Default when `run_reflex` runs** | `False` (env `REFLEX_DJANGO_DEV_PROXY=0`) |
| **Env** | `REFLEX_DJANGO_DEV_PROXY` |

When `True` and `REFLEX_DJANGO_SEPARATE_DEV_PORTS=False`, Django's catch-all reverse-proxies SPA routes to Vite in `DEBUG`. Default two-port dev turns this **off** so Vite and backend stay separate (avoids proxy loops on `:8000`).

Also off for `--from-build`, `--env dev`, and `--env prod`. Set `REFLEX_DJANGO_DEV_PROXY=0` in production.

!!! tip "Quick mental model"
    Default dev: **SEPARATE_DEV_PORTS=1**, **DEV_PROXY=0**, open `:3000`. Single-port compile dev: **`run_reflex --env dev`**, browse `:8000`.

### `REFLEX_DJANGO_DJANGO_PREFIX`

| | |
|:---|:---|
| **Type** | env (comma-separated prefixes) |
| **Default** | unset (auto-detect from `urlpatterns`) |
| **Env** | `REFLEX_DJANGO_DJANGO_PREFIX` |

Override which URL prefixes belong to Django (e.g. `/admin,/api,/rosetta`). Exported at compile time so Vite and the SPA know which paths hit the backend.

Prefer fixing `urlpatterns` or passing `django_prefix=` to `reflex_mount()`. Use this env when auto-detection misses a `re_path()` route or a legacy redirect you still need reserved. See [Routing](routing.md) and [Troubleshooting](troubleshooting.md).

Example:

```bash
export REFLEX_DJANGO_DJANGO_PREFIX="/admin,/api,/internal"
python manage.py run_reflex
```

Removed in v3: `REFLEX_DJANGO_HTTP_HOST`, `REFLEX_DJANGO_HTTP_PORT`, `REFLEX_DJANGO_HTTP_SUBPROCESS`. Use `RXDJANGO_PROXY_SERVER` for optional split-process dev instead.

---

## Reflex runtime (`rx.Config`)

| Setting | Type | Default | Purpose |
|:---|:---|:---|:---|
| `REFLEX_DJANGO_RX_CONFIG` | `dict` | `{}` | Reflex overrides: `app_name`, ports, `redis_url`, packages, CORS, etc. |
| `REFLEX_DJANGO_PLUGINS` | `list` | `[]` | Reflex plugins as dotted paths or instances. |
| `REFLEX_DJANGO_CREATE_APP` | `str \| None` | `None` | Custom zero-arg factory returning `rx.App`. |

`django_prefix` is not a setting. It is inferred from `urlpatterns` or passed to `reflex_mount()`.

---

## Frontend toolchain

| Setting | Type | Default | Purpose |
|:---|:---|:---|:---|
| `REFLEX_DJANGO_VITE_VERSION` | `str \| None` | `None` | Pin Vite version in `.web/package.json`. Env: same name. |

Pin when you hit bundler regressions (e.g. `TypeError: t is not a function`). Typical fix: `REFLEX_DJANGO_VITE_VERSION = "7.3.3"`, then wipe `.web/` and rebuild.

---

## Event middleware chain

| Setting | Type | Default | Purpose |
|:---|:---|:---|:---|
| `REFLEX_DJANGO_RUN_MIDDLEWARE_CHAIN` | `bool` | `True` | Run full `MIDDLEWARE` on Reflex events. |
| `REFLEX_DJANGO_EVENT_MIDDLEWARE_SKIP` | `tuple[str, ...]` | CSRF + AsyncStreaming | Skip list for WebSocket events. |
| `REFLEX_DJANGO_AUTO_REDIRECT_FROM_MIDDLEWARE` | `bool` | `True` | Turn 3xx into `rx.redirect(...)`. |
| `REFLEX_DJANGO_EVENT_POST_FROM_PAYLOAD` | `bool` | `False` | Feed handler kwargs into synthetic `request.POST`. |

Extend the skip list:

```python
from reflex_django.bridge.event_handler import DEFAULT_EVENT_MIDDLEWARE_SKIP

REFLEX_DJANGO_EVENT_MIDDLEWARE_SKIP = (
    *DEFAULT_EVENT_MIDDLEWARE_SKIP,
    "myapp.middleware.ExpensiveMiddleware",
)
```

---

## Performance and bridge tiers

Every Reflex event runs through `DjangoEventBridge.preprocess`. By default the **full** middleware chain runs (same as before tiered bridges). For high-frequency handlers, tune from `settings.py`:

| Setting | Default | Purpose |
|:---|:---|:---|
| `REFLEX_DJANGO_EVENT_BRIDGE_MODE` | `"full"` | Project default: `"full"`, `"smart"`, or `"none"` |
| `REFLEX_DJANGO_AUTH_ONLY_MIDDLEWARE` | session + auth | Middleware tuple for `"auth_only"` tier |
| `REFLEX_DJANGO_EVENT_BRIDGE_RESOLVER` | unset | Dotted path to custom `(state_cls, event) -> tier` callable |
| `REFLEX_DJANGO_EVENT_RESOLVE_URL` | `True` | Populate `request.resolver_match` on synthetic requests |
| `REFLEX_DJANGO_EVENT_CACHE` | `"default"` | `CACHES` alias for bridge cache |
| `REFLEX_DJANGO_EVENT_CACHE_TTL` | `60` | Seconds; `0` disables write |
| `REFLEX_DJANGO_EVENT_CACHE_KEY_PREFIX` | `"rxdj:event:"` | Key prefix for cached auth metadata |
| `REFLEX_DJANGO_PERFORMANCE_PRESET` | `"default"` | `"lean"` trims mirror/auth-sync defaults |
| `REFLEX_DJANGO_EVENT_METRICS` | `False` | DEBUG timing logs when `True` |
| `REFLEX_DJANGO_EVENT_METRICS_LOGGER` | unset | Logger name for bridge phase timings |

Event cache is **write-only** after middleware (post-middleware auth metadata). It does not skip session or auth on subsequent events.

**Override precedence** (highest wins):

1. `REFLEX_DJANGO_EVENT_BRIDGE_RESOLVER`
2. `State._reflex_django_bridge` (use `_` prefix — public attrs become Reflex vars)
3. `REFLEX_DJANGO_EVENT_BRIDGE_MODE`
4. Smart defaults (`AppState` → `full`, plain `rx.State` → `none`)

```python
# settings.py — large apps (opt-in)
REFLEX_DJANGO_EVENT_BRIDGE_MODE = "smart"

class FilterState(rx.State):
    _reflex_django_bridge = "none"
```

Upload events always run at least `"auth_only"`. Full scaling guide: [Scaling and performance](scaling.md).

---

## Reactive mirrors, pages, auth

| Setting | Default | Purpose |
|:---|:---|:---|
| `REFLEX_DJANGO_MIRROR_MESSAGES` | `True` | Mirror django.contrib.messages. |
| `REFLEX_DJANGO_MIRROR_CSRF` | `True` | Mirror CSRF token to UI state. |
| `REFLEX_DJANGO_AUTH_AUTO_SYNC` | `True` | Refresh user snapshot on each event. |
| `REFLEX_DJANGO_AUTO_DISCOVER_PAGES` | `True` | Import `{app}.views` (deprecated; prefer explicit imports). |
| `REFLEX_DJANGO_PAGE_PACKAGES` | `[]` | Explicit page modules (disables auto-discover when set). |
| `REFLEX_DJANGO_LOGIN_URL` | `"/login"` | Redirect target for `@login_required`. |
| `REFLEX_DJANGO_AUTH` | dict | Built-in auth pages config. See [Authentication](authentication.md). |

---

## Bundled defaults (no `DJANGO_SETTINGS_MODULE`)

When reflex-django supplies bundled settings, env vars include `REFLEX_DJANGO_DATABASE_URL`, `REFLEX_DJANGO_SECRET_KEY`, `REFLEX_DJANGO_DEBUG`, etc. Never ship bundled defaults in production.

---

## Reading order

1. Most projects need **zero** changes.
2. First touch is often `REFLEX_DJANGO_AUTH`.
3. Dev port confusion? Read **SEPARATE_DEV_PORTS**, **DEV_PROXY**, and **RXDJANGO_PROXY_SERVER** above.
4. Routing 404s? Check **DJANGO_PREFIX** and [Troubleshooting](troubleshooting.md).
5. High event volume or multi-worker deploy? Read [Scaling and performance](scaling.md).

---

## What just happened?

You have a grouped index of every `REFLEX_DJANGO_*` setting, including dev port and prefix overrides called out explicitly.

## Next up

[Public API at a glance →](public_api.md)