# Pages live in `views.py`

In `reflex-django`, a Reflex page is a Python function that returns an `rx.Component`, sitting in a Django app's `views.py` next to your models. There's nothing else to wire up — no `urls.py` entry per page, no separate `frontend/` folder.

This page explains how pages get registered, how URLs are split between Django and Reflex, and the small `@template` / `@page` decorator API.

---

## The smallest possible example

```python
# shop/views.py
import reflex as rx
from reflex_django import template


@template(route="/", title="Home")
def index() -> rx.Component:
    return rx.heading("Hello!")


@template(route="/about", title="About")
def about() -> rx.Component:
    return rx.text("This page lives in shop/views.py.")
```

That's it. Visit `http://localhost:8000/` and `/about` — both pages render. You never edit `urls.py` to add these routes.

> Important distinction: these are **Reflex pages**, not Django views. Django doesn't need a `path(...)` for them. The Reflex client-side router handles `/`, `/about`, and everything else that's not a Django-owned prefix.

---

## How discovery works

When the server starts, `reflex-django` walks every entry in `INSTALLED_APPS` and tries to import `{app}.views`. Any `@template` or `@page` decorators in those modules register their routes.

```python
INSTALLED_APPS = [
    "django.contrib.admin",      # skipped (django.* is always skipped)
    "django.contrib.auth",
    ...
    "reflex_django",             # skipped (itself)
    "shop",                      # shop/views.py imported, its pages registered
    "blog",                      # blog/views.py imported, its pages registered
]
```

If `{app}/views.py` doesn't exist, that app is silently skipped. If it raises an import error, you'll see it in the logs.

### Controlling discovery

| Setting | Effect |
|:---|:---|
| `REFLEX_DJANGO_AUTO_DISCOVER_PAGES = False` | Only `{app_name}.views` is imported (the one named in `reflex_mount`). |
| `REFLEX_DJANGO_PAGE_APPS = ["shop", "billing"]` | Limit the scan to specific app labels. |
| `REFLEX_DJANGO_PAGE_PACKAGES = ["frontend.pages.home"]` | Explicit list. Disables auto-discovery entirely. |
| `REFLEX_DJANGO_PAGE_MODULE = "ui"` | Look for `{app}/ui.py` instead of `{app}/views.py`. |

For most projects, the defaults are fine.

---

## `@template` vs `@page`

Two decorators ship with `reflex-django`. Pick the one that fits.

| Decorator | What it does | When to use |
|:---|:---|:---|
| `@template(route, title=..., on_load=...)` | Registers the page **and** wraps content in a centered layout container. | Most pages. Good default. |
| `@page(route, title=..., on_load=...)` | Registers the page with no layout wrapping. | When you need full control of the page's outer container. |

Both accept the standard Reflex page arguments: `route`, `title`, `description`, `image`, `meta`, `script_tags`, `on_load`, plus more. They're thin wrappers around `@rx.page`.

```python
from reflex_django import template, page

@template(route="/dashboard", title="Dashboard")
def dashboard() -> rx.Component:
    return rx.text("Inside the default layout wrapper")


@page(route="/bare", title="Bare page")
def bare() -> rx.Component:
    return rx.text("No layout — I own the outer container")
```

### `on_load`: run code when the page is visited

```python
@template(route="/cart", title="Cart", on_load=CartState.refresh)
def cart() -> rx.Component:
    return rx.foreach(CartState.items, cart_row)
```

`on_load` runs an event handler whenever the user navigates to this route. Use it to fetch data, gate by login, or update the title. You can pass a single handler or a list.

---

## The URL split: Django routes vs Reflex routes

Two layers decide who handles a given URL:

```text
1. The outer ASGI dispatcher:
     - /_event, /_upload, /_health, /ping, /auth-codespace, /_all_routes  → Reflex (always)
     - everything else                                                    → Django

2. Django's urls.py:
     - /admin/, /api/, ... (your explicit path() entries)                 → Django views
     - everything else (the SPA catch-all from reflex_mount)              → Reflex SPA shell
```

Reflex client-side routing then handles navigation between SPA pages (`/`, `/about`, `/cart`) without a full page reload.

### The cardinal rules

1. **Django routes go above `reflex_mount()`** in `urls.py`.
2. **Every prefix in `django_prefix=(...)`** must match a real `path(...)` line above.
3. **Don't add a `path()` for an SPA page.** `path("about/", ...)` is wrong — use `@template(route="/about")` instead.

```python
# config/urls.py — correct shape
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("shop.api_urls")),
]

urlpatterns += [
    reflex_mount(
        app_name="shop",
        django_prefix=("/admin", "/api"),     # matches the lines above
    ),
]
```

