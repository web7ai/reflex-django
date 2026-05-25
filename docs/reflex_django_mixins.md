# Mixins — compose your own state

The CRUD classes in `reflex-django` (`ModelState`, `ModelCRUDView`) are themselves built out of small **mixins**. Each mixin adds one piece of behavior: list rows, create rows, delete rows, scope to current user, enforce a permission, paginate, validate.

If your page needs something different from the standard CRUD shape — say, "list and create but never edit or delete", or "permission-checked admin tool with custom save logic" — you can compose only the mixins you need.

This page is a tour of the mixins and a few recipes.

---

## When you'd want this

- You want **fewer** capabilities than `ModelState` provides (e.g. a list page that only lets you add, not edit).
- You want **more** capabilities (e.g. add a `LoginRequiredMixin` to every CRUD action).
- You want to **build your own variant** of `ModelCRUDView` for your project's conventions.

If your page is a standard "list + edit + save + delete", stick with [`ModelState`](reactive_model_state.md). Mixins are a step deeper than most projects need.

---

## How the standard CRUD class is built

`ModelCRUDView` is just this composition, in MRO order:

```text
ModelCRUDView
├── DispatchMixin              # the run-loop that calls hooks
├── DeleteMixin                # delete handler + before/after_delete
├── UpdateMixin                # update handler + before/after_save
├── CreateMixin                # create handler + get_create_kwargs
├── ListMixin                  # list / refresh / filter / paginate
├── StateFieldsMixin           # auto-declared reactive vars from `fields`
├── PermissionMixin            # @login_required / @permission_required hooks
├── QuerysetMixin              # get_queryset / filter_queryset
├── SerializeMixin             # serializer wiring
└── ObjectMixin                # get_object_lookup
```

Drop any of these and you get a smaller, more specialized state class.

---

## The mixin catalog

### `BaseModelState`
The minimum a CRUD-ish state needs: `model`, `class Meta`, `dispatch()`. Almost never used directly — it's the bottom of the stack.

### `QuerysetMixin`
Provides `get_queryset()` and `filter_queryset(qs)`. Override both to control which rows the state can see.

```python
def get_queryset(self):
    return Order.objects.filter(tenant=self.request.user.tenant)

def filter_queryset(self, qs):
    qs = super().filter_queryset(qs)
    if self.only_recent:
        qs = qs.filter(created_at__gte=...)
    return qs
```

### `ObjectMixin`
Provides `get_object_lookup(pk)`. This is the "fetch one row by ID" path used by edit/delete. Override to add an ownership filter:

```python
def get_object_lookup(self, pk: int) -> dict:
    return {"pk": pk, "owner": self.request.user}
```

### `SerializeMixin`
Wires a `ReflexDjangoModelSerializer` (either auto-built from `fields` or your `serializer_class`).

### `StateFieldsMixin`
At class-definition time, auto-declares one reactive variable per entry in `fields` (and a matching `set_<field>` setter).

### `ListMixin`
Provides:

- `refresh()` — reload the list with current filter/search/page
- `filter()` — re-apply search
- `clear_filter()` — reset search
- `paginate(page)` / `next_page()` / `prev_page()` (when `paginate_by > 0`)

### `CreateMixin`
Provides:

- `create()` — enter "new row" mode (clears the form)
- The create branch of `save()` — used by `UpdateMixin.save`.
- Hooks: `get_create_kwargs(state_data)`, `before_save(instance)`, `after_save(instance)`

### `UpdateMixin`
Provides:

- `save()` — validate + create-or-update + reload
- `start_editing(pk)` / `cancel_edit()`
- Hooks: `before_save`, `after_save`, `clean_<field>`, `validate_state`

### `DeleteMixin`
Provides:

- `delete(pk)` — fetch + delete + reload
- Hooks: `before_delete(instance)`, `after_delete(instance)`

### `DispatchMixin`
The orchestrator. When a handler is called, it routes through:

1. `bind_request_context()` — exposes `self.request`, `self.request.user`
2. Permission checks (from `PermissionMixin`)
3. Validation hooks
4. Database operation
5. State variable updates
6. Browser diff

### `PermissionMixin`
Wires DRF-style permission classes:

```python
class Meta:
    permission_classes = (IsAuthenticated, IsStaffOrReadOnly)
```

Permission classes are checked on every dispatch before the operation runs.

### `LoginRequiredMixin`
Enforces login on every dispatched action. If anonymous, redirects to `REFLEX_DJANGO_LOGIN_URL`.

