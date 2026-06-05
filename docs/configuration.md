# Configuration

For the friendly overview (three knobs, two jobs, `app_name` FAQ), start at [The three knobs](mental_model.md). This page is the detailed reference.

Three knobs control a Django-first reflex-django project:

| Knob | Where | What it controls |
|:---|:---|:---|
| **Settings** | `REFLEX_DJANGO_RX_CONFIG` | `app_name`, ports, `redis_url`, and other `rx.Config` fields |
| **App** | `from reflex_django import app` | Pages: `app.add_page()` / `@page` (same as native Reflex `shop/shop.py`) |
| **URLs** | automatic (default) or `reflex_mount()` | SPA catch-all; override prefix/plugins only when needed |

With `REFLEX_DJANGO_AUTO_MOUNT=True` (the default), you **do not** need a `reflex_mount()` line in `urls.py`. The catch-all is appended at startup after your Django routes are defined.

There's no `rxconfig.py`. `reflex-django` synthesizes one in memory from settings and any optional `reflex_mount()` overrides.

This page is the reference for both. The settings table at the bottom is also available as a flat lookup at [REFLEX_DJANGO_* settings](settings_reference.md).

---

## Minimal `settings.py`

```python
REFLEX_DJANGO_RX_CONFIG = {
    "app_name": "shop",  # Reflex compile identity; folder name with underscores
    "frontend_port": 3000,
    "backend_port": 8000,
}
# REFLEX_DJANGO_AUTO_MOUNT defaults to True
```

`app_name` is required internally by Reflex (`DECORATED_PAGES` bucketing, virtual `{app_name}.{app_name}:app` module). Put it in settings — not in `urls.py`.

---

## Minimal `urls.py`

```python
# config/urls.py
import shop.views  # noqa: F401 — register @page decorators at import time

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("shop.api_urls")),
]
# SPA catch-all appended automatically by reflex_django.apps.ReflexDjangoConfig.ready()
```

Import every page module explicitly (or register pages with `app.add_page()`). Auto-discovery of `{app}.views` across `INSTALLED_APPS` still works but emits a deprecation warning until the next major release.

---

## Optional `reflex_mount()` — URL overrides only

Use when you need a non-root mount prefix, an explicit `django_prefix`, or per-project plugin overrides:

```python
from reflex_django.urls import reflex_mount

urlpatterns += reflex_mount(
    mount_prefix="/app",
    django_prefix=("/admin", "/api"),
)
```

When `REFLEX_DJANGO_AUTO_MOUNT=True` and `urls.py` already calls `reflex_mount()`, auto-mount **skips** (no duplicate catch-all).

You usually **do not** pass `django_prefix`. reflex-django reads `urlpatterns` and infers which path prefixes Django owns (the first segment of each top-level `path()`, such as `/admin` from `path("admin/", ...)`).

### What each argument does

| Argument | Default | What it does |
|:---|:---|:---|
| `app_name` | **deprecated** — use `REFLEX_DJANGO_RX_CONFIG["app_name"]` | Legacy override during migration only. |
| `mount_prefix` | `"/"` | URL prefix where the SPA catch-all lives. You almost never change this. |
| `django_prefix` | auto-detect | Path prefixes Django owns. Omit to infer from `urlpatterns`; pass `()` for none; pass a tuple to override. |
| `urlpatterns` | caller's list | Optional explicit pattern list for auto-detection when not using module-level `urlpatterns += [...]`. |
| `plugins` | `()` | Extra Reflex plugins. `ReflexDjangoPlugin` is added automatically — don't pass it yourself. |
| `rx_config` | `{}` | Optional per-mount `rx.Config` overrides (merged over `REFLEX_DJANGO_RX_CONFIG`). |
| `django_plugin` | `{}` | Extra kwargs for the built-in `ReflexDjangoPlugin`. Merged with `REFLEX_DJANGO_PLUGIN`. |

### What goes in `REFLEX_DJANGO_RX_CONFIG`

Prefer settings for Reflex runtime options. You can pass any standard Reflex `rx.Config` option *except* `plugins` (use `REFLEX_DJANGO_PLUGINS` or the `plugins=` argument instead). The most common ones:

```python
REFLEX_DJANGO_RX_CONFIG = {
    "frontend_port": 3000,
    "backend_port": 8000,
    "redis_url": os.environ.get("REDIS_URL"),
    "db_url": "sqlite:///db.sqlite3",
    "cors_allowed_origins": ["https://example.com"],
    "show_built_with_reflex": False,
    "loglevel": "info",
    "telemetry_enabled": False,
}
```

