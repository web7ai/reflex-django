# Configuration

reflex-django is **Django-first**. Reflex settings are registered through **`reflex_mount()`** in your root `urls.py`. Django settings control pages, auth, and optional overrides.

---

## Primary configuration: `reflex_mount()`

```python
# project/urls.py
from django.contrib import admin
from django.urls import include, path
from reflex_django.urls import reflex_mount

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("myapp.api_urls")),
]

urlpatterns += [
    reflex_mount(
        app_name="myapp",
        mount_prefix="/",
        django_prefix=("/admin", "/api"),
        plugins=[MyAnalyticsPlugin()],
        rx_config={
            "frontend_port": 3000,
            "backend_port": 8000,
            "db_url": "sqlite:///db.sqlite3",
        },
        django_plugin={
            "install_event_bridge": True,
        },
    ),
]
```

### `reflex_mount()` parameters

| Parameter | Default | Description |
|:---|:---|:---|
| **`app_name`** | Project folder name (`manage.py` parent, `-` → `_`) | Django/Reflex app label; pages live in `{app_name}/views.py` |
| **`mount_prefix`** | `"/"` | URL prefix for the SPA catch-all |
| **`django_prefix`** | `()` | Path prefixes owned by Django (`/admin`, `/api`, …). Must match real `path()` entries **above** `reflex_mount` |
| **`plugins`** | `()` | Extra Reflex plugins. **`ReflexDjangoPlugin` is added automatically** — do not pass it here |
| **`rx_config`** | `{}` | Allowed `rx.Config` keys: ports, `db_url`, `cors_allowed_origins`, etc. |
| **`django_plugin`** | `{}` | Keyword args merged into `ReflexDjangoPlugin` (also merged with `REFLEX_DJANGO_PLUGIN` in settings) |

### Allowed `rx_config` keys

Ports, database URL, CORS, log level, state manager mode, and other keys listed in `reflex_django.rxconfig_bridge.ALLOWED_RX_CONFIG_KEYS`. You cannot set `plugins` inside `rx_config` — use the `plugins=` argument on `reflex_mount()`.

---

## `app_name` vs `app_module_import`

| Concept | Value | Purpose |
|:---|:---|:---|
| **`app_name`** | e.g. `"demo"` | Label for your Django app; drives page discovery (`demo/views.py`) |
| **`app_module_import`** | `reflex_django.django_led_app` (automatic) | Where Reflex imports `app` |

Reflex normally loads `from demo.demo import app`. reflex-django sets `app_module_import` so Reflex uses the built-in factory instead. You never maintain `demo/demo.py`.

---

## Django settings (`REFLEX_DJANGO_*`)

| Setting | Default | Description |
|:---|:---|:---|
| **`REFLEX_DJANGO_URL_ROUTING`** | `"django_led"` | `"django_led"` (Django prefixes + SPA catch-all) or `"reflex_led"` |
| **`REFLEX_DJANGO_USE_RXCONFIG_FILE`** | `False` | When `True`, merge an on-disk `rxconfig.py` into runtime config |
| **`REFLEX_DJANGO_MATERIALIZE_RXCONFIG`** | `False` | When `True`, write/update stub `rxconfig.py` on demand |
| **`REFLEX_DJANGO_PLUGIN`** | `{}` | Extra `ReflexDjangoPlugin` keyword arguments |
| **`REFLEX_DJANGO_AUTO_PLUGIN`** | `True` | Deprecated; plugin is always enabled |
| **`REFLEX_DJANGO_PAGE_PACKAGES`** | `[]` | Explicit page modules; non-empty disables auto-discovery |
| **`REFLEX_DJANGO_AUTO_DISCOVER_PAGES`** | `True` | Import `{app}.views` for each `INSTALLED_APPS` entry |
| **`REFLEX_DJANGO_PAGE_APPS`** | `None` | Allowlist of app labels to scan |
| **`REFLEX_DJANGO_PAGE_MODULE`** | `"views"` | Submodule to import per app |
| **`REFLEX_DJANGO_CONTEXT_PROCESSORS`** | `()` | Extra context callables for Reflex events (JSON-serializable) |
| **`REFLEX_DJANGO_AUTO_LOAD_CONTEXT`** | `True` | Run context processors on every Reflex event (no manual `load_django_context()` in handlers) |
| **`REFLEX_DJANGO_USE_TEMPLATE_CONTEXT_PROCESSORS`** | `True` | Use Django template context processors when the list above is empty |
| **`REFLEX_DJANGO_LOGIN_URL`** | `"/login"` | Redirect for `@login_required` |
| **`REFLEX_DJANGO_AUTH`** | *(see [Authentication](authentication.md))* | Built-in auth pages configuration |
| **`REFLEX_DJANGO_AUTH_AUTO_SYNC`** | `True` | Refresh `AppState` user snapshot on each event |
| **`REFLEX_DJANGO_I18N_EVENT_BRIDGE`** | `True` | Language negotiation on WebSocket events |

