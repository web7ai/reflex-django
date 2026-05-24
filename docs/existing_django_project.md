# Existing Django project

Add a Reflex SPA to a **brownfield** Django codebase without replacing models, migrations, or admin. reflex-django is Django-first: you change `settings.py`, `urls.py`, and add pages in an app’s `views.py`.

---

## What you keep vs what you add

| Component | Action |
|:---|:---|
| `manage.py`, models, migrations, admin | **Keep** |
| Existing `/api/`, webhooks, templates | **Keep** — list prefixes in `django_prefix` |
| `rxconfig.py` | **Optional** — auto stub may appear; config lives in `reflex_mount()` |
| Reflex pages | **Add** in `{app}/views.py` with `@template` |
| `demo/demo.py` | **Do not add** — use `django_led_app` |

---

## Recommended layout

```text
myproject/                    # repo root (manage.py here)
├── manage.py
├── pyproject.toml
├── rxconfig.py               # optional auto stub
├── config/
│   ├── settings.py
│   └── urls.py               # reflex_mount() here
├── shop/                     # existing Django app
│   ├── models.py
│   ├── views.py              # add Reflex pages here
│   └── api/                  # optional existing HTTP API
└── .web/                     # created by run_reflex (frontend build)
```

You do **not** need a separate `frontend/frontend.py` package unless you prefer that structure. The documented pattern co-locates UI with the Django app.

---

## Step 1: Install

```bash
uv add reflex reflex-django
# or: pip install reflex reflex-django
```

---

## Step 2: Register `reflex_django`

`settings.py`:

```python
INSTALLED_APPS = [
    # ... existing apps
    "reflex_django",
]

MIDDLEWARE = [
    # ... existing middleware
    "reflex_django.streaming_middleware.AsyncStreamingMiddleware",
]
```

---

## Step 3: Wire `urls.py`

```python
from django.contrib import admin
from django.urls import include, path
from reflex_django.urls import reflex_mount

import shop.views  # noqa: F401  # only if auto-discovery is off

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("shop.api_urls")),   # existing API
]

urlpatterns += [
    reflex_mount(
        app_name="shop",
        django_prefix=("/admin", "/api"),
        rx_config={
            "frontend_port": 3000,
            "backend_port": 8000,
        },
    ),
]
```

Align `django_prefix` with every Django-owned top-level path. If APIs live under `/api/`, include `"/api"` and keep `path("api/", ...)` **before** `reflex_mount()`.

---

## Step 4: Add pages

```python
# shop/views.py
import reflex as rx
from reflex_django import template
from reflex_django.state import AppState
from shop.models import Product


class CatalogState(AppState):
    products: list[dict] = []

    @rx.event
    async def load(self):
        self.products = [
            {"name": p.name, "price": str(p.price)}
            async for p in Product.objects.filter(is_active=True)
        ]


@template(route="/catalog", title="Catalog")
def catalog() -> rx.Component:
    return rx.vstack(
        rx.foreach(
            CatalogState.products,
            lambda p: rx.text(f"{p['name']} — {p['price']}"),
        ),
        on_mount=CatalogState.load,
    )
```

Import models **inside** event handlers if you see `AppRegistryNotReady` at import time.

---

## Step 5: Run

```bash
python manage.py migrate   # as usual
python manage.py run_reflex
```

Standard Django commands unchanged:

```bash
python manage.py createsuperuser
python manage.py shell
```

---

## Using existing models and auth

- **ORM**: Use async APIs (`async for`, `await Model.objects.acreate(...)`) in `@rx.event` methods.
- **Auth**: Subclass `AppState`; use `self.request.user` after the event bridge runs.
- **Admin login**: Session cookies are shared — log in at `/admin/`, then use the SPA.

---

## API coexistence

| Traffic | Handler |
|:---|:---|
| `/api/*` | Django REST / views (unchanged) |
| `/admin/*` | Django admin |
| `/`, `/catalog`, … | Reflex SPA |

Your mobile or JS clients can keep calling `/api/`. The Reflex UI is an additional surface on the same origin.

---

## Pitfalls

**`DJANGO_SETTINGS_MODULE`**

`manage.py` wins. Ensure deployment env matches your project settings module.

**Port conflict**

Only one process should bind the Reflex backend port (default 8000). Use `run_reflex`, not `runserver`, for full-stack dev.

**Stale `rxconfig.py`**

If a stub has the wrong `app_name`, delete it or run `run_reflex` again — stubs with the reflex-django marker are refreshed automatically.

---

## Next steps

- [Architecture](architecture.md) — dispatcher and event bridge
- [Configuration](configuration.md) — all `REFLEX_DJANGO_*` settings
- [Serializers](serializers.md) — model → JSON for Reflex state

---

**Navigation:** [← Quickstart](quickstart.md) | [Project structure →](project_structure.md)
