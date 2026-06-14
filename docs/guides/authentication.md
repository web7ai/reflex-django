---
level: beginner
tags: [auth, sessions]
---

# Login and sessions

**What you'll learn:** How Django session auth reaches Reflex event handlers, how to gate pages and handlers, and how to customize the built-in login UI.

**When you need this:**

- You need `request.user` inside an `@rx.event` handler or want login-only pages.
- You want the canned login, register, and password-reset pages with your branding.

---

Django auth works inside Reflex events. Log in once at `/admin/` or through reflex-django's built-in login page, and every `@rx.event` handler sees `self.request.user` from the real session.

There is no second auth system. Same `sessionid` cookie, same `django_session` row.

---

## How auth reaches a Reflex event

Reflex events arrive on a WebSocket where Django middleware does not normally run. reflex-django's **`DjangoEventBridge`** fixes that on every event:

1. Build a synthetic `HttpRequest` from the WebSocket payload (cookies, headers, path).
2. Run `settings.MIDDLEWARE`, including sessions and authentication.
3. Eagerly resolve `request.user` with Django's async `aget_user`.
4. Bind the result onto your `AppState` instance.

If `request.user.is_authenticated` is `True` for `/admin/`, it is also `True` for the next Reflex event.

See [How they fit together](../overview/concepts.md) and [WebSocket event pipeline](../internals/event_pipeline.md) for the full picture.

---

## The live vs snapshot rule

`AppState` exposes the user in **two** ways:

| What it is | Where to use it |
|:---|:---|
| **`self.request.user`** / **`self.user`**, live user for this event | Handlers: authorization, ORM filters, mutations. |
| **`self.is_authenticated`**, **`self.username`**, **`self.email`**, …, reactive snapshots | Components: `rx.cond`, labels, nav bars. |

The reactive snapshot is sent to the browser. **Never** base a security decision on it alone.

```python
# wrong, snapshot is spoofable
@rx.event
async def delete_post(self, post_id: int):
    if self.is_authenticated and self.is_staff:
        await Post.objects.filter(pk=post_id).adelete()

# right, live user
@rx.event
async def delete_post(self, post_id: int):
    if self.request.user.is_authenticated and self.request.user.is_staff:
        await Post.objects.filter(pk=post_id).adelete()
```

Easier rule: handlers use `self.request.user`. Components use `self.is_authenticated` / `self.username`.

---

## Gating handlers

```python
from reflex_django.auth import login_required, permission_required
from reflex_django.states import AppState

class PostState(AppState):

    @rx.event
    @login_required
    async def create(self):
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

If the user is not authenticated (or lacks permission), the handler does not run. The decorator returns `rx.redirect(...)` to `RX_LOGIN_URL` (default `/login`).

For explicit checks:

```python
from reflex_django.auth import require_login_user

@rx.event
async def custom_check(self):
    user = require_login_user()
    ...
```

---

## Gating whole pages

Recommended: pass `login_required=True` on `@page`:

```python
from reflex_django.pages.decorators import page

@page(route="/account", title="Account", login_required=True)
def account() -> rx.Component:
    return rx.text("Members only.")
```

Or stack `@login_required` below `@page`, or pass a custom `login_url`:

```python
@page(route="/billing")
@login_required(login_url="/login?next=/billing")
def billing() -> rx.Component:
    ...
```

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

@rx.event
async def submit(self):
    messages.success(self.request, "Saved.")
```

Render with `DjangoUserState.messages`:

```python
from reflex_django.states import DjangoUserState

rx.foreach(
    DjangoUserState.messages,
    lambda m: rx.callout(m.message, color_scheme=m.level_tag),
)
```

---

## Built-in auth pages

When `RX_AUTH["ENABLED"]` is true (default), auth pages register automatically during page preparation (import/compile time). No `views.py` boilerplate required.

