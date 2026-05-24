# Installation

Install **reflex-django** into a Django project virtual environment and register it in `INSTALLED_APPS`. Configuration happens in **`urls.py`** via `reflex_mount()`, not in a mandatory `rxconfig.py`.

---

## Requirements

| Component | Version |
|:---|:---|
| **Python** | `>= 3.12, < 4.0` |
| **Django** | `>= 6.0, < 7.0` |
| **Reflex** | `>= 0.9.2, < 1.0` |

---

## Install packages

=== "uv (recommended)"

    ```bash
    uv add django reflex reflex-django
    ```

=== "pip"

    ```bash
    pip install django reflex reflex-django
    ```

---

## Register in Django

```python
# config/settings.py

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "reflex_django",      # required for run_reflex, helpers, discovery
    "myapp",
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
```

---

## Wire `reflex_mount()` in `urls.py`

```python
from django.contrib import admin
from django.urls import path
from reflex_django.urls import reflex_mount

urlpatterns = [path("admin/", admin.site.urls)]

urlpatterns += [
    reflex_mount(
        app_name="myapp",
        django_prefix=("/admin",),
        rx_config={"frontend_port": 3000, "backend_port": 8000},
    ),
]
```

See [Configuration](configuration.md) for all `reflex_mount()` options. For pages and `AppState`, follow the [Quickstart](quickstart.md).

`AsyncStreamingMiddleware` in `MIDDLEWARE` is required for clean ASGI streaming (admin, static). Details: [AsyncStreamingMiddleware](async_streaming_middleware.md).

---

## Verify

```bash
python manage.py migrate
python manage.py run_reflex
```

Or check Django management access:

```bash
python manage.py help
# reflex django help also works when using the Reflex CLI entry point
```

---

## Production

> [!WARNING]
> Always set `DJANGO_SETTINGS_MODULE` in production. Do not rely on `reflex_django.default_settings` (insecure dev fallback).

Use a real `SECRET_KEY`, `DEBUG = False`, and restricted `ALLOWED_HOSTS`. See [Deployment](deployment.md).

---

## Troubleshooting

**`AppRegistryNotReady`**

Import models inside `@rx.event` handlers, not at the top of `views.py`, during early imports.

**Settings ignored**

`DJANGO_SETTINGS_MODULE` from `manage.py` or the environment overrides everything else. Keep deployment env aligned with your project.

---

**Navigation:** [← Introduction](introduction.md) | [Quickstart →](quickstart.md) | [Configuration →](configuration.md)
