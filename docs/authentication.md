# Login & sessions

Django auth, but it works inside Reflex events too. You log in once at `/admin/` (or through `reflex-django`'s built-in login page) and from then on every `@rx.event` handler sees `self.request.user` — the real user, from the real session, with the real permissions.

This page covers the patterns you'll actually use: gating handlers, gating pages, the built-in login UI, and the small "live vs snapshot" rule that catches everyone once.

---

## How auth actually reaches a Reflex event

You probably remember from [How the two fit together](how_they_fit.md): Reflex events arrive on a WebSocket, where Django middleware doesn't normally run. `reflex-django` fixes that with the `DjangoEventBridge` — a small piece that, on every event:

1. Builds a synthetic `HttpRequest` from the WebSocket payload (cookies, headers, path).
2. Runs your `settings.MIDDLEWARE` chain on it — including `SessionMiddleware` and `AuthenticationMiddleware`.
3. Eagerly resolves `request.user` with Django's async `aget_user`.
4. Binds the result onto your `AppState` instance.

The cookie is the same `sessionid` cookie Django sets when you log in. The session row is the same row from `django_session`. There is no second auth system. If `request.user.is_authenticated` is `True` for `/admin/`, it's also `True` for the next Reflex event.

---

## The "live vs snapshot" rule (read this once)

`AppState` exposes the user in **two** ways. They look similar; one is safe for security checks and one isn't.

| What it is | Where to use it |
|:---|:---|
| **`self.request.user`** (or `self.user`) — the live Django user for this event, computed server-side | Inside `@rx.event` handlers. Use for authorization, ORM filters, mutations. |
| **`self.is_authenticated`**, **`self.username`**, **`self.email`**, … — reactive snapshot fields | Inside components (`rx.cond`, `rx.text`). Use for UI rendering only. |

The reactive snapshot is shipped to the browser. Browser state can be tampered with. **Never** base a security decision on the snapshot alone.

```python
# wrong — relies on browser-visible flag
@rx.event
async def delete_post(self, post_id: int):
    if self.is_authenticated and self.is_staff:    # snapshot — spoofable
        await Post.objects.filter(pk=post_id).adelete()

# right — checks the live user
@rx.event
async def delete_post(self, post_id: int):
    if self.request.user.is_authenticated and self.request.user.is_staff:
        await Post.objects.filter(pk=post_id).adelete()
```

Easier rule: in handlers, use `self.request.user`. In components, use `self.is_authenticated` / `self.username`.

---

## Gating handlers with decorators

`reflex-django` ships two decorators for the most common cases:

```python
from reflex_django.auth import login_required, permission_required

class PostState(AppState):

    @rx.event
    @login_required
    async def create(self):
        # self.request.user is guaranteed to be authenticated here
        await Post.objects.acreate(owner=self.request.user, title=self.title)

    @rx.event
    @permission_required("blog.change_post")
    async def edit(self, post_id: int):
        ...

    @rx.event
    @permission_required("blog.delete_post", redirect="/login")
    async def delete(self, post_id: int):
        ...
```

If the user isn't authenticated (or doesn't have the permission), the handler doesn't run. The decorator returns a `rx.redirect(...)` to `REFLEX_DJANGO_LOGIN_URL` (default: `/login`).

You can also do explicit checks if you need finer-grained control:

```python
from reflex_django.auth import require_login_user

@rx.event
async def custom_check(self):
    user = require_login_user()    # raises if not authenticated
    ...
```

---

## Gating whole pages

Wrap a page function with `@login_required` and Reflex will redirect anonymous visitors:

```python
import reflex as rx
from reflex_django import template
from reflex_django.auth import login_required

@template(route="/account", title="Account")
@login_required
def account() -> rx.Component:
    return rx.text("Members only.")
```

Or, if you want to control the redirect target per page:

```python
@template(route="/billing")
@login_required(login_url="/login?next=/billing")
def billing() -> rx.Component:
    ...
```

---

## Reading the user in handlers

Inside any `@rx.event async def` on an `AppState` subclass:

```python
class OrdersState(AppState):
    @rx.event
    async def my_orders(self):
        user = self.request.user
        if not user.is_authenticated:
            return rx.redirect("/login")
        self.orders = [
            {"id": o.id, "total": str(o.total)}
            async for o in Order.objects.filter(customer=user)
        ]
```

Everything you know about Django users works here:

- `user.is_authenticated`, `user.is_staff`, `user.is_superuser`
- `user.username`, `user.email`, `user.get_full_name()`
- `await user.aget_all_permissions()`, `user.has_perm("app.codename")` (sync-safe in this context — the bridge eager-resolves)
- `user.groups` (use async ORM or prefetch in heavy code paths)

