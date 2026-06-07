# Public API at a glance

Every public symbol you can import from `reflex_django`, grouped by what you'd use it for. This is the lookup-quickly page — for usage guides, follow the links to each topic.

---

## What you'll import on a typical day

```python
# state — the bridge to Django context
from reflex_django.states import AppState, ModelState

# pages
from reflex_django.pages.decorators import page
from reflex_django.pages.decorators.templates import centered_template as template

# urls.py
from reflex_django.urls import reflex_mount

# auth
from reflex_django.auth import (
    add_auth_pages,
    login_required,
    permission_required,
    require_login_user,
)

# serializers
from reflex_django.serializers import ReflexDjangoModelSerializer

# reactive snapshot var (use in UI components)
from reflex_django.states import DjangoUserState

# request access without an AppState subclass
from reflex_django import request, current_request, current_user

# ASGI entry
from reflex_django.asgi_entry import application

# routing mode helpers
from reflex_django.routing import UrlRoutingMode, resolve_url_routing

# custom rx.App factory
from reflex_django import app, create_app
```

Most projects don't import anything else.

---

## Page registration

| Symbol | Where it lives | What it does |
|:---|:---|:---|
| `page(route, ...)` | `reflex_django.pages.decorators` | Register a Reflex page (no layout wrapper). The default. ([Details](pages_in_views.md).) |
| `centered_template(route, ...)` | `reflex_django.pages.decorators.templates` | Same, but wraps content in a centered layout. Often imported `as template`. |
| `reflex_mount(...)` | `reflex_django.urls` | Mount Reflex in `urls.py`. ([Configuration](configuration.md).) |
| `admin_urlpatterns(prefix)` | `reflex_django.urls` | Convenience builder for admin URL patterns. |

---

## State classes

All State classes are importable from `reflex_django.states`.

| Class | Where it lives | Use it for |
|:---|:---|:---|
| `AppState` | `reflex_django.states` | Default state for pages that need Django context (`self.request.user`, session, …). ([Details](state_management.md).) |
| `ModelState` | `reflex_django.states` | Declarative CRUD over a Django model. Auto-builds serializer. ([Details](reactive_model_state.md).) |
| `ModelCRUDView` | `reflex_django.state` | Declarative CRUD with explicit `serializer_class`. ([Details](crud_with_mixins_and_states.md).) |
| `ModelListView` | `reflex_django.state` | Read-only `ModelState` variant — list/filter/paginate only. |
| `DjangoUserState` | `reflex_django.states` | Reactive snapshot of user/session for use in components. |
| `DjangoAuthState` | `reflex_django.states` | State backing the built-in auth pages. |
| `DjangoI18nState` | `reflex_django.states` | Reactive holder for language/i18n data. |

---

## Mixins

All in `reflex_django.mixins` (also re-exported from `reflex_django.state`):

| Mixin | Use it for |
|:---|:---|
| `LoginRequiredMixin` | Reject events when the user isn't authenticated. |
| `UserScopedMixin` | Auto-scope queries to the current user via `Meta.owner_field`. |
| `PermissionMixin` | DRF-style permission checks via `Meta.permission_classes`. |
| `PaginationMixin` | Pagination vars and handlers. |
| `ListMixin`, `CreateMixin`, `UpdateMixin`, `DeleteMixin` | Compose CRUD piece by piece. |
| `DispatchMixin` | The dispatch pipeline that calls hooks. |
| `QuerysetMixin`, `ObjectMixin`, `SerializeMixin`, `StateFieldsMixin`, `OrmApiMixin` | Lower-level building blocks. |

See [Mixins — compose your own state](reflex_django_mixins.md) for compositions.

---

## Serializers

| Symbol | Where it lives | What it does |
|:---|:---|:---|
| `ReflexDjangoModelSerializer` | `reflex_django.serializers` | DRF-style serializer (no DRF dependency) for converting models to JSON-safe dicts. ([Details](serializers.md).) |
| `serialize_model_row(instance, fields)` | `reflex_django.serialization` | Functional helper — serialize one instance to a dict. |

---

## Auth

All in `reflex_django.auth`:

| Symbol | What it does |
|:---|:---|
| `add_auth_pages()` | Register `/login`, `/register`, `/password-reset`, `/password-reset/confirm/[uid]/[key]`. |
| `login_required` | Handler decorator. Redirects unauthenticated requests. |
| `permission_required(perm)` | Handler decorator. Redirects when the permission is missing. |
| `require_login_user()` | Raises if no authenticated user is present. Returns the user. |
| `register_login_page()`, `register_register_page()`, `register_password_reset_page()`, `register_password_reset_confirm_page()` | Register individual auth pages. |
| `LoginPage`, `RegisterPage`, `PasswordResetPage`, `PasswordResetConfirmPage` | Page classes you can subclass to customize the UI. |
| `DjangoAuthState` | State backing the built-in auth pages. |
| `AuthSettings`, `get_auth_settings()` | Read the resolved `REFLEX_DJANGO_AUTH` settings. |
| `BaseAuthPage`, `AuthPageMeta` | Lower-level base classes for custom auth pages. |
| `ReflexDjangoAuthError` | Exception raised on auth failures. |
| `auser_has_perm(user, perm)` | Async permission check helper. |
| `session_auth_mixin(config, base)` | Factory for a state class with `.login()` / `.logout()` / `.register()` methods. |

---

## Request access

Three flavors. They all read the same per-event request.