By default `show_built_with_reflex` is forced to `False`. You can flip it back with `rx_config={"show_built_with_reflex": True}` or globally with `REFLEX_DJANGO_SHOW_BUILT_WITH_REFLEX = True` in settings.

### How `django_prefix` auto-detection works

reflex-django needs to know which URLs belong to Django (admin, API, webhooks, …) versus the Reflex SPA. That list drives two things: the SPA catch-all regex (so `/admin` without a trailing slash doesn't get swallowed) and the Vite dev proxy (so API calls don't loop back to the frontend).

**The default:** put your Django routes in `urlpatterns`, then append `reflex_mount()` last. No manual prefix list required.

**What gets picked up:** the first path segment of each top-level `path()` — `path("api/", include(...))` becomes `/api`. In `DEBUG`, local `MEDIA_URL` (e.g. `/media`) is included automatically. `STATIC_URL` is handled separately by the library.

**When to override:** pass `django_prefix` explicitly if you use bare `re_path()` patterns without a readable first segment, or if auto-detection picks up a legacy redirect route you don't want reserved:

```python
urlpatterns += [
    reflex_mount(
        app_name="shop",
        django_prefix=("/admin", "/api", "/webhooks"),
    ),
]
```

You only need the top-level prefix once (`"/api"` covers `/api/products/`, `/api/orders/`, and so on).

---

## ASGI entry point

You only write this file once and you don't touch it again:

```python
# config/asgi.py
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
from reflex_django.asgi_entry import application  # noqa: E402,F401
```

This is what `manage.py run_reflex` and your production server (uvicorn, granian, hypercorn, …) both point at.

---

## `REFLEX_DJANGO_*` settings

Optional tunables in `settings.py`. The defaults are sensible — most projects don't change any of these. Add the ones you need.

### Routing and serving

| Setting | Default | What it does |
|:---|:---|:---|
| `REFLEX_DJANGO_URL_ROUTING` | `"auto"` (→ `"django_outer"`) | Routing mode. Stick with the default. `"reflex_led"` is the legacy two-port layout. |
| `REFLEX_DJANGO_SERVE_FROM_BUILD` | `True` | `run_reflex` auto-builds the SPA and serves it from disk. Set to `False` (or use `--with-vite`) for the Vite HMR loop. |
| `REFLEX_DJANGO_RESERVED_REFLEX_PREFIXES` | `()` | Extra path prefixes always routed to Reflex. |
| `REFLEX_DJANGO_DEV_PROXY` | `False` | Auto-managed by `run_reflex --with-vite`. Don't set manually. |

For the dev URL (`:8000`), CSRF trusted origins, and optional dev HTTP middleware, see **[Local development](local_development.md)**.

### SPA shell rendering

| Setting | Default | What it does |
|:---|:---|:---|
| `REFLEX_DJANGO_RENDER_SPA_VIA_TEMPLATE_ENGINE` | `True` | Pipe the SPA `index.html` through Django's template engine, so `{{ request.user }}` and `{% csrf_token %}` work inside the shell. |
| `REFLEX_DJANGO_SHOW_BUILT_WITH_REFLEX` | `False` | Show or hide the "Built with Reflex" footer. |

### How events run through middleware

| Setting | Default | What it does |
|:---|:---|:---|
| `REFLEX_DJANGO_RUN_MIDDLEWARE_CHAIN` | `True` | Run the full `settings.MIDDLEWARE` chain on every Reflex event. |
| `REFLEX_DJANGO_EVENT_MIDDLEWARE_SKIP` | `("django.middleware.csrf.CsrfViewMiddleware", "reflex_django.streaming_middleware.AsyncStreamingMiddleware")` | Middleware classes to skip on WebSocket events. |
| `REFLEX_DJANGO_AUTO_REDIRECT_FROM_MIDDLEWARE` | `True` | Turn 3xx middleware responses into `rx.redirect(...)` automatically. |
| `REFLEX_DJANGO_EVENT_POST_FROM_PAYLOAD` | `False` | Feed event handler kwargs into the synthetic `request.POST`. |

### Reactive mirrors

These control whether Django's per-request data appears as reactive variables on `DjangoUserState` (so you can bind them in components).

| Setting | Default | What it does |
|:---|:---|:---|
| `REFLEX_DJANGO_MIRROR_MESSAGES` | `True` | Mirror `django.contrib.messages` to `DjangoUserState.messages`. |
| `REFLEX_DJANGO_MIRROR_CSRF` | `True` | Mirror the CSRF token to `DjangoUserState.csrf_token`. |
| `REFLEX_DJANGO_MIRROR_LANGUAGE` | `True` | Mirror language to `DjangoUserState.language` and `language_bidi`. |

