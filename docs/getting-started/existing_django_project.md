---
level: intermediate
tags: [integration, django, plugin]
---

# Add reflex-django to an existing Django project

**What you will learn:** How to bolt a Reflex SPA onto a brownfield Django project without touching your models, admin, or API.

**When you need this:**

- You already run Django in production and want reactive pages on the same origin.
- You want to keep DRF, webhooks, and management commands exactly as they are.

You add reflex-django like any other Django app. Your models stay put. Your API stays put. You register pages in `{app_name}/{app_name}.py` or with `@page` in `views.py`.

**Coming from plain Reflex?** See [Plugin path](existing_reflex_project_plugin.md) (same integration model; you already have `rxconfig.py`).

**Not sure which guide?** See [Getting started - brownfield](index.md#brownfield-integration).

---

## Quick checklist

- [ ] `uv add reflex reflex-django` (or `pip install`)
- [ ] `"reflex_django"` in `INSTALLED_APPS`
- [ ] `AsyncStreamingMiddleware` last in `MIDDLEWARE`
- [ ] `rxconfig.py` with `ReflexDjangoPlugin` and `rx.Config(...)`
- [ ] `{app_name}/{app_name}.py` with `app = rx.App()` (and `app.add_page(...)` or imports)
- [ ] `import yourapp.views` in `urls.py` when using `@page` in `views.py`
- [ ] `config/asgi.py` → plain `get_asgi_application()`
- [ ] `reflex run` for dev; `reflex export` for production builds

---

## What you keep, what you add

| You keep | You add |
|:---|:---|
| `manage.py`, models, migrations, admin | `reflex_django` in `INSTALLED_APPS` |
| Existing `/api/` and templates | `rxconfig.py` + `{app_name}/{app_name}.py` |
| Custom middleware | `AsyncStreamingMiddleware` at the bottom |
| DRF views, webhooks, scripts | Reflex pages (`app.add_page` or `@page`) |

You **do** add `rxconfig.py` and `{app_name}/{app_name}.py`. You **do not** add `RX_CONFIG` to `settings.py` (removed in v4).

---

## 1. Install

```bash
uv add reflex reflex-django
```

---

## 2. Register the app

In `settings.py`:

```python
INSTALLED_APPS = [
    # ...
    "reflex_django",
]

MIDDLEWARE = [
    # ...
    "reflex_django.middleware.AsyncStreamingMiddleware",  # must be last
]
```

---

## 3. Add `rxconfig.py`

At the project root (next to `manage.py`):

```python
import reflex as rx
from reflex_django.plugins import ReflexDjangoPlugin

config = rx.Config(
    app_name="myshop",
    frontend_port=3000,
    backend_port=8000,
    plugins=[
        ReflexDjangoPlugin(config={
            "settings_module": "config.settings",
            "django_prefix": ("/admin", "/api"),
            "mount_prefix": "/",
            "auto_mount": True,
        }),
        rx.plugins.RadixThemesPlugin(),
    ],
)
```

Plugin `config` keys (v4): `settings_module`, `django_prefix`, `mount_prefix`, `auto_mount` only.

---

## 4. Add the Reflex app module

Create `myshop/myshop.py` (match `app_name` in `rxconfig.py`):

```python
import reflex as rx

app = rx.App()
app.add_page(lambda: rx.text("Hello from Django + Reflex"), route="/")
```

For `@page` decorators in Django `views.py`, see [App entry and pages](../guides/app_entry_and_pages.md).

---

## 5. Wire URLs and ASGI

Import page modules in `urls.py` so `@page` registers at startup:

```python
from django.urls import path, include
import myshop.views  # noqa: F401

urlpatterns = [
  path("admin/", admin.site.urls),
  # reflex_mount catch-all is added by the plugin when auto_mount=True
]
```

`asgi.py` stays standard:

```python
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
application = get_asgi_application()
```

---

## 6. Run

```bash
reflex run
```

Use `reflex django migrate` or `python manage.py migrate` for Django tasks.

---

**Migrating from v3 django-first?** See [v4: Plugin-only integration](../reference/migration/v4_plugin_only.md).

**Next:** [Plugin path details](existing_reflex_project_plugin.md) · [Local development](local_development.md)
