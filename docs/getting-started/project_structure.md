---
level: beginner
tags: [structure, onboarding]
---

# Project structure

**What you will learn:** Where files live in a typical reflex-django v4 project.

---

## Recommended layout

```text
myproject/
├── manage.py
├── rxconfig.py                   # rx.Config + ReflexDjangoPlugin
├── pyproject.toml
│
├── config/
│   ├── settings.py               # Django only + optional RX_* tuning
│   ├── urls.py
│   └── asgi.py
│
├── shop/
│   ├── shop.py                   # app = rx.App()
│   ├── models.py
│   ├── admin.py
│   ├── views.py                  # optional @page functions
│   └── migrations/
│
└── .web/                         # generated (gitignore)
```

---

## What goes where

| Location | What lives there |
|:---|:---|
| `rxconfig.py` | `rx.Config`, `ReflexDjangoPlugin`, Reflex plugins, ports |
| `config/settings.py` | Django apps, middleware, database, optional `RX_*` |
| `config/urls.py` | Django routes; import page modules for `@page` |
| `{app}/{app}.py` | `app = rx.App()` and optional `app.add_page(...)` |
| `{app}/views.py` | `@page` pages and `AppState` subclasses |
| `{app}/models.py` | Django ORM (unchanged) |

---

## Minimal wiring

```python
--8<-- "snippets/minimal_rxconfig.py"
```

```python
--8<-- "snippets/minimal_settings.py"
```

```python
--8<-- "snippets/minimal_urls.py"
```

```python
--8<-- "snippets/minimal_asgi.py"
```

---

## Generated paths (gitignore)

```gitignore
.web/
.reflex/
staticfiles/
```

---

## Page registration

Import page modules in `urls.py`:

```python
import shop.views  # noqa: F401
```

At compile time (`reflex run` / `reflex export`), reflex-django imports page packages and syncs `@page` decorators onto your app.

See [App entry and pages](../guides/app_entry_and_pages.md).

---

## `app_name`

Set `app_name` in `rx.Config`. It must match `{app_name}/{app_name}.py` and groups `DECORATED_PAGES` at compile time.

---

**Next up:** [Configuration](configuration.md)
