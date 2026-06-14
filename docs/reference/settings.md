# `RX_*` settings

**What you will learn:** Every configuration knob reflex-django exposes, with defaults and when to change them.

**When you need this:**

- You are tuning routing, dev ports, or event middleware.
- You need the exact env var name for CI or Docker.

For narrative setup, see [Configuration](../getting-started/configuration.md) and [The three knobs](../overview/concepts.md).

Most projects change zero settings. The defaults are tuned for v1.0.

---

## Routing and proxy

| Setting | Type | Default | Purpose |
|:---|:---|:---|:---|
| `RX_PROXY_SERVER` | `str` | `""` | Optional. Base URL of a **separate** Django HTTP server for Vite dev proxy. When unset, Django prefixes are served from the Reflex backend. Env: `RX_PROXY_SERVER`. |
| `RX_MOUNT_PREFIX` | `str` | `"/"` | Catch-all mount prefix. Env: `RX_MOUNT_PREFIX`. |
| `RX_AUTO_MOUNT` | `bool` | `True` | Append SPA catch-all at startup. Env: `RX_AUTO_MOUNT=0`. |
| `RX_RESERVED_REFLEX_PREFIXES` | `tuple[str, ...]` | `()` | Extra Reflex path prefixes for dev proxy routing. |

---

## Serving and dev ports

How the SPA is built, proxied in dev, and served in production.

| Setting | Type | Default | Purpose |
|:---|:---|:---|:---|
| `RX_SERVE_FROM_BUILD` | `bool` | `False` | Serve compiled bundle from disk instead of Vite (`--from-build`). |
| `RX_AUTO_EXPORT_ON_START` | `bool` | `True` | Build missing SPA at ASGI boot. Set `False` in production CI builds. Env: `RX_AUTO_EXPORT_ON_START=0`. |
| `RX_RENDER_SPA_VIA_TEMPLATE_ENGINE` | `bool` | `True` | Run `index.html` through Django templates (`{% csrf_token %}`, etc.). |
| `RX_SHOW_BUILT_WITH_REFLEX` | `bool` | `False` | Show or hide the Reflex footer. |
| `RX_FRONTEND_PORT` | `int` | `3000` | Vite port. Prefer `RX_CONFIG["frontend_port"]`. Env: `RX_FRONTEND_PORT`. |
| `RX_BACKEND_PORT` | `int` | `8000` | ASGI port. Prefer `RX_CONFIG["backend_port"]`. Env: `RX_BACKEND_PORT`. |
| `RX_COMPILE_DEV` | env | unset | Set to `1` by `run_reflex --env dev`. Compile-only dev on backend port. |

### `RX_SEPARATE_DEV_PORTS`

| | |
|:---|:---|
| **Type** | `bool` |
| **Default in settings** | `False` |
| **Default when `run_reflex` runs** | `True` (env `RX_SEPARATE_DEV_PORTS=1`) |
| **Env** | `RX_SEPARATE_DEV_PORTS` |

Two-port dev: browse Vite on the frontend port for the SPA; backend port serves admin, API, and `/_event`. Default `run_reflex` sets this automatically.

Set `False` together with `RX_DEV_PROXY=1` if you want single-origin HMR on `:8000` (Django reverse-proxies Vite). See [Local development](../getting-started/local_development.md).

### `RX_DEV_PROXY`

| | |
|:---|:---|
| **Type** | `bool` |
| **Default in settings** | `True` |
| **Default when `run_reflex` runs** | `False` (env `RX_DEV_PROXY=0`) |
| **Env** | `RX_DEV_PROXY` |

When `True` and `RX_SEPARATE_DEV_PORTS=False`, Django's catch-all reverse-proxies SPA routes to Vite in `DEBUG`. Default two-port dev turns this **off** so Vite and backend stay separate (avoids proxy loops on `:8000`).

Also off for `--from-build`, `--env dev`, and `--env prod`. Set `RX_DEV_PROXY=0` in production.

!!! tip "Quick mental model"
    Default dev: **SEPARATE_DEV_PORTS=1**, **DEV_PROXY=0**, open `:3000`. Single-port compile dev: **`run_reflex --env dev`**, browse `:8000`.

### `RX_DJANGO_PREFIX`

| | |
|:---|:---|
| **Type** | env (comma-separated prefixes) |
| **Default** | unset (auto-detect from `urlpatterns`) |
| **Env** | `RX_DJANGO_PREFIX` |

Override which URL prefixes belong to Django (e.g. `/admin,/api,/rosetta`). Exported at compile time so Vite and the SPA know which paths hit the backend.

Prefer fixing `urlpatterns` or passing `django_prefix=` to `reflex_mount()`. Use this env when auto-detection misses a `re_path()` route or a legacy redirect you still need reserved. See [Routing](../internals/routing.md) and [Troubleshooting](../operations/troubleshooting.md).

Example:

```bash
export RX_DJANGO_PREFIX="/admin,/api,/internal"
python manage.py run_reflex
```

Use `RX_PROXY_SERVER` for optional split-process dev when Django runs on `runserver` separately from Reflex.

---

## Reflex runtime (`rx.Config`)

| Setting | Type | Default | Purpose |
|:---|:---|:---|:---|
| `RX_CONFIG` | `dict` | `{}` | Reflex overrides: `app_name`, ports, `redis_url`, packages, CORS, etc. |
| `RX_PLUGINS` | `list` | `[]` | Reflex plugins as dotted paths or instances. |
| `RX_CREATE_APP` | `str \| None` | `None` | Custom zero-arg factory returning `rx.App`. |

