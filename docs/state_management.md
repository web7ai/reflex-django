# AppState — your bridge to Django

`AppState` is the most important class in `reflex-django`. It's a regular Reflex `State` that also knows about your Django session. If you only learn one new thing from these docs, learn this.

This page explains what `AppState` gives you, how it does it, and how to choose between `AppState`, plain `rx.State`, and the higher-level `ModelState`.

---

## What `AppState` is

It's a `rx.State` subclass. It adds two things:

1. **Django context attributes on `self`** — inside any `@rx.event` handler, you can read `self.request`, `self.user`, `self.session`, `self.messages`, `self.csrf_token`, `self.response`. They're filled in by `reflex-django` before your handler runs, using your real Django middleware.
2. **Reactive snapshot variables for the UI** — things like `self.is_authenticated`, `self.username`, `self.email`. These are normal Reflex variables you can bind in components.

You use it exactly like a regular Reflex state — just subclass `AppState` instead of `rx.State`:

```python
from reflex_django.state import AppState

class CartState(AppState):
    items: list[dict] = []

    @rx.event
    async def add(self, product_id: int):
        if not self.request.user.is_authenticated:
            return rx.redirect("/login")
        await Cart.objects.acreate(owner=self.request.user, product_id=product_id)
```

That's the whole API surface. The rest of this page is detail.

---

## What lives on `self`

Inside any `@rx.event async def` method on an `AppState` subclass:

### Per-event Django context

| Attribute | What it is |
|:---|:---|
| `self.request` | A synthetic `HttpRequest`, fully populated by your `settings.MIDDLEWARE`. |
| `self.user` | `request.user`, already resolved (no `SynchronousOnlyOperation`). |
| `self.session` | The session, async-safe (`await self.session.aget(...)`, `asave()`). |
| `self.messages` | Snapshot of `django.contrib.messages` (JSON-safe list). |
| `self.csrf_token` | The CSRF token for the current request. |
| `self.response` | The `HttpResponse` produced by middleware (200 unless a middleware short-circuited). |
| `self.resolver_match` | `ResolverMatch` if the path resolved to a Django view. |
| `self.django_request` | The raw `HttpRequest` (same object as `self.request`, just a different alias). |
| `self.django_response` | The raw `HttpResponse`. |
| `self.django_context` | Dict of context-processor keys, if `REFLEX_DJANGO_AUTO_LOAD_CONTEXT` is on. |

### Reactive variables (also bindable in components)

| Variable | What it reflects |
|:---|:---|
| `self.is_authenticated` | `request.user.is_authenticated` |
| `self.username` | `request.user.get_username()` |
| `self.email` | `request.user.email` |
| `self.is_staff`, `self.is_superuser` | Mirror Django user flags |
| `self.user_id` | The user's primary key |
| `self.group_names` | List of group names the user belongs to |
| `self.perms` | JSON-safe list of permissions (`{app}.{codename}` strings) |

You use the per-event context (`self.user`, `self.session`) inside handlers — for authorization, queries, mutations. You use the reactive variables (`self.is_authenticated`, `self.username`) in components — for `rx.cond`, text bindings, conditional rendering.

```python
class DashboardState(AppState):
    @rx.event
    async def delete_account(self):
        # Per-event context — live, authoritative, NOT sent to the browser
        if not self.user.is_authenticated:
            return rx.redirect("/login")
        if self.user.is_superuser:
            return  # don't let admins delete themselves accidentally
        await self.user.adelete()


def dashboard_ui():
    return rx.vstack(
        rx.cond(
            DashboardState.is_authenticated,           # reactive — used in UI
            rx.text(f"Welcome, {DashboardState.username}"),
            rx.link("Log in", href="/login"),
        ),
    )
```

> **The security rule:** never make authorization decisions based on the reactive snapshot variables alone. Always check `self.user` / `self.request.user` in the handler. The reactive ones are sent to the browser and can be spoofed; the per-event ones are computed server-side every time.