| Symbol | Where it lives | Style |
|:---|:---|:---|
| `self.request`, `self.user` on `AppState` | `reflex_django.states` | Method-style |
| `request` (module proxy) | `reflex_django` | Attribute proxy (`request.user`, `request.GET`) |
| `current_request()`, `current_user()`, `current_session()`, `current_language()`, `current_csrf_token()`, `current_messages()`, `current_response()` | `reflex_django` | Functional |

For test setup:

| Symbol | What it does |
|:---|:---|
| `begin_event_request(...)` | Set up a per-event request context (returns a token). |
| `end_event_request(token)` | Tear down the context. |
| `begin_event_response(response)` / `end_event_response(token)` | Same for the response side. |

See [Testing](testing.md) for usage.

---

## ASGI / bootstrap

| Symbol | Where it lives | What it does |
|:---|:---|:---|
| `application` | `reflex_django.asgi_entry` | The ASGI callable. Point your ASGI server here. |
| `build_application()` | `reflex_django.asgi_entry` | Build a fresh ASGI app on demand (mode-aware). |
| `build_django_outer_application()` | `reflex_django.asgi_entry` | Build the Django-outer variant explicitly. |
| `configure_django()` | `reflex_django.asgi` | Idempotent `django.setup()` wrapper. |
| `build_django_asgi()`, `make_dispatcher()` | `reflex_django.asgi` | Lower-level builders. |
| `install_reflex_django_integration()` | `reflex_django.integration` | Run all bootstrap steps manually. Rarely needed outside tests. |
| `UrlRoutingMode`, `resolve_url_routing()` | `reflex_django.routing` | Routing mode enum and resolver. |
| `app`, `create_app()` | `reflex_django` / `reflex_django.app_factory` | Shared Reflex app instance and factory. |

---

## Plugin and CLI

| Symbol | Where it lives | What it does |
|:---|:---|:---|
| `ReflexDjangoPlugin` | `reflex_django` | The Reflex plugin that wires everything in. Added automatically by `reflex_mount()`. |
| `django_cli` | `reflex_django` | The `reflex django ...` command tree. |
| `DjangoEventBridge` | `reflex_django` | The per-event request/response bridge. (Reference only — usually not imported directly.) |
| `EventMiddlewareHandler` / `run_middleware_chain` | `reflex_django` | The Django middleware runner used by the bridge. |

---

## Django HTTP dev middleware

Optional **development-only** middleware for the Vite port (`:3000`) and Django admin CSRF. Not used on WebSocket events — see [Custom middleware in events](django_middleware_to_reflex.md).

| Symbol | Where it lives | What it does |
|:---|:---|:---|
| `DEFAULT_DEV_MIDDLEWARE` | `reflex_django.django_dev_middleware` | Tuple of dotted paths to prepend to `MIDDLEWARE` in dev settings. |
| `EnsureRequestBodyAttrsMiddleware` | `reflex_django.django_dev_middleware` | Sets `_body` / `_read_started` only for empty requests (synthetic Reflex/Django requests). |
| `DevViteProxyHostMiddleware` | `reflex_django.django_dev_middleware` | Sets `X-Forwarded-Host` / `X-Forwarded-Proto` from `Origin` when the Vite proxy omits them. |

Post-compile frontend helpers live in `reflex_django.frontend_stability` (called by the plugin; not imported in app code). See [Local development](local_development.md).

---

## Models

| Symbol | Where it lives | What it does |
|:---|:---|:---|
| `reflex_django.model.Model` | `reflex_django.model` | Optional `django.db.models.Model` subclass. Uses `BigAutoField` PK by default. Use it or plain `Model`, both fine. |

---

## Session cookie JS helpers

For custom login UI that needs to refresh cookies on the client:

| Symbol | What it does |
|:---|:---|
| `session_cookie_set_js(request, value)` | JS snippet that sets the session cookie. |
| `session_cookie_clear_js(request)` | JS snippet that clears the session cookie. |
| `session_cookie_name_and_suffix(request)` | Returns `(name, suffix)` for cookie domain/path attrs. |

---

## Admin

| Symbol | Where it lives | What it does |
|:---|:---|:---|
| `register_admin(model, **kwargs)` | `reflex_django.admin` | Convenience wrapper around `django.contrib.admin.register`. |

---

## Streaming middleware

| Symbol | Where it lives | What it does |
|:---|:---|:---|
| `reflex_django.streaming_middleware.AsyncStreamingMiddleware` | `reflex_django.streaming_middleware` | The Django middleware you add to `MIDDLEWARE`. ([Details](async_streaming_middleware.md).) |

---

## Lazy imports

The `reflex_django` package uses PEP 562 lazy attribute access, so importing it never touches Django's app registry. Top-level symbols are resolvable through attribute access:

```python
import reflex_django

reflex_django.add_auth_pages
reflex_django.ReflexDjangoPlugin
# ...
```

State classes and page decorators live in dedicated modules instead of the top-level package:

```python
from reflex_django.states import AppState, DjangoUserState
from reflex_django.pages.decorators import page
from reflex_django.pages.decorators.templates import centered_template as template
```

If you see `module 'reflex_django' has no attribute 'X'`, double-check the spelling against this page.

---

## Versioning

Public API symbols listed on this page follow semantic versioning. Anything in `reflex_django._*` or in deeply nested submodules (e.g. `reflex_django.mixins.session_auth._sync_session_cookie_then_nav`) is internal and may change between releases.

For the current version, see the package metadata:

```bash
uv pip show reflex-django
# or
python -c "import importlib.metadata; print(importlib.metadata.version('reflex-django'))"
```

---

**Next:** [FAQ →](faq.md)
