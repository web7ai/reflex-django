# Model state

`ModelState` is declarative CRUD for one Django model. It extends `AppState` and wires list, search, pagination, save, update, create, delete, validation, and form state from a model/serializer declaration.

## Quick example

```python
--8<-- "snippets/model_state_example.py"
```

```python
# shop/shop.py
import reflex as rx
from shop.views import ProductState, catalog

app = rx.App()
app.add_page(catalog, route="/products", title="Products", on_load=ProductState.load)
```

## `ModelState`

Use `ModelState` for normal CRUD pages:

```python
class ProductState(ModelState):
    model = Product
    fields = ["name", "price", "active"]
    paginate_by = 20
    search_fields = ("name",)
```

`ModelState[Product]` generic syntax is supported when you want the model inferred from the type parameter, but explicit `model = Product` is usually clearer.

Built-in reactive vars include `data`, `error`, `field_errors`, `editing_id`, `form_reset_key`, `page`, `page_size`, `page_count`, `total_count`, `search`, `ordering`, and one var per writable field.

## Handlers

| Handler | Purpose |
|:---|:---|
| `load` | Refresh the list |
| `refresh` | Alias for reload |
| `save` | Create or update depending on `editing_id` |
| `create` | Insert a new row |
| `update` | Update an existing row |
| `delete` | Remove row by id |
| `load_row` / `start_edit` | Load one row into form fields |
| `cancel_edit` | Clear edit state |
| `filter` | Apply search text |
| `paginate` | Change page/page size |
| `next_page` / `prev_page` | Move through pages when pagination is enabled |
| `go_to_page` | Clamp and load a specific page |
| `set_page_size` | Clamp page size to `max_page_size`, reset to page 1, reload |
| `clear_filter` | Clear stored queryset filter kwargs |
| `set_{search_var}` / `clear_{search_var}` | Search handlers when `search_fields` is set |
| `set_{ordering_var}` | Dynamic ordering handler when `allow_dynamic_ordering=True` |

Handlers are async and use Django's async ORM or `sync_to_async` wrappers internally where needed.

Set `use_canonical_api = False` to skip the canonical names such as `load`, `save`, `refresh`, and `delete` when you only want custom event names.

## Configuration

Set options as class attributes for IDE autocomplete, or inside `class Meta`. Class attributes win over `Meta`.

| Option | Default | Purpose |
|:---|:---|:---|
| `model` | required for generated serializer | Django model |
| `fields` / `state_fields` | serializer writable fields | Form/state vars |
| `serializer_class` / `Meta.serializer` | generated from model + fields | Serializer class |
| `list_var` | `data` on `ModelState` | List variable name |
| `error_var` | `error` | General error var |
| `structured_errors` | `False` | Populate `field_errors` |
| `field_errors_var` | `field_errors` | Field error var when structured errors are on |
| `editing_var` | `editing_id` | Current edit primary key |
| `read_only_fields` | serializer read-only | Extra fields excluded from forms |
| `required_fields` | first writable field | Required form fields |
| `exclude_from_row` | `()` | Serialized fields excluded from list rows |
| `ordering` | model `Meta.ordering`, `-created_at`, then `-pk` | Default ordering |
| `allow_dynamic_ordering` | `False` | Allow UI/order var to change ordering |
| `search_fields` | `()` | Text fields searched by `filter` |
| `paginate_by` | `None` | Page size; enables pagination vars |
| `max_page_size` | `100` | Upper bound for page size |
| `queryset_select_related` | `()` | `select_related` fields |
| `queryset_prefetch` | `()` | `prefetch_related` fields |
| `backend_class` | `DjangoORMBackend` | Storage backend |
| `permission_classes` | `()` | Permission classes checked before actions |
| `login_required_actions` | default write actions | Actions requiring auth |
| `run_model_validation` | `False` | Call model validation before save |
| `reset_after_save` | `True` | Clear form after save |
| `form_reset_var` | `form_reset_key` | Bumped after form reset |
| `use_form_submit` | `False` | Prefer submit-form handlers |
| `incremental_updates` | `False` | Patch list rows after mutations when safe |
| `use_canonical_api` | `True` | Register canonical handler aliases |

