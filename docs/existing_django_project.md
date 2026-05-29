# Add reflex-django to an existing Django project

This is the brownfield path. You already have a working Django project — models, migrations, admin, maybe a DRF API — and you just want to bolt on a reactive UI without rebuilding anything.

Good news: you don't have to touch your models or your existing views. You add `reflex-django` like any other Django app, list the URL prefixes you already own, and start dropping Reflex pages into your apps' `views.py`.

---

## What you keep, what you add

| You keep | You add |
|:---|:---|
| `manage.py`, models, migrations, admin | `reflex_django` in `INSTALLED_APPS` |
| Your existing `/api/` and templates | `reflex_mount(...)` in `urls.py` |
| Your custom middleware | `AsyncStreamingMiddleware` at the bottom of `MIDDLEWARE` |
| Your DRF views, webhooks, command-line scripts | `@page` pages inside any app's `views.py` |
| Your `settings.py` (mostly) | A few `REFLEX_DJANGO_*` keys (optional) |

You don't add an `rxconfig.py`. You don't add a `{app}/{app}.py`. You don't move things around. Promise.

---

## 1. Install

```bash
uv add reflex reflex-django
# or
pip install reflex reflex-django
```

---

## 2. Register the app

In `settings.py`:

```python
INSTALLED_APPS = [
    # ... your existing apps ...
    "reflex_django",
]

MIDDLEWARE = [
    # ... your existing middleware ...
    "reflex_django.streaming_middleware.AsyncStreamingMiddleware",   # last
]
```

The streaming middleware needs to be **last**. It's there to keep Django's admin streaming responses ASGI-safe; it does nothing under WSGI. ([Details](async_streaming_middleware.md).)

---

## 3. List your existing prefixes in `reflex_mount()`

This is the only step that needs care. `reflex-django` adds a catch-all URL pattern at the bottom of `urls.py` that serves the Reflex SPA for anything Django doesn't already own. So you need to tell it which prefixes Django *does* own.

```python
# config/urls.py
from django.contrib import admin
from django.urls import include, path
from reflex_django.urls import reflex_mount

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("shop.api_urls")),
    path("webhooks/", include("shop.webhooks_urls")),
]

urlpatterns += [
    reflex_mount(
        app_name="shop",
        django_prefix=("/admin", "/api", "/webhooks"),
        rx_config={"backend_port": 8000},
    ),
]
```

The rule is: **every `path()` line above `reflex_mount()` should have a matching prefix in `django_prefix`.** If you forget one, the SPA catch-all will try to serve the SPA shell when the user visits that URL.

If your URLs are organized into `include()`d files, just list the top-level prefix once (e.g. `"/api"` is enough to cover `/api/products/`, `/api/orders/`, etc.).

---

## 4. Point ASGI at `reflex_django`

If you have an existing `config/asgi.py`, replace it (or merge the import in):

```python
# config/asgi.py
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
from reflex_django.asgi_entry import application  # noqa: E402,F401
```

If you were previously deploying with `gunicorn` (WSGI), you'll want to switch to an ASGI server like `uvicorn`, `granian`, or `hypercorn`. ([Deployment guide](deployment.md) has examples.)

---

## 5. Add a Reflex page

Pick any Django app that's in `INSTALLED_APPS` (the same one you named in `app_name`, by default). Open its `views.py` and add a Reflex page:

```python
# shop/views.py — your existing module
import reflex as rx
from reflex_django.pages.decorators import page
from reflex_django.states import AppState

# ... your existing Django views can stay here, unchanged ...


class CatalogState(AppState):
    products: list[dict] = []

    @rx.event
    async def load(self):
        from shop.models import Product   # import inside the handler is safer
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
            lambda p: rx.text(p["name"], " — $", p["price"]),
        ),
    )
```

Notice: this file can hold both Django views (functions returning `HttpResponse`) and Reflex pages (functions returning `rx.Component`). They don't collide.

> **Why is the model import inside the handler?** Because `views.py` may get imported before Django's app registry is ready. Putting model imports inside the handler dodges `AppRegistryNotReady`. Once your project is fully booted, both patterns work, but the inside-handler version is the bulletproof one.

---

## 6. Run

```bash
python manage.py migrate   # if you have new migrations
python manage.py run_reflex
```

