# Quickstart

This tutorial builds a **Django-first** Reflex app from scratch: Django owns settings and URLs; pages live in `myapp/views.py`; you run **`python manage.py run_reflex`**.

Estimated time: ~15 minutes.

---

## Prerequisites

- Python **3.12+**
- **[uv](https://docs.astral.sh/uv/)** (recommended) or pip

---

## Step 1: Create the Django project

```bash
mkdir myshop && cd myshop
uv init
uv add django reflex reflex-django
uv run django-admin startproject config .
uv run python manage.py startapp shop
```

Layout:

```text
myshop/
├── manage.py
├── config/
│   ├── settings.py
│   └── urls.py
└── shop/
    ├── models.py
    └── views.py      # Reflex pages go here
```

---

## Step 2: Configure Django

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

ROOT_URLCONF = "config.urls"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
```

`config/urls.py`:

```python
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

`reflex_mount()` does three things:

1. Registers Reflex config (ports, `app_name`, plugins)
2. Enables `ReflexDjangoPlugin` automatically
3. Appends a catch-all URL pattern so the SPA is served for non-Django paths

---

## Step 3: Add Reflex pages in `shop/views.py`

```python
# shop/views.py
import reflex as rx
from reflex_django import template
from reflex_django.state import AppState


class HomeState(AppState):
    greeting: str = "Hello!"

    @rx.event
    async def on_load(self):
        user = self.request.user
        if user.is_authenticated:
            self.greeting = f"Welcome, {user.get_username()}!"
        else:
            self.greeting = "Hello, guest — try /admin/ to log in."


@template(route="/", title="Home")
def index() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.heading("My Shop"),
            rx.text(HomeState.greeting),
            spacing="4",
        ),
        min_height="80vh",
    )


@template(route="/about", title="About")
def about() -> rx.Component:
    return rx.text("About page — defined in shop/views.py")
```

No `shop/shop.py` file. reflex-django discovers `shop.views` via `INSTALLED_APPS` and loads the app through `reflex_django.django_led_app`.

---

## Step 4: Migrate and run

```bash
uv run python manage.py migrate
uv run python manage.py run_reflex
```

Open:

- **http://localhost:3000/** — Reflex dev UI (home, about)
- **http://localhost:3000/admin/** — Django admin (proxied through the dev stack)

> **Do not** use `runserver` on port 8000 while `run_reflex` is active. The unified process must own the backend port so WebSockets (`/_event`) work.

---

## Step 5: Create a superuser and test auth

```bash
uv run python manage.py createsuperuser
```

1. Visit **http://localhost:3000/admin/** and log in.
2. Return to **http://localhost:3000/** and refresh — the home page should show your username.

The event bridge reads the same session cookie Django set at login.

---

## What about `rxconfig.py`?

You do **not** need to create `rxconfig.py` by hand. On first `run_reflex`, reflex-django may write a **minimal stub** so the Reflex CLI’s file checks pass. Live settings still come from `reflex_mount()`. The stub looks like:

```python
import reflex as rx

config = rx.Config(
    app_name='shop',
    app_module_import='reflex_django.django_led_app',
)
```

Treat it as documentation on disk, not the source of truth.

---

## Common commands

| Task | Command |
|:---|:---|
| Dev server | `python manage.py run_reflex` |
| Migrations | `python manage.py migrate` |
| Superuser | `python manage.py createsuperuser` |
| Shell | `python manage.py shell` |

You can also use `uv run reflex django migrate` when the Reflex CLI is on your PATH; `manage.py` is the usual Django-first entry point.

---

## Troubleshooting

**Template picker / “Initializing …” on first run**

reflex-django prepares `.web` and a stub `rxconfig.py` without running `reflex init`. If you still see prompts, ensure `reflex_django` is in `INSTALLED_APPS` and `reflex_mount()` is in `urls.py`, then restart `run_reflex`.

**Guest user after admin login**

Confirm `AuthenticationMiddleware` and `SessionMiddleware` are enabled. The event bridge is on by default via `ReflexDjangoPlugin`.

**`ModuleNotFoundError: shop.shop`**

Do not create `shop/shop.py`. Set `app_name="shop"` on `reflex_mount()` and use `reflex_django.django_led_app` (handled automatically).

---

**Navigation:** [← Configuration](configuration.md) | [Next: Existing Django Project →](existing_django_project.md)
