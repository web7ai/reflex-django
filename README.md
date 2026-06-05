# reflex-django

**Keep Django. Get a reactive UI in Python. Same process, same port, same cookies.**

[![PyPI](https://img.shields.io/pypi/v/reflex-django?color=%23e91e63&label=pypi)](https://pypi.org/project/reflex-django)
[![Python](https://img.shields.io/pypi/pyversions/reflex-django.svg?color=%23ad1457)](https://pypi.org/project/reflex-django)
[![Docs](https://img.shields.io/badge/docs-online-%23ec407a)](https://web7ai.github.io/reflex-django/)
[![License](https://img.shields.io/github/license/web7ai/reflex-django.svg?color=%23f06292)](https://github.com/web7ai/reflex-django/blob/main/LICENSE)

[Documentation](https://web7ai.github.io/reflex-django/) · [GitHub](https://github.com/web7ai/reflex-django) · [PyPI](https://pypi.org/project/reflex-django)

---

## What is it?

You love Django — the ORM, the admin, migrations, the way it just *works*. You also want a modern, reactive UI written in Python, not React.

`reflex-django` runs Django and [Reflex](https://reflex.dev) as **one ASGI app on one port**. Reflex config lives in `settings.py`. Pages live in `views.py`. The SPA catch-all is automatic. The Django session you got from `/admin/login/` is the same session your Reflex button handlers see.

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

REFLEX_DJANGO_RX_CONFIG = {
    "app_name": "shop",
    "frontend_port": 3000,
    "backend_port": 8000,
}
```

`config/urls.py`:

```python
import shop.views  # noqa: F401 — register @page decorators at import time

from django.contrib import admin
from django.urls import path

urlpatterns = [path("admin/", admin.site.urls)]
# catch-all: automatic (REFLEX_DJANGO_AUTO_MOUNT=True)
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

Open <http://localhost:8000/>. Admin at <http://localhost:8000/admin/>.

That's it.

---

## Why it exists

Reflex sends UI events over a **WebSocket** on `/_event`. Django middleware doesn't run on WebSockets. So `request.user`, sessions, messages, and CSRF aren't available inside `@rx.event` handlers by default — and the SPA usually wants its own port, which breaks cookie sharing.

`reflex-django` builds a synthetic `HttpRequest` for every event, runs your full `settings.MIDDLEWARE` chain on it, and binds `self.request`, `self.user`, `self.session`, `self.messages`, `self.csrf_token` onto your `AppState` handler. One process. One port. Same auth as your admin.

Full explanation: [Why reflex-django exists](https://web7ai.github.io/reflex-django/why_reflex_django/).

---

## Three knobs

| Knob | Where | What you configure |
|:---|:---|:---|
| **Settings** | `settings.py` | `INSTALLED_APPS`, `MIDDLEWARE`, `REFLEX_DJANGO_RX_CONFIG` (`app_name`, ports, `redis_url`, …) |
| **App** | `{app}/views.py` | `@page` pages and `AppState` subclasses (`from reflex_django import app` for `add_page`) |
| **URLs** | `urls.py` | Django routes + `import shop.views` to register pages; catch-all is automatic |

No `rxconfig.py`. No `{app}/{app}.py`. No required `reflex_mount()` line. Call `reflex_mount()` only for URL overrides (`mount_prefix`, explicit `django_prefix`).

Full map: [The three knobs](https://web7ai.github.io/reflex-django/mental_model/).

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

- **[The three knobs (start here)](https://web7ai.github.io/reflex-django/mental_model/)** — settings, app, URLs; page registration vs catch-all
- **[Why reflex-django exists](https://web7ai.github.io/reflex-django/why_reflex_django/)** — the one-page story
- **[How Django works in 5 minutes](https://web7ai.github.io/reflex-django/how_django_works/)**
- **[How Reflex works in 5 minutes](https://web7ai.github.io/reflex-django/how_reflex_works/)**
- **[How the two fit together](https://web7ai.github.io/reflex-django/how_they_fit/)**
- **[Your first app — a 15-minute todo list](https://web7ai.github.io/reflex-django/quickstart/)**
- **[Local development (Vite, admin CSRF, frontend patches)](https://web7ai.github.io/reflex-django/local_development/)**
- **[Add to an existing Django project](https://web7ai.github.io/reflex-django/existing_django_project/)**

Site: <https://web7ai.github.io/reflex-django/>

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

**Author:** Mohannad Irshedat · [GitHub](https://github.com/web7ai/reflex-django) · [Docs](https://web7ai.github.io/reflex-django/)