### Page discovery

| Setting | Default | What it does |
|:---|:---|:---|
| `REFLEX_DJANGO_PAGE_PACKAGES` | `[]` | Explicit list of page modules. If non-empty, disables auto-discovery. |
| `REFLEX_DJANGO_AUTO_DISCOVER_PAGES` | `True` | Walk `INSTALLED_APPS` and import `{app}.views`. |
| `REFLEX_DJANGO_PAGE_APPS` | `None` | Allowlist of app labels to scan. `None` means "all of them". |
| `REFLEX_DJANGO_PAGE_MODULE` | `"views"` | Which submodule to import per app. |

### Context processors

| Setting | Default | What it does |
|:---|:---|:---|
| `REFLEX_DJANGO_CONTEXT_PROCESSORS` | `()` | Extra context callables to run on every Reflex event. |
| `REFLEX_DJANGO_AUTO_LOAD_CONTEXT` | `True` | Run context processors automatically. |
| `REFLEX_DJANGO_USE_TEMPLATE_CONTEXT_PROCESSORS` | `True` | Use Django's template context processors when the explicit list is empty. |

### Reflex runtime (`rx.Config`)

| Setting | Default | What it does |
|:---|:---|:---|
| `REFLEX_DJANGO_RX_CONFIG` | `{}` | Reflex runtime options: `frontend_port`, `backend_port`, `redis_url`, `frontend_packages`, CORS, log level, etc. This is the right place for `redis_url` and ports — not `urls.py`. |
| `REFLEX_DJANGO_PLUGINS` | `[]` | Reflex plugins as dotted paths or instances (e.g. Radix, Tailwind). |

### Plugin and rxconfig

| Setting | Default | What it does |
|:---|:---|:---|
| `REFLEX_DJANGO_USE_RXCONFIG_FILE` | `False` | Merge an existing on-disk `rxconfig.py` into the runtime config. |
| `REFLEX_DJANGO_MATERIALIZE_RXCONFIG` | `False` | Write a stub `rxconfig.py` to disk. |
| `REFLEX_DJANGO_PLUGIN` | `{}` | Extra kwargs for the built-in `ReflexDjangoPlugin`. |
| `REFLEX_DJANGO_AUTO_PLUGIN` | `True` | Always enabled. Kept for backwards compatibility. |

### Auth

| Setting | Default | What it does |
|:---|:---|:---|
| `REFLEX_DJANGO_LOGIN_URL` | `"/login"` | Where `@login_required` redirects to. |
| `REFLEX_DJANGO_AUTH` | see [Login & sessions](authentication.md) | Configuration for the built-in auth pages. |
| `REFLEX_DJANGO_AUTH_AUTO_SYNC` | `True` | Refresh the `AppState` user snapshot on every event. |

---

## The `ReflexDjangoPlugin`

`reflex-django` always registers a built-in Reflex plugin called `ReflexDjangoPlugin`. You don't instantiate it. To customize, pass kwargs via `django_plugin={...}` on `reflex_mount()` or set `REFLEX_DJANGO_PLUGIN = {...}` in settings — both are merged.

| Plugin argument | Default | What it does |
|:---|:---|:---|
| `django_prefix` | auto-detected | Inherited from `reflex_mount()` (auto or explicit). |
| `install_event_bridge` | `True` | Wire `DjangoEventBridge` into Reflex's event pipeline. Almost always leave on. |
| `install_auth_pages` | `False` | Auto-register the built-in login/register/reset pages. Prefer calling `add_auth_pages()` explicitly. |

---

## How `DJANGO_SETTINGS_MODULE` is resolved

In order of preference:

1. The `DJANGO_SETTINGS_MODULE` environment variable, if it's set.
2. Auto-discovery: `reflex-django` walks up looking for `manage.py` and reads its settings reference.
3. Falls back to `reflex_django.default_settings` (dev-only — **never** rely on this in production).

In production, always set `DJANGO_SETTINGS_MODULE` explicitly in your container or systemd unit.

---

## Middleware

Standard Django middleware works as-is. Add one helper at the bottom:

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "reflex_django.streaming_middleware.AsyncStreamingMiddleware",   # last
]
```

The `AsyncStreamingMiddleware` line keeps Django's admin streaming responses ASGI-safe. ([Why](async_streaming_middleware.md).)

Every middleware in this list runs on every Reflex event by default (except `CsrfViewMiddleware` and `AsyncStreamingMiddleware`, which are skipped on WebSocket events for good reasons). If you write a custom middleware that puts `request.tenant` on every request, it'll also be there on `self.request.tenant` inside your `@rx.event` handlers.

---

## Configuration ladder

### Level 0 — defaults (zero `urls.py` mount line)

```python
# settings.py
REFLEX_DJANGO_RX_CONFIG = {"app_name": "shop", "frontend_port": 3000, "backend_port": 8000}
```

```python
# urls.py
import shop.views  # noqa: F401

