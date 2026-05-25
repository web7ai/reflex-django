# Configuration

`reflex-django` is Django-first. The runtime config is built from two sources:

1. **`reflex_mount()`** in your `ROOT_URLCONF` — Reflex `rx.Config` values (ports, plugins, allowed CORS, etc.) and the SPA catch-all URL pattern.
2. **Django settings (`REFLEX_DJANGO_*`)** — integration behaviour: middleware chain wiring, reactive mirrors, template rendering, build/serve defaults.

There is no hand-maintained `rxconfig.py`. The integration synthesises one in memory (`sys.modules["rxconfig"]`) from the two sources above.

---

## 1. `reflex_mount()` — Reflex configuration

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
| `app_name` | Project folder name | Django/Reflex app label; pages discovered from `{app_name}/views.py`. |
| `mount_prefix` | `"/"` | URL prefix for the SPA catch-all. |
| `django_prefix` | `()` | Paths Django owns (`/admin`, `/api`, …). Must match real `path()` entries above. |
| `plugins` | `()` | Extra Reflex plugins. `ReflexDjangoPlugin` is added automatically — don't pass it. |
| `rx_config` | `{}` | Allowed `rx.Config` keys: ports, `db_url`, `cors_allowed_origins`, `show_built_with_reflex`, etc. |
| `django_plugin` | `{}` | Kwargs merged into `ReflexDjangoPlugin` (also merged with `REFLEX_DJANGO_PLUGIN`). |

### Allowed `rx_config` keys

Ports, database URL, CORS allowlist, log level, state-manager mode, and any other key in `reflex_django.rxconfig_bridge.ALLOWED_RX_CONFIG_KEYS`. You **cannot** set `plugins` inside `rx_config`; use the `plugins=` argument on `reflex_mount()`.

By default `show_built_with_reflex` is forced to `False`; override per-mount via `rx_config={"show_built_with_reflex": True}` or globally with `REFLEX_DJANGO_SHOW_BUILT_WITH_REFLEX = True`.

---

## 2. `REFLEX_DJANGO_*` settings

### Routing & serving

| Setting | Default | Description |
|:---|:---|:---|
| `REFLEX_DJANGO_URL_ROUTING` | `"auto"` (resolves to `django_outer`) | Routing mode. Set to `"reflex_led"` to fall back to the legacy two-port layout. |
| `REFLEX_DJANGO_SERVE_FROM_BUILD` | `True` | `manage.py run_reflex` auto-exports the SPA and serves it from disk. Set to `False` (or pass `--with-vite`) to use the Vite HMR dev loop. |
| `REFLEX_DJANGO_RESERVED_REFLEX_PREFIXES` | `()` | Extra path prefixes always routed to Reflex. |
| `REFLEX_DJANGO_DEV_PROXY` | `False` (auto-managed by `run_reflex`) | Used only when `--with-vite` is active. |

### SPA shell rendering

| Setting | Default | Description |
|:---|:---|:---|
| `REFLEX_DJANGO_RENDER_SPA_VIA_TEMPLATE_ENGINE` | `True` | Pipe the SPA `index.html` through Django's template engine so `{{ }}` and `{% %}` tags render server-side. |
| `REFLEX_DJANGO_SHOW_BUILT_WITH_REFLEX` | `False` | Toggle the "Built with Reflex" badge. |

### Event middleware chain

| Setting | Default | Description |
|:---|:---|:---|
| `REFLEX_DJANGO_RUN_MIDDLEWARE_CHAIN` | `True` | Run the full `settings.MIDDLEWARE` chain on every Reflex event. |
| `REFLEX_DJANGO_EVENT_MIDDLEWARE_SKIP` | `("django.middleware.csrf.CsrfViewMiddleware", "reflex_django.streaming_middleware.AsyncStreamingMiddleware")` | Middleware to skip on Socket.IO events. |
| `REFLEX_DJANGO_AUTO_REDIRECT_FROM_MIDDLEWARE` | `True` | Translate 3xx middleware responses into `rx.redirect(...)` automatically. |
| `REFLEX_DJANGO_EVENT_POST_FROM_PAYLOAD` | `False` | Feed event kwargs into the synthetic `request.POST`. |

### Reactive mirrors

| Setting | Default | Description |
|:---|:---|:---|
| `REFLEX_DJANGO_MIRROR_MESSAGES` | `True` | Mirror `django.contrib.messages` to `DjangoUserState.messages`. |
| `REFLEX_DJANGO_MIRROR_CSRF` | `True` | Mirror CSRF token to `DjangoUserState.csrf_token`. |
| `REFLEX_DJANGO_MIRROR_LANGUAGE` | `True` | Mirror language to `DjangoUserState.language` + `language_bidi`. |

### Pages & context processors