---

## Why `views.py` and not `urls.py` or a separate `pages/` folder?

Three reasons:

1. **Familiarity.** Django developers already know that `views.py` is where "things that render pages" live. We don't move that convention.
2. **Co-location.** Reflex pages often query Django models from the same app. Keeping them in the same folder makes imports trivial and changes obvious.
3. **No extra plumbing.** Putting pages in `INSTALLED_APPS` modules means Django's app registry handles discovery for us.

If your team really prefers a separate `frontend/` package, that's fine too — point `REFLEX_DJANGO_PAGE_PACKAGES` at the modules you want to load. See [Project structure](project_structure.md#alternative-layout-pages-in-a-separate-package).

---

## Multiple apps, multiple files

Each app's `views.py` registers its own pages. You can spread them across as many files as you like:

```text
shop/
├── views.py                 # registers /, /cart, /checkout
└── ...

blog/
├── views.py                 # registers /blog, /blog/<slug>
└── ...
```

If `views.py` gets too long, split it into a package:

```text
shop/
└── views/
    ├── __init__.py          # from .home import *; from .cart import *
    ├── home.py
    ├── cart.py
    └── checkout.py
```

The default discovery imports `{app}.views`, which works for both file and package layouts.

---

## Pre-built auth pages

`reflex-django` ships login, register, password-reset, and password-reset-confirm pages. Drop one call into your `views.py` to register them all:

```python
# shop/views.py
from reflex_django.auth import add_auth_pages

add_auth_pages()
```

That registers `/login`, `/register`, `/password_reset`, `/password_reset_confirm`. Customize URLs and titles via `REFLEX_DJANGO_AUTH` in settings. ([Details](authentication.md).)

---

## The `django_led_app` module

You might see this name mentioned. Here's what it is — and why you don't have to think about it.

Classic Reflex projects have a `shop/shop.py` file containing `app = rx.App()`. In `reflex-django`, that file doesn't exist. Instead, Reflex loads the app from a built-in module:

```text
reflex_django.django_led_app:app
```

At startup, that module:

1. Imports page modules from `INSTALLED_APPS`.
2. Creates `rx.App()`.
3. Applies the routes from all the `@template` / `@page` decorators it found.

You don't import it. You don't create it. It just makes "pages in `views.py`" work.

---

## Reserved Reflex paths — don't touch these

These paths are always routed to Reflex's inner ASGI, regardless of any URL patterns you write. Don't add Django routes under them:

| Path | What it is |
|:---|:---|
| `/_event` | Socket.IO state channel (the WebSocket carrying all UI events) |
| `/_upload` | Reflex file upload endpoint |
| `/_health`, `/ping` | Liveness probes |
| `/_all_routes` | Internal route enumeration |
| `/auth-codespace` | Reflex dev tooling |

If you need to extend the list (uncommon), add to `REFLEX_DJANGO_RESERVED_REFLEX_PREFIXES` in settings.

---

## Common mistakes

**SPA pages return a blank screen**
You added a permissive Django pattern (like `re_path(r"^.*$", ...)`) *above* `reflex_mount()`. It captures `/`, `/about`, etc. before the SPA catch-all gets a chance. Keep Django routes under explicit prefixes; let Reflex own the root.

**`AppRegistryNotReady` when starting**
You're touching a Django model at the top of `views.py` (class-level field default, module-level query, etc.). Move that into a handler:

```python
# wrong — runs at import time, Django app registry isn't ready yet
class HomeState(AppState):
    products = list(Product.objects.all())

# right — runs per event
class HomeState(AppState):
    products: list[dict] = []

    @rx.event
    async def on_load(self):
        self.products = [{"name": p.name} async for p in Product.objects.all()]
```

**Page doesn't show up after adding it**
1. Is the app listed in `INSTALLED_APPS`?
2. Is auto-discovery enabled (`REFLEX_DJANGO_AUTO_DISCOVER_PAGES = True`, the default)?
3. Did you save the file? `manage.py run_reflex` watches for changes, but the SPA rebuild can take a few seconds.
4. Try `Ctrl+C` and restart. If still missing, delete `.web/` and run again.

---

## Running it

```bash
python manage.py run_reflex
```

Then visit `http://localhost:8000/`. Your admin stays at `/admin/`, your API at `/api/`, and your Reflex pages everywhere else.

For details on the URL dispatcher, the SPA catch-all, and how WebSocket scopes are routed, see [Routing & URL dispatching](routing.md).

---

**Next:** [AppState — your bridge to Django →](state_management.md)
