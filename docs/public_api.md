# Public API at a glance

Every public symbol you can import from `reflex_django`, grouped by what you'd use it for. This is the lookup-quickly page — for usage guides, follow the links to each topic.

---

## What you'll import on a typical day

```python
# state — the bridge to Django context
from reflex_django.state import AppState, ModelState, ModelCRUDView

# pages
from reflex_django import template, page

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
from reflex_django import DjangoUserState

# request access without an AppState subclass
from reflex_django import request, current_request, current_user

# ASGI entry
from reflex_django.asgi_entry import application
```

Most projects don't import anything else.

---

## Page registration

| Symbol | Where it lives | What it does |
|:---|:---|:---|
| `template(route, ...)` | `reflex_django` | Register a Reflex page with the default layout wrapper. ([Details](pages_in_views.md).) |
| `page(route, ...)` | `reflex_django` | Same, but without the layout wrapper. |
| `reflex_mount(...)` | `reflex_django.urls` | Mount Reflex in `urls.py`. ([Configuration](configuration.md).) |
| `admin_urlpatterns(prefix)` | `reflex_django.urls` | Convenience builder for admin URL patterns. |

---

## State classes

| Class | Where it lives | Use it for |
|:---|:---|:---|
| `AppState` | `reflex_django.state` | Default state for pages that need Django context (`self.request.user`, session, …). ([Details](state_management.md).) |
| `ModelState` | `reflex_django.state` | Declarative CRUD over a Django model. Auto-builds serializer. ([Details](reactive_model_state.md).) |
| `ModelCRUDView` | `reflex_django.state` | Declarative CRUD with explicit `serializer_class`. ([Details](crud_with_mixins_and_states.md).) |
| `ModelListView` | `reflex_django.state` | Read-only `ModelState` variant — list/filter/paginate only. |
| `DjangoUserState` | `reflex_django` | Reactive snapshot of user/session for use in components. |
| `DjangoAuthState` | `reflex_django` | State backing the built-in auth pages. |
| `DjangoContextState` | `reflex_django` | Reactive holder for context-processor output. |
| `DjangoI18nState` | `reflex_django` | Reactive holder for language/i18n data. |

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
| `add_auth_pages()` | Register `/login`, `/register`, `/password_reset`, `/password_reset_confirm`. |
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
| `self.request`, `self.user` on `AppState` | `reflex_django.state` | Method-style |
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

All in `reflex_django.asgi_entry` (and a couple of helpers in `reflex_django`):

| Symbol | What it does |
|:---|:---|
| `application` | The ASGI callable. Point your ASGI server here. |
| `build_application()` | Build a fresh ASGI app on demand (useful in tests). |
| `build_django_outer_application()` | The specific "Django outer" variant builder. |
| `configure_django()` | Idempotent `django.setup()` wrapper. |
| `build_django_asgi()`, `make_dispatcher()` | Lower-level builders. |
| `install_reflex_django_integration()` | Run all the bootstrap steps manually. Rarely needed. |

---

## Plugin and CLI

| Symbol | Where it lives | What it does |
|:---|:---|:---|
| `ReflexDjangoPlugin` | `reflex_django` | The Reflex plugin that wires everything in. Added automatically by `reflex_mount()`. |
| `django_cli` | `reflex_django` | The `reflex django ...` command tree. |
| `DjangoEventBridge` | `reflex_django` | The per-event request/response bridge. (Reference only — usually not imported directly.) |
| `EventMiddlewareHandler` / `run_middleware_chain` | `reflex_django` | The Django middleware runner used by the bridge. |

---

## Models

| Symbol | Where it lives | What it does |
|:---|:---|:---|
| `reflex_django.model.Model` | `reflex_django.model` | Optional `django.db.models.Model` subclass. Uses `BigAutoField` PK by default. Use it or plain `Model`, both fine. |

---

## Reflex-context helpers

| Symbol | What it does |
|:---|:---|
| `builtin_user_context(request)` | Returns the JSON snapshot of `request.user` used in `self.request.context["user"]`. |
| `builtin_i18n_context(request)` | Returns the i18n context dict (`LANGUAGE_CODE`, `LANGUAGE_BIDI`). |
| `collect_reflex_context(request)` | Runs all registered context processors and returns the merged dict. |

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

The `reflex_django` package uses PEP 562 lazy attribute access, so importing it never touches Django's app registry. The symbols above are all resolvable through:

```python
import reflex_django

reflex_django.AppState
reflex_django.template
reflex_django.add_auth_pages
# ...
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