`REFLEX_DJANGO_APP_NAME` and `REFLEX_DJANGO_RX_CONFIG` are **removed** — use `reflex_mount(app_name=..., rx_config={...})` instead.

---

## `rxconfig.py` on disk

| Situation | Behavior |
|:---|:---|
| No file | Config built only from `reflex_mount()` (default for `run_reflex`) |
| Auto stub (reflex-django marker in file) | Removed on `run_reflex` unless `REFLEX_DJANGO_MATERIALIZE_RXCONFIG=True`; live config always from `reflex_mount()` |
| Your own full `rxconfig.py` | Set `REFLEX_DJANGO_USE_RXCONFIG_FILE=True` to merge it |

`run_reflex` registers config in memory (`sys.modules['rxconfig']`) and does **not** create `rxconfig.py` by default.

---

## `ReflexDjangoPlugin`

Registered automatically by reflex-django. You rarely instantiate it yourself. When you pass `django_plugin={...}` on `reflex_mount()`, those kwargs are merged with `REFLEX_DJANGO_PLUGIN`.

| Parameter | Default | Description |
|:---|:---|:---|
| **`settings_module`** | *(deprecated)* | Use `manage.py` / `DJANGO_SETTINGS_MODULE` |
| **`backend_prefix`** | `""` | Legacy; prefer `django_prefix` on `reflex_mount()` |
| **`admin_prefix`** | `"/admin"` | Legacy admin prefix hint |
| **`django_prefix`** | `()` | Merged from `reflex_mount(django_prefix=...)` |
| **`install_event_bridge`** | `True` | Session/user bridge for WebSocket events |
| **`install_auth_pages`** | `False` | Auto-register auth pages (prefer explicit `add_auth_pages`) |

---

## Django settings module resolution

```text
[1] DJANGO_SETTINGS_MODULE already set (manage.py, env, deployment)?
    └── YES → use it
[2] Parse nearest manage.py
    └── found → use it
[3] reflex_django.default_settings (dev fallback only)
```

In production, always set `DJANGO_SETTINGS_MODULE` explicitly.

---

## Middleware

Add streaming middleware at the **end** of `MIDDLEWARE` when not using default settings:

```python
MIDDLEWARE = [
    # ...
    "reflex_django.streaming_middleware.AsyncStreamingMiddleware",
]
```

Why it matters under ASGI (`run_reflex`): [AsyncStreamingMiddleware](async_streaming_middleware.md).

---

## Minimal `settings.py` checklist

```python
INSTALLED_APPS = [..., "reflex_django", "myapp"]
ROOT_URLCONF = "config.urls"   # must import reflex_mount()
# Session + auth middleware (standard stack)
```

```python
# config/urls.py — reflex_mount last
urlpatterns += [reflex_mount(app_name="myapp", rx_config={...})]
```

---

## Common pitfalls

**Prefix mismatch**

`django_prefix=("/api",)` must match `path("api/", ...)` in the same `urls.py`. The ASGI dispatcher and catch-all regex both use this list.

**Circular imports**

Import Django models inside `@rx.event` methods, not at module top level in `views.py`, if you hit `AppRegistryNotReady`.

**Wrong app module**

Never point `app_name` at a non-existent package expecting `app_name/app_name.py`. Use `app_name` for the Django app with `views.py`; the loader is always `django_led_app`.

---

**Navigation:** [← Installation](installation.md) | [Next: Quickstart →](quickstart.md)
