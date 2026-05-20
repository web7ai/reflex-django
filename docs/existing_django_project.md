# Existing Django Project (Brownfield Integration)

If you already have a mature Django application with established models, a database, migrations, an admin panel, and existing URL endpoints, **reflex-django** allows you to seamlessly layer a modern, reactive Reflex user interface on top of it.

This guide walks you through integrating Reflex without modifying your existing domain models or database structure.

---

## What Stays vs What You Add

Your existing Django backend codebase remains the absolute source of truth. You will simply layer Reflex directly alongside it:

| Component | Status | Location / Action |
|:---|:---|:---|
| `manage.py`, settings, models, apps, migrations | **Keep as-is** | Remains unchanged in your backend. |
| Existing HTTP URLs (e.g., `/api/`, templates) | **Keep as-is** | Served under your configured `backend_prefix`. |
| Django Admin registrations | **Keep as-is** | Served under your configured `admin_prefix`. |
| **`rxconfig.py`** | **Add new** | Created at your project root. |
| **Frontend UI package** | **Add new** | A dedicated folder hosting Reflex pages, components, and states. |

---

## Recommended Codebase Layout

When layering Reflex onto an existing Django project, we recommend organizing them in a unified monorepo structure. Here is an example folder layout:

```text
myproject/                      # Git repository root
├── manage.py                   # Existing Django manage.py
├── pyproject.toml              # Project dependencies
├── rxconfig.py                 # NEW: Reflex configuration
├── myproject/                  # Existing Django main package
│   ├── settings.py
│   └── urls.py
├── shop/                       # Existing Django application apps
│   ├── models.py
│   └── views.py
└── frontend/                   # NEW: Reflex app directory
    ├── __init__.py
    └── frontend.py             # Reflex pages and main application router
```

---

## Step-by-Step Integration

### Step 1: Install the Libraries
In the virtual environment where your Django project is installed, add `reflex` and `reflex-django`:

=== "Using uv (Recommended)"

    ```bash
    uv add reflex reflex-django
    ```

=== "Using pip"

    ```bash
    pip install reflex reflex-django
    ```

### Step 2: Initialize the Reflex Frontend
From the root of your project directory (the folder where your `manage.py` lives), run the initialization command:

<div class="termy">

```console
$ uv run reflex init frontend
Scaffolding frontend project...
Reflex frontend initialized successfully.
```

</div>

> [!CAUTION]
> **Do not run `django-admin startproject` again.** You are only bootstrapping the Reflex client package into your existing workspace.

### Step 3: Wire Up `rxconfig.py`
Open the newly created `rxconfig.py` file and configure the `ReflexDjangoPlugin`. Make sure the `settings_module` parameter points to your existing Django settings dotted path:

```python
# rxconfig.py
import reflex as rx
from reflex_django import ReflexDjangoPlugin

config = rx.Config(
    app_name="frontend",  # Points to the folder containing your Reflex code
    plugins=[
        ReflexDjangoPlugin(
            settings_module="myproject.settings",  # Dotted path to settings.py
            backend_prefix="/api",                 # Prefix for existing Django HTTP endpoints
            admin_prefix="/admin",                 # Mount path for existing Django Admin
        ),
    ],
)
```

### Step 4: Register with `INSTALLED_APPS` (Optional)
If you plan to use `ModelCRUDView`, automatic model registration, or the pre-built login templates inside your Reflex pages, add the library to your Django settings file:

```python
# myproject/settings.py

INSTALLED_APPS = [
    # ... Your existing apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.sessions",
    
    # Register the helper app
    "reflex_django",
    
    # Your custom app
    "shop",
]
```

### Step 5: Align URL Prefixes
To prevent path collisions, you must ensure that your existing Django routes (configured in `urls.py`) align with the prefixes configured in `rxconfig.py`.

For example, if your existing endpoints are served under `/api/`, configure the `backend_prefix` accordingly:

```python
# myproject/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("shop.urls")),  # This matches backend_prefix="/api"
]
```

### Step 6: Use Existing Models in Reflex States
Now you can start consuming your existing models directly inside Reflex states.

```python
# frontend/frontend.py
import reflex as rx
from reflex_django.state import AppState
from shop.models import Product  # Import your existing Django models

class CatalogState(AppState):
    products: list[dict] = []

    @rx.event
    async def load_catalog(self):
        # Safely query models using the Django async ORM
        queryset = Product.objects.filter(is_active=True).order_by("-id")
        
        # Serialize the query results to a list of dicts for the frontend
        self.products = [
            {"id": p.id, "name": p.name, "price": float(p.price)}
            async for p in queryset
        ]

def index() -> rx.Component:
    return rx.vstack(
        rx.heading("Active Catalog"),
        rx.foreach(
            CatalogState.products,
            lambda item: rx.hstack(
                rx.text(item["name"], weight="bold"),
                rx.text(f"${item['price']}"),
            )
        ),
        on_mount=CatalogState.load_catalog
    )

app = rx.App()
app.add_page(index, route="/")
```

---

## Important Rules for Existing Apps

> [!WARNING]
> **1. Avoid Circular Imports at the Module Level**
> Never import Django models or querysets at the top level of your Reflex files. Doing so can cause Python to evaluate models *before* Django's app registry has loaded, resulting in an `AppRegistryNotReady` exception. Always keep imports or operations inside your event methods or run them lazily.
>
> **2. Environment Variable Precedence**
> If your existing setup uses `.env` files or defines `DJANGO_SETTINGS_MODULE` in the environment, that environment variable **takes precedence** over the `settings_module` parameter inside `rxconfig.py`. Make sure they are identical to avoid database sync issues.

---

## Next Steps

* Discover how data flows between the two frameworks: Read the [Architecture Overview](architecture.md).
* Learn how to serialize complex Django database records: Explore [Model Serializers](serializers.md).

---

**Navigation:** [← Quickstart](quickstart.md) | [Next: Project Structure →](project_structure.md)
