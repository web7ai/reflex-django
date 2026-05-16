# Existing Django project

Add **Reflex** and **reflex-django** to a codebase that already has `manage.py`, apps, models, and `settings.py`.

> Greenfield setup: [Quickstart](quickstart.md).

---

## Prerequisites

- [Installation](installation.md)  
- [Configuration](configuration.md)

---

## What stays vs what you add

| Keep as-is | Add or adjust |
|------------|----------------|
| `manage.py`, Django apps, models, migrations | `rxconfig.py`, Reflex app module, pages/states |
| `settings.py` (`SECRET_KEY`, `DATABASES`, `AUTH`) | `ReflexDjangoPlugin` in `rxconfig.py` |
| Existing API `urlpatterns` | `backend_prefix` on the plugin |
| Django admin registrations | `admin_prefix` alignment |

---

## Example layout

*Example application layout—not part of the reflex-django package.*

```text
myproject/
├── manage.py
├── myproject/
│   ├── settings.py
│   └── urls.py
├── shop/                    # your existing apps
│   └── models.py
├── rxconfig.py              # NEW
└── frontend/                # NEW — name from reflex init
    └── frontend.py
```

---

## Step-by-step

### 1. Add dependencies

In the same virtual environment as Django:

```bash
uv add reflex reflex-django
```

### 2. Scaffold Reflex only

From the project root (where `manage.py` lives):

```bash
uv run reflex init frontend
```

Do **not** run `django-admin startproject` again.

### 3. Wire `rxconfig.py`

```python
import reflex as rx
from reflex_django import ReflexDjangoPlugin

config = rx.Config(
    app_name="frontend",  # your Reflex module name
    plugins=[
        ReflexDjangoPlugin(settings_module="myproject.settings"),
    ],
)
```

Use your **existing** dotted settings path.

### 4. Optional: `INSTALLED_APPS`

Add `"reflex_django"` if you use `ModelCRUDView`, `register_admin`, or canned auth pages.

### 5. Settings module precedence

`configure_django()` respects `DJANGO_SETTINGS_MODULE` in the environment **before** the plugin argument:

1. Env `DJANGO_SETTINGS_MODULE` (wins)  
2. Plugin `settings_module`  
3. `reflex_django.default_settings`

> **Tip:** In production, set `DJANGO_SETTINGS_MODULE` explicitly and keep it identical for `reflex run` and `reflex django migrate`.

### 6. Align URL prefixes

In `ReflexDjangoPlugin`:

```python
ReflexDjangoPlugin(
    settings_module="myproject.settings",
    backend_prefix="/api",   # if APIs live under /api/
    admin_prefix="/admin",
)
```

Your `ROOT_URLCONF` must mount routes at paths the dispatcher forwards. See [Routing](routing.md).

### 7. Run migrations (unchanged history)

```bash
uv run reflex django migrate
```

The CLI loads `rxconfig` first, then `configure_django()`.

### 8. Use existing models in Reflex states

*Example application code.*

```python
from reflex_django.state import AppState
from shop.models import Product  # your app

class ProductState(AppState):
    ...
```

Import models in state modules after normal Reflex startup (plugin already called `configure_django()`).

### 9. Run

```bash
uv run reflex run
```

### 10. Auth strategy

- **Reflex auth UI:** `add_auth_pages(app)` — [Authentication](authentication.md)  
- **Keep Django login views:** serve them on HTTP under a Django prefix; Reflex pages use `current_user()` when the session cookie is present.

---

## Comparison: greenfield vs brownfield

| | Quickstart | This guide |
|---|------------|------------|
| Django project | Created new | Already exists |
| `reflex init` | Yes | Yes |
| `startproject` | Yes | **No** |
| Migrations | New | Existing + `reflex django migrate` |

---

## Advanced usage

- **Gradual rollout:** new features in Reflex; legacy routes remain Django HTTP/templates under `backend_prefix`.
- **Monorepo:** set `DJANGO_SETTINGS_MODULE` per environment; one `rxconfig.py` per Reflex app if needed.

---

## Common mistakes

- Duplicate `startproject` → conflicting settings packages.  
- Plugin `settings_module` ignored because `.env` sets a different `DJANGO_SETTINGS_MODULE`.  
- API 404: `backend_prefix` does not match `urlpatterns`.  
- Circular imports: import models inside methods or after app load, not at broken module cycles.

---

## Developer notes

- `reflex run` composes ASGI internally; merging into your existing `asgi.py` is not documented as a first-class API—see generic notes in [Deployment](deployment.md).
- Do **not** use `reflex django init` as the brownfield path (beta scaffold per README).

---

## Troubleshooting

Same as [Quickstart](quickstart.md), plus:

- **Wrong settings loaded** — `python -c "import os; print(os.environ.get('DJANGO_SETTINGS_MODULE'))"` before run.  
- **Models not found** — app not in `INSTALLED_APPS`.

---

## See also

- [Project structure](project_structure.md)  
- [Architecture](architecture.md)  
- [CLI](cli.md)

---

**Navigation:** [← Quickstart](quickstart.md) | [Next: Project structure →](project_structure.md)
