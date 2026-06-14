---
level: beginner
tags: [state, appstate]
---

# AppState bridge

**What you'll learn:** How `AppState` connects Reflex event handlers to Django sessions, users, and middleware, and when to use plain `rx.State` or `ModelState` instead.

**When you need this:**

- You need `request.user` or the session inside an `@rx.event` handler.
- You are deciding whether a page needs Django context or is pure UI state.

---

`AppState` is the most important class in reflex-django. It is a regular Reflex `State` that also knows about your Django session. Subclass it whenever a page needs Django context in handlers.

---

## What `AppState` adds

It is a `rx.State` subclass with two layers:

1. **Per-event Django context on `self`**, inside any `@rx.event` handler, read `self.request`, `self.user`, `self.session`, `self.messages`, `self.csrf_token`, `self.response`. reflex-django fills these before your handler runs, using your real Django middleware.
2. **Reactive snapshot variables for the UI**, `self.is_authenticated`, `self.username`, `self.email`, and similar fields you can bind in components.

```python
from reflex_django.states import AppState

class CartState(AppState):
    items: list[dict] = []

    @rx.event
    async def add(self, product_id: int):
        if not self.request.user.is_authenticated:
            return rx.redirect("/login")
        from shop.models import Cart
        await Cart.objects.acreate(owner=self.request.user, product_id=product_id)
```

That is the core API. The rest of this page is detail.

---

## What lives on `self`

Inside any `@rx.event async def` method on an `AppState` subclass:

### Per-event Django context

| Attribute | What it is |
|:---|:---|
| `self.request` | Synthetic `HttpRequest`, populated by `settings.MIDDLEWARE`. |
| `self.user` | `request.user`, already resolved (no `SynchronousOnlyOperation`). |
| `self.session` | The session, async-safe (`await self.session.aget(...)`, `asave()`). |
| `self.messages` | Snapshot of `django.contrib.messages` (JSON-safe list). |
| `self.csrf_token` | CSRF token for the current request. |
| `self.response` | `HttpResponse` from middleware (200 unless middleware short-circuited). |
| `self.resolver_match` | `ResolverMatch` if the path resolved to a Django view. |

### Reactive variables (bindable in components)

| Variable | What it reflects |
|:---|:---|
| `self.is_authenticated` | `request.user.is_authenticated` |
| `self.username` | `request.user.get_username()` |
| `self.email` | `request.user.email` |
| `self.is_staff`, `self.is_superuser` | Django user flags |
| `self.user_id` | User primary key |
| `self.group_names` | Group names |
| `self.perms` | JSON-safe permission strings (`{app}.{codename}`) |

Use per-event context (`self.user`, `self.session`) in handlers for authorization and mutations. Use reactive variables (`self.is_authenticated`, `self.username`) in components for rendering.

```python
class DashboardState(AppState):
    @rx.event
    async def delete_account(self):
        if not self.user.is_authenticated:
            return rx.redirect("/login")
        if self.user.is_superuser:
            return
        await self.user.adelete()


def dashboard_ui():
    return rx.vstack(
        rx.cond(
            DashboardState.is_authenticated,
            rx.text(f"Welcome, {DashboardState.username}"),
            rx.link("Log in", href="/login"),
        ),
    )
```

!!! warning "Security rule"
    Never make authorization decisions from reactive snapshot variables alone. They are sent to the browser and can be tampered with. Always check `self.request.user` or `self.user` in the handler.

---

## How it works (briefly)

Every Reflex event arrives on `/_event` as a WebSocket frame. By default that bypasses Django's HTTP pipeline. reflex-django inserts the **`DjangoEventBridge`** before your handler:

1. Resolve bridge tier for the handler's state class (`full`, `auth_only`, or `none`). Default project mode is **`full`** (unchanged legacy behavior).
2. If tier is `none`, skip Django setup and run your handler immediately.
3. Read `router_data` from the event (cookies, path, query string, headers).
4. Build a synthetic `HttpRequest`.
5. Run middleware for the tier — full `MIDDLEWARE` or the auth-only subset.
6. Eagerly resolve `request.user` with Django's async `aget_user`.
7. Bind the result onto state when the tier requires it; sync auth snapshots on `full` (and `auth_only` for `DjangoUserState` handlers).
8. Run your handler.

With `REFLEX_DJANGO_EVENT_BRIDGE_MODE = "smart"`, plain `rx.State` handlers use tier `none` automatically — no middleware, no `self.request`. `AppState` and `ModelState` still get tier `full`.

If middleware returns a 3xx (for example login required), the bridge converts it to `rx.redirect(...)` unless you set `REFLEX_DJANGO_AUTO_REDIRECT_FROM_MIDDLEWARE = False`.

See [WebSocket event pipeline](websocket_event_pipeline.md) for the full plumbing and [Scaling and performance](scaling.md) for tuning.

---

## When to use `AppState` vs `rx.State` vs `ModelState`