---

## How it works (briefly)

Every Reflex event is a WebSocket frame on `/_event`. By default, that doesn't go through Django's HTTP pipeline. `reflex-django` inserts a small piece called the **`DjangoEventBridge`** *before* your handler runs:

1. The bridge reads `router_data` from the event (cookies, path, query string, headers).
2. It builds a synthetic `HttpRequest` from that data.
3. It runs your full `settings.MIDDLEWARE` chain on the request. `SessionMiddleware` loads the session. `AuthenticationMiddleware` resolves the user. Your custom middleware runs too.
4. It eagerly resolves `request.user` using Django's async `aget_user` (so you don't get `SynchronousOnlyOperation` later).
5. It binds the result onto your `AppState` instance: `self.request`, `self.user`, `self.session`, etc.
6. *Then* your handler runs.

If any middleware short-circuits with a 3xx — e.g. `LoginRequiredMiddleware` returning a redirect — the bridge converts that into a Reflex `rx.redirect(...)` and skips your handler. You can opt out with `REFLEX_DJANGO_AUTO_REDIRECT_FROM_MIDDLEWARE = False`.

For the full plumbing, see [The WebSocket event pipeline](websocket_event_pipeline.md).

---

## When to use `AppState` vs plain `rx.State` vs `ModelState`

You have three choices. They stack:

| Class | Inherits from | Use it when |
|:---|:---|:---|
| `rx.State` | (Reflex) | The page doesn't need Django context. Pure UI state — counters, filters, modals. |
| **`AppState`** | `rx.State` + the Django bridge | The page reads `request.user` or session, or runs custom Django middleware logic. **Default choice for anything user-aware.** |
| `ModelState` | `AppState` + CRUD machinery | The page is mostly "list, edit, save, delete" rows from one Django model. |

```python
# Pure UI state — no Django needed
class FilterState(rx.State):
    query: str = ""
    sort: str = "newest"


# User-aware state — uses self.user, self.session
class CartState(AppState):
    @rx.event
    async def add(self, product_id: int):
        user = self.request.user
        ...


# CRUD on a model — uses ModelState (which is itself an AppState)
class ProductState(ModelState):
    model = Product
    fields = ["name", "price"]
    # auto-generates load/save/delete handlers and a `data` list
```

A page can use several states at once. Use `rx.State` for the filter bar and `AppState` for the user-specific data. Use `AppState` for one screen and `ModelState` for another. Mix and match freely.

---

## Reading the request

Three equivalent styles. They all read the same per-event request:

```python
# Style A — self.request (on AppState / ModelState handlers)
class CatalogState(AppState):
    @rx.event
    async def search(self, q: str):
        page = self.request.GET.get("page", "1")
        theme = self.request.COOKIES.get("theme", "light")
        if self.request.user.is_authenticated:
            ...


# Style B — module-level request proxy (works in any rx.State too)
from reflex_django import request

class FilterState(rx.State):
    @rx.event
    async def apply(self):
        q = request.GET.get("q", "")
        ...


# Style C — functional helpers (explicit, no inheritance needed)
from reflex_django import current_request, current_user

class FilterState(rx.State):
    @rx.event
    async def apply(self):
        req = current_request()
        user = current_user()
        ...
```

All three return the same `HttpRequest` for the current event. Inside an `AppState` subclass, `self.request` is the most natural — that's what we use throughout these docs.

Outside an event (at import time, in a background thread), there's no request. `self.request` will be `None` and the helpers return anonymous defaults.

---

## Writing to the session

```python
class PreferencesState(AppState):
    @rx.event
    async def set_theme(self, theme: str):
        self.session["theme"] = theme
        await self.session.asave()
```

Use `await self.session.asave()` to persist. The next event for the same user will see the new value.

---

## Adding flash messages