| Route | What it does |
|:---|:---|
| `/login` | Username/password sign in |
| `/register` | Create a new user |
| `/password-reset` | Send a reset email |
| `/password-reset/confirm/[uid]/[key]` | Set a new password |

Customize URLs and behavior in settings:

```python
--8<-- "snippets/auth_settings.py"
```

To register pages individually:

```python
from reflex_django.auth import register_login_page, register_register_page

register_login_page()
register_register_page()
```

For explicit control over the whole set, call `add_auth_pages(app)` in an advanced setup.

---

## Make it yours

Customize the canned login, register, and password-reset pages from `RX_AUTH` in `settings.py`. No subclasses required for text and logo changes.

### Text and logo only

```python
--8<-- "snippets/auth_branding_settings.py"
```

`BRAND_TEXT` or `BRAND_ICON_SRC` replaces the default icon above form headings on login and register pages. Override copy with the `MESSAGES` dict (headings, button labels, validation strings, and more).

### Custom layout (shell, card, gradients)

When settings are not enough, subclass `LoginPage`, `RegisterPage`, or related base classes and point to them with `PAGE_CLASSES`:

```python
RX_AUTH = {
    "PAGE_CLASSES": {
        "login": "myapp.auth.BrandedLoginPage",
        "register": "myapp.auth.BrandedRegisterPage",
        "password_reset": "myapp.auth.BrandedPasswordResetPage",
        "password_reset_confirm": "myapp.auth.BrandedPasswordResetConfirmPage",
    },
}
```

Override `shell()`, `card()`, and `heading()` on a shared mixin. Keep form logic in reflex-django base classes.

!!! tip "Start with settings"
    Try `BRAND_TEXT`, `BRAND_ICON_SRC`, and `MESSAGES` first. Reach for `PAGE_CLASSES` only when you need a different shell or card layout.

---

## Custom login flow

For a fully custom login page, use `login` / `logout` on `AppState`:

```python
from reflex_django.states import AppState

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

`await self.login(...)` calls Django's `aauthenticate` + `alogin`. `await self.logout()` calls `alogout`.

### Cookie sync after login

After `self.login(...)`, the browser may still hold the anonymous session cookie until the next HTTP response sets a fresh one. For most apps a redirect is enough. To force an immediate cookie update:

```python
from reflex_django.bridge.context import current_request
from reflex_django.mixins.session_auth import _sync_session_cookie_then_nav

@rx.event
async def submit(self):
    ok = await self.login(self.username, self.password)
    if not ok:
        self.error = "Invalid credentials"
        return
    return _sync_session_cookie_then_nav(current_request(), "/")
```

### Cookie sync after logout

Use the built-in `DjangoAuthState.logout` event, or pair `await self.logout()` with `_sync_session_cookie_then_nav(..., clear_cookie=True)`. Bare `rx.redirect("/login")` after logout can leave stale `sessionid` cookies and a stale Reflex websocket `token`, causing a `/` ↔ `/login` redirect loop.

```python
from reflex_django.bridge.context import current_request
from reflex_django.mixins.session_auth import _sync_session_cookie_then_nav

@rx.event
async def sign_out(self):
    await self.logout()
    return _sync_session_cookie_then_nav(current_request(), "/login", clear_cookie=True)
```

Built-in `AppState.logout()` and `DjangoAuthState.logout` also call `invalidate_event_cache()` so the event bridge drops cached auth metadata for that session. Custom logout handlers should do the same:

```python
from reflex_django.bridge import invalidate_event_cache

