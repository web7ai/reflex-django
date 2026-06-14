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
| **A Django project** | [Existing Django project](https://web7ai.github.io/reflex-django/getting-started/existing_django_project/) | `python manage.py run_reflex` |
| **A Reflex project** (move config to settings) | [Existing Reflex project](https://web7ai.github.io/reflex-django/getting-started/existing_reflex_project/) | `python manage.py run_reflex` |
| **A Reflex project** (keep `rxconfig.py`) | [Reflex plugin path](https://web7ai.github.io/reflex-django/getting-started/existing_reflex_project_plugin/) | `reflex run` |

**Django-first** (default): config in `settings.py` (`RX_CONFIG`), pages in `views.py`, `from reflex_django import app`.

**Reflex-first** (plugin): add `ReflexDjangoPlugin(config={...})` to `rxconfig.py`, keep `app = rx.App()`, use `reflex run` / `reflex export`.

Both paths need a Django shell (`manage.py`, `settings.py`, `urls.py`) for ORM, admin, and migrations.

---

## Minimal setup (new Django project)

```bash
uv add django reflex reflex-django
```

`config/settings.py`:

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

RX_CONFIG = {
    "app_name": "shop",
    "frontend_port": 3000,
    "backend_port": 8000,
}
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
python manage.py migrate
python manage.py run_reflex
```

Open **http://localhost:3000/** for the Reflex UI. Admin at **http://localhost:8000/admin/** (or via `:3000` when Vite proxies are active).

---

## Existing Django project

You keep models, admin, DRF, and webhooks. You add:

1. `reflex-django` to `INSTALLED_APPS` and `RX_CONFIG` in `settings.py`
2. `@page` functions in `{app}/views.py` (import the module in `urls.py`)
3. `python manage.py run_reflex` for local dev

Full walkthrough: **[Add to an existing Django project](https://web7ai.github.io/reflex-django/getting-started/existing_django_project/)**

---

## Existing Reflex project

You keep page components and most event handlers. You wrap the app in a Django shell for ORM, admin, and sessions.

**Option A — settings path** (recommended for long-term Django-first layout):

- Move `rxconfig.py` fields → `RX_CONFIG` in `settings.py`
- Replace `app = rx.App()` with `from reflex_django import app` (or keep pages in `views.py` with `@page`)
- Dev: `python manage.py run_reflex`

Guide: **[Add to an existing Reflex project](https://web7ai.github.io/reflex-django/getting-started/existing_reflex_project/)**

**Option B — plugin path** (minimal change, keep Reflex CLI):

```python
# rxconfig.py
from reflex_django.plugins import ReflexDjangoPlugin

config = rx.Config(
    app_name="myshop",
    plugins=[
        ReflexDjangoPlugin(config={
            "settings_module": "config.settings",
            "django_prefix": ("/admin", "/api"),
        }),
    ],
)
```

Keep `app = rx.App()` in `{app}/{app}.py`. Dev: `reflex run`, `reflex export`, `reflex deploy`.

Guide: **[Plugin path for existing Reflex](https://web7ai.github.io/reflex-django/getting-started/existing_reflex_project_plugin/)**

---

## Read the docs

Start here on the docs site:

1. **[Getting started](https://web7ai.github.io/reflex-django/getting-started/)** — install, quickstart, project layout
2. **[Your first app](https://web7ai.github.io/reflex-django/getting-started/quickstart/)** — todo tutorial
3. **[Troubleshooting](https://web7ai.github.io/reflex-django/operations/troubleshooting/)** — ports, proxies, CSRF

More essentials:

- [How it fits](https://web7ai.github.io/reflex-django/overview/concepts/) — settings, app, URLs
- [Local development](https://web7ai.github.io/reflex-django/getting-started/local_development/) — `:3000` vs `:8000`
- [Add to an existing Django project](https://web7ai.github.io/reflex-django/getting-started/existing_django_project/)
- [Add to an existing Reflex project](https://web7ai.github.io/reflex-django/getting-started/existing_reflex_project/)
- [Reflex plugin path](https://web7ai.github.io/reflex-django/getting-started/existing_reflex_project_plugin/) — keep `rxconfig.py` and `reflex run`

Full site: **https://web7ai.github.io/reflex-django/**

---

## Versions

| | Version |
|:---|:---|
| reflex-django | 3.0+ |
| Python | 3.12+ |
| Django | 6.0+ |
| Reflex | 0.9.4+ |

Upgrading from 2.x? See the [v3 migration guide](https://web7ai.github.io/reflex-django/reference/migration/v3_cleanup/).

---

## Common commands

```bash
# Django-first (default)
python manage.py run_reflex
python manage.py run_reflex --env dev      # single-port compile dev
python manage.py export_reflex             # build SPA for deploy

# Reflex-first (with ReflexDjangoPlugin in rxconfig.py)
reflex run
reflex export

# Django (both paths)
python manage.py migrate
python manage.py createsuperuser
```

---

**Author:** Mohannad Irshedat · [GitHub](https://github.com/web7ai/reflex-django) · [Docs](https://web7ai.github.io/reflex-django/)