| Class | Inherits from | Use it when |
|:---|:---|:---|
| `rx.State` | (Reflex) | Pure UI state: counters, filters, modals. No Django context needed. |
| **`AppState`** | `rx.State` + Django bridge | Page reads `request.user` or session, or runs custom middleware logic. **Default for user-aware pages.** |
| `ModelState` | `AppState` + CRUD machinery | Page is mostly list/edit/save/delete for one Django model. |

```python
class FilterState(rx.State):
    query: str = ""
    # With REFLEX_DJANGO_EVENT_BRIDGE_MODE = "smart", tier "none" is automatic.
    # To force Django context on a plain rx.State handler:
    # _reflex_django_bridge = "full"


class CartState(AppState):
    @rx.event
    async def add(self, product_id: int):
        user = self.request.user
        ...


class ProductState(ModelState):
    model = Product
    fields = ["name", "price"]
```

A page can mix several states. Use `rx.State` for a filter bar and `AppState` for user-specific data. Use `_reflex_django_bridge` (underscore prefix) for per-class tier overrides — public class attrs become Reflex state vars. See [Scaling and performance](scaling.md).

---

## Reading the request

Three equivalent styles inside handlers:

```python
# Style A, self.request on AppState / ModelState
class CatalogState(AppState):
    @rx.event
    async def search(self, q: str):
        page = self.request.GET.get("page", "1")


# Style B, module-level request proxy
from reflex_django import request

class FilterState(rx.State):
    @rx.event
    async def apply(self):
        q = request.GET.get("q", "")


# Style C, functional helpers
from reflex_django import current_request, current_user
```

All three return the same `HttpRequest` for the current event. Outside an event (import time, background threads), there is no request and helpers return anonymous defaults.

---

## Session and flash messages

```python
class PreferencesState(AppState):
    @rx.event
    async def set_theme(self, theme: str):
        self.session["theme"] = theme
        await self.session.asave()
```

```python
from django.contrib import messages

class CheckoutState(AppState):
    @rx.event
    async def submit(self):
        messages.success(self.request, "Order placed!")
```

Render messages in the UI with `DjangoUserState.messages`:

```python
from reflex_django.states import DjangoUserState

rx.foreach(
    DjangoUserState.messages,
    lambda m: rx.callout(m.message, color_scheme=m.level_tag),
)
```

---

## Full example: profile page

```python
import reflex as rx
from reflex_django.pages.decorators import page
from reflex_django.states import AppState


class ProfileState(AppState):
    bio: str = ""
    saved: bool = False

    @rx.event
    async def on_load(self):
        if not self.request.user.is_authenticated:
            return rx.redirect("/login")
        self.bio = self.request.user.profile.bio or ""

    @rx.event
    async def save(self):
        user = self.request.user
        if not user.is_authenticated:
            return
        user.profile.bio = self.bio.strip()
        await user.profile.asave()
        self.saved = True


@page(route="/profile", title="Profile", on_load=ProfileState.on_load)
def profile() -> rx.Component:
    return rx.vstack(
        rx.heading(f"Hi, {ProfileState.username}"),
        rx.text_area(value=ProfileState.bio, on_change=ProfileState.set_bio),
        rx.button("Save", on_click=ProfileState.save),
        rx.cond(ProfileState.saved, rx.callout("Saved!", color_scheme="green")),
    )
```

Five things to notice: `AppState` gives you `self.request.user`; `on_load` gates by login; async ORM with `asave()`; reactive `ProfileState.username` in the UI; no model instances stored in state fields.

---

## Avoid model instances in state fields

State fields serialize to JSON and ship to the browser. Convert models to dicts first:

```python
# wrong
self.product = product

# right
self.product = {"id": product.id, "name": product.name, "price": str(product.price)}
```

Same rule for `Decimal`, `datetime`, and `date`: convert to strings.

---

## Do not read `request.user` at class definition time

Class-level defaults run at import time with no live request:

```python
# wrong
class HomeState(AppState):
    greeting: str = f"Hi, {request.user}"

# right
class HomeState(AppState):
    greeting: str = "Hi"

    @rx.event
    async def on_load(self):
        if self.request.user.is_authenticated:
            self.greeting = f"Hi, {self.request.user.get_username()}"
```

---

## A note on `DjangoUserState`

`DjangoUserState` exposes reactive variables (`is_authenticated`, `username`, and so on) **without** per-event `self.request`. Use it for UI-only snapshots, like a navbar:

```python
from reflex_django.states import DjangoUserState

def navbar():
    return rx.cond(
        DjangoUserState.is_authenticated,
        rx.text(f"Hi, {DjangoUserState.username}"),
        rx.link("Log in", href="/login"),
    )
```

For authenticated actions, use `AppState` instead.

When `REFLEX_DJANGO_AUTH_AUTO_SYNC = True` (default), snapshot fields refresh on every event for `AppState` subclasses.

---

## What just happened?

You learned that `AppState` runs Django middleware on every Reflex event, gives you real `self.request.user` in handlers, and exposes reactive snapshots for the UI. Use the live user for security, snapshots for display.

---

**Next up:** [Database integration](database_integration.md)