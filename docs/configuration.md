---
level: beginner
tags: [configuration, settings]
---

# Configuration

**What you'll learn:** Every place you configure reflex-django v1: settings, the shared `app` singleton, optional URL overrides, and the most common `REFLEX_DJANGO_*` tunables.

**When you need this:**

- You finished [Project structure](project_structure.md) and need the detailed settings reference beyond [The three knobs](mental_model.md).
- A route, port, or compile identity is wrong and you need to know which setting fixes it.

---

For the friendly overview (three knobs, two jobs, `app_name` FAQ), start at [The three knobs](mental_model.md). This page is the detailed reference. The flat settings table also lives at [REFLEX_DJANGO_* settings](settings_reference.md).

---

## Three knobs (v1)

| Knob | Where | What it controls |
|:---|:---|:---|
| **Settings** | `REFLEX_DJANGO_RX_CONFIG` | `app_name`, ports, `redis_url`, and other `rx.Config` fields |
| **App** | `from reflex_django import app` | Pages via `@page` or `app.add_page()` on the shared singleton (`reflex_django.reflex_app`) |
| **URLs** | automatic (default) or `reflex_mount()` | SPA catch-all; override prefix or plugins only when needed |

With `REFLEX_DJANGO_AUTO_MOUNT=True` (the default), you do **not** need a `reflex_mount()` line in `urls.py`. The catch-all is appended at startup after your Django routes are defined.

There is no `rxconfig.py`. reflex-django synthesizes one in memory from settings and any optional `reflex_mount()` overrides.

---

## Minimal settings and URLs

```python
--8<-- "snippets/minimal_settings.py"
```

```python
--8<-- "snippets/minimal_urls.py"
```

`app_name` is required internally by Reflex (`DECORATED_PAGES` bucketing, virtual compile module). Put it in settings, not in `urls.py`.

Import every page module explicitly (or register pages with `app.add_page()`). Auto-discovery of `{app}.views` across `INSTALLED_APPS` still works but emits a deprecation warning until the next major release.

---

## ASGI entry point

Write this once and leave it alone:

```python
--8<-- "snippets/minimal_asgi.py"
```

Point `manage.py run_reflex` and your production server (uvicorn, granian, hypercorn, and so on) at this module.

---

## Optional `reflex_mount()` (URL overrides only)

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
| `mount_prefix` | `"/"` | URL prefix where the SPA catch-all lives. You almost never change this. |
| `django_prefix` | auto-detect | Path prefixes Django owns. Omit to infer from `urlpatterns`; pass `()` for none; pass a tuple to override. |
| `urlpatterns` | caller's list | Optional explicit pattern list for auto-detection when not using module-level `urlpatterns += [...]`. |
| `plugins` | `()` | Extra Reflex plugins. The built-in Django plugin is added automatically. |
| `rx_config` | `{}` | Optional per-mount `rx.Config` overrides (merged over `REFLEX_DJANGO_RX_CONFIG`). |
| `django_plugin` | `{}` | Extra kwargs for the built-in Django integration plugin. Merged with `REFLEX_DJANGO_PLUGIN`. |

### Common `REFLEX_DJANGO_RX_CONFIG` fields

Prefer settings for Reflex runtime options. You can pass any standard Reflex `rx.Config` option *except* `plugins` (use `REFLEX_DJANGO_PLUGINS` or the `plugins=` argument instead):

