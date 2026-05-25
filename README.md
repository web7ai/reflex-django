<p align="center">
  <a href="https://github.com/mohannadirshedat/reflex-django">
    <img src="https://raw.githubusercontent.com/mohannadirshedat/reflex-django/main/logo.png" alt="reflex-django" width="200">
  </a>
</p>

<h1 align="center">reflex-django</h1>

<p align="center">
  <strong>Keep Django. Get a reactive UI in Python. Same process, same port, same cookies.</strong>
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

## What is it?

You love Django — the ORM, the admin, migrations, the way it just *works*. You also want a modern, reactive UI written in Python, not React.

`reflex-django` runs Django and [Reflex](https://reflex.dev) as **one ASGI app on one port**. Configuration lives in `urls.py`. Pages live in `views.py`. The Django session you got from `/admin/login/` is the same session your Reflex button handlers see.

- **Same port** — Django at `8000`, Reflex at `8000`. No CORS, no token bridge, no second dev server.
- **Same cookies** — log in once at `/admin/`, every Reflex event sees `self.request.user`.
- **Same middleware** — your full `settings.MIDDLEWARE` chain runs on every Reflex event.
- **One command** — `python manage.py run_reflex`.

---

## Minimal setup

Install:

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
    "reflex_django.streaming_middleware.AsyncStreamingMiddleware",
]
```

`config/urls.py`:

```python
from django.contrib import admin
from django.urls import path
from reflex_django.urls import reflex_mount

urlpatterns = [path("admin/", admin.site.urls)]
urlpatterns += [
    reflex_mount(app_name="shop", django_prefix=("/admin",)),
]
```

`config/asgi.py`:

```python
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
from reflex_django.asgi_entry import application  # noqa: E402,F401
```

`shop/views.py`:

```python
import reflex as rx
from reflex_django import template
from reflex_django.state import AppState


class HomeState(AppState):
    @rx.event
    async def on_load(self):
        user = self.request.user
        self.greeting = (
            f"Hi, {user.get_username()}!"
            if user.is_authenticated
            else "Hello, guest. Log in at /admin/."
        )


@template(route="/", title="Home", on_load=HomeState.on_load)
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

Open <http://localhost:8000/>. Admin at <http://localhost:8000/admin/>.

That's it.

---

## Why it exists

Reflex sends UI events over a **WebSocket** on `/_event`. Django middleware doesn't run on WebSockets. So `request.user`, sessions, messages, and CSRF aren't available inside `@rx.event` handlers by default — and the SPA usually wants its own port, which breaks cookie sharing.

`reflex-django` builds a synthetic `HttpRequest` for every event, runs your full `settings.MIDDLEWARE` chain on it, and binds `self.request`, `self.user`, `self.session`, `self.messages`, `self.csrf_token` onto your `AppState` handler. One process. One port. Same auth as your admin.

Full explanation: [Why reflex-django exists](https://mohannadirshedat.github.io/reflex-django/why_reflex_django/).

---

## Three files, three jobs

| File | What you configure |
|:---|:---|
| `settings.py` | `INSTALLED_APPS`, `MIDDLEWARE` (incl. `AsyncStreamingMiddleware`), `REFLEX_DJANGO_*` |
| `urls.py` | `reflex_mount(app_name=..., django_prefix=..., rx_config={...})` |
| `{app}/views.py` | `@template`-decorated pages and `AppState` subclasses |

No `rxconfig.py`. No `{app}/{app}.py`. No separate frontend.

---

## Versions

| | Version |
|:---|:---|
| Python | 3.12+ |
| Django | 6.0+ |
| Reflex | 0.9.2+ |

---

## Documentation

The full docs walk you through the *why*, the *how*, and every knob:

- **[Why reflex-django exists](https://mohannadirshedat.github.io/reflex-django/why_reflex_django/)** — the one-page story
- **[How Django works in 5 minutes](https://mohannadirshedat.github.io/reflex-django/how_django_works/)**
- **[How Reflex works in 5 minutes](https://mohannadirshedat.github.io/reflex-django/how_reflex_works/)**
- **[How the two fit together](https://mohannadirshedat.github.io/reflex-django/how_they_fit/)**
- **[Your first app — a 15-minute todo list](https://mohannadirshedat.github.io/reflex-django/quickstart/)**
- **[Add to an existing Django project](https://mohannadirshedat.github.io/reflex-django/existing_django_project/)**

Site: <https://mohannadirshedat.github.io/reflex-django/>

---

## Common commands

```bash
python manage.py run_reflex            # dev server (auto-rebuild + watch)
python manage.py run_reflex --skip-rebuild   # faster reloads for pure Python edits
python manage.py export_reflex         # build the SPA bundle (for CI / deploy)
python manage.py migrate
python manage.py createsuperuser
```

---

**Author:** Mohannad Irshedat · [GitHub](https://github.com/mohannadirshedat/reflex-django) · [Docs](https://mohannadirshedat.github.io/reflex-django/)
