# Auth

Django session auth works inside Reflex events. Users can log in through Django admin, built-in reflex-django auth pages, or custom handlers. Bridge-bound handlers on `AppState` see the live Django user through `self.request.user`.

## Live user vs UI snapshot

| Use in handlers | Use in UI |
|:---|:---|
| `self.request.user` | `self.is_authenticated` |
| `current_user()` | `self.username` |
| Django permission checks | Show/hide buttons |

Never authorize from the reactive snapshot alone. It is client-visible and can lag behind the session.

## Built-in auth pages

Built-in login, signup, and password-reset pages are explicit opt-in. They are not mounted just because `reflex_django` is installed or `RX_AUTH["ENABLED"]` is true.

Register them from `{app}/{app}.py`:

```python
--8<-- "snippets/auth_app_entry.py"
```

Configure routes, field names, redirects, messages, and optional custom page classes in `settings.py`:

```python
--8<-- "snippets/auth_settings.py"
```

Branding and custom classes:

```python
--8<-- "snippets/auth_branding_settings.py"
```

Prefer explicit `add_auth_pages(app)` over `autoload()`. Individual registration helpers include `register_login_page(app)`, `register_register_page(app)`, and password-reset page registration functions. If you do not call one of these helpers, routes such as `/login`, `/register`, and `/password-reset` are not created.

### Custom page classes

Use `RX_AUTH["PAGE_CLASSES"]` when you want to replace built-in page state/classes while keeping the registry flow:

```python
RX_AUTH = {
    "PAGE_CLASSES": {
        "login": "shop.auth_pages.CustomLoginPage",
        "register": "shop.auth_pages.CustomRegisterPage",
    },
}
```

The public auth page classes include `BaseAuthPage`, `LoginPage`, `RegisterPage`, `PasswordResetPage`, and `PasswordResetConfirmPage`. You can also register pages one at a time with `register_login_page(app)`, `register_register_page(app)`, `register_password_reset_page(app)`, and `register_password_reset_confirm_page(app)`.

## `RX_AUTH`

Common keys:

| Key | Purpose |
|:---|:---|
| `ENABLED` | Allow explicit built-in auth page registration |
| `SIGNUP_ENABLED` | Enable registration page |
| `PASSWORD_RESET_ENABLED` | Enable password-reset pages |
| `LOGIN_URL`, `SIGNUP_URL`, `PASSWORD_RESET_URL` | Route paths |
| `LOGIN_REDIRECT_URL`, `LOGOUT_REDIRECT_URL`, `SIGNUP_REDIRECT_URL` | Redirect targets |
| `REDIRECT_AUTHENTICATED_USER` | Where logged-in users go from login/register |
| `LOGIN_FIELDS` | `username`, `email`, or both depending on configured auth flow |
| `MESSAGES` | UI/error copy |
| `PAGE_CLASSES` | Optional custom page state/classes |

`RX_SITE_ORIGIN` controls password-reset links when no request is bound.

## Gate a handler

```python
from reflex_django.auth import login_required, permission_required
from reflex_django.states import AppState


class PostState(AppState):
    @rx.event
    @login_required
    async def create(self):
        await Post.objects.acreate(owner=self.request.user, title=self.title)

    @rx.event
    @permission_required("blog.publish_post")
    async def publish(self):
        ...
```

Group and role guards are also available:

```python
from reflex_django.auth import group_required, staff_required, superuser_required


@rx.event
@group_required("Editors")
async def editor_action(self):
    ...
```

If a handler is denied, the decorator redirects to `redirect`/login URL by default, calls `on_denied(state)` when supplied, or uses `state.on_permission_denied()` when present.

## Gate a page

`@page(login_required=True)` handles the common login-only case:

```python
from reflex_django.pages.decorators import page


@page(route="/dashboard", login_required=True)
def dashboard() -> rx.Component:
    ...
```

Permission, group, staff, and superuser decorators also wrap page functions:

```python
from reflex_django.auth import permission_required, staff_required


@permission_required("shop.view_reports", redirect="/login")
@page(route="/reports")
def reports() -> rx.Component:
    ...


@staff_required(redirect="/login")
@page(route="/admin-tools")
def admin_tools() -> rx.Component:
    ...
```

Page wrappers render a client-side loading/fallback state, but the actual guard is an always-mounted server event on `DjangoAuthState`. Unauthorized users are redirected by the server, not merely hidden in the UI.

## Imperative helpers

```python
from reflex_django.auth import (
    ReflexDjangoAuthError,
    auser_has_perm,
    auser_in_group,
    require_login_user,
)

user = require_login_user(self.request)
allowed = await auser_has_perm(user, "shop.change_product")
in_group = await auser_in_group(user, "Editors")
```

## Programmatic login/logout

`DjangoUserState` / `AppState` expose async session helpers:

```python
ok = await self.login(username, password)
await self.logout()
```

Successful login/logout mirrors cookie state for the browser and often performs a short deferred full-page navigation so the next document request sends the updated session.

`RX_LOGOUT_PRESERVE_SESSION_KEYS` lists session keys copied before logout and restored on the anonymous session. The default keeps `"theme"`.

## `session_auth_mixin`

For a custom login UI without the built-in pages:

```python
from reflex_django.mixins import SessionAuthConfig, session_auth_mixin

LoginState = session_auth_mixin(
    SessionAuthConfig(
        state_class_name="LoginState",
        post_login_redirect="/",
        post_logout_redirect="/login",
        login_fields=("username", "email"),
    )
)
```

The generated state includes username/password/error vars, submit handlers, optional form-submit handler, logout handler, and cookie-sync navigation.

## Cookie security

Built-in Reflex login/logout syncs Django `sessionid` through JavaScript because WebSocket events cannot apply `Set-Cookie` headers like normal HTTP responses. The fallback settings therefore set `SESSION_COOKIE_HTTPONLY=False`.

If your app requires HttpOnly session cookies, use a dedicated HTTP login/logout flow or cookie-sync endpoint. See [Security](security.md).

## User snapshot

```python
from reflex_django import user_snapshot

data = user_snapshot(self.request.user)
```

Set `RX_USER_SNAPSHOT_INCLUDE_GROUPS = True` to add group names.

## FAQ

**Same cookie as admin?** Yes. One `sessionid`, one Django session.

**Works on WebSocket events?** Yes. The bridge runs the configured event tier and binds the request/user to `AppState`. See [Bridge](../learn/bridge.md).

**Next:** [Bridge utilities](bridge-utilities.md), [Security](security.md), and [Pages and state](pages-and-state.md).
