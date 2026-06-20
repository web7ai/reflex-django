# Auth

Django session auth works inside Reflex events. Log in at `/admin/`, through built-in reflex-django auth pages, or programmatically in handlers. Every handler on `AppState` sees `self.request.user` from the real session.

## Live user vs snapshot

| Use in handlers | Use in UI |
|:---|:---|
| `self.request.user` | `self.is_authenticated` |
| Check permissions here | Show/hide buttons here |

Never authorize from the reactive snapshot alone.

## Built-in auth pages

Register login, signup, and password-reset pages from `shop/shop.py`:

```python
--8<-- "snippets/auth_app_entry.py"
```

Configure routes and fields in `settings.py`:

```python
--8<-- "snippets/auth_settings.py"
```

Branding and custom page classes:

```python
--8<-- "snippets/auth_branding_settings.py"
```

Prefer explicit `add_auth_pages(app)` over `autoload()`. The latter finds `app` from `rxconfig` at import time and is mainly for advanced setups.

Individual registration: `register_login_page(app)`, `register_register_page(app)`, etc.

## Gate a handler

```python
from reflex_django.auth import login_required
from reflex_django.states import AppState


class PostState(AppState):
    @rx.event
    @login_required
    async def create(self):
        await Post.objects.acreate(owner=self.request.user, title=self.title)
```

## Gate a page

```python
from reflex_django.pages.decorators import page

@page(route="/dashboard", login_required=True)
def dashboard() -> rx.Component:
    ...
```

Or redirect manually:

```python
@rx.event
async def on_load(self):
    if not self.request.user.is_authenticated:
        return rx.redirect("/admin/")
```

## Permissions

```python
from reflex_django.auth import permission_required

@rx.event
@permission_required("shop.add_product")
async def create_product(self):
    ...
```

Imperative check: `await auser_has_perm(self.request.user, "app.change_model")`.

## Programmatic login and logout

Built-in auth pages use `DjangoAuthState` (dynamic class with login form events). For custom flows on `AppState` subclasses that include auth bridge methods, call:

```python
ok = await self.login(username, password)
await self.logout()
```

These use Django's async session auth and mirror cookies for the browser. See auth page source or extend `DjangoUserState` patterns.

## User snapshot for custom UI

```python
from reflex_django import user_snapshot

data = user_snapshot(self.request.user)
```

Set `RX_USER_SNAPSHOT_INCLUDE_GROUPS = True` to add group names.

## Customize login UI

`RX_AUTH` controls routes, field names, messages, branding, and optional custom page classes. See snippets above.

## FAQ

**Same cookie as admin?** Yes. One `sessionid`, one login.

**Works on WebSocket events?** Yes. The bridge runs session and auth middleware on each event. See [Bridge](../learn/bridge.md).

**Next:** [Bridge utilities](bridge-utilities.md) for `current_user` and session mirrors.
