# reflex-django mixins

Reference for the **composable mixin stack** behind `ModelCRUDView` and **`session_auth_mixin`**.

These are **optional** on top of the bridges. You can build the same behavior with plain `rx.State`—see [State management](state_management.md).

For a hands-on tutorial, see [CRUD with mixins](crud_with_mixins_and_states.md).

---

## Prerequisites

- [State management](state_management.md) — especially Part B (helpers) and Part C (this page)  
- [Architecture](architecture.md)

---

## `ModelCRUDView` MRO (simplified)

```text
ModelCRUDView
  └── DispatchMixin
        └── DeleteMixin, ListMixin, UpdateMixin, CreateMixin, StateFieldsMixin
        └── PermissionMixin, LoginRequiredMixin
        └── BaseModelState
```

`ModelListView` = list stack + permissions + login required (no create/update/delete dispatch actions).

Import mixins:

```python
from reflex_django.state.mixins import (
    ListMixin,
    CreateMixin,
    UpdateMixin,
    DeleteMixin,
    DispatchMixin,
    StateFieldsMixin,
    QuerySetMixin,
    PermissionMixin,
    LoginRequiredMixin,
    UserScopedMixin,
    IsAuthenticated,
    AllowAny,
)
```

---

## `DispatchMixin.dispatch`

Central pipeline (`src/reflex_django/state/mixins/dispatch.py`):

```text
bind_request_context → build_context → setup
  → check_permissions → handler → teardown
```

Actions (`state/constants.py`): `load_list`, `save`, `delete`, `start_edit`, `cancel_edit`.

---

## Hook catalog

| Hook | Mixin | Purpose |
|------|-------|---------|
| `get_queryset` | QuerySetMixin | Base queryset |
| `filter_queryset` | QuerySetMixin | Search/filter extension point |
| `get_ordering` | QuerySetMixin | From `Meta.ordering` (default `("-created_at",)`) |
| `get_object` / `get_object_lookup` | ObjectMixin | Fetch row for edit/delete |
| `perform_create` / `get_create_kwargs` | CreateMixin | Insert |
| `perform_update` / `get_update_kwargs` | UpdateMixin | Update |
| `perform_delete` | DeleteMixin | Delete |
| `validate_state` / `clean_{field}` | StateFieldsMixin | Validation |
| `on_state_invalid` / `on_save_success` | StateFieldsMixin / Create | Error/success hooks |
| `check_permissions` | PermissionMixin | `permission_classes` |

---

## `UserScopedMixin`

Reflex MRO cannot prioritize plain mixins; assembly **re-injects** scoping hooks when `UserScopedMixin` is in bases:

```python
class NotesState(AppState, ModelCRUDView, UserScopedMixin):
    scope_field = "user_id"  # or "user" for FK name
```

Equivalent manual hooks: `get_queryset`, `get_object_lookup`, `get_create_kwargs` with `self.request.user`.

---

## Permissions

```python
from reflex_django.state.mixins import IsAuthenticated, AllowAny

class MyState(AppState, ModelCRUDView):
    permission_classes = (IsAuthenticated,)
```

`IsAuthenticated.has_permission` checks `ctx.user is not None` (not `user.is_authenticated`).

---

## Composed mixins (partial CRUD)

From README—list + create only, no generated `save_*` from full `ModelCRUDView`:

```python
from reflex_django.state import AppState
from reflex_django.state.mixins import (
    ListMixin,
    StateFieldsMixin,
    CreateMixin,
    PermissionMixin,
    IsAuthenticated,
)

class AdminTagState(AppState, ListMixin, StateFieldsMixin, CreateMixin, PermissionMixin):
    serializer_class = TagSerializer
    permission_classes = (IsAuthenticated,)
```

You wire `@rx.event` handlers yourself.

---

## `session_auth_mixin`

From `reflex_django.mixins` (not package root):

```python
from reflex_django.mixins import SessionAuthConfig, session_auth_mixin
from reflex_django import DjangoUserState

cfg = SessionAuthConfig(
    post_login_redirect="/",
    post_logout_redirect="/login",
    redirect_when_authenticated="/",
)

LoginState = session_auth_mixin(cfg, base=DjangoUserState)
```

Provides username/password fields, `submit_login`, `logout`, optional `submit_login_form` (`form_data`), and **session cookie JS sync** after `alogin` (see [Authentication](authentication.md)).

Also: `populate_session_auth_state` for custom auth state builders.

---

## When to use which

| Need | Use |
|------|-----|
| Full CRUD + generated events | `ModelCRUDView` |
| Read-only table | `ModelListView` |
| Subset of operations | Composed mixins |
| Custom login form | `session_auth_mixin` or canned `LoginPage` |

---

## Advanced usage

- Override generated method names in class body to replace assembly output (same name wins).  
- `backend_class` on `Meta` to swap `DjangoORMBackend`.

---

## Common mistakes

- Expecting built-in pagination vars on mixins.  
- Importing `session_auth_mixin` from `reflex_django` root (use `reflex_django.mixins`).

---

## Developer notes

- Assembly: `src/reflex_django/state/assembly.py`, `AppStateMeta` in `states.py`.

---

## See also

- [CRUD with mixins](crud_with_mixins_and_states.md)  
- [CRUD without mixins](crud_without_mixins.md)

---

**Navigation:** [← CRUD without mixins](crud_without_mixins.md) | [Next: CRUD with mixins →](crud_with_mixins_and_states.md)
