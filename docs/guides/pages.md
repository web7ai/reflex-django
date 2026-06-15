---
level: beginner
tags: [pages, routing]
---

# Pages in `views.py`

Add Reflex routes with `@page` in `views.py`. Import that module from `urls.py` so routes register at startup. Django still owns `/admin`, `/api`, and similar prefixes.

Open this page when you added a page but it does not show up, or when you are unsure whether a route belongs in `urls.py` or in `@page`.

!!! tip "Confused by {app_name}/{app_name}.py vs {app_name}/views.py vs RX_PAGE_PACKAGES?"
    Read [App entry module and page registration](app_entry_and_pages.md) first. It explains the mental model in plain language.

---

## The smallest example

```python
--8<-- "snippets/minimal_views.py"
```

After `reflex run`, visit `http://localhost:3000/` (default two-port dev). You never add a Django `path()` for SPA routes. Do import the views module so `@page` runs.

!!! tip "Reflex pages are not Django views"
    Django does not need a `path(...)` for `/` or `/about`. The Reflex client-side router handles SPA navigation. Django only needs explicit routes for admin, API, media, and similar prefixes.

---

## When pages get registered (import and compile time)

This is the most important timing detail: **pages register when Python imports your views modules and before Reflex compiles**, not lazily when the server handles its first request.

Two moments matter:

1. **Django import time.** When `urls.py` runs `import shop.views`, every `@page` decorator in that module executes and records the route.
2. **Reflex compile time.** Before each compile, reflex-django calls `prepare_pages_for_compile()`, which imports page packages again and syncs decorated pages onto the shared `app`.

```text
urls.py loads
    -> import shop.views
        -> @page decorators run
            -> routes recorded in DECORATED_PAGES

reflex run / compile
    -> prepare_pages_for_compile()
        -> import page packages (RX_PAGE_PACKAGES or {app_name}.views)
        -> app.add_page(...) for each route
        -> Reflex builds .web/
```

**Recommended:** import page modules explicitly in `urls.py`:

```python
--8<-- "snippets/minimal_urls.py"
```

For pages outside `{app_name}.views`, set `RX_PAGE_PACKAGES` in settings or add more `import` lines in `urls.py`.

| Setting | Effect |
|:---|:---|
| `RX_PAGE_PACKAGES = ["frontend.pages"]` | Only listed modules are imported at compile time. |
| `RX_PAGE_MODULE = "ui"` | Default compile import uses `{app_name}.ui` instead of `.views`. |

---

## `@page` and layout helpers

The primary decorator is `@page`. An optional `centered_template` helper wraps content in a centered layout when you want a quick shell.

| Decorator | What it does | When to use |
|:---|:---|:---|
| `@page(route, title=..., on_load=...)` | Registers the page with no layout wrapping. | Default. You own the outer container. |
| `centered_template(route, title=..., on_load=...)` | Registers the page and wraps content in a centered layout. | Quick centered layout without writing one. |

Both accept standard Reflex page arguments: `route`, `title`, `description`, `image`, `meta`, `script_tags`, `on_load`, and more. They are thin wrappers around Reflex's page registration.

```python
from reflex_django.pages.decorators import page
from reflex_django.pages.decorators.templates import centered_template as template

@page(route="/bare", title="Bare page")
def bare() -> rx.Component:
    return rx.text("No layout wrapper here")


@template(route="/dashboard", title="Dashboard")
def dashboard() -> rx.Component:
    return rx.text("Inside the centered layout wrapper")
```

### Gating pages by login

Pass `login_required=True` on `@page`, or use `@login_required` from `reflex_django.auth`. See [Login and sessions](authentication.md).

### `on_load`: run code when the page is visited

```python
@page(route="/cart", title="Cart", on_load=CartState.refresh)
def cart() -> rx.Component:
    return rx.foreach(CartState.items, cart_row)
```

`on_load` runs an event handler whenever the user navigates to this route. Pass a single handler or a list.

---

## The URL split: Django routes vs Reflex routes

Two layers decide who handles a URL:

```text
1. The outer ASGI dispatcher:
     /_event, /_upload, /_health, /ping, /auth-codespace, /_all_routes  -> Reflex (always)
     everything else                                                    -> Django

2. Django urlpatterns:
     /admin/, /api/, ... (your explicit path() entries)                 -> Django views
     everything else (SPA catch-all, auto-mounted by default)           -> Reflex SPA shell
```

Reflex client-side routing then handles navigation between SPA pages (`/`, `/about`, `/cart`) without a full page reload.

### The cardinal rules

1. **List Django routes in `urlpatterns`.** The catch-all is appended automatically (`RX_AUTO_MOUNT=True`).
2. **Django prefixes are inferred** from those routes unless you override via `reflex_mount(django_prefix=...)`.
3. **Do not add a `path()` for an SPA page.** Use `@page(route="/about")` instead.
4. **Import page modules** so `@page` runs at import time.