```python
REFLEX_DJANGO_RX_CONFIG = {
    "app_name": "shop",
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

By default `show_built_with_reflex` is forced to `False`. Flip it back with `rx_config={"show_built_with_reflex": True}` or globally with `REFLEX_DJANGO_SHOW_BUILT_WITH_REFLEX = True`.

### How `django_prefix` auto-detection works

reflex-django needs to know which URLs belong to Django (admin, API, webhooks, and so on) versus the Reflex SPA. That list drives the SPA catch-all regex and the Vite dev proxy.

**The default:** put Django routes in `urlpatterns`, then let auto-mount append the catch-all. No manual prefix list required.

**What gets picked up:** the first path segment of each top-level `path()`. In `DEBUG`, local `MEDIA_URL` (for example `/media`) is included automatically. `STATIC_URL` is handled separately.

**When to override:** pass `django_prefix` explicitly if you use bare `re_path()` patterns without a readable first segment, or if auto-detection picks up a legacy redirect route you do not want reserved:

```python
urlpatterns += reflex_mount(
    django_prefix=("/admin", "/api", "/webhooks"),
)
```

You only need the top-level prefix once (`"/api"` covers `/api/products/` and `/api/orders/`).

---

## `REFLEX_DJANGO_*` settings (summary)

Optional tunables in `settings.py`. Defaults are sensible. Most projects change only a few.

### Routing and serving

| Setting | Default | What it does |
|:---|:---|:---|
| `REFLEX_DJANGO_URL_ROUTING` | `"auto"` (becomes `"django_outer"`) | Routing mode. Set `"reflex_outer"` when Reflex owns the public port. See [Routing](routing.md). Legacy aliases `"reflex_led"` and `"django_led"` still work. |
| `REFLEX_DJANGO_SERVE_FROM_BUILD` | `False` | When `False`, `run_reflex` runs Vite for HMR. Set `True` (or pass `--from-build`) to serve a pre-built SPA from disk. |
| `REFLEX_DJANGO_RESERVED_REFLEX_PREFIXES` | `()` | Extra path prefixes always routed to Reflex. |
| `REFLEX_DJANGO_DEV_PROXY` | `True` in settings; `False` when default Vite mode runs | When `True`, Django reverse-proxies SPA routes to Vite in DEBUG. |

For the dev URL (`:8000`), CSRF trusted origins, and optional dev HTTP middleware, see [Local development](local_development.md).

### Media files

User uploads need standard Django media settings plus a dev URL mount. reflex-django only auto-routes the `/media` prefix in DEBUG; it does not serve files. See [Media files](media_files.md).

### SPA shell rendering

| Setting | Default | What it does |
|:---|:---|:---|
| `REFLEX_DJANGO_RENDER_SPA_VIA_TEMPLATE_ENGINE` | `True` | Pipe the SPA `index.html` through Django's template engine so `{{ request.user }}` and `{% csrf_token %}` work in the shell. |
| `REFLEX_DJANGO_SHOW_BUILT_WITH_REFLEX` | `False` | Show or hide the "Built with Reflex" footer. |

### How events run through middleware

| Setting | Default | What it does |
|:---|:---|:---|
| `REFLEX_DJANGO_RUN_MIDDLEWARE_CHAIN` | `True` | Run the full `settings.MIDDLEWARE` chain on every Reflex event. |
| `REFLEX_DJANGO_EVENT_MIDDLEWARE_SKIP` | CSRF + `AsyncStreamingMiddleware` | Middleware classes to skip on WebSocket events. |
| `REFLEX_DJANGO_AUTO_REDIRECT_FROM_MIDDLEWARE` | `True` | Turn 3xx middleware responses into `rx.redirect(...)` automatically. |
| `REFLEX_DJANGO_EVENT_POST_FROM_PAYLOAD` | `False` | Feed event handler kwargs into the synthetic `request.POST`. |

### Reactive mirrors

| Setting | Default | What it does |
|:---|:---|:---|
| `REFLEX_DJANGO_MIRROR_MESSAGES` | `True` | Mirror `django.contrib.messages` to `DjangoUserState.messages`. |
| `REFLEX_DJANGO_MIRROR_CSRF` | `True` | Mirror the CSRF token to `DjangoUserState.csrf_token`. |
| `REFLEX_DJANGO_MIRROR_LANGUAGE` | `True` | Mirror language to `DjangoUserState.language` and `language_bidi`. |

### Page discovery

| Setting | Default | What it does |
|:---|:---|:---|
| `REFLEX_DJANGO_PAGE_PACKAGES` | `[]` | Explicit list of page modules. If non-empty, disables auto-discovery. |
| `REFLEX_DJANGO_AUTO_DISCOVER_PAGES` | `True` (deprecated) | Walk `INSTALLED_APPS` and import `{app}.views` at compile time. |
| `REFLEX_DJANGO_PAGE_APPS` | `None` | Allowlist of app labels to scan. `None` means all of them. |
| `REFLEX_DJANGO_PAGE_MODULE` | `"views"` | Which submodule to import per app. |

### Reflex runtime (`rx.Config`)

| Setting | Default | What it does |
|:---|:---|:---|
| `REFLEX_DJANGO_RX_CONFIG` | `{}` | Reflex runtime options: ports, `redis_url`, CORS, log level, **`app_name`**, and so on. |
| `REFLEX_DJANGO_PLUGINS` | `[]` | Reflex plugins as dotted paths or instances (Radix, Tailwind, and so on). |

### Plugin and rxconfig

| Setting | Default | What it does |
|:---|:---|:---|
| `REFLEX_DJANGO_USE_RXCONFIG_FILE` | `False` | Merge an existing on-disk `rxconfig.py` into the runtime config. |
| `REFLEX_DJANGO_MATERIALIZE_RXCONFIG` | `False` | Write a stub `rxconfig.py` to disk. |
| `REFLEX_DJANGO_PLUGIN` | `{}` | Extra kwargs for the built-in Django integration plugin. |
| `REFLEX_DJANGO_AUTO_PLUGIN` | `True` | Always enabled. Kept for backwards compatibility. |

### Auth

| Setting | Default | What it does |
|:---|:---|:---|
| `REFLEX_DJANGO_LOGIN_URL` | `"/login"` | Where `@login_required` redirects to. |
| `REFLEX_DJANGO_AUTH` | see [Login and sessions](authentication.md) | Built-in auth pages and branding. |
| `REFLEX_DJANGO_AUTH_AUTO_SYNC` | `True` | Refresh the `AppState` user snapshot on every event. |

---

## Middleware

Standard Django middleware works as-is. Add the streaming helper at the bottom:

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

The `AsyncStreamingMiddleware` line keeps Django's admin streaming responses ASGI-safe. See [AsyncStreamingMiddleware](async_streaming_middleware.md).

Every middleware in this list runs on every Reflex event by default (except the skipped ones on WebSocket events). Custom middleware that sets `request.tenant` will also expose it on `self.request.tenant` inside `@rx.event` handlers.

---

## Configuration ladder

### Level 0: defaults (zero mount line)

Settings and URLs from the snippets above. Catch-all appended automatically.

Pages use native Reflex style on the shared app:

```python
from reflex_django import app

