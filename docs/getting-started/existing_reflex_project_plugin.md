---
level: intermediate
tags: [integration, reflex, plugin]
---

# Add reflex-django to an existing Reflex project (plugin path)

**What you will learn:** How to integrate reflex-django with minimal changes to a plain Reflex project by adding `ReflexDjangoPlugin` to `rxconfig.py` and keeping `reflex run`.

**When you need this:**

- You want to keep `rxconfig.py`, `app = rx.App()`, and standard Reflex CLI commands (`reflex run`, `reflex export`, `reflex deploy`).
- You are fine adding a Django shell (`manage.py`, `settings.py`, `urls.py`) for ORM, admin, and sessions.

**Upgrading from v3?** See [v4: Plugin-only integration](../reference/migration/v4_plugin_only.md) or [Add to an existing Django project](existing_django_project.md).

**Not sure which guide?** See [Getting started — brownfield](index.md#brownfield-integration).

## What stays the same

| You keep | You add |
|:---|:---|
| `rxconfig.py` as config source | Django project shell |
| `app = rx.App()` in `{app}/{app}.py` | `ReflexDjangoPlugin` in `plugins` |
| `reflex run` / `reflex export` | `manage.py migrate`, `createsuperuser` |
| Page components and handlers | `INSTALLED_APPS`, `urls.py`, ASGI |

---

## 1. Add Django around your Reflex app

```bash
uv add django reflex-django
uv run django-admin startproject config .
```

Register reflex-django in `settings.py`, set `MIDDLEWARE` (include `AsyncStreamingMiddleware` last), and point `config/asgi.py` at `get_asgi_application()`. See [Add to an existing Django project](existing_django_project.md) for the Django shell details.

---

## 2. Add the plugin to `rxconfig.py`

```python
import reflex as rx
from reflex_django.plugins import ReflexDjangoPlugin

config = rx.Config(
    app_name="myshop",
    plugins=[
        ReflexDjangoPlugin(config={
            # Optional when discoverable from manage.py:
            "settings_module": "config.settings",
            # Optional; auto-detected from urlpatterns when omitted:
            "django_prefix": ("/admin", "/api"),
            "mount_prefix": "/",
            "auto_mount": True,
        }),
        rx.plugins.RadixThemesPlugin(),
    ],
)
```

`RXDJANGOPLUGIN` is an alias for `ReflexDjangoPlugin`.

### Plugin `config` keys

| Key | Required | Default | Purpose |
|:---|:---|:---|:---|
| `settings_module` | No | from `manage.py` | `DJANGO_SETTINGS_MODULE` |
| `django_prefix` | No | auto from `urlpatterns` | ASGI dispatcher prefixes |
| `mount_prefix` | No | `"/"` | SPA catch-all prefix |
| `auto_mount` | No | `True` | append `reflex_mount` catch-all |

---

## 3. Run with Reflex CLI

```bash
reflex run
```

- Browse `http://localhost:3000/` for the Reflex UI (HMR).
- Django admin/API on configured prefixes are mounted in the Reflex backend via `api_transformer`.

Database setup still uses Django:

```bash
reflex django migrate
reflex django createsuperuser
```

Or use `python manage.py` directly.

---

## Production notes

- Build the frontend with `reflex export` (plugin bootstrap runs automatically).
- Self-hosted: run the Reflex backend with Django prefixes in-process, or split Django and Reflex with `RX_PROXY_SERVER`.
- Reflex Cloud hosts Reflex only; deploy Django admin/API on a separate Django service.

See [Deployment](../operations/deployment.md).

---

**Next:** [Configuration](configuration.md) or [Add to an existing Django project](existing_django_project.md).