await self.logout()
invalidate_event_cache(session_key=getattr(self.session, "session_key", None))
```

---

## Browser storage: Django `sessionid` vs Reflex `token`

Django session auth uses the **`sessionid` cookie** (backed by the `django_session` table and `request.user`). Reflex stores a separate per-tab UUID in **`sessionStorage` under key `token`** (`router.session.client_token`) for WebSocket state identity  -  it is **not** login state.

| Storage | Cleared on logout? | Notes |
|:---|:---|:---|
| `sessionid` / `csrftoken` cookies | Yes | Expired via `document.cookie` (requires `SESSION_COOKIE_HTTPONLY = False` in reflex-django defaults, or an HTTP cookie-sync view) |
| `sessionStorage.token` | Yes | Removed so the next page load gets a fresh websocket client id |
| `localStorage` | **No** | Theme and other app prefs are preserved |
| Non-auth cookies (e.g. `theme=dark`) | **No** | Only auth cookie names are stripped |

Built-in login/logout navigation clears the Reflex `token`, syncs `sessionid`, and uses `window.location.replace(...)` for a clean document load. Custom handlers that skip `_sync_session_cookie_then_nav` may need manual DevTools cookie/storage clears to recover.

The built-in login page runs `on_load_login` for anonymous visitors: it expires any visible stale `sessionid` / `csrftoken` cookies (including variants with different path/domain attributes). Submitting the login form also rotates to a fresh Django session server-side before `alogin`, so a leftover browser cookie cannot reuse the pre-logout session row.

Bundled defaults set `SESSION_COOKIE_HTTPONLY = False` because Reflex WebSocket events do not deliver Django `Set-Cookie` headers to the browser. Production apps that require HttpOnly session cookies should expose a small HTTP view that sets cookies and reloads the SPA.

Configure session keys to keep across logout (server-side prefs only):

```python
RX_LOGOUT_PRESERVE_SESSION_KEYS = ("theme",)
```

---

## Navbar auth: `DjangoAuthState`

Built-in auth pages register `DjangoAuthState`, a lightweight state whose `is_authenticated` is a computed `@rx.var`:

```python
from reflex_django.auth import DjangoAuthState

def navbar():
    return rx.cond(
        DjangoAuthState.is_authenticated,
        rx.text("Logged in"),
        rx.link("Sign in", href="/login"),
    )
```

If your app uses `AppState` everywhere, `MyState.is_authenticated` is usually enough. When `RX_AUTH_AUTO_SYNC = True` (default), snapshot fields refresh on every event.

---

## Permission checks

```python
if await self.user.ahas_perm("blog.delete_post"):
    ...

@rx.event
@permission_required("blog.delete_post", redirect="/login")
async def delete_post(self, post_id: int):
    ...
```

Reactive `self.perms` is fine for hiding UI elements, not for access control.

---

## CSRF on Reflex events

`CsrfViewMiddleware` is skipped on WebSocket events by design. CSRF protects cross-site HTML form posts; Reflex events are same-origin WebSocket messages initiated by your SPA.

For mutations, prefer `@login_required` / `@permission_required` and server-side checks on `self.request.user`. The CSRF token remains available on `self.csrf_token` and `DjangoUserState.csrf_token` for HTTP form posts.

---

## What is not built in

reflex-django ships Django session auth. It does **not** ship OAuth, OIDC, JWT, or multi-tenant auth out of the box.

Wire `django-allauth` or similar through normal Django setup. Users who log in through Google still get `request.user.is_authenticated == True` inside handlers automatically.

---

## Cheat sheet

| You want to… | Do this |
|:---|:---|
| Live user in a handler | `self.request.user` |
| Show "Hi, name" in the UI | `AppState.username` in components |
| Gate a handler | `@login_required` |
| Gate by permission | `@permission_required("app.codename")` |
| Gate a whole page | `@page(..., login_required=True)` |
| Log in from code | `await self.login(username, password)` |
| Log out | `await self.logout()` |
| Brand built-in auth pages | `RX_AUTH`, see [Make it yours](#make-it-yours) |
| Render flash messages | `rx.foreach(DjangoUserState.messages, ...)` |

---

## What just happened?

You learned that Django session auth flows through the event bridge into `self.request.user`, that snapshots are for UI only, and that built-in auth pages register at compile time and customize through `RX_AUTH`.

---

**Next up:** [Media files](media.md)