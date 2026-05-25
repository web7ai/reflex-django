<p align="center">
  <a href="https://github.com/mohannadirshedat/reflex-django">
    <img src="https://raw.githubusercontent.com/mohannadirshedat/reflex-django/main/logo.png" alt="reflex-django" width="200">
  </a>
</p>

<h1 align="center">reflex-django</h1>

<p align="center">
  <strong>Django + Reflex in one process — configure in urls.py, pages in views.py.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/reflex-django"><img src="https://img.shields.io/pypi/v/reflex-django?color=%2334D058&label=pypi" alt="PyPI"></a>
  <a href="https://pypi.org/project/reflex-django"><img src="https://img.shields.io/pypi/pyversions/reflex-django.svg" alt="Python"></a>
  <a href="https://mohannadirshedat.github.io/reflex-django/"><img src="https://img.shields.io/badge/docs-online-blue" alt="Docs"></a>
  <a href="https://github.com/mohannadirshedat/reflex-django/blob/main/LICENSE"><img src="https://img.shields.io/github/license/mohannadirshedat/reflex-django.svg" alt="License"></a>
</p>

<p align="center">
  <a href="https://mohannadirshedat.github.io/reflex-django/">Documentation</a> ·
  <a href="https://github.com/mohannadirshedat/reflex-django">GitHub</a> ·
  <a href="https://pypi.org/project/reflex-django">PyPI</a>
</p>

---

## What it does

- **Django** — `/admin`, `/api`, ORM, migrations, sessions
- **Reflex** — SPA UI, client routes, WebSocket events
- **One port, one command** — `python manage.py run_reflex` serves everything on `http://localhost:8000/`
- **Full `settings.MIDDLEWARE` chain** runs on every Reflex event
- **`self.request`, `self.response`, `self.messages`, `self.csrf_token`** available inside `AppState`
- **No `myapp/myapp.py`** — pages in `myapp/views.py`, app loaded via `django_led_app`

Reflex settings go in **`reflex_mount()`** in `urls.py`, not in a large `rxconfig.py`. ASGI deployments use `reflex_django.asgi_entry:application` as the ASGI callable.

See [Single-port Django-outer architecture](docs/single_port_django_outer.md) and [Migration guide](docs/migration_django_outer.md).

---

## Minimal setup (copy-paste)

### Install

```bash
uv add django reflex reflex-django
```

### `config/settings.py`

```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "reflex_django",
    "shop",  # your app
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "reflex_django.streaming_middleware.AsyncStreamingMiddleware",  # ASGI streaming
]

ROOT_URLCONF = "config.urls"
```

### `config/urls.py`

```python
from django.contrib import admin
from django.urls import path
from reflex_django.urls import reflex_mount

urlpatterns = [path("admin/", admin.site.urls)]

urlpatterns += [
    reflex_mount(
        app_name="shop",
        django_prefix=("/admin",),
        rx_config={"frontend_port": 3000, "backend_port": 8000},
    ),
]
```

### `shop/views.py` — pages + AppState

```python
import reflex as rx
from reflex_django import template
from reflex_django.state import AppState


class HomeState(AppState):
    message: str = "Hello"

    @rx.event
    async def on_load(self):
        if self.request.user.is_authenticated:
            self.message = f"Hello, {self.request.user.get_username()}"
        else:
            self.message = "Hello, guest"


@template(route="/", title="Home")
def index() -> rx.Component:
    return rx.vstack(
        rx.heading("Home"),
        rx.text(HomeState.message),
    )
```

### Run

```bash
python manage.py migrate
python manage.py run_reflex
```

Open http://localhost:3000/ — admin at http://localhost:3000/admin/

Full walkthrough: [Quickstart](https://mohannadirshedat.github.io/reflex-django/quickstart/)

---

## Three files to remember

| File | You configure |
|:---|:---|
| **settings.py** | `INSTALLED_APPS`, `MIDDLEWARE` (incl. `AsyncStreamingMiddleware`) |
| **urls.py** | `reflex_mount(app_name=..., django_prefix=..., rx_config={...})` |
| **{app}/views.py** | `@template(route=...)` pages and `AppState` subclasses |

---

## AppState in one minute

Subclass `AppState` when a page needs the Django user or session:

```python
from reflex_django.state import AppState

class MyState(AppState):
    @rx.event
    async def on_load(self):
        user = self.request.user          # Django User
        if user.is_authenticated:
            ...
        self.request.session["key"] = "value"
        await self.request.session.asave()
```

The event bridge attaches `self.request` on every WebSocket event (same cookies as `/admin/`).

---

## Why reflex-django?

Reflex uses **WebSockets** for UI events — Django middleware does not run there by default. reflex-django adds an **event bridge** so `self.request.user` and sessions work in `@rx.event` handlers.

| Django | Python |
|:---|:---|
| 6.0.x | 3.12+ |

---

## Documentation

| Topic | Link |
|:---|:---|
| Quickstart (step-by-step) | [quickstart.md](docs/quickstart.md) |
| `reflex_mount()` reference | [configuration.md](docs/configuration.md) |
| `AsyncStreamingMiddleware` | [async_streaming_middleware.md](docs/async_streaming_middleware.md) |
| Pages in `views.py` | [pages_in_views.md](docs/pages_in_views.md) |
| URLs & `django_led_app` | [django_urls.md](docs/django_urls.md) |
| Brownfield Django | [existing_django_project.md](docs/existing_django_project.md) |
| Auth & permissions | [authentication.md](docs/authentication.md) |

**Site:** https://mohannadirshedat.github.io/reflex-django/

---

## Commands

```bash
python manage.py run_reflex      # dev server
python manage.py migrate
python manage.py createsuperuser
```

---

**Author:** Mohannad Irshedat · [GitHub](https://github.com/mohannadirshedat/reflex-django)
