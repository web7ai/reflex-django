# Project structure

Recommended layout for a **monorepo** that hosts Django and Reflex together under `reflex run`.

---

## Prerequisites

- [Quickstart](quickstart.md) or [Existing Django project](existing_django_project.md)

---

## Canonical layout

*Example application layout.*

```text
myapp/
├── rxconfig.py              # ReflexDjangoPlugin + app_name
├── manage.py
├── pyproject.toml
├── backend/                   # Django project package
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py / asgi.py      # optional; reflex run uses plugin ASGI
├── catalog/                   # Django apps (models, admin)
│   ├── models.py
│   ├── serializers.py         # ReflexDjangoModelSerializer (your code)
│   └── admin.py
└── myapp/                     # Reflex app module (name = rxconfig app_name)
    ├── myapp.py               # rx.App, add_page
    ├── pages/
    └── states/
        ├── products.py        # manual CRUD example
        └── posts.py           # ModelCRUDView example
```

---

## File responsibilities

| File | Role |
|------|------|
| `rxconfig.py` | Reflex config; plugin bootstraps Django |
| `manage.py` | Django entry; prefer `reflex django` for same settings |
| `backend/settings.py` | `INSTALLED_APPS`, `DATABASES`, `REFLEX_DJANGO_*` |
| `backend/urls.py` | HTTP routes under prefixes (admin, API) |
| `myapp/myapp.py` | `app = rx.App()`, pages, optional `add_auth_pages` |
| `states/*.py` | `AppState`, `ModelCRUDView`, event handlers |
| `catalog/models.py` | Django models (your domain) |

---

## `ROOT_URLCONF` and plugin prefixes

The HTTP dispatcher forwards paths matching:

- `backend_prefix` (e.g. `/api`)  
- `admin_prefix` (default `/admin`)  
- `STATIC_URL` when staticfiles enabled  
- `extra_prefixes`

Your `urlpatterns` must use the **same path segments** the browser requests. Mismatches are the most common 404 cause. See [Routing](routing.md).

---

## Where to put serializers

Place `ReflexDjangoModelSerializer` subclasses next to models or in `serializers.py` inside each Django app. Import them from Reflex state modules. See [Serializers](serializers.md).

---

## Dev vs production static files

| Mode | Static behavior |
|------|-----------------|
| Dev | Vite proxy + Django `ASGIStaticFilesHandler` when `DEBUG` |
| Prod | `reflex django collectstatic` → `STATIC_ROOT`; dispatcher forwards `STATIC_URL` |

---

## Advanced usage

- **Multiple Django apps:** keep domain logic in apps; Reflex states orchestrate UI only.  
- **Multiple Reflex apps:** uncommon; separate `rxconfig` / `app_name` per UI with shared Django settings.

> **Warning:** Running two unrelated Reflex apps against one Django project is out of scope for the bundled plugin defaults.

---

## Common mistakes

- Reflex `app_name` in `rxconfig.py` does not match the Python package directory.  
- Models imported at module level before `rxconfig` loads in tests without `DJANGO_SETTINGS_MODULE`.

---

## See also

- [Architecture](architecture.md)  
- [Configuration](configuration.md)

---

**Navigation:** [← Existing Django project](existing_django_project.md) | [Next: Architecture →](architecture.md)
