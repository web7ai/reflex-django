# Install

Install three packages, add one app to `INSTALLED_APPS`, and add one line to `urls.py`. That's the whole setup.

If you'd like to understand what these pieces do before installing, read [Why reflex-django exists](why_reflex_django.md) first. Otherwise, dive in.

---

## What you need

| | Version |
|:---|:---|
| **Python** | 3.12 or newer |
| **Django** | 6.0 or newer |
| **Reflex** | 0.9.2 or newer |

If you don't have a Django project yet, the [Your first app](quickstart.md) tutorial walks you through creating one from scratch.

---

## 1. Install the packages

We recommend [`uv`](https://github.com/astral-sh/uv), but `pip` works fine too.

=== "uv (recommended)"

    ```bash
    uv add django reflex reflex-django
    ```

=== "pip"

    ```bash
    pip install django reflex reflex-django
    ```

That installs Django, Reflex, and `reflex-django` itself. Nothing else to install.

---

## 2. Register `reflex_django` in `settings.py`

Add `"reflex_django"` to `INSTALLED_APPS`, and add one line to `MIDDLEWARE` at the bottom:

```python
# config/settings.py

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "reflex_django",        # <- add this
    "myapp",                # <- your app
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "reflex_django.streaming_middleware.AsyncStreamingMiddleware",   # <- add this (last)
]

ROOT_URLCONF = "config.urls"
```

The `AsyncStreamingMiddleware` line keeps Django's admin streaming responses happy under ASGI. It does nothing on plain HTTP servers, so it's safe to leave on. ([Why it exists](async_streaming_middleware.md).)

---

## 3. Wire `reflex_mount()` into `urls.py`

```python
# config/urls.py
from django.contrib import admin
from django.urls import path
from reflex_django.urls import reflex_mount

urlpatterns = [path("admin/", admin.site.urls)]

urlpatterns += [
    reflex_mount(
        app_name="myapp",
        django_prefix=("/admin",),
        rx_config={"backend_port": 8000},
    ),
]
```

The two rules that matter:

- **Django routes first**, `reflex_mount()` last.
- **`django_prefix`** lists the paths Django owns. Every prefix here must have a matching `path(...)` line above it.

For the full set of options, see [Configuration](configuration.md).

---

## 4. Point your ASGI entry at `reflex_django`

```python
# config/asgi.py
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
from reflex_django.asgi_entry import application  # noqa: E402,F401
```

That's the single ASGI callable both `manage.py run_reflex` and your production server (uvicorn, granian, hypercorn, …) will use. It composes Django and Reflex on one port.

---

## 5. Run

```bash
python manage.py migrate
python manage.py run_reflex
```

Open `http://localhost:3000/` — the Vite dev server with hot reload. The first run takes a moment because it compiles the Reflex SPA, but subsequent runs are quick. (The Django backend, including `/admin/`, runs on port `8000` behind it and is reachable from the same URL.)

---

## Production note

> [!WARNING]
> In production, **always** set `DJANGO_SETTINGS_MODULE` to your real settings module. Don't rely on `reflex_django.default_settings` — that's a development convenience with an insecure `SECRET_KEY`.

Other production essentials (real `SECRET_KEY`, `DEBUG = False`, restricted `ALLOWED_HOSTS`, static files, reverse proxy) live in the [Deployment](deployment.md) guide.

---

## Common bumps

**`AppRegistryNotReady` at import time**
You're probably importing a Django model at the top of `views.py`. Move the import inside your event handler. (Django needs `django.setup()` to finish before model classes can be touched.)

**Settings are getting ignored**
`DJANGO_SETTINGS_MODULE` from your shell environment always wins. If you're confused, run `python -c "import os; print(os.environ.get('DJANGO_SETTINGS_MODULE'))"` and see what's actually set.

**`ModuleNotFoundError: shop.shop`**
You don't need `shop/shop.py`. `reflex_mount(app_name="shop")` loads pages from `shop/views.py` via `reflex_django.django_led_app`. If something is asking for `shop.shop`, you probably have a leftover `rxconfig.py` from a previous Reflex setup — delete it.

---

**Next:** [Your first app →](quickstart.md)
