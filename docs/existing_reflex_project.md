---
level: intermediate
tags: [integration, reflex]
---

# Add reflex-django to an existing Reflex project

**What you will learn:** How to wrap a plain Reflex app in Django without throwing away your components and event handlers.

**When you need this:**

- You have `rxconfig.py`, `reflex run`, and pages you want to keep.
- You want Django ORM, migrations, admin, and `request.user` on the same origin.

Most UI code stays as-is. You mainly change where config lives, how the app boots, and (when needed) swap `rx.State` for `AppState`.

**Not sure which guide?** See [Integration guides](integration_guides.md).

**The other direction:** [Add to an existing Django project](existing_django_project.md).

---

## What changes, what stays

| You keep | You change |
|:---|:---|
| Page components | Config: `rxconfig.py` → `settings.py` |
| Most `@rx.event` handler logic | Dev: `reflex run` → `python manage.py run_reflex` |
| `.web/` build output | App entry: `app = rx.App()` → `from reflex_django import app` |
| Custom Reflex plugins | Move plugins to `REFLEX_DJANGO_PLUGINS` |
| Your `pages/` package | Optional: `rx.State` → `AppState` for Django context |

You **add** a Django project shell (`manage.py`, `config/`, `INSTALLED_APPS`, `urls.py`) around what you already have.

---

## Before and after

**Before:** `rxconfig.py`, `myshop/myshop.py` with `app.add_page(...)`, `reflex run`.

**After:** `config/settings.py` with `REFLEX_DJANGO_RX_CONFIG`, pages in `myshop/views.py`, `python manage.py run_reflex`.

---

## 1. Add Django around your Reflex app

```bash
uv add django reflex-django
uv run django-admin startproject config .
uv run python manage.py startapp myshop
```

Register reflex-django and your app:

```python
--8<-- "snippets/minimal_settings.py"
```

Copy port and plugin values from your old `rxconfig.py`. See [Configuration](configuration.md).

---

## 2. Move config off `rxconfig.py`

```python
REFLEX_DJANGO_RX_CONFIG = {
    "app_name": "myshop",
    "backend_port": 8000,
    "frontend_port": 3000,
}
REFLEX_DJANGO_PLUGINS = ["reflex.plugins.RadixThemesPlugin"]
```

Delete `rxconfig.py`, or set `REFLEX_DJANGO_USE_RXCONFIG_FILE = True` only if CI still needs the file temporarily.

!!! warning "Remove stale entry modules"
    Delete `{app}/{app}.py` if it only existed for plain Reflex. v1.0 pages live in `views.py` with `@page`, or you call `app.add_page()` after `from reflex_django import app`.

---

## 3. Replace your app entry

**Option A: `@page` in `views.py` (recommended)**

```python
--8<-- "snippets/minimal_views.py"
```

**Option B: keep `app.add_page()`**

```python
from reflex_django import app
from myshop.pages.home import home

app.add_page(home, route="/", title="Home")
```

Wire imports in `urls.py`:

```python
--8<-- "snippets/minimal_urls.py"
```

For a `pages/` package, set `REFLEX_DJANGO_PAGE_PACKAGES` or import submodules from `views.py`. See [Pages in views.py](pages_in_views.md).

---

## 4. Point ASGI at reflex-django

```python
--8<-- "snippets/minimal_asgi.py"
```

---

## 5. Upgrade state when you need Django

Use `AppState` instead of `rx.State` when you need `self.request.user`, sessions, or the ORM. See [AppState](state_management.md).

---

## 6. Run

--8<-- "snippets/run_reflex_command.md"

| URL | What you get |
|:---|:---|
| `http://localhost:3000/` | Reflex UI (HMR; Vite proxies backend paths) |
| `http://localhost:8000/admin/` | Django admin |

Create a superuser after your first `migrate`:

```bash
python manage.py createsuperuser
```

---

## Optional split-process dev

Set `RXDJANGO_PROXY_SERVER` when Django should run on `runserver` separately from Reflex. See [Migrating to mount-only](migration/v3_mount_only.md).

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

- **`ModuleNotFoundError: myshop.myshop`**: delete stale `rxconfig.py` and `{app}/{app}.py`; set `app_name` in settings.
- **Pages missing**: add `import myshop.views` in `urls.py`.
- **`AppRegistryNotReady`**: import models inside handlers.
- **Plugins missing**: move them to `REFLEX_DJANGO_PLUGINS` in settings.

---

## Production

```bash
python manage.py export_reflex --frontend-only --no-zip --stage-to-static-root
python manage.py collectstatic --noinput
uvicorn config.asgi:application --host 0.0.0.0 --port 8000
```

See [Deployment](deployment.md).

---

## What just happened?

You moved Reflex config into Django settings, deleted the standalone bootstrap path, and pointed ASGI at plain Django. Your pages still compile to the same `.web/` tree; auth, ORM, and admin run through Django with Reflex events on the same session cookies.

---

**Next up:** [Add to an existing Django project](existing_django_project.md)
