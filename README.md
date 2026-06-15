# reflex-django

**Keep Django. Get a reactive UI in Python. One process, shared cookies, native Reflex dev.**

[![PyPI](https://img.shields.io/pypi/v/reflex-django?color=%23e91e63&label=pypi)](https://pypi.org/project/reflex-django)
[![Python](https://img.shields.io/pypi/pyversions/reflex-django.svg?color=%23ad1457)](https://pypi.org/project/reflex-django)
[![Docs](https://img.shields.io/badge/docs-online-%23ec407a)](https://web7ai.github.io/reflex-django/)
[![License](https://img.shields.io/github/license/web7ai/reflex-django.svg?color=%23f06292)](https://github.com/web7ai/reflex-django/blob/main/LICENSE)

[Documentation](https://web7ai.github.io/reflex-django/) · [GitHub](https://github.com/web7ai/reflex-django) · [PyPI](https://pypi.org/project/reflex-django)

---

## What is it?

You love Django. You also want a modern, reactive UI in Python, not a separate React repo.

`reflex-django` runs Django and [Reflex](https://reflex.dev) together on one origin with shared session cookies. Reflex handlers see the same `request.user` as Django admin and your API.

- **Same cookies** — `self.request.user` inside every `@rx.event`
- **Same middleware** — your full `settings.MIDDLEWARE` chain on events
- **Django admin + ORM** — keep models, migrations, and admin as-is
- **Two dev ports** — Vite on `:3000`, backend on `:8000` (proxies wire admin/API for you)

---

## New or existing?

| You already have | Integration guide | Dev command |
|:---|:---|:---|
| **A Reflex + Django project** | [Plugin integration](https://web7ai.github.io/reflex-django/getting-started/existing_reflex_project_plugin/) | `reflex run` |

Add `ReflexDjangoPlugin` to `rxconfig.py`, keep `app = rx.App()` in `{app}/{app}.py`, and use normal Django settings for ORM, admin, and migrations.

---

## Minimal setup

```bash
uv add django reflex reflex-django
```

`rxconfig.py`:

```python
import reflex as rx
from reflex_django.plugins import ReflexDjangoPlugin

config = rx.Config(
    app_name="shop",
    frontend_port=3000,
    backend_port=8000,
    plugins=[
        ReflexDjangoPlugin(config={
            "settings_module": "config.settings",
            "django_prefix": ("/admin", "/api"),
            "mount_prefix": "/",
            "auto_mount": True,
        }),
    ],
)
```

`config/settings.py` (Django only — no `RX_CONFIG`):

```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "reflex_django",
    "shop",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "reflex_django.bridge.streaming.AsyncStreamingMiddleware",
]
```

`shop/shop.py`:

```python
import reflex as rx

app = rx.App()
```

`config/urls.py`:

```python
import shop.views  # noqa: F401

from django.contrib import admin
from django.urls import path

urlpatterns = [path("admin/", admin.site.urls)]
```

`config/asgi.py`:

```python
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.asgi import get_asgi_application

application = get_asgi_application()  # noqa: E402,F401
```

`shop/views.py`:

```python
import reflex as rx
from reflex_django.pages.decorators import page
from reflex_django.states import AppState


class HomeState(AppState):
    @rx.event
    async def on_load(self):
        user = self.request.user
        self.greeting = (
            f"Hi, {user.get_username()}!"
            if user.is_authenticated
            else "Hello, guest. Log in at /admin/."
        )


@page(route="/", title="Home", on_load=HomeState.on_load)
def index() -> rx.Component:
    return rx.vstack(
        rx.heading("My Shop"),
        rx.text(HomeState.greeting),
    )
```

Run:

```bash
reflex django migrate
reflex run
```

Open **http://localhost:3000/** for the Reflex UI. Admin at **http://localhost:8000/admin/** (or via `:3000` when Vite proxies are active).

---

## Dev proxy: `RX_PROXY_SERVER` (optional)

**Default — leave unset.** `reflex run` mounts Django inside the Reflex backend on `:8000`. Vite on `:3000` proxies admin, API, `/_event`, and the SPA to that single backend. One command, shared cookies on the browser origin.

**Split Django — set when Django runs separately.** If you prefer `python manage.py runserver` in its own terminal (or Django on another host), point reflex-django at it:

```python
# config/settings.py
RX_PROXY_SERVER = "http://127.0.0.1:8000"
```

Then:

```bash
# Terminal 1
python manage.py runserver

# Terminal 2
reflex run
```

Vite still serves the SPA on `:3000`, but `/admin` and `/api` proxy to your Django server; `/_event` and other Reflex paths stay on the Reflex backend. reflex-django skips in-process Django dispatch when `RX_PROXY_SERVER` is set.

| | Default (unset) | `RX_PROXY_SERVER` set |
|:---|:---|:---|
| Django | Mounted in Reflex backend | Separate `runserver` (or other HTTP server) |
| Dev commands | `reflex run` only | `runserver` + `reflex run` |
| Typical use | Most projects | Django-only debugging, familiar two-process dev |

This is a **dev-only** setting. Production uses your reverse proxy and plain Django ASGI — not `RX_PROXY_SERVER`.

More: [Local development](https://web7ai.github.io/reflex-django/getting-started/local_development/) · [Routing](https://web7ai.github.io/reflex-django/internals/routing/)

---

## Existing projects

Add Django (`manage.py`, `settings.py`, `urls.py`), put `ReflexDjangoPlugin` in `rxconfig.py`, and use `reflex run`.

Guide: **[Plugin integration](https://web7ai.github.io/reflex-django/getting-started/existing_reflex_project_plugin/)**

v3 → v4 migration: **[v4 plugin-only](https://web7ai.github.io/reflex-django/reference/migration/v4_plugin_only/)**

---

## Read the docs

Start here on the docs site:

1. **[Getting started](https://web7ai.github.io/reflex-django/getting-started/)** — install, quickstart, project layout
2. **[Your first app](https://web7ai.github.io/reflex-django/getting-started/quickstart/)** — todo tutorial
3. **[Troubleshooting](https://web7ai.github.io/reflex-django/operations/troubleshooting/)** — ports, proxies, CSRF

More essentials:

- [How it fits](https://web7ai.github.io/reflex-django/overview/concepts/) — settings, app, URLs
- [Local development](https://web7ai.github.io/reflex-django/getting-started/local_development/) — `:3000` vs `:8000`
- [Plugin integration](https://web7ai.github.io/reflex-django/getting-started/existing_reflex_project_plugin/)
- [v4 migration](https://web7ai.github.io/reflex-django/reference/migration/v4_plugin_only/)

Full site: **https://web7ai.github.io/reflex-django/**

---

## Versions

| | Version |
|:---|:---|
| reflex-django | 4.0+ |
| Python | 3.12+ |
| Django | 6.0+ |
| Reflex | 0.9.4+ |

Upgrading from 3.x? See the [v4 migration guide](https://web7ai.github.io/reflex-django/reference/migration/v4_plugin_only/).

---

## Common commands

```bash
reflex run
reflex export
reflex django migrate
reflex django createsuperuser
```

---

**Author:** Mohannad Irshedat · [GitHub](https://github.com/web7ai/reflex-django) · [Docs](https://web7ai.github.io/reflex-django/)