```python
from django.contrib import messages

class CheckoutState(AppState):
    @rx.event
    async def submit(self):
        try:
            ...
            messages.success(self.request, "Order placed!")
        except Exception:
            messages.error(self.request, "Something went wrong.")
```

Then in your UI, bind to `DjangoUserState.messages`:

```python
rx.foreach(
    DjangoUserState.messages,
    lambda m: rx.callout(m.message, color_scheme=m.level_tag),
)
```

---

## A full example — a small profile page

This is what a typical `AppState` page looks like: per-event Django context for the work, reactive variables for the rendering.

```python
# accounts/views.py
import reflex as rx
from reflex_django import template
from reflex_django.state import AppState


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


@template(route="/profile", title="Profile", on_load=ProfileState.on_load)
def profile() -> rx.Component:
    return rx.vstack(
        rx.heading(f"Hi, {ProfileState.username}"),
        rx.text_area(
            value=ProfileState.bio,
            on_change=ProfileState.set_bio,
            placeholder="Tell us about yourself",
        ),
        rx.button("Save", on_click=ProfileState.save),
        rx.cond(ProfileState.saved, rx.callout("Saved!", color_scheme="green")),
        spacing="3",
    )
```

Five things to notice:

1. **`ProfileState(AppState)`** — that one swap is what gives us `self.request.user`.
2. **`on_load` gates by login.** Returning `rx.redirect("/login")` from a handler navigates the browser.
3. **`self.request.user.profile.bio`** — we use the real Django user object. Same auth as `/admin/`.
4. **`await user.profile.asave()`** — async ORM for non-blocking writes.
5. **`ProfileState.username`** in the UI — the reactive snapshot, auto-refreshed on each event.

---

## Avoid storing model instances in state fields

State fields are serialized to JSON and shipped to the browser. Django model instances aren't JSON-serializable. Always convert them to dicts (or use a [serializer](serializers.md)) before assigning:

```python
# wrong — will crash on the JSON roundtrip
self.product = product

# right — primitives only
self.product = {"id": product.id, "name": product.name, "price": str(product.price)}
```

The same applies to `Decimal`, `datetime`, `date` objects — convert to strings first.

---

## Don't read `request.user` at class definition time

Class-level defaults run at import time, when Django's app registry might not be ready and there's certainly no live request. So this is wrong:

```python
# wrong — runs once, at import, with no request
class HomeState(AppState):
    greeting: str = f"Hi, {request.user}"
```

This is right:

```python
class HomeState(AppState):
    greeting: str = "Hi"

    @rx.event
    async def on_load(self):
        if self.request.user.is_authenticated:
            self.greeting = f"Hi, {self.request.user.get_username()}"
```

Class defaults are values, not snapshots of the current user.

---

## A note on `DjangoUserState`

`reflex-django` also ships a smaller class called `DjangoUserState`. It exposes the same reactive variables (`is_authenticated`, `username`, etc.) **without** the per-event `self.request` and `self.user`. Use it when you only need the UI snapshot — for example, a navbar that shows the username:

```python
from reflex_django import DjangoUserState

def navbar():
    return rx.hstack(
        rx.cond(
            DjangoUserState.is_authenticated,
            rx.text(f"Hi, {DjangoUserState.username}"),
            rx.link("Log in", href="/login"),
        ),
    )
```

If your page also needs to perform authenticated actions, use `AppState` instead — it includes everything `DjangoUserState` has plus the live request.

---

## Summary

- Subclass `AppState` whenever a page needs Django context inside event handlers.
- Use `self.request`, `self.user`, `self.session` in handlers — they're real, fresh, server-side.
- Use `AppState.is_authenticated`, `AppState.username`, etc. in components — they're reactive snapshots.
- Never base security decisions on the reactive snapshot alone. Check the live `self.user` in the handler.
- Avoid storing model instances in state fields. Convert to dicts or use a serializer.

---

**Next:** [Talking to the database →](database_integration.md)
