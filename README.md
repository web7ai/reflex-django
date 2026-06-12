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

`reflex-django` runs Django and [Reflex](https://reflex.dev) together. Reflex config lives in `settings.py`. Pages live in `views.py`. The SPA catch-all mounts automatically. The session from `/admin/login/` is the same session your Reflex handlers see.

- **One command** — `python manage.py run_reflex`
- **Same cookies** — `self.request.user` inside every `@rx.event`
- **Same middleware** — your full `settings.MIDDLEWARE` chain on events
- **Two dev ports** — Vite on `:3000`, backend on `:8000` (proxies wire admin/API for you)

---

## Minimal setup

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

REFLEX_DJANGO_RX_CONFIG = {
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

## Read the docs

Start here on the docs site:

1. **[Learning path](https://web7ai.github.io/reflex-django/learning_path/)** — pick your route from zero to shipping
2. **[Your first app](https://web7ai.github.io/reflex-django/quickstart/)** — 15-minute todo tutorial
3. **[Troubleshooting](https://web7ai.github.io/reflex-django/troubleshooting/)** — when ports, proxies, or CSRF fight back

More essentials:

- [The three knobs](https://web7ai.github.io/reflex-django/mental_model/) — settings, app, URLs
- [Local development](https://web7ai.github.io/reflex-django/local_development/) — `:3000` vs `:8000` vs `:8001`
- [Add to an existing Django project](https://web7ai.github.io/reflex-django/existing_django_project/)

Full site: **https://web7ai.github.io/reflex-django/**

---

## Versions

| | Version |
|:---|:---|
| Python | 3.12+ |
| Django | 6.0+ |
| Reflex | 0.9.4+ |

---

## Common commands

```bash
python manage.py run_reflex
python manage.py run_reflex --env dev      # single-port compile dev
python manage.py export_reflex             # build SPA for deploy
python manage.py migrate
python manage.py createsuperuser
```

---

**Author:** Mohannad Irshedat · [GitHub](https://github.com/web7ai/reflex-django) · [Docs](https://web7ai.github.io/reflex-django/)
