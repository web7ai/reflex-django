---
level: intermediate
tags: [crud, comparison]
---

# Choosing ModelState vs ModelCRUDView

**What you'll learn:** Which declarative CRUD class to pick for a new page, and how small a refactor is if you switch later.

**When you need this:**

- You have seen both `ModelState` and `ModelCRUDView` and want one decision page.
- You are planning several CRUD screens and want consistent naming across the project.

Both classes run the same dispatch pipeline, validation hooks, and `Meta` options. Switching later is a small rename refactor, not a rewrite.

---

## Side by side

```python
# ModelState (recommended for most new pages)
from reflex_django.states import ModelState


class ProductState(ModelState):
    model = Product
    fields = ["name", "price", "sku"]
    list_var = "products"
```

```python
# ModelCRUDView (explicit serializer + named handlers)
from reflex_django.states import AppState
from reflex_django.state import ModelCRUDView


class ProductState(AppState, ModelCRUDView):
    model = Product
    serializer_class = ProductSerializer
    list_var = "products"
    save_event = "save_product"
    delete_event = "delete_product"
```

| | `ModelState` | `ModelCRUDView` |
|:---|:---|:---|
| Inheritance | One parent: `ModelState` | Compose: `AppState, ModelCRUDView` |
| Serializer | Auto-built from `fields` | You provide `serializer_class` |
| Default list var | `data` | plural model name (e.g. `products`) |
| Default save | `save()` | `save_product` (model-dependent) |
| Default delete | `delete(pk)` | `delete_product(pk)` |
| Trade-off | Less explicit, fewer files | More explicit API surface |

---

## Feature parity

These work the same on both classes:

- Pagination (`paginate_by`), search (`search_fields`), structured errors
- Hooks: `get_queryset`, `filter_queryset`, `get_object_lookup`, `get_create_kwargs`
- Validation: `clean_<field>`, `validate_state`, `clean_state`, `run_model_validation`
- Lifecycle: `before_save`, `after_save`, `before_delete`, `after_delete`
- Mixins from `reflex_django.state.mixins` (see [Mixins](../guides/mixins.md))

Nothing is exclusive to one class.

---

## When ModelState is the better choice

- No serializer exists yet for this model.
- The page is a one-off prototype.
- Generic handler names (`save`, `delete`) are fine.

```python
class TaskState(ModelState):
    model = Task
    fields = ["title", "done"]
    list_var = "tasks"
```

Five lines of declaration, then your UI.

---

## When ModelCRUDView is the better choice

- You already maintain a `ReflexDjangoModelSerializer` (or want one file per model schema).
- Many CRUD states share a module and verb-noun names reduce confusion (`save_order` vs six different `save` methods).
- You want to compose a subset of CRUD mixins (list + create only, for example).
- The same field list also backs an HTTP API and you want one serializer definition for Reflex.

```python
class OrderState(AppState, ModelCRUDView):
    model = Order
    serializer_class = OrderSerializer
    list_var = "orders"
    save_event = "save_order"
    delete_event = "delete_order"
```

---

## Read-only lists

Both stacks support read-only list states via `ModelListView`:

```python
from reflex_django.states import AppState
from reflex_django.state import ModelListView


class CatalogState(AppState, ModelListView):
    model = Product
    fields = ["name", "price"]
    search_fields = ("name",)
    paginate_by = 20
    list_var = "products"
```

No form fields, no save or delete handlers. Good for public catalogs and audit views.

---

## Decision tree

```text
Need a CRUD page?
|
+-- Standard list / edit / save / delete?
|   +-- No serializer yet, generic names OK     -> ModelState
|   +-- Explicit serializer or named handlers     -> ModelCRUDView
|
+-- Read-only list?                               -> ModelListView
|
+-- Wizard, multi-model, or unusual workflow?     -> AppState + manual handlers
|                                                  (see CRUD the manual way)
|
+-- Only some CRUD actions (e.g. list + create)?  -> ModelCRUDView + mixins
```

---

## Switching between them

```python
# Before
class TaskState(ModelState):
    model = Task
    fields = ["title", "done"]
    list_var = "tasks"


# After
class TaskState(AppState, ModelCRUDView):
    model = Task
    serializer_class = TaskSerializer
    list_var = "tasks"
    save_event = "save_task"
    delete_event = "delete_task"
```

Update UI call sites (`TaskState.save()` becomes `TaskState.save_task()` if you use named events). Hooks and `Meta` options stay the same.

---

## What just happened?

You compared the two declarative CRUD classes on naming, serializers, and composition. For most new pages, start with `ModelState`; reach for `ModelCRUDView` when explicit schemas or handler names matter.

**Next up:** [Mixins: compose your own state →](../guides/mixins.md)