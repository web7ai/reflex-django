# Authentication

Django **session authentication** in Reflex events, a unified **`AppState`** auth bridge, decorators, and optional canned login/register pages.

---

## Prerequisites

- [Django middleware to Reflex](django_middleware_to_reflex.md) — how `DjangoEventBridge` binds `request.user` per event  
- [State management](state_management.md) — plain `rx.State` vs helper states

---

## How authentication reaches Reflex

Reflex UI actions run over **Socket.IO**, not through Django’s HTTP middleware stack. **`DjangoEventBridge`** (enabled by default on `ReflexDjangoPlugin`) rebuilds a synthetic `HttpRequest` for every event, loads the session from the cookie, and resolves `request.user` with Django’s **`aget_user`**—the same auth backends and session store as normal Django views.

```mermaid
flowchart TB
  subgraph browser [Browser]
    UI[Reflex UI]
    Cookie[sessionid cookie]
  end
  subgraph event [Each Reflex event]
    E[Event + router_data]
    Bridge[DjangoEventBridge.preprocess]
    Req[Synthetic HttpRequest]
    Sess[SESSION_ENGINE]
    User[aget_user]
    CTX[current_request / current_user]
    Sync[AppState.refresh_django_user_fields]
    H[Your handler]
  end
  UI --> E
  Cookie --> E
  E --> Bridge --> Req
  Req --> Sess --> User --> CTX
  CTX --> Sync --> H
```

| Path | Middleware | Session | User |
|------|------------|---------|------|
| **HTTP** (`/admin`, `/api`, …) | Full Django `MIDDLEWARE` | `SessionMiddleware` | `AuthenticationMiddleware` |
| **Reflex events** | Bridge only (session + auth + optional i18n) | `SESSION_ENGINE` on synthetic request | `aget_user` in bridge |

There is **no second auth implementation**—handlers use Django’s session row and user model. OAuth, JWT, and multi-tenant auth are not built in yet.

---

## Two layers: live objects vs reactive snapshot

`AppState` (and `DjangoUserState`) expose **two** ways to read auth, on purpose:

| Layer | Where | Use for |
|-------|--------|---------|
| **Live** | `self.user`, `self.session` in `@rx.event` handlers | Authorization, ORM scoping, session writes |
| **Snapshot** | `self.is_authenticated`, `self.username`, `self.email`, … | UI bindings (`rx.cond`, `rx.text`) |

```python
# Live — always current for this event; not sent to the browser as a Reflex var
if self.user.is_authenticated:
    await MyModel.objects.filter(owner=self.user).adelete()

# Snapshot — synced to the client for components
rx.cond(DashboardState.is_authenticated, rx.text(DashboardState.username), ...)
```

**Rule:** Never use snapshot fields alone to allow deletes, admin actions, or private data—always check `self.user` or `require_login_user()` in the handler.

When **`REFLEX_DJANGO_AUTH_AUTO_SYNC`** is `True` (default), the bridge refreshes snapshot fields on every event for **`AppState`** subclasses, so navbars and dashboards update after login/logout without calling `sync_from_django` on every page.

---

## Accessing the Django request on `AppState`

Every Reflex event runs with a **synthetic `HttpRequest`** built by **`DjangoEventBridge`** from `router_data` (path, query string, cookies, headers, client IP). **`AppState`** (and subclasses like **`ModelState`**) expose that request on the state instance so handlers feel like Django views.

### Three equivalent styles

| Style | Where | Best for |
|-------|--------|----------|
| **`self.request`** | `AppState` / `ModelState` handlers | Instance-based code, CRUD hooks (`get_queryset`, …) |
| **`self.django_request`** | Same | When you need the raw `HttpRequest` object |
| **`from reflex_django import request`** | Any `rx.State` handler | Plain `rx.State` without `AppState` |
| **`current_request()` / `current_user()`** | Any handler | Explicit, functional style |

All of them read the **same** bridged request for the current event. Outside an event (import time, background task), there is no request—`request.user` is anonymous and `request.GET` is empty.

