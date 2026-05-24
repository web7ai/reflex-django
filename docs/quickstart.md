# Quickstart

A minimal **reflex-django** app in four steps: Django `settings.py`, `urls.py`, Reflex pages in `views.py`, and `AppState` for the logged-in user.

**Time:** ~10 minutes · **Command:** `python manage.py run_reflex`

---

## 1. Create the project

```bash
mkdir myshop && cd myshop
uv init
uv add django reflex reflex-django
uv run django-admin startproject config .
uv run python manage.py startapp shop
```

```text
myshop/
├── manage.py
├── config/
│   ├── settings.py    ← step 2
│   └── urls.py        ← step 3
└── shop/
    └── views.py       ← step 4 (pages + state)
```

---

## 2. `settings.py` — register Django + reflex-django

Only three things matter for a minimal setup:

1. **`reflex_django` and your app** in `INSTALLED_APPS`
2. **Session + auth middleware** (so `AppState` can see the user)
3. **`AsyncStreamingMiddleware` last** (ASGI-safe admin/static streaming)

```python
# config/settings.py
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = "change-me-in-production"
DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

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

ROOT_URLCONF = "config.urls"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
```

Why `AsyncStreamingMiddleware`? See [AsyncStreamingMiddleware](async_streaming_middleware.md).

---

## 3. `urls.py` — wire Reflex with `reflex_mount()`

Django routes come **first**. **`reflex_mount()` last.**

```python
# config/urls.py
from django.contrib import admin
from django.urls import path

from reflex_django.urls import reflex_mount

urlpatterns = [
    path("admin/", admin.site.urls),
]

urlpatterns += [
    reflex_mount(
        app_name="shop",
        django_prefix=("/admin",),
        rx_config={
            "frontend_port": 3000,
            "backend_port": 8000,
        },
    ),
]
```

| Argument | Meaning |
|:---|:---|
| `app_name="shop"` | Pages live in `shop/views.py` |
| `django_prefix` | Paths Django owns (must match `path("admin/", ...)` above) |
| `rx_config` | Reflex ports (and any other allowed `rx.Config` keys) |

You do **not** create `shop/shop.py`. Reflex loads the app from `reflex_django.django_led_app`.

---

## 4. `views.py` — pages and `AppState`

### Pages with `@template`

`@template` registers a route and wraps content in a simple layout:

```python
# shop/views.py
import reflex as rx
from reflex_django import template
from reflex_django.state import AppState


class HomeState(AppState):
    """Use AppState when you need Django session / user."""

    greeting: str = "Hello!"

    @rx.event
    async def on_load(self):
        if self.request.user.is_authenticated:
            self.greeting = f"Hi, {self.request.user.get_username()}!"
        else:
            self.greeting = "Hello, guest — log in at /admin/"


@template(route="/", title="Home")
def index() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.heading("My Shop"),
            rx.text(HomeState.greeting),
            rx.link("About", href="/about"),
            spacing="4",
        ),
        min_height="70vh",
    )


@template(route="/about", title="About")
def about() -> rx.Component:
    return rx.text("This page is shop/views.py — not a Django path().")
```

### How `AppState` works

| In event handlers (`@rx.event`) | In the UI |
|:---|:---|
| `self.request.user` — Django user | `self.is_authenticated` |
| `self.request.session` — read/write session | `self.username`, `self.email` |
| `await self.has_perm("app.change_model")` | Auto-updated each event |

Reflex events run over WebSocket. The **event bridge** (enabled automatically) builds a Django-like `request` on each event so you can use the same session as `/admin/`.

```python
@rx.event
async def save_theme(self, value: str):
    self.request.session["theme"] = value
    await self.request.session.asave()
```

---

## 5. Run

```bash
uv run python manage.py migrate
uv run python manage.py run_reflex
```

| URL | What you see |
|:---|:---|
| http://localhost:3000/ | Home page |
| http://localhost:3000/about | About page |
| http://localhost:3000/admin/ | Django admin |

Optional — test login:

```bash
uv run python manage.py createsuperuser
```

Log in at `/admin/`, then refresh `/` — `HomeState.greeting` should show your username.

---

## Cheat sheet

| File | Responsibility |
|:---|:---|
| `settings.py` | Django apps, middleware, database |
| `urls.py` | `reflex_mount(...)` — Reflex ports + `app_name` |
| `shop/views.py` | `@template` pages + `AppState` classes |
| `manage.py run_reflex` | Dev server (Django + Reflex + WebSockets) |

No hand-written `rxconfig.py` required. A stub may appear on first run; real config comes from `reflex_mount()`.

---

## Troubleshooting

| Problem | Fix |
|:---|:---|
| Template picker on first run | Ensure `reflex_django` in `INSTALLED_APPS` and `reflex_mount()` in `urls.py`; restart `run_reflex` |
| Guest after admin login | Keep `SessionMiddleware` + `AuthenticationMiddleware` |
| `ModuleNotFoundError: shop.shop` | Do not add `shop/shop.py`; use `app_name="shop"` on `reflex_mount()` |
| Admin warnings in console | Add `AsyncStreamingMiddleware` at end of `MIDDLEWARE` |

---

**Navigation:** [← Configuration](configuration.md) | [AsyncStreamingMiddleware →](async_streaming_middleware.md) | [Existing Django Project →](existing_django_project.md)