urlpatterns = [path("admin/", admin.site.urls)]
# catch-all appended automatically when REFLEX_DJANGO_AUTO_MOUNT=True (default)
```

```python
# pages — native Reflex style
from reflex_django import app

app.add_page(home, route="/")
```

### Level 1 — settings overrides (no manual mount)

| Setting | Override |
|:---|:---|
| `REFLEX_DJANGO_AUTO_MOUNT = False` | Disable catch-all auto-append; use manual `reflex_mount()` |
| `REFLEX_DJANGO_MOUNT_PREFIX` | SPA mount path (default `/`) |
| `REFLEX_DJANGO_RX_CONFIG` | Any allowed `rx.Config` field, including **`app_name`** |
| `REFLEX_DJANGO_PLUGINS` | Reflex plugins |
| `REFLEX_DJANGO_PLUGIN` | `ReflexDjangoPlugin` kwargs (`django_prefix`, …) |
| `REFLEX_DJANGO_URL_ROUTING` | `django_outer` / `django_led` / `reflex_led` |
| `REFLEX_DJANGO_USE_RXCONFIG_FILE = True` | Own on-disk `rxconfig.py` instead of synthesized config |

### Level 2 — explicit `reflex_mount()` (URL overrides)

Manual mount **wins over auto-mount** (duplicate detection). Kwargs merge over settings:

```python
urlpatterns += reflex_mount(
    mount_prefix="/app",
    django_prefix=("/admin", "/api/v2"),
    rx_config={"frontend_port": 3001},
)
```

### Level 3 — custom `rx.App`

**Factory setting:**

```python
REFLEX_DJANGO_CREATE_APP = "myapp.reflex.create_app"  # callable() → rx.App
```

**Direct assignment (always supported):**

```python
import reflex as rx
import reflex_django.django_led_app as django_led

django_led._app = rx.App(theme=rx.theme(accent_color="blue"))
```

Import `from reflex_django import app` in page modules — same singleton object.

### Level 4 — routing escape hatches

| Mode | When |
|:---|:---|
| `REFLEX_LED` | Reflex-first; auto-mount URL append skipped |
| `REFLEX_DJANGO_AUTO_MOUNT=False` | API-only Django or custom URL layout |

`django_led_app.app` is the **public** app entry (replaces `shop/shop.py`). You are expected to import it when using `app.add_page()`.

---

## Common configuration mistakes

**Prefix mismatch (404 on `/api/...`)**
Your Django route is `path("v1/", ...)` but you expected `/api` to be reserved. Auto-detection only sees the first segment of each `path()` — here that is `/v1`, not `/api`. Either rename the Django path or pass `django_prefix=("/api", "/v1", ...)` explicitly.

**`AppRegistryNotReady` at import time**
You imported a model at the top of `views.py`. Move the import inside the handler function. Models are only safe to import after Django finishes its app registry.

**Stale `rxconfig.py` on disk**
If you previously experimented with plain Reflex and have a leftover `rxconfig.py`, set `REFLEX_DJANGO_USE_RXCONFIG_FILE = True` to merge it, or just delete it. By default `reflex-django` ignores files on disk.

**Wrong `app_name`**
Set `app_name` in `REFLEX_DJANGO_RX_CONFIG` — it is the Reflex compile identity (often your primary Django app label), not a Python module path like `shop.shop`. The runtime loader is always `reflex_django.django_led_app`.

---

## Minimal checklist

If you want to start from a blank-ish project, here's the smallest set of edits:

```python
# settings.py
INSTALLED_APPS = [..., "reflex_django", "myapp"]
ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"

REFLEX_DJANGO_RX_CONFIG = {
    "app_name": "myapp",
    "frontend_port": 3000,
    "backend_port": 8000,
}

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "reflex_django.streaming_middleware.AsyncStreamingMiddleware",
]

STATIC_ROOT = BASE_DIR / "staticfiles"
```

```python
# urls.py
import myapp.views  # noqa: F401

urlpatterns = [path("admin/", admin.site.urls)]
```

```python
# asgi.py
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
from reflex_django.asgi_entry import application
```

---

**Next:** [Pages live in views.py →](pages_in_views.md)