```mermaid
flowchart LR
  Bridge[DjangoEventBridge] --> Http[HttpRequest]
  Http --> CTX[current_request contextvar]
  CTX --> SR[self.request / request proxy]
  CTX --> SU[self.user]
  Dispatch[ModelCRUDView.dispatch] --> Bind[bind_request_context]
  Bind --> SR
```

### `self.request` — `DjangoStateRequest` wrapper

On **`AppState`**, **`self.request`** is a **`DjangoStateRequest`** that wraps the synthetic `HttpRequest` and (when context collection runs) merged **context-processor** output.

| Access | What you get |
|--------|----------------|
| **`self.request.user`** | Live Django user (`AnonymousUser` when logged out)—use for ORM filters and authorization |
| **`self.request.django_request`** | Same as **`self.django_request`** — raw `HttpRequest` |
| **`self.request.GET`**, **`.POST`**, **`.path`**, **`.method`**, **`.META`**, **`.COOKIES`** | Forwarded from the underlying `HttpRequest` |
| **`self.request.LANGUAGE_CODE`**, **`self.request.SITE_NAME`**, … | Keys from **`REFLEX_DJANGO_CONTEXT_PROCESSORS`** (when loaded) |
| **`self.request.context`** | `dict` copy of all processor keys (e.g. `context["user"]` for JSON snapshot) |

**`self.user`** is a shortcut for **`self.request.user`** (and **`current_user()`**). Prefer **`self.request.user`** in CRUD hooks for consistency with Django view style.

**Important:** **`self.request.user`** is the **live** user model. Context processors often expose a **JSON `user` snapshot** for templates—that lives in **`self.request.context["user"]`**, not in **`self.request.user`**.

### Example: dashboard handler (plain `AppState`)

```python
import reflex as rx
from reflex_django.state import AppState

class DashboardState(AppState):
    last_path: str = ""

    @rx.event
    async def on_load(self):
        # Auth — same as self.user
        if not self.request.user.is_authenticated:
            return rx.redirect("/login")

        # Query string from the page URL (router_data)
        tab = self.request.GET.get("tab", "overview")

        # Session (also available as self.session["key"])
        self.request.session["last_visit"] = "dashboard"

        # Optional: context processor keys when configured
        site = getattr(self.request, "SITE_NAME", None)

        self.last_path = self.request.path
        return rx.toast.info(f"Tab={tab}, site={site}")
```

### Example: user-scoped CRUD hooks (`ModelState` / `ModelCRUDView`)

During **`dispatch`** (`save`, `refresh`, `load`, …), reflex-django calls **`bind_request_context()`**, which attaches **`self.request`** with context processors when **`load_context_processors`** is `True` (default).

```python
from reflex_django.state import ModelState
from notes.models import Note

class NotesState(ModelState):
    model = Note
    fields = ["title", "content"]
    ordering = ("-id",)

    def get_queryset(self):
        # Scope rows to the logged-in user
        return Note.objects.filter(owner=self.request.user)

    def get_object_lookup(self, pk: int) -> dict:
        return {"pk": pk, "owner": self.request.user}

    def get_create_kwargs(self, state_data: dict) -> dict:
        return {**state_data, "owner": self.request.user}

    def filter_queryset(self, qs):
        # Processor key (settings.REFLEX_DJANGO_CONTEXT_PROCESSORS)
        if getattr(self.request, "LANGUAGE_CODE", None) == "ar":
            qs = qs.filter(locale="ar")
        return qs
```

`ModelState` subclasses **`AppState`**, so you can use **`self.request`** in custom **`@rx.event`** methods as well as in generated CRUD hooks.

### Example: read query params on a plain `rx.State`

When a class does **not** subclass `AppState`, use the module proxy:

```python
import reflex as rx
from reflex_django import request

class SearchState(rx.State):
    @rx.event
    async def run_search(self):
        q = request.GET.get("q", "").strip()
        if not request.user.is_authenticated:
            return rx.toast.error("Sign in to search")
        # ... ORM using request.user
```

Invalid import: `from reflex_django.state import request` — use **`from reflex_django import request`**.

### `self.django_request` — raw `HttpRequest`

Use when a Django API expects the real request object (login, messages, third-party helpers):