| Setting | Default | Description |
|:---|:---|:---|
| `REFLEX_DJANGO_PAGE_PACKAGES` | `[]` | Explicit page modules. Non-empty disables auto-discovery. |
| `REFLEX_DJANGO_AUTO_DISCOVER_PAGES` | `True` | Import `{app}.views` for each `INSTALLED_APPS` entry. |
| `REFLEX_DJANGO_PAGE_APPS` | `None` | Allowlist of app labels to scan. |
| `REFLEX_DJANGO_PAGE_MODULE` | `"views"` | Submodule to import per app. |
| `REFLEX_DJANGO_CONTEXT_PROCESSORS` | `()` | Extra context callables for Reflex events (JSON-serialisable). |
| `REFLEX_DJANGO_AUTO_LOAD_CONTEXT` | `True` | Run context processors on every Reflex event automatically. |
| `REFLEX_DJANGO_USE_TEMPLATE_CONTEXT_PROCESSORS` | `True` | Use Django template context processors when the explicit list is empty. |

### Plugin & rxconfig

| Setting | Default | Description |
|:---|:---|:---|
| `REFLEX_DJANGO_USE_RXCONFIG_FILE` | `False` | When `True`, merge an on-disk `rxconfig.py` into runtime config. |
| `REFLEX_DJANGO_MATERIALIZE_RXCONFIG` | `False` | When `True`, write/update a stub `rxconfig.py` on demand. |
| `REFLEX_DJANGO_PLUGIN` | `{}` | Extra `ReflexDjangoPlugin` keyword arguments. |
| `REFLEX_DJANGO_AUTO_PLUGIN` | `True` | Plugin is always enabled; flag kept for backwards compatibility. |

### Auth

| Setting | Default | Description |
|:---|:---|:---|
| `REFLEX_DJANGO_LOGIN_URL` | `"/login"` | Redirect target for `@login_required`. |
| `REFLEX_DJANGO_AUTH` | see [Authentication](authentication.md) | Built-in auth-page configuration. |
| `REFLEX_DJANGO_AUTH_AUTO_SYNC` | `True` | Refresh `AppState` user snapshot on each event. |

---

## 3. `ReflexDjangoPlugin`

The integration registers `ReflexDjangoPlugin` automatically — you rarely instantiate it yourself. To customise, pass `django_plugin={...}` on `reflex_mount()` or set `REFLEX_DJANGO_PLUGIN = {...}` in settings. Both are merged.

| Parameter | Default | Description |
|:---|:---|:---|
| `django_prefix` | `()` | Merged from `reflex_mount(django_prefix=...)`. |
| `install_event_bridge` | `True` | Wire `DjangoEventBridge` into Reflex's event pipeline. |
| `install_auth_pages` | `False` | Auto-register built-in auth pages (prefer explicit `add_auth_pages()`). |

---

## 4. Django settings module resolution

```text
[1] DJANGO_SETTINGS_MODULE is already set (manage.py / env / deployment)?
    └── yes → use it
[2] Walk up to find the nearest manage.py and parse its settings reference
    └── found → use it
[3] Fall back to reflex_django.default_settings (dev convenience only)
```

In production, always set `DJANGO_SETTINGS_MODULE` explicitly via your container/service env.

---

## 5. Middleware

Standard Django middleware works as-is, plus one ASGI helper at the end:

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "reflex_django.streaming_middleware.AsyncStreamingMiddleware",
]
```

`AsyncStreamingMiddleware` keeps the Django admin streaming responses ASGI-safe. See [AsyncStreamingMiddleware](async_streaming_middleware.md).

Every middleware on this list also runs on every Reflex event by default (except `CsrfViewMiddleware` and `AsyncStreamingMiddleware`, which are skipped on Socket.IO events). Add your own — `LoginRequiredMiddleware`, `RatelimitMiddleware`, multi-tenancy, audit logging — and they apply to both HTTP and Reflex events uniformly.

---

## 6. Minimal `settings.py` checklist

```python
INSTALLED_APPS = [..., "reflex_django", "myapp"]
ROOT_URLCONF = "config.urls"     # must import reflex_mount()
ASGI_APPLICATION = "config.asgi.application"

MIDDLEWARE = [
    # standard stack
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    # ASGI streaming helper
    "reflex_django.streaming_middleware.AsyncStreamingMiddleware",
]

STATIC_ROOT = BASE_DIR / "staticfiles"   # where the SPA bundle is staged
```

```python
# config/urls.py — reflex_mount last
urlpatterns += [reflex_mount(app_name="myapp", rx_config={"backend_port": 8000})]
```

```python
# config/asgi.py — single ASGI entry point
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
from reflex_django.asgi_entry import application  # noqa: E402,F401
```

---

## 7. Common pitfalls

**Prefix mismatch**

`django_prefix=("/api",)` must correspond to `path("api/", ...)` in the same `urls.py`. The outer dispatcher and the Django URL resolver both consult this list.

**Circular imports**

Import Django models inside `@rx.event` methods, not at module top level in `views.py`, if you hit `AppRegistryNotReady`.

**Hand-maintained `rxconfig.py`**

If you previously kept `rxconfig.py` checked in, set `REFLEX_DJANGO_USE_RXCONFIG_FILE = True` to merge it. Otherwise the integration synthesises one in memory and ignores the file on disk.

**Wrong `app_name`**

`app_name` is a Django app label, not a Python package path. It should match the directory containing `views.py`. The loader is always `reflex_django.django_led_app`; you never create `{app_name}/{app_name}.py`.

---

**Navigation:** [← Installation](installation.md) | [Next: Quickstart →](quickstart.md)
