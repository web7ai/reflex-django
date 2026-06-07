# Pages live in `views.py`

In `reflex-django`, a Reflex page is a Python function that returns an `rx.Component`, sitting in a Django app's `views.py` next to your models. There's nothing else to wire up — no `urls.py` entry per page, no separate `frontend/` folder.

This page explains how pages get registered, how URLs are split between Django and Reflex, and the small `@page` decorator API (plus the optional `centered_template` layout helper).

---

## The smallest possible example

```python
# shop/views.py
import reflex as rx
from reflex_django.pages.decorators import page


@page(route="/", title="Home")
def index() -> rx.Component:
    return rx.heading("Hello!")


@page(route="/about", title="About")
def about() -> rx.Component:
    return rx.text("This page lives in shop/views.py.")
```

That's it. After `python manage.py run_reflex`, visit `http://localhost:3000/` and `/about` — both pages render. You never edit `urls.py` to add SPA routes (do import the views module so `@page` runs).

> Important distinction: these are **Reflex pages**, not Django views. Django doesn't need a `path(...)` for them. The Reflex client-side router handles `/`, `/about`, and everything else that's not a Django-owned prefix.

---

## How discovery works

When the server starts, `reflex-django` walks every entry in `INSTALLED_APPS` and tries to import `{app}.views`. Any `@page` (or `centered_template`) decorators in those modules register their routes.

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

## `@page` and the centered layout helper

The primary decorator is `@page`. An optional `centered_template` helper is also available when you want a ready-made centered layout.

| Decorator | What it does | When to use |
|:---|:---|:---|
| `@page(route, title=..., on_load=...)` | Registers the page with no layout wrapping. | The default. You own the page's outer container. |
| `centered_template(route, title=..., on_load=...)` | Registers the page **and** wraps content in a centered layout container. | When you want a quick centered layout without writing one. |

Both accept the standard Reflex page arguments: `route`, `title`, `description`, `image`, `meta`, `script_tags`, `on_load`, plus more. They're thin wrappers around `@rx.page`.

```python
from reflex_django.pages.decorators import page
from reflex_django.pages.decorators.templates import centered_template as template

@page(route="/bare", title="Bare page")
def bare() -> rx.Component:
    return rx.text("No layout — I own the outer container")


@template(route="/dashboard", title="Dashboard")
def dashboard() -> rx.Component:
    return rx.text("Inside the centered layout wrapper")
```

### `on_load`: run code when the page is visited

```python
@page(route="/cart", title="Cart", on_load=CartState.refresh)
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
     - everything else (the SPA catch-all, auto-mounted by default)       → Reflex SPA shell
```

Reflex client-side routing then handles navigation between SPA pages (`/`, `/about`, `/cart`) without a full page reload.

### The cardinal rules

1. **List Django routes in `urlpatterns`** — the catch-all is appended automatically (`REFLEX_DJANGO_AUTO_MOUNT=True`).
2. **Django prefixes are inferred** from those routes — you don't need to list them manually unless you override via `reflex_mount(django_prefix=...)`.
3. **Don't add a `path()` for an SPA page.** `path("about/", ...)` is wrong — use `@page(route="/about")` instead.
4. **Import page modules** so `@page` runs at import time (auto-discover still works but is deprecated).

```python
# config/urls.py — correct shape
import shop.views  # noqa: F401

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("shop.api_urls")),
]
# catch-all: automatic (REFLEX_DJANGO_AUTO_MOUNT=True)
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

Explicit `import shop.views` (or `REFLEX_DJANGO_PAGE_PACKAGES`) loads these modules at compile time. Deprecated auto-discover imports `{app}.views` for every `INSTALLED_APPS` entry — works for both file and package layouts, but prefer explicit imports.

---

## Pre-built auth pages

When `REFLEX_DJANGO_AUTH["ENABLED"]` is true (default), login, register, and password-reset pages are **registered automatically** during page discovery — no `views.py` boilerplate required.

Customize URLs, copy, branding, and page classes via `REFLEX_DJANGO_AUTH` in settings:

```python
REFLEX_DJANGO_AUTH = {
    "LOGIN_FIELDS": ["email"],
    "BRAND_TEXT": "My App",
    "PAGE_CLASSES": {
        "login": "myapp.auth.BrandedLoginPage",
    },
}
```

For explicit control, call `add_auth_pages(app)` in an advanced setup. ([Details](authentication.md).)

---

## The `app` object (`django_led_app`)

Classic Reflex projects have a `shop/shop.py` file containing `app = rx.App()`. In `reflex-django`, that file doesn't exist. Use the built-in singleton instead:

```python
from reflex_django import app  # same object as reflex_django.django_led_app.app

import reflex as rx

def about() -> rx.Component:
    return rx.text("About")

app.add_page(about, route="/about")
```

Reflex compile loads `reflex_django.django_led_app:app`. The singleton is created on first access; `ensure_django_led_app_ready()` merges `@page` decorators and applies plugins on the same instance.

**Recommended:** import page modules in `urls.py` (`import shop.views  # noqa: F401`) so decorators run before the catch-all mounts. Auto-discovery across `INSTALLED_APPS` still works but is deprecated.

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
1. Is the page module imported in `urls.py` (or listed in `REFLEX_DJANGO_PAGE_PACKAGES`)? `@page` runs at import time.
2. If you rely on auto-discover: is the app in `INSTALLED_APPS` and is `REFLEX_DJANGO_AUTO_DISCOVER_PAGES = True`?
3. Did you save the file? `manage.py run_reflex` watches for changes, but the SPA rebuild can take a few seconds.
4. Try `Ctrl+C` and restart. If still missing, delete `.web/` and run again.

---

## Running it

```bash
python manage.py run_reflex
```

Open **`http://localhost:3000/`** for Reflex pages (default two-port dev). Admin and API are on `:8000` (the SPA reaches them via `env.json`). See [Local development](local_development.md).

For details on the URL dispatcher, the SPA catch-all, and how WebSocket scopes are routed, see [Routing & URL dispatching](routing.md).

---

**Next:** [AppState — your bridge to Django →](state_management.md)