---

## Why `views.py`?

Three reasons:

1. **Familiarity.** Django developers already expect page logic in `views.py`.
2. **Co-location.** Reflex pages often query models from the same app. Keeping them together makes imports trivial.
3. **No extra plumbing.** Importing app modules uses Django's normal app registry.

If your team prefers a separate `frontend/` package, point `RX_PAGE_PACKAGES` at the modules you want. See [Project structure](../getting-started/project_structure.md).

---

## Multiple apps and split files

Each app's `views.py` registers its own pages. When a file grows, turn it into a package:

```text
shop/
└── views/
    ├── __init__.py          # from .home import *; from .cart import *
    ├── home.py
    ├── cart.py
    └── checkout.py
```

Explicit `import shop.views` (or `RX_PAGE_PACKAGES`) loads these modules at import/compile time.

---

## Entry module (`{app_name}/{app_name}.py`)

Reflex expects an entry module on disk at `{app_name}/{app_name}.py` (from `app_name in rx.Config`). In most projects, keep it as a thin stub that re-exports `app`. Put page imports in `{app_name}/views.py` instead.

You *can* register pages in the entry module (`@page` or `app.add_page`), but for larger apps that splits registration across two places and causes confusion. See [App entry module and page registration](app_entry_and_pages.md) for the recommended pattern, custom `rx.App` config, and anti-patterns.

**Dynamic routes** use Reflex bracket syntax (`/items/[id]`, catch-all `[...splat]`). Register dynamic routes before static routes that share the same prefix. See [Reflex dynamic routing](https://reflex.dev/docs/pages/dynamic-routing/).

---

## Pre-built auth pages

When `RX_AUTH["ENABLED"]` is true (default), login, register, and password-reset pages register automatically during page preparation. No `views.py` boilerplate required.

Customize URLs, copy, and branding via `RX_AUTH` in settings. See [Login and sessions](authentication.md).

For explicit control, call `add_auth_pages(app)` in an advanced setup.

---

## The app module

In v4 you own `{app_name}/{app_name}.py` with `app = rx.App()`, same as plain Reflex:

```python
# shop/shop.py
import reflex as rx

app = rx.App()

def about() -> rx.Component:
    return rx.text("About")

app.add_page(about, route="/about")
```

At compile time, reflex-django imports this module via `import_app_entry_module()` and loads the `app` object. `@page` decorators in `views.py` are merged onto the same instance during `prepare_pages_for_compile()`.

**Recommended:** import page modules in `urls.py` so decorators run before the catch-all mounts.

---

## Reserved Reflex paths

These paths always route to Reflex's inner ASGI. Do not add Django routes under them:

| Path | What it is |
|:---|:---|
| `/_event` | Socket.IO state channel (WebSocket carrying UI events) |
| `/_upload` | Reflex file upload endpoint |
| `/_health`, `/ping` | Liveness probes |
| `/_all_routes` | Internal route enumeration |
| `/auth-codespace` | Reflex dev tooling |

Extend the list with `RX_RESERVED_REFLEX_PREFIXES` if needed (uncommon).

---

## Common mistakes

**SPA pages return a blank screen**
You added a permissive Django pattern (like `re_path(r"^.*$", ...)`) above the SPA catch-all. It captures `/`, `/about`, and so on before Reflex gets a chance. Keep Django routes under explicit prefixes.

**`AppRegistryNotReady` when importing views**
You touched a Django model at module level in `views.py`. Move queries and model imports into handlers:

```python
# wrong, runs at import time
class HomeState(AppState):
    products = list(Product.objects.all())

# right, runs per event
class HomeState(AppState):
    products: list[dict] = []

    @rx.event
    async def on_load(self):
        from shop.models import Product
        self.products = [{"name": p.name} async for p in Product.objects.all()]
```

**Page does not show up after adding it**

1. Is the page module imported in `urls.py` (or listed in `RX_PAGE_PACKAGES`)?
2. If the page lives in another app, is that module imported from your `{app_name}/views.py` hub? See [App entry and pages](app_entry_and_pages.md).
3. If the page is in `{app_name}/{app_name}.py`, restart `reflex run` once (cold start)  -  it should not require a second save after restart.
4. Did you save the file? The SPA rebuild can take a few seconds.
5. Restart `reflex run`. If still missing, delete `.web/` and run again.

---

## Running it

```bash
reflex run
```

Open **`http://localhost:3000/`** for Reflex pages (default two-port dev). Admin and API are on `:8000`. See [Local development](../getting-started/local_development.md).

For the URL dispatcher, SPA catch-all, and WebSocket routing details, see [Routing](../internals/routing.md).

---

## What just happened?

You learned that `@page` in `views.py` registers SPA routes at **import and compile time**, that Django `urlpatterns` only need explicit prefixes like admin and API, and that your `app` lives in `{app_name}/{app_name}.py`.

---

**Next up:** [AppState bridge](state.md)