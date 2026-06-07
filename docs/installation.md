# Install

Install three packages, add one app to `INSTALLED_APPS`, import your page module in `urls.py`, and set `app_name` in settings. The SPA catch-all mounts itself at startup.

If you'd like to understand what these pieces do before installing, read [Why reflex-django exists](why_reflex_django.md) first. Otherwise, dive in.

---

## What you need

| | Version |
|:---|:---|
| **Python** | 3.12 or newer |
| **Django** | 6.0 or newer |
| **Reflex** | 0.9.2 or newer |

If you don't have a Django project yet, the [Your first app](quickstart.md) tutorial walks you through creating one from scratch.

**Brownfield?** Pick the guide that matches what you already have:

- [Add to an existing Django project](existing_django_project.md) — you have models, admin, API; you want Reflex pages
- [Add to an existing Reflex project](existing_reflex_project.md) — you have `rxconfig.py` and `reflex run`; you want Django ORM and admin

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

## 3. Wire `urls.py` and `REFLEX_DJANGO_RX_CONFIG`

```python
# config/urls.py
import myapp.views  # noqa: F401

from django.contrib import admin
from django.urls import path

urlpatterns = [path("admin/", admin.site.urls)]
# Catch-all appended automatically when REFLEX_DJANGO_AUTO_MOUNT=True (default).
```

Add `app_name`, ports, and `redis_url` in settings:

```python
REFLEX_DJANGO_RX_CONFIG = {
    "app_name": "myapp",
    "frontend_port": 3000,
    "backend_port": 8000,
}
```

Optional: call `reflex_mount()` in `urls.py` only when you need URL overrides (`mount_prefix`, explicit `django_prefix`). Django prefixes are otherwise inferred from your routes.

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

`run_reflex` starts **both** Vite (`:3000`) and the Django/Reflex backend (`:8000`). Open **`http://localhost:3000/`** for your Reflex UI and hot reload. Use **`http://localhost:8000/admin/`** for the admin directly. The first run takes a moment while the SPA compiles and Vite comes up. Pass `--env dev` if you prefer compile-only dev on `:8000`. Details: [Local development](local_development.md).

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
You don't need `shop/shop.py`. Set `"app_name": "shop"` in `REFLEX_DJANGO_RX_CONFIG` and import `shop.views` in `urls.py` (or use `from reflex_django import app` with `app.add_page()`). If something is asking for `shop.shop`, you probably have a leftover `rxconfig.py` from a previous Reflex setup — delete it.

---

**Next:** [Your first app →](quickstart.md)
