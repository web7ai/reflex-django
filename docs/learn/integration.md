# Integration

Get reflex-django running in a Django project. When you finish this page you can open **http://localhost:3000/** and see your Reflex app.

## Install

```bash
uv add django reflex reflex-django
```

Requirements: Python 3.12+, Django 6.0+, Reflex 0.9.4+.

## Project layout

```text
myshop/
├── manage.py
├── rxconfig.py
├── config/
│   ├── settings.py
│   ├── urls.py
│   └── asgi.py
└── shop/
    ├── shop.py          # app = rx.App() + app.add_page(...)
    ├── views.py         # components and state (optional)
    └── models.py
```

`app_name` in `rx.Config` must match `shop/shop.py` when your app is named `shop`.

## rxconfig.py

```python
--8<-- "snippets/profile_rxconfig.py"
```

The default `integrated` profile turns on embed, mount, proxy, and bridge. See [Profiles](profiles.md) for all presets and override patterns. You will learn each pillar in the next pages. If you later disable bridge or resolve an event to tier `none`, Django request context is not bound for that event.

## Public imports

The package root lazily resolves Django-heavy imports so `import reflex_django` is safe during Django app loading. Common public imports:

```python
from reflex_django import configure_django, create_app, register_admin
from reflex_django.plugins import ReflexDjangoPlugin
from reflex_django.states import AppState, ModelState
```

Most apps only need `ReflexDjangoPlugin` in `rxconfig.py` and `AppState`/`ModelState` in page modules. `configure_django()`, `create_app()`, and `build_django_asgi()` are advanced helpers for scripts, tests, app factories, and split ASGI deployment.

## settings.py

```python
--8<-- "snippets/minimal_settings.py"
```

Add the usual Django dev defaults (`SECRET_KEY`, `DEBUG`, `DATABASES`, etc.). Put `AsyncStreamingMiddleware` last in `MIDDLEWARE`.

## urls.py and asgi.py

```python
--8<-- "snippets/minimal_urls.py"
```

```python
--8<-- "snippets/minimal_asgi.py"
```

`urls.py` is for Django routes only. SPA routes come from `app.add_page` in `shop/shop.py` (or optional `@page` in `shop/views.py`). See [Pages and state](../advanced/pages-and-state.md).

## App module

Create `shop/views.py` with state and UI:

```python
--8<-- "snippets/minimal_home_views.py"
```

Register the page in `shop/shop.py`:

```python
--8<-- "snippets/minimal_app_entry.py"
```

See the [Tutorial](quickstart.md) for a full app with `AppState` and the ORM. For serializers and declarative CRUD, see [Serializers](../advanced/serializers.md) and [Model state](../advanced/model-state.md).

## Run

--8<-- "snippets/reflex_run_command.md"

## Starting from an existing project

**Django project:** Add `rxconfig.py`, `shop/shop.py`, register `reflex_django` in settings, keep your models and admin.

**Reflex project:** Run `django-admin startproject config .`, register the plugin in your existing `rxconfig.py`, add settings and urls as above.

## Common bumps

| Symptom | Fix |
|:---|:---|
| `ModuleNotFoundError: shop.shop` | Create `shop/shop.py` with `app = rx.App()` |
| `AppRegistryNotReady` | Import models inside handlers, not at module top |
| Blank page on first run | Wait for compile to finish, then refresh |

More fixes: [Troubleshooting](../advanced/troubleshooting.md).

**Next:** [Profiles](profiles.md)
