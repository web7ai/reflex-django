# Pages and state

Register pages the **Reflex way** on `app` in `{app_name}/{app_name}.py`. reflex-django loads that module at compile time. What reflex-django adds is **state**: use `AppState` when handlers need Django context (`self.request.user`, session, CSRF) and bridge is enabled for that event.

You do not wire SPA routes in Django `urls.py`. The removed v3 `RX_PAGE_PACKAGES` setting is not used. The current `RX_PAGE_MODULE` setting only controls the optional decorated-page module suffix, defaulting to `views`.

## Option A: `app.add_page` (typical Reflex)

Define the app in `shop/shop.py` and register pages with `app.add_page`:

```python
--8<-- "snippets/minimal_app_entry.py"
```

Put components and state in the same file or import them from another module:

```python
# shop/views.py
import reflex as rx
from reflex_django.states import AppState


class HomeState(AppState):
    greeting: str = ""

    @rx.event
    async def on_load(self):
        user = self.request.user
        self.greeting = (
            f"Hi, {user.get_username()}!"
            if user.is_authenticated
            else "Hello, guest. Log in at /admin/."
        )


def index() -> rx.Component:
    return rx.vstack(
        rx.heading("My Shop"),
        rx.text(HomeState.greeting),
    )
```

`app_name="shop"` in `rxconfig.py` must match `shop/shop.py`.

## Option B: `@page` in `views.py` (optional)

If `{app_name}/views.py` exists, reflex-django imports it automatically before compile. You can use the reflex-django `@page` decorator instead of `app.add_page`:

```python
--8<-- "snippets/minimal_views.py"
```

Use one style per project. Both work with `AppState`.

### `@page` options

`@page` forwards normal Reflex page kwargs (`title`, `on_load`, etc.) and records metadata in `PAGE_REGISTRY` so reflex-django can migrate decorated pages to the configured app name during compile.

```python
from reflex_django.pages.decorators import page


@page(
    route="/orders",
    title="Orders",
    login_required=True,
    breadcrumbs=(("Home", "/"), ("Orders", None)),
)
def orders() -> rx.Component:
    ...
```

| Option | Purpose |
|:---|:---|
| `route` | Client route |
| `login_required` | Wrap page with the auth page guard |
| `login_url` | Login URL override |
| `breadcrumbs` | `((label, href), ...)`; `href=None` marks the active segment |
| `**kwargs` | Forwarded to `reflex.page` |

`get_breadcrumbs_for_route(route)` reads registered breadcrumb metadata.

### Layout templates

Use `reflex_template` or the built-in `centered_template` helper to wrap decorated pages:

```python
from reflex_django.pages.decorators import page, reflex_template
from reflex_django.pages.decorators.templates import centered_template


@reflex_template(centered_template)
@page(route="/login")
def login() -> rx.Component:
    ...
```

`reflex_template` expects a callable that returns a page decorator, matching common Reflex layout helper patterns.

## Django `urls.py`

Only for Django-owned paths (admin, API). No SPA routes:

```python
--8<-- "snippets/minimal_urls.py"
```

## AppState vs rx.State

| Need | Use |
|:---|:---|
| `self.request.user`, session, CSRF in handlers | `AppState` |
| Modals, filters, theme (UI only) | `rx.State` |

| In handlers | In components |
|:---|:---|
| `self.request.user` for auth checks | `self.is_authenticated` for UI |
| `self.session` for session data | `self.username` for display |

Authorize with `self.request.user`, not the reactive snapshot alone. See [Bridge](../learn/bridge.md).

## AppState handler API

Inside bridge-bound `AppState` handlers, these helpers mirror Django request data:

| API | Purpose |
|:---|:---|
| `self.request` | Synthetic Django `HttpRequest` for the event |
| `self.user` / `self.request.user` | Live Django user object |
| `self.session` | Session proxy; save after mutation when needed |
| `self.messages` | Mirrored Django messages |
| `self.csrf_token` | Mirrored CSRF token |
| `self.response` | Middleware response, if one short-circuited |
| `await self.has_perm("app.perm")` | Async permission check |
| `await self.has_group("Group")` | Async group check |
| `await self.refresh_django_user_fields()` | Refresh reactive auth snapshot vars |
| `on_auth_failed()` / `on_permission_denied()` | Override generated guard failure handling |

These APIs require bridge context. For UI-only state that does not need Django, use plain `rx.State` and optionally `_rx_bridge = "none"`.

## Splitting page modules

With `app.add_page`, import UI from anywhere in `shop.py`:

```python
from shop.pages.dashboard import dashboard_page

app.add_page(dashboard_page, route="/dashboard")
```

With `@page`, keep decorators in `{app_name}/views.py` or import submodules there so the single auto-import pulls them in:

```python
# shop/views.py
from shop.pages import dashboard  # noqa: F401
```

Set `RX_PAGE_MODULE` when your decorated-page module is not named `views`.

## Tips

- Handlers should be `async def`
- Store dicts in state, not model instances
- Paginate large lists. Reactive vars ship to the browser
- Import Django models inside handlers when early imports would hit `AppRegistryNotReady`
- Use `AppState` for Django-aware handlers and plain `rx.State` for UI-only state

See the [Tutorial](../learn/quickstart.md) for a full example.