For ORM queries, scope by `owner=user` (or `tenant=user.tenant`, etc.) — same pattern as in Django views.

---

## Reading and writing the session

```python
class PreferencesState(AppState):
    @rx.event
    async def set_theme(self, theme: str):
        self.session["theme"] = theme
        await self.session.asave()

    @rx.event
    async def on_load(self):
        self.theme = self.session.get("theme", "light")
```

The session is the same per-user session backed by `django_session`. It's shared between HTTP requests and Reflex events.

---

## Flash messages

Add messages from a handler:

```python
from django.contrib import messages

@rx.event
async def submit(self):
    try:
        ...
        messages.success(self.request, "Saved.")
    except Exception:
        messages.error(self.request, "Couldn't save.")
```

Render them in your UI by binding to the reactive `DjangoUserState.messages` list:

```python
from reflex_django import DjangoUserState

def message_banner():
    return rx.foreach(
        DjangoUserState.messages,
        lambda m: rx.callout(m.message, color_scheme=m.level_tag),
    )
```

Each message has `level`, `level_tag`, `message`, `tags`, and `extra_tags`.

---

## The built-in auth pages

If you want login, register, password-reset, and password-reset-confirm pages without writing them, drop one call into your `views.py`:

```python
# shop/views.py
from reflex_django.auth import add_auth_pages

add_auth_pages()
```

That registers four routes (with sensible defaults):

| Route | What it does |
|:---|:---|
| `/login` | Username/password sign in |
| `/register` | Create a new user |
| `/password_reset` | Send a reset email |
| `/password_reset_confirm` | Set a new password |

### Customizing them

Put a `REFLEX_DJANGO_AUTH` dict in `settings.py` to change titles, URLs, or behavior:

```python
REFLEX_DJANGO_AUTH = {
    "login_url": "/sign-in",
    "register_url": "/sign-up",
    "post_login_url": "/dashboard",
    "post_logout_url": "/",
    "username_field": "email",
    "min_password_length": 10,
    "register_enabled": True,
    "password_reset_enabled": True,
    "page_titles": {
        "login": "Sign in to MyShop",
        "register": "Create your account",
    },
}
```

To register pages individually instead of all at once:

```python
from reflex_django.auth import register_login_page, register_register_page

register_login_page()
register_register_page()
```

---

## Custom login flow

If you want a fully custom login page, use the `login`/`logout` helpers on `AppState`:

```python
class AuthState(AppState):
    username: str = ""
    password: str = ""
    error: str = ""

    @rx.event
    async def submit(self):
        self.error = ""
        ok = await self.login(self.username, self.password)
        if not ok:
            self.error = "Invalid username or password."
            self.password = ""
            return
        return rx.redirect("/")

    @rx.event
    async def sign_out(self):
        await self.logout()
        return rx.redirect("/login")
```

`await self.login(...)` calls Django's `aauthenticate` + `alogin` and updates the session. `await self.logout()` calls `alogout`.

### A note on cookie sync after login

Reflex's WebSocket connection was opened with the *anonymous* session cookie. After `self.login(...)`, Django updates the session row server-side, but the browser still has the old cookie until the next HTTP response sets it. For most apps this is fine — the next HTTP navigation or page load updates the cookie. If you want it to update immediately, redirect through an HTTP response:

```python
from reflex_django.context import current_request
from reflex_django.mixins.session_auth import _sync_session_cookie_then_nav

@rx.event
async def submit(self):
    ok = await self.login(self.username, self.password)
    if not ok:
        self.error = "Invalid credentials"
        return
    return _sync_session_cookie_then_nav(current_request(), "/")
```

That issues a real HTTP redirect that carries the fresh `Set-Cookie` header.

---

## Login UI snapshot vs `AppState` snapshot

A small detail that occasionally trips people up.

There are **two** ways the UI can react to login state:

1. **Inheriting from `AppState`** — `MyState.is_authenticated`, `MyState.username`. These are part of your normal state tree and update via the per-event refresh.
2. **`DjangoAuthState`** — a separate, lightweight Reflex state shipped with the built-in auth pages. Its `is_authenticated` is a `@rx.var` (a computed reactive variable) that calls `current_user()` each time, independent of your `AppState` subtree.

```python
from reflex_django.auth import DjangoAuthState

def navbar():
    return rx.hstack(
        rx.cond(
            DjangoAuthState.is_authenticated,
            rx.text("logged in"),
            rx.link("Sign in", href="/login"),
        ),
    )
```