```python
from reflex_django.context import current_request
from reflex_django.mixins.session_auth import _sync_session_cookie_then_nav

class AuthState(AppState):
    @rx.event
    async def sign_in_and_go(self):
        ok = await self.login(self.username, self.password)
        if not ok:
            return await self.on_auth_failed()
        http = self.django_request  # or current_request()
        if http is not None:
            return _sync_session_cookie_then_nav(http, "/")
```

### Context processors on `self.request`

Enable processors in Django settings via **`REFLEX_DJANGO_CONTEXT_PROCESSORS`** (see [Django context to Reflex](django_context_to_reflex.md)). During **`ModelCRUDView.dispatch`**, keys are merged onto **`self.request`**:

```python
# Attribute style (template-like)
lang = self.request.LANGUAGE_CODE

# Dict style (explicit)
snapshot = self.request.context.get("user", {})
perms = self.request.context.get("permissions", [])
```

Disable collection but keep the HTTP request:

```python
class PublicState(ModelState):
    model = Article
    fields = ["title", "body"]
    load_context_processors = False  # class body or Meta
```

### What not to do

| Do not | Do instead |
|--------|------------|
| Pass **`self.request.user`** into **`rx.text(...)`** | Use snapshot vars: **`self.username`**, **`self.is_authenticated`** |
| Rely on **`self.is_authenticated`** alone to allow deletes | Check **`self.request.user`** or **`require_login_user()`** in the handler |
| Expect CSRF middleware on Reflex events | Protect mutations with **`@login_required`**, permissions, or Django HTTP views |
| Use **`self.request`** at import time | Only inside **`@rx.event`** handlers (after the bridge runs) |

### HTTP details

Query params, cookies, and headers come from **`event.router_data`**. See [Django middleware to Reflex](django_middleware_to_reflex.md) for the full bridge pipeline and **`from reflex_django import request`** API (`request.headers`, `request.COOKIES`, `request.path`, …).

---

## Quick start

**1. Plugin** (in `rxconfig.py`):

```python
from reflex_django import ReflexDjangoPlugin

config = rx.Config(
    app_name="myapp",
    plugins=[
        ReflexDjangoPlugin(
            settings_module="backend.settings",
            install_event_bridge=True,  # default
        )
    ],
)
```

**2. State** — subclass `AppState`:

```python
import reflex as rx
from reflex_django.state import AppState

class AppStateRoot(AppState):
    """Rename to match your app; shown as one Reflex state tree."""

    @rx.event
    async def on_load(self):
        # Optional: auto-sync usually makes this unnecessary for auth fields
        await self.refresh_django_user_fields()
```

**3. Protect handlers and pages:**

```python
from reflex_django.auth import login_required, permission_required

@rx.event
@login_required
async def members_only(self):
    return self.user.get_username()

@rx.event
@permission_required("shop.view_product", redirect="/login")
async def list_products(self):
    ...
```

---

## Complete example: layout, dashboard, and custom login

This pattern fits apps that use **`AppState`** for both navigation and feature state (no separate `DjangoUserState` class required).

**`myapp/state.py`**