## `ModelCRUDView`

`ModelCRUDView` is the lower-level mixin stack. Combine it with `AppState` when you need legacy/plural list var names, custom event names, or finer assembly control:

```python
class NotesState(AppState, ModelCRUDView):
    serializer_class = NoteSerializer
    list_var = "notes"
    paginate_by = 20
    search_fields = ("title", "content")
```

After class creation, inspect resolved options with:

```python
NotesState.options().list_var
NotesState.get_options().permission_classes
```

## Serializers

When you omit an explicit serializer, reflex-django builds one from `model` and `fields`. For custom row shapes, set `Meta.serializer` or `serializer_class`:

```python
from reflex_django.serializers import ReflexDjangoModelSerializer


class ProductSerializer(ReflexDjangoModelSerializer):
    class Meta:
        model = Product
        fields = ("id", "name", "price")


class ProductState(ModelState):
    model = Product
    fields = ["name", "price"]

    class Meta:
        serializer = ProductSerializer
```

See [Serializers](serializers.md).

## Scoping

Filter by the logged-in user in `get_queryset`, or use `UserScopedMixin`:

```python
from reflex_django.state.mixins.scoping import UserScopedMixin


class TodoState(UserScopedMixin, ModelState):
    model = Todo
    fields = ["title", "done"]
    scope_field = "user_id"
```

`UserScopedMixin` filters list/query lookups by `self.get_user().pk` and adds the scope field on create. Always authorize with `self.request.user` or permission classes in handlers.

## Customizing lists

Override queryset hooks when list data needs filtering, joins, or custom ordering:

```python
class ProductState(ModelState):
    model = Product
    fields = ["name", "price"]
    queryset_select_related = ("owner",)
    queryset_prefetch = ("tags",)

    def get_queryset(self):
        return Product.objects.filter(active=True)

    def filter_queryset(self, queryset):
        return queryset.filter(owner=self.request.user)
```

`get_scoped_queryset()` applies `select_related`, `prefetch_related`, `filter_queryset`, search, and ordering in that order. Live updates also call `get_scoped_queryset()` before serializing a changed row.

## Permissions

Use `permission_classes` for CRUD actions:

```python
from reflex_django.state.mixins.permission import AllowAny, IsAuthenticated


class TodoState(ModelState):
    model = Todo
    fields = ["title", "done"]
    permission_classes = (IsAuthenticated,)
```

`login_required_actions` controls which generated actions require login. Write actions are protected by default.

Permission classes implement `has_permission(state, ctx)` and `has_object_permission(state, ctx, obj)`. `AllowAny` always passes. `IsAuthenticated` passes when the action context has a user. Failed checks raise `PermissionError` and flow through the state permission-denied handling.

## Incremental updates

Set `incremental_updates = True` to patch the list after local mutations:

```python
class ProductState(ModelState):
    model = Product
    fields = ["name", "price"]
    incremental_updates = True
```

Updates replace an existing row in place. Deletes remove the row and decrement total count. Creates are inserted when pagination is disabled; paginated creates fall back to a full refresh because the correct page can change.

For cross-tab or cross-request updates, see [Live updates](live-updates.md).

## Pluggable backend

`backend_class` defaults to `DjangoORMBackend`. Custom backends can implement the `StateBackend` contract when data does not come directly from Django ORM:

| Method | Purpose |
|:---|:---|
| `list_rows(ctx)` | Return serialized list rows |
| `retrieve(ctx, pk)` | Load one object |
| `create(ctx, data)` | Create and return an object |
| `update(ctx, instance, data)` | Update and return an object |
| `delete(ctx, instance)` | Delete an object |

Backends receive an `ActionContext` with resolved options, request/user context, and action data.

## Scaffolding

Generate a starting `ModelState` plus list/form/page components:

```bash
reflex django scaffold shop.Product --output shop/product_views.py
```

The scaffold uses the shared FieldSpec schema. See [Forms and FieldSpec](forms.md) and [CLI](cli.md).

**Next:** [Database](database.md), [Forms and FieldSpec](forms.md), or [Live updates](live-updates.md).