### `UserScopedMixin`
The "scope to current user" mixin. Replaces three hooks (`get_queryset`, `get_object_lookup`, `get_create_kwargs`) with sensible defaults driven by `Meta.owner_field`.

```python
class TodoState(UserScopedMixin, ModelState):
    model = Todo
    fields = ["title", "done"]

    class Meta:
        list_var = "todos"
        owner_field = "owner"     # the FK field on Todo
```

### `PaginationMixin`
Provides the pagination variables and handlers when `Meta.paginate_by > 0`. Already included in `ModelState`/`ModelCRUDView`.

### `OrmApiMixin`
Provides the low-level async ORM wrappers used by `Create`/`Update`/`Delete`. You almost never override these directly.

---

## Recipes

### List + create, no edit, no delete

For an "append-only" log:

```python
from reflex_django.state import (
    BaseModelState, DispatchMixin, CreateMixin, ListMixin,
    StateFieldsMixin, SerializeMixin, QuerysetMixin, ObjectMixin,
    PermissionMixin,
)
from reflex_django.state import AppState


class AuditLogState(
    AppState,
    DispatchMixin,
    CreateMixin,
    ListMixin,
    StateFieldsMixin,
    PermissionMixin,
    QuerysetMixin,
    SerializeMixin,
    ObjectMixin,
    BaseModelState,
):
    model = AuditLog
    fields = ["action", "details"]

    class Meta:
        list_var = "events"
```

No `UpdateMixin`, no `DeleteMixin` → those handlers don't exist on the class. Users physically can't call them from the UI.

### Read-only list

Use `ModelListView` directly (it's already composed this way):

```python
from reflex_django.state import ModelListView

class CatalogState(ModelListView):
    model = Product
    fields = ["name", "price"]
    class Meta:
        list_var = "products"
        paginate_by = 25
```

### Login required + per-user scope

```python
from reflex_django.mixins import LoginRequiredMixin, UserScopedMixin
from reflex_django.state import ModelState


class NotesState(LoginRequiredMixin, UserScopedMixin, ModelState):
    model = Note
    fields = ["title", "body"]

    class Meta:
        list_var = "notes"
        owner_field = "owner"
```

Order matters: `LoginRequiredMixin` and `UserScopedMixin` go *before* `ModelState`. The MRO walks left to right, so the auth and scoping checks run before the standard CRUD machinery.

### DRF-style permission classes

```python
from reflex_django.permissions import IsAuthenticated, IsStaff


class AdminToolState(AppState, ModelCRUDView):
    model = Tool
    serializer_class = ToolSerializer

    class Meta:
        list_var = "tools"
        permission_classes = (IsAuthenticated, IsStaff)
```

Permission classes are called with `(state, action_name)` on every dispatch and must return `True`. If any returns `False`, the dispatch is rejected.

### Building your own base class

If most of your CRUD pages need login + user-scoping, factor it out:

```python
# myapp/state_bases.py
from reflex_django.mixins import LoginRequiredMixin, UserScopedMixin
from reflex_django.state import ModelState


class AuthScopedModelState(LoginRequiredMixin, UserScopedMixin, ModelState):
    """Project-wide CRUD base: requires login, scopes to current user."""
    class Meta:
        abstract = True
        owner_field = "owner"
```

```python
# blog/views.py
class PostState(AuthScopedModelState):
    model = Post
    fields = ["title", "content"]

    class Meta(AuthScopedModelState.Meta):
        list_var = "posts"
```

---

## Session-login mixin (for canned auth pages)

The built-in login page uses a special mixin called `session_auth_mixin`:

```python
from reflex_django.mixins import session_auth_mixin, SessionAuthConfig
from reflex_django import DjangoUserState


config = SessionAuthConfig(
    login_url="/login",
    post_login_url="/",
    post_logout_url="/login",
    username_field="username",
    min_password_length=8,
)

AuthBase = session_auth_mixin(config, base=DjangoUserState)


class MyAuthState(AuthBase):
    """Now has .login(), .logout(), .register() methods."""
```

You don't usually need this directly — `add_auth_pages()` wires it up for you. It's here for projects building a custom auth UI on top of the same primitives.

---

## When not to bother with mixins

Honestly: most of the time. `ModelState` covers 90% of cases with no composition required. Reach for mixins when:

- You explicitly want fewer capabilities (security via removed methods).
- You want to centralize a project-wide pattern (login + scope, audit log, etc.).
- You want to share behavior across CRUD and non-CRUD states.

If you're starting your first `reflex-django` project, skip this page and come back when you actually feel the need.

---

**Next:** [Forms & validation →](forms_and_validation.md)