app.add_page(home, route="/")
```

### Level 1: settings overrides (no manual mount)

| Setting | Override |
|:---|:---|
| `REFLEX_DJANGO_AUTO_MOUNT = False` | Disable catch-all auto-append; use manual `reflex_mount()` |
| `REFLEX_DJANGO_MOUNT_PREFIX` | SPA mount path (default `/`) |
| `REFLEX_DJANGO_RX_CONFIG` | Any allowed `rx.Config` field, including **`app_name`** |
| `REFLEX_DJANGO_PLUGINS` | Reflex plugins |
| `REFLEX_DJANGO_PLUGIN` | Built-in plugin kwargs (`django_prefix`, and so on) |
| `REFLEX_DJANGO_URL_ROUTING` | `django_outer` / `reflex_outer` |
| `REFLEX_DJANGO_USE_RXCONFIG_FILE = True` | Merge an on-disk `rxconfig.py` |

### Level 2: explicit `reflex_mount()`

Manual mount **wins over auto-mount**. Kwargs merge over settings:

```python
urlpatterns += reflex_mount(
    mount_prefix="/app",
    django_prefix=("/admin", "/api/v2"),
    rx_config={"frontend_port": 3001},
)
```

### Level 3: custom `rx.App`

**Factory setting:**

```python
REFLEX_DJANGO_CREATE_APP = "myapp.reflex.create_app"  # callable() -> rx.App
```

**Direct assignment:**

```python
import reflex as rx
import reflex_django.reflex_app as reflex_app_module

reflex_app_module._app = rx.App(theme=rx.theme(accent_color="blue"))
```

Import `from reflex_django import app` in page modules. It is the same singleton object.

### Level 4: routing escape hatches

| Mode | When |
|:---|:---|
| `reflex_outer` | Reflex owns the public port; Django HTTP runs in a worker |
| `REFLEX_DJANGO_AUTO_MOUNT=False` | API-only Django or a fully custom URL layout |

---

## How `DJANGO_SETTINGS_MODULE` is resolved

In order of preference:

1. The `DJANGO_SETTINGS_MODULE` environment variable, if set.
2. Auto-discovery: reflex-django walks up looking for `manage.py` and reads its settings reference.
3. Falls back to `reflex_django.default_settings` (dev-only, never rely on this in production).

In production, always set `DJANGO_SETTINGS_MODULE` explicitly in your container or systemd unit.

---

## Common configuration mistakes

**Prefix mismatch (404 on `/api/...`)**
Your Django route is `path("v1/", ...)` but you expected `/api` to be reserved. Auto-detection only sees the first segment. Either rename the Django path or pass `django_prefix=("/api", "/v1", ...)` explicitly.

**`AppRegistryNotReady` at import time**
You imported a model at the top of `views.py`. Move the import inside the handler. Models are only safe after Django finishes its app registry.

**Stale `rxconfig.py` on disk**
If you have a leftover `rxconfig.py` from plain Reflex, set `REFLEX_DJANGO_USE_RXCONFIG_FILE = True` to merge it, or delete it. By default reflex-django ignores files on disk.

**Wrong `app_name`**
Set `app_name` in `REFLEX_DJANGO_RX_CONFIG`. It is the Reflex compile identity (often your primary Django app label), not a Python module path like `shop.shop`. The runtime loader is `reflex_django.reflex_app:app`.

!!! warning "Do not pass plugins in REFLEX_DJANGO_RX_CONFIG"
    Put plugins in `REFLEX_DJANGO_PLUGINS` or the `plugins=` argument on `reflex_mount()`. The `plugins` key inside `REFLEX_DJANGO_RX_CONFIG` is ignored.

---

## What just happened?

You mapped the three configuration knobs to concrete files, saw the minimal wiring snippets, and got a tour of the `REFLEX_DJANGO_*` settings most projects touch. Page registration and the SPA catch-all are separate jobs controlled by imports/settings versus auto-mount.

---

**Next up:** [Pages in views.py](pages_in_views.md)