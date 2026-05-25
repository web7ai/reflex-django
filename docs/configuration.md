# Configuration with `reflex_mount()`

All `reflex-django` configuration lives in two places, and one of them is optional:

1. **`reflex_mount(...)`** in `urls.py` — Reflex options (ports, app name, prefixes) and the SPA catch-all URL pattern.
2. **`REFLEX_DJANGO_*` settings** in `settings.py` — integration tunables (which middleware to skip on events, which reactive mirrors to expose, where pages live).

There's no `rxconfig.py`. `reflex-django` synthesizes one in memory from the two sources above.

This page is the reference for both. The settings table at the bottom is also available as a flat lookup at [REFLEX_DJANGO_* settings](settings_reference.md).

---

## `reflex_mount()` — the one call you actually write

```python
# config/urls.py
from django.contrib import admin
from django.urls import include, path
from reflex_django.urls import reflex_mount

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("shop.api_urls")),
]

urlpatterns += [
    reflex_mount(
        app_name="shop",
        mount_prefix="/",
        django_prefix=("/admin", "/api"),
        plugins=[],
        rx_config={
            "backend_port": 8000,
        },
        django_plugin={},
    ),
]
```

### What each argument does

| Argument | Default | What it does |
|:---|:---|:---|
| `app_name` | folder containing `manage.py` (underscored) | The Reflex `app_name`. Also the default Django app to scan for pages. |
| `mount_prefix` | `"/"` | URL prefix where the SPA catch-all lives. You almost never change this. |
| `django_prefix` | `()` | Path prefixes Django owns. Must match real `path(...)` entries above. |
| `plugins` | `()` | Extra Reflex plugins. `ReflexDjangoPlugin` is added automatically — don't pass it yourself. |
| `rx_config` | `{}` | Allowed `rx.Config` keys (ports, `db_url`, CORS, log level, …). |
| `django_plugin` | `{}` | Extra kwargs for the built-in `ReflexDjangoPlugin`. Merged with `REFLEX_DJANGO_PLUGIN`. |

### What goes in `rx_config`

You can pass any standard Reflex `rx.Config` option *except* `plugins` (use the `plugins=` argument instead). The most common ones:

```python
rx_config={
    "backend_port": 8000,
    "db_url": "sqlite:///db.sqlite3",
    "cors_allowed_origins": ["https://example.com"],
    "show_built_with_reflex": False,
    "loglevel": "info",
    "telemetry_enabled": False,
}
```

By default `show_built_with_reflex` is forced to `False`. You can flip it back with `rx_config={"show_built_with_reflex": True}` or globally with `REFLEX_DJANGO_SHOW_BUILT_WITH_REFLEX = True` in settings.

### The `django_prefix` rule

Every prefix you list in `django_prefix` should match a real `path(...)` above the `reflex_mount()` line. If you forget one, the SPA catch-all will try to render the SPA for that URL.

```python
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("shop.api_urls")),
    path("webhooks/stripe/", stripe_webhook),
]

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
| `django_prefix` | `()` | Inherited from `reflex_mount(django_prefix=...)`. |
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

## Common configuration mistakes

**Prefix mismatch (404 on `/api/...`)**
You added `django_prefix=("/api",)` but your URLs say `path("v1/", ...)`. The dispatcher and Django's URL resolver both consult `django_prefix`. Keep them aligned.

**`AppRegistryNotReady` at import time**
You imported a model at the top of `views.py`. Move the import inside the handler function. Models are only safe to import after Django finishes its app registry.

**Stale `rxconfig.py` on disk**
If you previously experimented with plain Reflex and have a leftover `rxconfig.py`, set `REFLEX_DJANGO_USE_RXCONFIG_FILE = True` to merge it, or just delete it. By default `reflex-django` ignores files on disk.

**Wrong `app_name`**
`app_name` is a Django app label (the folder name with your `views.py`), not a Python module path like `shop.shop`. The loader is always `reflex_django.django_led_app`.

---

## Minimal checklist

If you want to start from a blank-ish project, here's the smallest set of edits:

```python
# settings.py
INSTALLED_APPS = [..., "reflex_django", "myapp"]
ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"

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
urlpatterns += [reflex_mount(app_name="myapp", rx_config={"backend_port": 8000})]
```

```python
# asgi.py
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
from reflex_django.asgi_entry import application
```

---

**Next:** [Pages live in views.py →](pages_in_views.md)