```python
import reflex as rx
from reflex_django.state import AppState


class SiteState(AppState):
    login_username: str = ""
    login_password: str = ""
    login_error: str = ""

    @rx.event
    async def submit_login(self):
        self.login_error = ""
        ok = await self.login(self.login_username, self.login_password)
        if not ok:
            self.login_error = "Invalid username or password."
            self.login_password = ""
            return
        # After login, sync browser cookie (see "Session cookie sync" below)
        from reflex_django.context import current_request
        from reflex_django.mixins.session_auth import _sync_session_cookie_then_nav

        request = current_request()
        if request is not None:
            return _sync_session_cookie_then_nav(request, "/")

    @rx.event
    async def sign_out(self):
        await self.logout()
        from reflex_django.context import current_request
        from reflex_django.mixins.session_auth import _sync_session_cookie_then_nav

        request = current_request()
        if request is not None:
            return _sync_session_cookie_then_nav(
                request, "/login", clear_cookie=True
            )


def navbar() -> rx.Component:
    return rx.hstack(
        rx.link("Home", href="/"),
        rx.spacer(),
        rx.cond(
            SiteState.is_authenticated,
            rx.hstack(
                rx.text("Hi, ", SiteState.username),
                rx.button("Log out", on_click=SiteState.sign_out),
            ),
            rx.link("Sign in", href="/login"),
        ),
        width="100%",
        padding="1rem",
    )


def dashboard_page() -> rx.Component:
    return rx.vstack(
        navbar(),
        rx.heading("Dashboard"),
        rx.cond(
            SiteState.is_staff,
            rx.badge("Staff"),
            rx.fragment(),
        ),
        rx.text("Theme from session: ", SiteState.username),  # bind real vars as needed
        padding="2rem",
    )


def login_page() -> rx.Component:
    return rx.center(
        rx.card(
            rx.heading("Sign in"),
            rx.input(
                placeholder="Username",
                value=SiteState.login_username,
                on_change=SiteState.set_login_username,
            ),
            rx.input(
                placeholder="Password",
                type="password",
                value=SiteState.login_password,
                on_change=SiteState.set_login_password,
            ),
            rx.cond(
                SiteState.login_error != "",
                rx.callout(SiteState.login_error, color_scheme="red"),
            ),
            rx.button("Sign in", on_click=SiteState.submit_login, width="100%"),
            padding="1.5rem",
        ),
        min_height="80vh",
    )
```

**`myapp/myapp.py`**

```python
import reflex as rx
from reflex_django.auth import login_required

from myapp.state import dashboard_page, login_page

app = rx.App()
app.add_page(dashboard_page, route="/", title="Dashboard")
app.add_page(login_page, route="/login", title="Sign in")

# Optional: wrap page function for client-side login gate
@rx.page(route="/settings")
@login_required
def settings_page():
    return rx.heading("Settings")
```