- `http://localhost:8000/admin/` — your admin, unchanged.
- `http://localhost:8000/api/...` — your existing API, unchanged.
- `http://localhost:8000/catalog` — your new Reflex page.

Your existing tests, management commands, and migrations all keep working.

---

## How it sits beside your API

If you also have a DRF API at `/api/`, both surfaces coexist:

| Path | Who handles it |
|:---|:---|
| `/admin/...` | Your admin |
| `/api/...` | Your DRF / function views |
| `/webhooks/...` | Your webhook handlers |
| `/_event`, `/_upload`, `/_health` | Reflex internals (WebSocket, uploads, health) |
| `/`, `/catalog`, `/about`, … | Reflex SPA |

Same origin, same port, same cookies. Your mobile app can keep hitting `/api/` while a browser sees the new SPA at `/`. No CORS to configure. ([More on routing](routing.md).)

---

## Using your existing models

Inside any `@rx.event` handler on an `AppState` subclass, you can:

- **Query the ORM** with `async for`, `await Model.objects.aget(...)`, `acreate`, `asave`, `adelete`.
- **Read the logged-in user** via `self.request.user` — same user as `/admin/`.
- **Read or write the session** via `self.request.session` (or `await self.session.aset(...)` for async).
- **Add flash messages** via `messages.add_message(self.request, ...)`.

```python
@rx.event
async def add_to_cart(self, product_id: int):
    from shop.models import Cart, Product
    product = await Product.objects.aget(pk=product_id)
    cart, _ = await Cart.objects.aget_or_create(owner=self.request.user)
    await cart.items.aadd(product)
```

Same model classes you've been using in your existing views and admin. No new layer.

---

## What if my Reflex pages live in a different package?

Not all teams want UI code in the same app as models. That's fine. Either:

**Option A** — put pages in any other app's `views.py`. `reflex-django` auto-discovers `views.py` in every app listed in `INSTALLED_APPS` (skipping `django.*` and `reflex_django` itself):

```python
INSTALLED_APPS = [
    # ...
    "shop",        # models live here
    "frontend",    # frontend/views.py has the Reflex pages
]
```

**Option B** — point at an explicit list of page modules in `settings.py`:

```python
REFLEX_DJANGO_PAGE_PACKAGES = ["frontend.pages.home", "frontend.pages.catalog"]
```

That disables auto-discovery and uses only the modules you list. Good for monorepos with a clear separation between domain code and UI code.

---

## Common bumps in a real project

**`AppRegistryNotReady`**
You imported a model at the top of `views.py` and that file got imported during early bootstrap. Move the import inside the handler:

```python
@rx.event
async def load(self):
    from shop.models import Product
    ...
```

**404 on `/api/orders/`**
You added a Django route but forgot to add the prefix to `django_prefix`. Add `"/api"` (top-level prefix is enough; you don't need to list every sub-path).

**Port conflict with `runserver`**
Only one process should bind the Reflex backend port. Don't run `python manage.py runserver 8000` alongside `python manage.py run_reflex`.

**Leftover `rxconfig.py`**
If you previously experimented with plain Reflex, you might have a `rxconfig.py` at the project root pointing at `{app}.{app}`. Delete it. `reflex_mount()` is the only config you need.

**Existing custom middleware not running on Reflex events**
Good news — it *does* run, by default. The `DjangoEventBridge` walks your full `settings.MIDDLEWARE` chain on every Reflex event. If something specific isn't applying, see [Custom middleware in events](django_middleware_to_reflex.md) for the skip list and disable flags.

**`dispatch is not a function` in the browser console**
The compiled SPA's dispatcher map is out of sync with your live state classes. Stop the dev server, delete `.web/`, and restart `python manage.py run_reflex`. The next build re-generates a fresh dispatcher.

---

## What's next

- **[Project structure](project_structure.md)** — recommended file layout for a hybrid Django/Reflex project.
- **[Configuration](configuration.md)** — every `reflex_mount()` argument and every `REFLEX_DJANGO_*` setting.
- **[CRUD with ModelState](reactive_model_state.md)** — declarative CRUD that pairs naturally with your existing Django models.

---

**Next:** [Project structure →](project_structure.md)
