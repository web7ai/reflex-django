# Add reflex-django to an existing Reflex project

You already have a working Reflex app -- pages, state classes, maybe a custom theme -- and you want Django in the mix: the ORM, migrations, admin, sessions, and your existing middleware stack.

This guide walks you through wrapping your Reflex project in Django **without throwing away your UI code**. Most of your components and event handlers stay as they are. You mainly change *where config lives*, *how the app boots*, and (optionally) swap `rx.State` for `AppState` when you need `request.user`.

Not sure which guide? See [Integration guides](integration_guides.md).

Looking for the other direction? See [Add to an existing Django project](existing_django_project.md).

---

## Pick your starting point

| You have... | You want... | This guide |
|:---|:---|:---|
| A plain Reflex repo (`rxconfig.py`, `reflex run`) | Django ORM + admin + auth on the same origin | **You are in the right place** |
| No Django at all yet | A full Django project around your Reflex UI | Start with [Step 1](#1-add-django-around-your-reflex-app) below |
| Already tried `ReflexDjangoPlugin` in `rxconfig.py` | The current `django_outer` layout | Follow this guide -- plugin-in-rxconfig was the old bootstrap |

---

## What changes, what stays

| You keep | You change |
|:---|:---|
| Page components | Config: `rxconfig.py` -> `settings.py` |
| Most `@rx.event` handler logic | Dev: `reflex run` -> `python manage.py run_reflex` |
| `.web/` build output | App entry: `app = rx.App()` -> `from reflex_django import app` |
| Custom Reflex plugins | Move plugins to `REFLEX_DJANGO_PLUGINS` |
| Your `pages/` package | Optional: `rx.State` -> `AppState` for Django context |

You **add** a Django project shell (`manage.py`, `config/`, `INSTALLED_APPS`, `urls.py`) around what you already have.

---

## Before and after

**Before:** `rxconfig.py`, `myshop/myshop.py` with `app.add_page(...)`, `reflex run`.

**After:** `config/settings.py` with `REFLEX_DJANGO_RX_CONFIG`, pages in `myshop/views.py`, `python manage.py run_reflex`.

---

## 1. Add Django around your Reflex app

``bash
uv add django reflex-django
uv run django-admin startproject config .
uv run python manage.py startapp myshop
``

In `config/settings.py`: add `reflex_django` and your app to `INSTALLED_APPS`, append `AsyncStreamingMiddleware` last in `MIDDLEWARE`, and set:

``python
REFLEX_DJANGO_RX_CONFIG = {
    "app_name": "myshop",
    "frontend_port": 3000,
    "backend_port": 8000,
}
``

Copy values from your old `rxconfig.py`. See [Configuration](configuration.md).

---

## 2. Move config off rxconfig.py

``python
REFLEX_DJANGO_RX_CONFIG = {"app_name": "myshop", "backend_port": 8000, "frontend_port": 3000}
REFLEX_DJANGO_PLUGINS = ["reflex.plugins.RadixThemesPlugin"]
``

Delete `rxconfig.py`, or set `REFLEX_DJANGO_USE_RXCONFIG_FILE = True` if CI still needs it.

---

## 3. Replace your app entry module

**Option A -- `@page` in `views.py` (recommended):**

``python
import reflex as rx
from reflex_django.pages.decorators import page

@page(route="/", title="Home")
def home() -> rx.Component:
    return rx.heading("Home")
``

**Option B -- keep `app.add_page()`:**

``python
from reflex_django import app
from myshop.pages.home import home
app.add_page(home, route="/", title="Home")
``

Wire imports in `config/urls.py`:

``python
import myshop.views  # noqa: F401
urlpatterns = [path("admin/", admin.site.urls)]
``

For a `pages/` package: `REFLEX_DJANGO_PAGE_PACKAGES` or import submodules from `views.py`.

---

## 4. Point ASGI at reflex-django

``python
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
from reflex_django.asgi_entry import application  # noqa: E402,F401
``

---

## 5. Upgrade state when you need Django

Use `AppState` instead of `rx.State` when you need `self.request.user`, sessions, or the ORM. See [AppState](state_management.md).

---

## 6. Run

``bash
python manage.py migrate
python manage.py run_reflex
``

| URL | What you get |
|:---|:---|
| `http://localhost:3000/` | Reflex UI (HMR) |
| `http://localhost:8000/admin/` | Django admin |

---

## Routing mode

Default: **`django_outer`**. Optional: **`reflex_outer`**. See [comparison](routing.md#choosing-a-mode-django_outer-vs-reflex_outer).

---

## Side-by-side cheat sheet

| Task | Plain Reflex | reflex-django |
|:---|:---|:---|
| Config | `rxconfig.py` | `REFLEX_DJANGO_RX_CONFIG` |
| App | `app = rx.App()` | `from reflex_django import app` |
| Dev | `reflex run` | `python manage.py run_reflex` |
| User | N/A | `self.request.user` on `AppState` |

---

## Common bumps

- **`ModuleNotFoundError: myshop.myshop`** -- delete stale `rxconfig.py`
- **Pages missing** -- `import myshop.views` in `urls.py`
- **`AppRegistryNotReady`** -- import models inside handlers
- **Plugins missing** -- `REFLEX_DJANGO_PLUGINS` in settings

---

## Production

``bash
python manage.py export_reflex --frontend-only --no-zip --stage-to-static-root
python manage.py collectstatic --noinput
uvicorn config.asgi:application --host 0.0.0.0 --port 8000
``

See [Deployment](deployment.md).

---

## What's next

- [AppState](state_management.md) | [Pages in views.py](pages_in_views.md) | [Database](database_integration.md)
- [Existing Django project](existing_django_project.md) | [Configuration](configuration.md)

---

**Next:** [Add to an existing Django project](existing_django_project.md)
