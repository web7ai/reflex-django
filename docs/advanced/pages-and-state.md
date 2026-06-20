# Pages and state

Register pages the **Reflex way** on `app` in `{app_name}/{app_name}.py`. reflex-django loads that module at compile time. What reflex-django adds is **state**: use `AppState` when handlers need Django context (`self.request.user`, session, CSRF).

You do not wire SPA routes in Django `urls.py`. There is no page package setting in `settings.py`.

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

## Tips

- Handlers should be `async def`
- Store dicts in state, not model instances
- Paginate large lists. Reactive vars ship to the browser

See the [Tutorial](../learn/quickstart.md) for a full example.