If you use `add_auth_pages()`, `DjangoAuthState` is registered automatically. If your app uses `AppState` everywhere, `MyState.is_authenticated` is enough.

When `REFLEX_DJANGO_AUTH_AUTO_SYNC = True` (default), the bridge refreshes the snapshot fields on every event for all `AppState` subclasses. You usually don't need to call `await self.refresh_django_user_fields()` yourself.

---

## Permission checks

```python
# In a handler
if await self.user.ahas_perm("blog.delete_post"):
    ...

# Or via decorator
@rx.event
@permission_required("blog.delete_post", redirect="/login")
async def delete_post(self, post_id: int):
    ...

# Or read all permissions
perms = await self.user.aget_all_permissions()
```

The reactive `self.perms` field (a JSON-safe list of `app.codename` strings) is fine for UI hiding/showing, but again: only use it for visual hints, not for actual access checks.

---

## Common patterns

### Optional login on a page

```python
@template(route="/", on_load=HomeState.on_load)
def home() -> rx.Component:
    return rx.cond(
        HomeState.is_authenticated,
        rx.text(f"Hi, {HomeState.username}"),
        rx.text("Hello, guest."),
    )


class HomeState(AppState):
    @rx.event
    async def on_load(self):
        # AppState auto-refreshes is_authenticated/username; no extra work needed.
        pass
```

### Required login on a page

```python
@template(route="/dashboard", on_load=DashboardState.on_load)
def dashboard() -> rx.Component:
    return rx.heading("Dashboard")


class DashboardState(AppState):
    @rx.event
    async def on_load(self):
        if not self.request.user.is_authenticated:
            return rx.redirect("/login?next=/dashboard")
```

### Required role/permission

```python
class AdminToolsState(AppState):
    @rx.event
    @permission_required("staff.view_admin_tools", redirect="/login")
    async def on_load(self):
        ...
```

### Owner-scoped CRUD

```python
class TodosState(AppState):
    todos: list[dict] = []

    @rx.event
    async def load(self):
        if not self.request.user.is_authenticated:
            self.todos = []
            return
        self.todos = [
            {"id": t.id, "title": t.title}
            async for t in Todo.objects.filter(owner=self.request.user)
        ]
```

For the `ModelState`/`ModelCRUDView` equivalent of "scope to current user", see the [user-scoping section in the CRUD guide](crud_with_mixins_and_states.md).

---

## What about CSRF on Reflex events?

`CsrfViewMiddleware` is intentionally **skipped** on Reflex WebSocket events. CSRF protects HTML form submissions where a third-party site could trigger a request with the user's cookies. A persistent WebSocket initiated by your own SPA doesn't have that attack shape — and Reflex events can't be triggered from a third-party origin anyway because of same-origin enforcement on the WebSocket.

If you need extra protection on a mutation, prefer:

- `@login_required` / `@permission_required` decorators on the handler.
- Server-side checks on `self.request.user` before mutating.
- For truly sensitive operations (account deletion, password change), require re-authentication or perform them through a dedicated Django HTTP view.

The CSRF token itself is still available on `self.csrf_token` and `DjangoUserState.csrf_token` for any forms you POST through HTTP.

---

## What's not built in (yet)

`reflex-django` ships Django session auth. It does **not** ship:

- OAuth / OIDC providers (use `django-allauth` or `social-auth-app-django` with your normal Django setup; the session it produces works inside Reflex too)
- JWT
- Multi-tenant auth

These work fine through Django — the built-in middleware-based session is the integration point. Wire `django-allauth` as usual; users who log in through Google will have `request.user.is_authenticated == True` inside `@rx.event` handlers automatically.

---

## Cheat sheet

| You want to… | Do this |
|:---|:---|
| Get the live user in a handler | `self.request.user` |
| Show "Hi, name" in the UI | `rx.text(f"Hi, {AppState.username}")` |
| Gate a handler by login | `@login_required` |
| Gate a handler by permission | `@permission_required("app.codename")` |
| Gate a whole page | wrap the page function with `@login_required` |
| Log a user in from code | `await self.login(username, password)` |
| Log a user out | `await self.logout()` |
| Read the session | `self.session["key"]` |
| Write the session | `self.session["key"] = value; await self.session.asave()` |
| Add a flash message | `messages.success(self.request, "Saved")` |
| Render flash messages | `rx.foreach(DjangoUserState.messages, ...)` |
| Use built-in login/register/reset pages | `add_auth_pages()` in any `views.py` |

---

**Next:** [CRUD the manual way →](crud_without_mixins.md) · [Or: jump to CRUD with ModelState →](reactive_model_state.md)
