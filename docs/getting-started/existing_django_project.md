---
level: intermediate
tags: [integration, django]
---

# Add reflex-django to an existing Django project

**What you will learn:** How to bolt a Reflex SPA onto a brownfield Django project without touching your models, admin, or API.

**When you need this:**

- You already run Django in production and want reactive pages on the same origin.
- You want to keep DRF, webhooks, and management commands exactly as they are.

Good news: you add reflex-django like any other Django app. Your models stay put. Your API stays put. You drop `@page` functions into an app's `views.py`.

**Coming from plain Reflex?** See [Add to an existing Reflex project](existing_reflex_project.md).

**Not sure which guide?** See [Integration guides](index.md).

---

## Quick checklist

- [ ] `uv add reflex reflex-django` (or `pip install`)
- [ ] `"reflex_django"` in `INSTALLED_APPS`
- [ ] `AsyncStreamingMiddleware` last in `MIDDLEWARE`
- [ ] `RX_CONFIG` in `settings.py`
- [ ] `import yourapp.views` in `urls.py` (so `@page` registers)
- [ ] `config/asgi.py` → plain `get_asgi_application()` (see `snippets/minimal_asgi.py` in the repo docs)
- [ ] First `@page` in `{app}/views.py` with optional `AppState`
- [ ] `python manage.py run_reflex` (not `runserver` + `reflex run`)

---

## What you keep, what you add

| You keep | You add |
|:---|:---|
| `manage.py`, models, migrations, admin | `reflex_django` in `INSTALLED_APPS` |
| Existing `/api/` and templates | `RX_CONFIG`; page imports in `urls.py` |
| Custom middleware | `AsyncStreamingMiddleware` at the bottom; optional `DEFAULT_DEV_MIDDLEWARE` in dev |
| DRF views, webhooks, scripts | `@page` pages in any app's `views.py` |

You do **not** add `rxconfig.py`. You do **not** add `{app}/{app}.py`.

---

## 1. Install

```bash
uv add reflex reflex-django
# or
pip install reflex reflex-django
```

---

## 2. Register the app

```python
--8<-- "snippets/minimal_settings.py"
```

For local dev (admin from `:3000`), prepend dev middleware and CSRF origins. See [Local development](local_development.md).

The streaming middleware must be **last**. It keeps Django admin streaming responses ASGI-safe. See [Async streaming middleware](../internals/streaming_middleware.md).

---

## 3. Configure Reflex and import pages

```python
--8<-- "snippets/minimal_urls.py"
```

Auto-detection reads the **first segment** of each top-level `path()` (`path("api/", include(...))` covers `/api/products/`, and so on). Pass explicit `RX_DJANGO_PREFIX` only if auto-detection misses a prefix. See [The three knobs](../overview/concepts.md).

---

## 4. Point ASGI at reflex-django

```python
--8<-- "snippets/minimal_asgi.py"
```

If you deploy with WSGI today (`gunicorn` sync workers), plan a move to an ASGI server (uvicorn, granian, hypercorn). See [Deployment](../operations/deployment.md).

---

## 5. Add a Reflex page

Pick any app in `INSTALLED_APPS` (usually the one in `app_name`):

```python
# shop/views.py
import reflex as rx
from reflex_django.pages.decorators import page
from reflex_django.states import AppState

# ... existing Django views can stay unchanged ...


class CatalogState(AppState):
    products: list[dict] = []

    @rx.event
    async def load(self):
        from shop.models import Product
        self.products = [
            {"id": p.id, "name": p.name, "price": str(p.price)}
            async for p in Product.objects.filter(is_active=True)
        ]


@page(route="/catalog", title="Catalog", on_load=CatalogState.load)
def catalog() -> rx.Component:
    return rx.vstack(
        rx.heading("Catalog"),
        rx.foreach(
            CatalogState.products,
            lambda p: rx.text(p["name"], " - $", p["price"]),
        ),
    )
```

This file can hold both Django views (`HttpResponse`) and Reflex pages (`rx.Component`). They do not collide.

!!! tip "Import models inside handlers"
    `views.py` may import before Django's app registry is ready. Importing models inside `@rx.event` handlers avoids `AppRegistryNotReady`.

---

## 6. Run

--8<-- "snippets/run_reflex_command.md"

- `http://localhost:3000/`: new Reflex pages (SPA + hot reload)
- `http://localhost:3000/admin/` or `http://localhost:8000/admin/`: admin (Django mounted in Reflex backend)
- `http://localhost:3000/api/...` or `http://localhost:8000/api/...`: existing API

With `RX_SEPARATE_DEV_PORTS=True`, Vite on `:3000` proxies admin, API, and `/_event` to the Reflex backend. Optional: `--env dev` to browse only `:8000`.

---

## How it sits beside your API

| Path | Who handles it |
|:---|:---|
| `/admin/...` | Your admin |
| `/api/...` | Your DRF / function views |
| `/webhooks/...` | Your webhook handlers |
| `/_event`, `/_upload`, `/_health` | Reflex internals |
| `/`, `/catalog`, `/about`, ... | Reflex SPA |

Same origin, same cookies. Mobile clients can keep hitting `/api/` while browsers get the SPA at `/`. See [Routing](../internals/routing.md).

---

## Optional split-process dev

If you need Django on `runserver` separately from Reflex, set `RX_PROXY_SERVER` and run both processes. See [Routing](../internals/routing.md) and [Local development](local_development.md).

--8<-- "snippets/proxy_server_settings.py"

---

## Pages in a different package

**Option A:** Put pages in any app's `views.py`. reflex-django scans `views.py` in every `INSTALLED_APPS` entry (except `django.*` and `reflex_django`).

**Option B:** List explicit modules:

```python
RX_PAGE_PACKAGES = ["frontend.pages.home", "frontend.pages.catalog"]
```

That disables auto-discovery and uses only the modules you list.

---

## Common bumps

**`AppRegistryNotReady`**
Move model imports inside handlers.

**404 on `/api/orders/`**
Ensure `path("api/", ...)` appears in `urlpatterns` before the SPA catch-all. Auto-detection should pick up `/api`. For unusual layouts, set `RX_DJANGO_PREFIX`.

**Port conflict**
Do not run `runserver 8000` alongside `run_reflex`.

**Leftover `rxconfig.py`**
Delete it. Config lives in `settings.py` now.

**Middleware not running on Reflex events**
It does run by default. See [Custom middleware in events](../guides/middleware.md) if something specific is skipped.

---

## What just happened?

You treated reflex-django as another Django app: installed it, pointed ASGI at the combined entry, imported pages from `urls.py`, and started the default two-port dev loop. Your existing models and API stayed untouched while Reflex pages joined the same origin.

---

**Next up:** [Project structure](project_structure.md)