Use **`add_auth_pages(app)`** instead of a custom login page when you want batteries-included UI ([Canned auth pages](#canned-auth-pages) below).

---

## `AppState` API reference

Import:

```python
from reflex_django.state import AppState
```

`AppState` extends `DjangoUserState` and is the recommended base for dashboards and **`ModelCRUDView`** CRUD states.

Handlers (server): **`self.request`**, **`self.django_request`**, **`self.user`**, **`self.session`**.  
UI (reactive): **`self.is_authenticated`**, **`self.username`**, **`self.email`**, …

See [Accessing the Django request on `AppState`](#accessing-the-django-request-on-appstate) for full **`self.request`** examples.

### `self.request` and `self.django_request`

| Property | Type | Role |
|----------|------|------|
| **`self.request`** | `DjangoStateRequest` | **`.user`**, **`.GET`**, **`.path`**, context-processor keys, **`.context`** dict |
| **`self.django_request`** | `HttpRequest \| None` | Raw Django request from the event bridge |

```python
class OrdersState(AppState):
    @rx.event
    async def export_csv(self):
        if not self.request.user.is_staff:
            return await self.on_permission_denied()
        tenant = self.request.GET.get("tenant")
        rows = await Order.objects.filter(tenant_id=tenant).aiterator()
        ...
```

Equivalent: **`from reflex_django import request`** then **`request.user`**, **`request.GET.get("tenant")`** in any `rx.State`.

### `self.user` (property)

Returns the live Django user for the current event (`AnonymousUser` when logged out). Supports everything on your user model: `is_authenticated`, `username`, `email`, `is_staff`, `is_superuser`, and `user.groups` (use async ORM or prefetch in handlers).

```python
class OrdersState(AppState):
    @rx.event
    async def ship_order(self, order_id: int):
        if not self.user.is_authenticated:
            return rx.toast.error("Sign in required")
        order = await Order.objects.aget(pk=order_id, customer=self.user)
        ...
```

Equivalent without `AppState`: `from reflex_django import current_user` then `user = current_user()`, or **`self.request.user`** when you subclass **`AppState`**.

### `self.session` (property)

A **`SessionProxy`** over Django’s session for this event. Reads and writes persist to the session backend; **`__setitem__`** and **`__delitem__`** call `save()` automatically.

```python
class PreferencesState(AppState):
    @rx.event
    async def set_theme(self, theme: str):
        self.session["theme"] = theme  # auto-saved

    @rx.event
    async def clear_theme(self):
        del self.session["theme"]

    @rx.event
    async def load_theme(self) -> str:
        return self.session.get("theme", "light")
```

For bulk updates, you can call `await self.session.asave()` explicitly after several in-memory changes if you bypass the proxy’s setters.

### Snapshot fields (reactive UI)

| Field | Meaning |
|-------|---------|
| `user_id` | Primary key or `None` |
| `username` | `get_username()` |
| `email` | Email address |
| `first_name`, `last_name` | Profile names |
| `is_authenticated` | Logged in |
| `is_staff`, `is_superuser` | Django flags |
| `group_names` | List of group names when loaded |

Refresh manually:

```python
await self.refresh_django_user_fields()
# or
await self.sync_from_django(include_groups=True)
```

Group names are only loaded when `REFLEX_DJANGO_USER_SNAPSHOT_INCLUDE_GROUPS` is `True` or `include_groups=True` is passed.

### `await self.has_perm(perm: str) -> bool`

Async wrapper around Django’s `user.has_perm("app_label.codename")`.

```python
if await self.has_perm("billing.change_invoice"):
    await self._save_invoice()
else:
    return await self.on_permission_denied()
```

### `await self.has_group(name: str) -> bool`

Checks membership by group **name**. Uses `group_names` when already loaded; otherwise one async DB query.

```python
if await self.has_group("editors"):
    self.show_editor_tools = True
```

### `await self.login(username, password, *, login_fields=None) -> bool`

Uses Django’s **`aauthenticate`** (via `aauthenticate_login_fields`) and **`alogin`**. On success, saves the session and refreshes snapshot fields. Returns `False` and calls **`on_auth_failed()`** when credentials fail or no request is bound.

```python
ok = await self.login(email, password, login_fields=("email",))
```

`login_fields` defaults to `REFLEX_DJANGO_AUTH["LOGIN_FIELDS"]` or `("username",)`.

### `await self.logout() -> None`

Calls **`alogout`**, saves the session, and refreshes snapshot fields. Pair with cookie sync JS when you need the browser’s `sessionid` updated ([Session cookie sync](#session-cookie-sync-after-login)).

### Hooks

```python
class BrandedState(AppState):
    async def on_auth_failed(self):
        self.login_error = "We could not sign you in."
        return rx.toast.error("Invalid credentials")

    async def on_permission_denied(self):
        return rx.redirect("/forbidden")
```

Default `on_permission_denied` shows a generic error toast.

---

## Server-side authorization (without decorators)

Use these inside any `rx.State` or `AppState` handler:

```python
from reflex_django import current_user, require_login_user
from reflex_django.auth import auser_has_perm, ReflexDjangoAuthError

@rx.event
async def delete_item(self, item_id: int):
    try:
        user = require_login_user()
    except ReflexDjangoAuthError:
        return rx.toast.error("Sign in required")

    if not await auser_has_perm(user, "shop.delete_product"):
        return rx.toast.error("Permission denied")

  # safe to delete
```

`require_login_user()` raises when the user is anonymous—useful when you want explicit error handling instead of `rx.redirect`.

---

## Decorators

Import from `reflex_django.auth` or `from reflex_django import login_required, permission_required`.

### `@login_required`

Works on **page functions** (no `self`) and **event handlers** (`async def handler(self, ...)`).

```python
from reflex_django.auth import login_required

# Page: UI gate using DjangoAuthState snapshot + redirect on mount
@rx.page(route="/dashboard")
@login_required
def dashboard():
    return rx.heading("Members only")

# Event: server check + rx.redirect when anonymous
class SecretState(AppState):
    @rx.event
    @login_required(login_url="/login")
    async def load_secret(self):
        return {"data": "classified"}
```

| Parameter | Default | Role |
|-----------|---------|------|
| `login_url` | `REFLEX_DJANGO_LOGIN_URL` | Redirect target for anonymous users on **events** |

> **Warning:** Page decorators only affect what the **client** renders first. Always protect events that return or mutate private data.

### `@permission_required`

**Event handlers** enforce the permission with `auser_has_perm`. **Pages** gate on login (and optional `fallback` component); enforce fine-grained permissions in `on_load` events or handler methods.

```python
from reflex_django.auth import permission_required

class CatalogState(AppState):
    @rx.event
    @permission_required("products.view_product", redirect="/login")
    async def load_catalog(self):
        return await Product.objects.all().values_list("name", flat=True)

    @rx.event
    @permission_required(
        "products.delete_product",
        on_denied=lambda self: rx.toast.error("Not allowed"),
    )
    async def delete_product(self, product_id: int):
        await Product.objects.filter(pk=product_id).adelete()
```

| Parameter | Role |
|-----------|------|
| `perm` | Django permission string (`app_label.codename`) |
| `redirect` | `rx.redirect` target when denied (handlers) |
| `login_url` | Used when anonymous (falls back to redirect) |
| `fallback` | Page-only: component factory when not authenticated |
| `on_denied` | Event-only: `callable(state)` return value (e.g. toast, redirect) |

If `on_denied` is omitted and the state defines `on_permission_denied`, that method is awaited.

---

## Settings

| Setting | Default | Meaning |
|---------|---------|---------|
| `REFLEX_DJANGO_AUTH_AUTO_SYNC` | `True` | Refresh `AppState` snapshot vars on each event |
| `REFLEX_DJANGO_USER_SNAPSHOT_INCLUDE_GROUPS` | `False` | Include `group_names` in sync (extra query) |
| `REFLEX_DJANGO_LOGIN_URL` | `/login` | Default redirect for decorators |
| `REFLEX_DJANGO_AUTH` | (see README) | Canned pages, routes, `LOGIN_FIELDS`, messages |

Disable auto-sync if you need to minimize per-event work and will call `sync_from_django` yourself:

```python
# settings.py
REFLEX_DJANGO_AUTH_AUTO_SYNC = False
```

---

## Session cookie sync after login

Reflex events **do not** run `SessionMiddleware`, so `alogin` may not send `Set-Cookie` to the browser. Without syncing, the next full page load can still send an old `sessionid`.

**After `await self.login(...)` or registration**, mirror the cookie and navigate:

```python
from reflex_django.context import current_request
from reflex_django.mixins.session_auth import _sync_session_cookie_then_nav

request = current_request()
if request is not None:
    return _sync_session_cookie_then_nav(request, "/")  # post-login path
```

Logout with cookie clear:

```python
await self.logout()
return _sync_session_cookie_then_nav(request, "/login", clear_cookie=True)
```

Lower-level helpers: `session_cookie_set_js`, `session_cookie_clear_js` from `reflex_django`.

**HttpOnly cookies:** JS cookie mirroring cannot set `HttpOnly`; see Django `SESSION_COOKIE_HTTPONLY` tradeoffs in production.

---

## `AppState` + `ModelCRUDView`

CRUD states should inherit **`AppState`** so list/save/delete handlers can use **`self.request.user`** (or **`self.user`**) and default `login_required` wrapping. **`ModelCRUDView.dispatch`** calls **`bind_request_context()`** before hooks run—use **`self.request`** inside **`get_queryset`**, **`get_create_kwargs`**, etc.

```python
from reflex_django.state import AppState, ModelCRUDView
from reflex_django.state.mixins.scoping import UserScopedMixin

class NotesState(AppState, ModelCRUDView, UserScopedMixin):
    scope_field = "user_id"

    class Meta:
        serializer = NoteSerializer
        list_var = "notes"

    def get_queryset(self, ctx):
        # self.user is available in hooks
        return super().get_queryset(ctx).filter(user=ctx.user)
```

Generated handlers call `require_login_user()` when the action is listed in `Meta.login_required_actions`.

---

## `DjangoUserState` without `AppState`

`DjangoUserState` is the same auth mixin without `AppStateMeta` / CRUD assembly. Use it for a **navbar-only** state or with **`session_auth_mixin`**:

```python
from reflex_django import DjangoUserState
from reflex_django.mixins import SessionAuthConfig, session_auth_mixin

LoginState = session_auth_mixin(
    SessionAuthConfig(
        post_login_redirect="/",
        post_logout_redirect="/login",
    ),
    base=DjangoUserState,
)
```

`DjangoAuthState` (canned auth pages) is a flat class built from `DjangoUserState` + login/register/reset mixins.

---

## Canned auth pages

**Settings** (`backend/settings.py`):

```python
REFLEX_DJANGO_AUTH = {
    "SIGNUP_ENABLED": True,
    "PASSWORD_RESET_ENABLED": True,
    "LOGIN_URL": "/login",
    "SIGNUP_URL": "/register",
    "LOGIN_REDIRECT_URL": "/",
    "LOGIN_FIELDS": ["username"],  # or ["email"] or ["username", "email"]
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "noreply@localhost"
```

**App module:**

```python
from reflex_django.auth import add_auth_pages, login_required

app = rx.App()
add_auth_pages(app)

app.add_page(index, route="/", on_load=...)  # your pages

@login_required
def dashboard():
    return rx.heading("Members only")
```

Pages: `LoginPage`, `RegisterPage`, `PasswordResetPage`, `PasswordResetConfirmPage`. Customize via `BaseAuthPage` hooks or `REFLEX_DJANGO_AUTH["MESSAGES"]`.

See [README authentication section](../README.md) for the full `REFLEX_DJANGO_AUTH` key table.

---

## Choosing an API

| Goal | Recommended API |
|------|-----------------|
| Navbar / `rx.cond` on login | `AppState` snapshot fields + auto-sync |
| Check permission in handler | `await self.has_perm(...)` or `@permission_required` |
| Scoped queryset | `self.user` in `get_queryset` / `filter(user=self.user)` |
| Custom login form | `await self.login(...)` + `_sync_session_cookie_then_nav` |
| Ready-made auth UI | `add_auth_pages(app)` + `DjangoAuthState` |
| No AppState in this class | `current_user()` in plain `rx.State` |

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|----------------|-----|
| `current_user()` always anonymous | Event bridge off | `install_event_bridge=True` on plugin |
| `self.request.user` always anonymous | Same as above | Enable bridge; ensure `sessionid` cookie is sent |
| `AttributeError` on `self.request` outside event | No bridged request | Only access inside `@rx.event` handlers |
| `self.request.SITE_NAME` missing | Processors not loaded | Set `REFLEX_DJANGO_CONTEXT_PROCESSORS`; use CRUD `dispatch` or `bind_request_context` |
| Confused `request.user` in UI | User model in component tree | Use `self.username` / `self.is_authenticated` in `rx.*` |
| Login works once, next event anonymous | Browser cookie stale | `_sync_session_cookie_then_nav` after login |
| UI shows logged out while handler sees user | Snapshot not synced | Enable `REFLEX_DJANGO_AUTH_AUTO_SYNC` or `on_load=State.sync_from_django` |
| `RuntimeError: No Django session` | Handler outside event / bridge failed | Ensure bridge runs; check logs for preprocess errors |
| Permission always denied | Wrong codename or user lacks perm | Verify in Django admin; use `user.has_perm` in shell |
| `ImportError: _session_async_save` | Old import path | Use `from reflex_django.state.auth_bridge import session_async_save` |

---

## Security checklist

1. Authorize **mutations** with **`self.request.user`**, **`self.user`**, `require_login_user()`, or `has_perm`—not `is_authenticated` alone on the client.  
2. Use **`@login_required`** / **`@permission_required`** on events that return private data.  
3. Use a stable **`SECRET_KEY`** in production (password reset tokens).  
4. Set **`SIGNUP_ENABLED=False`** if only admins may create users.  
5. Scope querysets to **`self.request.user`** (or `UserScopedMixin`) for multi-user data.

---

## See also

- [State management](state_management.md) — plain `rx.State` vs helpers  
- [Django middleware to Reflex](django_middleware_to_reflex.md) — bridge internals  
- [CRUD with mixins](crud_with_mixins_and_states.md) — `ModelCRUDView`  
- [Best practices](best_practices.md)

---

**Navigation:** [← Forms and validation](forms_and_validation.md) | [Next: API integration →](api_integration.md)
