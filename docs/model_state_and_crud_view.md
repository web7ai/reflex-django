# Choosing ModelState vs ModelCRUDView

You've seen both in the previous two pages. They do the same thing — declarative CRUD over a Django model — but with different defaults. This page is the one-place comparison so you can decide.

**TL;DR:**

- Use **`ModelState`** for new pages. Short, generic, one inheritance.
- Use **`ModelCRUDView`** when you need explicit serializers or named handlers (`save_post`, `posts`) instead of generic ones.

Both classes use the exact same dispatch pipeline, validation hooks, and Meta options. Switching between them later is a small refactor, not a rewrite.

---

## Side by side

```python
# ModelState — recommended for most cases
class ProductState(ModelState):
    model = Product
    fields = ["name", "price", "sku"]

    class Meta:
        list_var = "products"
```

```python
# ModelCRUDView — when you want an explicit serializer + named handlers
class ProductState(AppState, ModelCRUDView):
    model = Product
    serializer_class = ProductSerializer

    class Meta:
        list_var = "products"
        save_event = "save_product"
        delete_event = "delete_product"
```

Both produce a working CRUD state. The differences are visible in how you call them:

| | `ModelState` | `ModelCRUDView` |
|:---|:---|:---|
| Inheritance | `class X(ModelState)` (one parent) | `class X(AppState, ModelCRUDView)` (you compose) |
| Serializer | Auto-built from `fields` | Provided explicitly via `serializer_class` |
| List variable | `state.data` (default) or via `Meta.list_var` | Plural model name or via `Meta.list_var` |
| Save handler | `state.save()` | `state.save_product()` (or `state.save()` if you don't set `save_event`) |
| Delete handler | `state.delete(pk)` | `state.delete_product(pk)` (or `state.delete(pk)`) |
| What you give up | A bit of explicitness | A line of code (no serializer file) |

---

## Feature parity

These all work identically on both classes:

- All `Meta` options (`list_var`, `ordering`, `paginate_by`, `search_fields`, `reset_after_save`, …)
- All hooks (`get_queryset`, `filter_queryset`, `get_object_lookup`, `get_create_kwargs`, `clean_<field>`, `validate_state`, `before_save`, `after_save`, …)
- All mixins from [`reflex_django.mixins`](reflex_django_mixins.md)
- Pagination, search, structured errors, form reset

Nothing is "only available on one of them".

---

## When `ModelState` is the better choice

- You don't already have a serializer for this model.
- The page is a one-off — you don't need to reuse the schema elsewhere.
- You want the smallest possible amount of code.
- You're prototyping.

```python
class TaskState(ModelState):
    model = Task
    fields = ["title", "done"]

    class Meta:
        list_var = "tasks"

# 5 lines. Done.
```

---

## When `ModelCRUDView` is the better choice

- You already have a serializer (typically from DRF) and you want to reuse it.
- You have many CRUD pages and want their state APIs to read like a small admin DSL — `state.save_order()` is clearer than `state.save()` when six similar states live in the same module.
- You want to compose explicit mixins (e.g. "list + create only, no edit, no delete") instead of subclassing the all-in-one `ModelState`. See [Mixins](reflex_django_mixins.md).
- You want to surface the same schema to both Reflex (via this state) and an HTTP endpoint (via DRF) without duplicating field definitions.

```python
class OrderState(AppState, ModelCRUDView):
    model = Order
    serializer_class = OrderSerializer   # shared with /api/orders/

    class Meta:
        list_var = "orders"
        save_event = "save_order"
        delete_event = "delete_order"
        permission_classes = (StaffOnly,)
```

---

## Read-only lists

If you only need a list — no editing, no deletes — both classes have a read-only sibling: `ModelListView`. It strips the writable fields and `save`/`delete` handlers, leaving just `refresh`, `filter`, `paginate`.

```python
from reflex_django.state import ModelListView

class CatalogState(ModelListView):
    model = Product
    fields = ["name", "price"]
    search_fields = ("name",)

    class Meta:
        list_var = "products"
        paginate_by = 20
```

Good for public-facing product catalogs, search results, audit logs.

---

## A decision tree

```text
Need a CRUD page?
│
├── Mostly standard (list/edit/save/delete)?
│   │
│   ├── Yes, simple naming is fine               → ModelState
│   │
│   ├── Already have a DRF serializer?           → ModelCRUDView
│   │
│   └── Want plural / verb-noun handler names?   → ModelCRUDView
│
├── Read-only list?                              → ModelListView
│
├── Weird workflow (wizard, multi-model form,
│   computed list, etc.)?                        → Plain AppState + manual handlers
│                                                  (see "CRUD the manual way")
│
└── Need to compose only some CRUD operations
    (e.g. list + create, no delete)?             → ModelCRUDView + explicit mixins
```

---

## Switching between them

If you start with `ModelState` and later realize you want explicit serializers:

```python
# Before
class TaskState(ModelState):
    model = Task
    fields = ["title", "done"]

    class Meta:
        list_var = "tasks"


# After
from blog.serializers import TaskSerializer

class TaskState(AppState, ModelCRUDView):
    model = Task
    serializer_class = TaskSerializer

    class Meta:
        list_var = "tasks"
        save_event = "save_task"
        delete_event = "delete_task"
```

You'll need to update the UI call sites: `TaskState.save()` becomes `TaskState.save_task()`, etc. Everything else (hooks, Meta options, validation) stays the same.

---

**Next:** [Mixins — compose your own state →](reflex_django_mixins.md)
