---
level: advanced
tags: [crud, mixins]
---

# Mixins: compose your own state

**What you'll learn:** Which CRUD mixins exist, how `ModelCRUDView` stacks them, and how to build a slimmer or stricter state class for non-standard pages.

**When you need this:**

- You need fewer capabilities than full CRUD (list + create only, no delete).
- You want a project-wide base (login required + user scope on every model page).

If your page is standard list, edit, save, and delete, use [`ModelState`](crud.md#modelstate) and skip this page until you feel the constraint.

---

## How ModelCRUDView is built

`ModelCRUDView` composes small mixins from `reflex_django.state.mixins`:

```text
ModelCRUDView
+-- ModelORMMixin        # canonical load/save/delete API
+-- DispatchMixin        # action routing and hook orchestration
+-- LoginRequiredMixin   # redirect anonymous users
+-- (via assembly) List, Create, Update, Delete, QuerySet, Serialize, ...
```

Drop a mixin from a custom stack and the matching handlers disappear from your state class.

---

## Mixin catalog

### `QuerySetMixin`
`get_queryset()` and `filter_queryset(qs)`. Override to control visible rows.

### `ObjectMixin`
`get_object_lookup(pk)` for edit and delete fetches. Add ownership keys here.

### `SerializeMixin`
Wires `ReflexDjangoModelSerializer` (auto-built or `serializer_class`).

### `StateFieldsMixin`
Declares reactive vars from writable serializer fields. Validation lives here (`validate_state`, `clean_<field>`, `clean_state`).

### `ListMixin`
`refresh()`, search helpers, pagination events when `paginate_by` is set.

### `CreateMixin` / `UpdateMixin` / `DeleteMixin`
Create, save, and delete paths with `get_create_kwargs`, `before_save`, `after_save`, `before_delete`, `after_delete`.

### `DispatchMixin`
Routes actions (`save`, `delete`, `start_edit`, list load) through permission checks and hooks.

### `PermissionMixin` + `IsAuthenticated`
DRF-style `permission_classes` checked before each action.

### `LoginRequiredMixin`
Redirects anonymous users to `REFLEX_DJANGO_LOGIN_URL`.

### `UserScopedMixin`
Filters queryset, lookups, and create kwargs by the logged-in user. Set `scope_field` (default `"user_id"`). Use `"owner"` or `"owner_id"` for owner FKs.

### `PaginationMixin`
Page vars and handlers when `paginate_by > 0`.

---

## Recipes

### List + create only (no edit, no delete)

Compose mixins without `UpdateMixin` or `DeleteMixin`:

```python
from reflex_django.states import AppState
from reflex_django.state import BaseModelState
from reflex_django.state.mixins import (
    CreateMixin,
    DispatchMixin,
    ListMixin,
    ObjectMixin,
    PermissionMixin,
    QuerySetMixin,
    SerializeMixin,
    StateFieldsMixin,
)


class AuditLogState(
    AppState,
    DispatchMixin,
    CreateMixin,
    ListMixin,
    StateFieldsMixin,
    PermissionMixin,
    QuerySetMixin,
    SerializeMixin,
    ObjectMixin,
    BaseModelState,
):
    model = AuditLog
    fields = ["action", "details"]
    list_var = "events"
```

Users cannot call delete or edit handlers that were never assembled.

### Login required + per-user scope

```python
from reflex_django.state.mixins import LoginRequiredMixin, UserScopedMixin
from reflex_django.states import ModelState


class NotesState(LoginRequiredMixin, UserScopedMixin, ModelState):
    model = Note
    fields = ["title", "body"]
    scope_field = "owner_id"
    list_var = "notes"
```

Put auth and scoping mixins before `ModelState` so checks run first.

### Staff-only admin tool

```python
from reflex_django.state.mixins import IsAuthenticated
from reflex_django.states import AppState
from reflex_django.state import ModelCRUDView


class AdminToolState(AppState, ModelCRUDView):
    model = Tool
    serializer_class = ToolSerializer
    permission_classes = (IsAuthenticated,)  # add your own staff check class
    list_var = "tools"
```

Add a custom permission class that checks `request.user.is_staff` when you need staff-only tools.

### Project-wide CRUD base

```python
# myapp/state_bases.py
from reflex_django.state.mixins import LoginRequiredMixin, UserScopedMixin
from reflex_django.states import ModelState


class AuthScopedModelState(LoginRequiredMixin, UserScopedMixin, ModelState):
    scope_field = "owner_id"


# blog/views.py
class PostState(AuthScopedModelState):
    model = Post
    fields = ["title", "content"]
    list_var = "posts"
```

---

## Session auth mixin (custom login UI)

Built-in auth pages use `session_auth_mixin` from `reflex_django.mixins`:

```python
from reflex_django.mixins import SessionAuthConfig, session_auth_mixin
from reflex_django.states import DjangoUserState

config = SessionAuthConfig(
    login_url="/login",
    post_login_url="/",
    post_logout_url="/login",
)

AuthBase = session_auth_mixin(config, base=DjangoUserState)


class MyAuthState(AuthBase):
    pass
```

Most projects call `add_auth_pages()` instead of wiring this by hand.

---

## When not to bother

`ModelState` covers most apps. Reach for mixins when you deliberately want fewer methods, a shared base class, or behavior shared between CRUD and non-CRUD states.

---

## What just happened?

You saw how declarative CRUD is assembled from focused mixins, and how to compose narrower stacks when full CRUD is too much.

**Next up:** [Forms and validation →](forms.md)