`django_prefix` is not a setting. It is inferred from `urlpatterns` or passed to `reflex_mount()`.

---

## Frontend toolchain

| Setting | Type | Default | Purpose |
|:---|:---|:---|:---|
| `RX_VITE_VERSION` | `str \| None` | `None` | Pin Vite version in `.web/package.json`. Env: same name. |

Pin when you hit bundler regressions (e.g. `TypeError: t is not a function`). Typical fix: `RX_VITE_VERSION = "7.3.3"`, then wipe `.web/` and rebuild.

---

## Event middleware chain

| Setting | Type | Default | Purpose |
|:---|:---|:---|:---|
| `RX_RUN_MIDDLEWARE_CHAIN` | `bool` | `True` | Run full `MIDDLEWARE` on Reflex events. |
| `RX_EVENT_MIDDLEWARE_SKIP` | `tuple[str, ...]` | CSRF + AsyncStreaming | Skip list for WebSocket events. |
| `RX_AUTO_REDIRECT_FROM_MIDDLEWARE` | `bool` | `True` | Turn 3xx into `rx.redirect(...)`. |
| `RX_EVENT_POST_FROM_PAYLOAD` | `bool` | `False` | Feed handler kwargs into synthetic `request.POST`. |

Extend the skip list:

```python
from reflex_django.bridge.event_handler import DEFAULT_EVENT_MIDDLEWARE_SKIP

RX_EVENT_MIDDLEWARE_SKIP = (
    *DEFAULT_EVENT_MIDDLEWARE_SKIP,
    "myapp.middleware.ExpensiveMiddleware",
)
```

---

## Performance and bridge tiers

Every Reflex event runs through `DjangoEventBridge.preprocess`. By default the **full** middleware chain runs (same as before tiered bridges). For high-frequency handlers, tune from `settings.py`:

| Setting | Default | Purpose |
|:---|:---|:---|
| `RX_EVENT_BRIDGE_MODE` | `"full"` | Project default: `"full"`, `"smart"`, or `"none"` |
| `RX_AUTH_ONLY_MIDDLEWARE` | session + auth | Middleware tuple for `"auth_only"` tier |
| `RX_EVENT_BRIDGE_RESOLVER` | unset | Dotted path to custom `(state_cls, event) -> tier` callable |
| `RX_EVENT_RESOLVE_URL` | `True` | Populate `request.resolver_match` on synthetic requests |
| `RX_EVENT_CACHE` | `"default"` | `CACHES` alias for bridge cache |
| `RX_EVENT_CACHE_TTL` | `60` | Seconds; `0` disables write |
| `RX_EVENT_CACHE_KEY_PREFIX` | `"rx:event:"` | Key prefix for cached auth metadata |
| `RX_PERFORMANCE_PRESET` | `"default"` | `"lean"` trims mirror/auth-sync defaults |
| `RX_EVENT_METRICS` | `False` | DEBUG timing logs when `True` |
| `RX_EVENT_METRICS_LOGGER` | unset | Logger name for bridge phase timings |

Event cache is **write-only** after middleware (post-middleware auth metadata). It does not skip session or auth on subsequent events.

**Override precedence** (highest wins):

1. `RX_EVENT_BRIDGE_RESOLVER`
2. `State._rx_bridge` (use `_` prefix  -  public attrs become Reflex vars)
3. `RX_EVENT_BRIDGE_MODE`
4. Smart defaults (`AppState` → `full`, plain `rx.State` → `none`)

```python
# settings.py  -  large apps (opt-in)
RX_EVENT_BRIDGE_MODE = "smart"

class FilterState(rx.State):
    _rx_bridge = "none"
```

Upload events always run at least `"auth_only"`. Full scaling guide: [Scaling and performance](../operations/scaling.md).

---

## Reactive mirrors, pages, auth

| Setting | Default | Purpose |
|:---|:---|:---|
| `RX_MIRROR_MESSAGES` | `True` | Mirror django.contrib.messages. |
| `RX_MIRROR_CSRF` | `True` | Mirror CSRF token to UI state. |
| `RX_AUTH_AUTO_SYNC` | `True` | Refresh user snapshot on each event. |
| `RX_AUTO_DISCOVER_PAGES` | `True` | Import `{app}.views` (deprecated; prefer explicit imports). |
| `RX_PAGE_PACKAGES` | `[]` | Explicit page modules (disables auto-discover when set). |
| `RX_LOGIN_URL` | `"/login"` | Redirect target for `@login_required`. |
| `RX_AUTH` | dict | Built-in auth pages config. See [Authentication](../guides/authentication.md). |

---

## Bundled defaults (no `DJANGO_SETTINGS_MODULE`)

When reflex-django supplies bundled settings, env vars include `RX_DATABASE_URL`, `RX_SECRET_KEY`, `RX_DEBUG`, etc. Never ship bundled defaults in production.

---

## Reading order

1. Most projects need **zero** changes.
2. First touch is often `RX_AUTH`.
3. Dev port confusion? Read **SEPARATE_DEV_PORTS**, **DEV_PROXY**, and **RX_PROXY_SERVER** above.
4. Routing 404s? Check **DJANGO_PREFIX** and [Troubleshooting](../operations/troubleshooting.md).
5. High event volume or multi-worker deploy? Read [Scaling and performance](../operations/scaling.md).

---

## What just happened?

You have a grouped index of every `RX_*` setting, including dev port and prefix overrides called out explicitly.

## Next up

[Public API at a glance →](api.md)