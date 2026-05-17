# Project structure

Recommended layout for a **monorepo** that hosts Django and Reflex together under `reflex run`.

---

## Prerequisites

- [Quickstart](quickstart.md) or [Existing Django project](existing_django_project.md)

---

## Canonical layout

*Example application layout for a monorepo Reflex + Django project.*

```text
myapp/                         # project root (CLI name)
├── rxconfig.py                # ReflexDjangoPlugin, RadixThemesPlugin, TailwindV4Plugin
├── manage.py
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── config/                    # Django project package
│   ├── settings.py            # or settings/ package (base, dev, prod)
│   ├── urls.py
│   └── api/urls.py            # starter: routes under /api
├── accounts/                  # starter: UserProfile + avatar
├── todos/                     # starter: Task model
└── myapp/                     # Reflex app (name = rxconfig app_name)
    ├── myapp.py               # rx.App, add_auth_pages, register_pages
    ├── routes.py
    ├── STRUCTURE.md
    ├── layout/                # page_layout, header, footer (starter)
    ├── pages/
    ├── forms/
    ├── components/
    ├── ui/                    # tokens, buttons, callouts, typography
    └── states/
```

---

## Reflex app layers

| Layer | Directory | Role |
|-------|-----------|------|
| Entry | `myapp.py`, `routes.py` | App wiring and route registry |
| Layout | `layout/` | Header, footer, shells |
| Pages | `pages/` | Full screens |
| Forms | `forms/` | `rx.form` assemblies |
| Components | `components/` | Composed widgets |
| UI | `ui/` | Radix primitives (see DESIGN.md) |
| States | `states/` | `AppState`, `ModelCRUDView`, handlers |

Auth routes (`/login`, `/register`, password reset) come from **`reflex_django.auth.add_auth_pages`** — not from `pages/`.

---

## File responsibilities

| File | Role |
|------|------|
| `rxconfig.py` | Reflex config; plugin bootstraps Django |
| `manage.py` | Django entry; prefer `reflex django` for same settings |
| `config/settings.py` or `config/settings/` | `INSTALLED_APPS`, `DATABASES`, `REFLEX_DJANGO_*` |
| `config/urls.py` | HTTP routes under prefixes (admin, API) |
| `myapp/myapp.py` | `app = rx.App()`, `add_auth_pages`, `register_pages` |
| `states/*.py` | `AppState`, `ModelCRUDView`, event handlers |
| `todos/models.py` | Django models (your domain) |

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
- [CLI](cli.md)

---

**Navigation:** [← Existing Django project](existing_django_project.md) | [Next: Architecture →](architecture.md)
