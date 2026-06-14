---
level: intermediate
tags: [crud, modelstate]
---

# CRUD with ModelState

**What you'll learn:** How `ModelState` declares a Django model and field list, then generates reactive vars, handlers, pagination, search, and validation hooks for a standard CRUD page.

**When you need this:**

- Your page is mostly one model with list, edit, save, and delete.
- You want less boilerplate than the manual approach in [CRUD the manual way](../guides/crud.md#manual).

`ModelState` is the declarative version of the inventory page you wrote by hand. You declare `model` and `fields`; the framework generates state variables, `load`/`save`/`delete` handlers, and list refresh logic. You still write the UI.

---

## The smallest CRUD state

```python
# shop/views.py
from reflex_django.states import ModelState
from shop.models import Product


class ProductState(ModelState):
    model = Product
    fields = ["name", "price", "sku", "is_active"]
    ordering = ("-created_at",)
    list_var = "products"
```

From those lines you get:

- Reactive list: `ProductState.products` (or `ProductState.data` if you omit `list_var`)
- Form fields: `name`, `price`, `sku`, `is_active` with `set_<field>` setters
- Handlers: `refresh`, `load`, `save`, `create`, `delete`, `cancel_edit`, `filter`, `paginate`
- Tracking vars: `editing_id`, `form_reset_key`, `error`, `search`

You write components; `ModelState` writes the wiring.

---

## How assembly works (briefly)

When Python defines `class ProductState(ModelState):`, a small assembly step runs:

1. **Build a serializer** from `model` + `fields` (unless you pass `serializer_class`).
2. **Declare state fields** with Python types matching Django fields.
3. **Inject handlers** for list load, save, delete, and edit mode.
4. **Register helper vars** (`editing_id`, pagination, search) when configured.

At runtime, each event goes through a dispatch pipeline: bind request context, check permissions, validate, hit the database, update reactive vars, send the diff to the browser. Override hooks at any stage.

---

## A complete catalog page

### Model

```python
# shop/models.py
from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=120)
    sku = models.CharField(max_length=32, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
```

### State

```python
# shop/views.py
import reflex as rx
from reflex_django.pages.decorators import page
from reflex_django.states import ModelState
from shop.models import Product


class ProductState(ModelState):
    model = Product
    fields = ["name", "price", "sku", "is_active"]
    ordering = ("-created_at",)
    search_fields = ("name", "sku")
    list_var = "products"
    paginate_by = 10
    structured_errors = True
    run_model_validation = True
    reset_after_save = True
```

!!! tip "Class body vs inner Meta"
    v1.0 prefers settings on the class body (`paginate_by = 10`) for IDE autocomplete. An inner `class Meta(ModelCRUDMeta):` still works for overrides.

### UI (excerpt)

```python
def products_page() -> rx.Component:
    errs = ProductState.field_errors
    return rx.vstack(
        rx.heading("Catalog"),
        rx.hstack(
            rx.input(
                placeholder="Search",
                value=ProductState.search,
                on_change=ProductState.set_search,
            ),
            rx.button("Refresh", on_click=ProductState.refresh),
            rx.button("Add new", on_click=ProductState.create),
        ),
        rx.cond(
            ProductState.editing_id != -1,
            rx.form(
                rx.vstack(
                    rx.input(value=ProductState.name, on_change=ProductState.set_name),
                    rx.cond(errs["name"] != "", rx.text(errs["name"], color="red", size="1")),
                    rx.button("Save", on_click=ProductState.save),
                    rx.button("Cancel", on_click=ProductState.cancel_edit, variant="ghost"),
                ),
                key=ProductState.form_reset_key,
            ),
        ),
        rx.foreach(ProductState.products, product_row),
        spacing="4",
        padding="2em",
    )


def product_row(row: dict) -> rx.Component:
    return rx.hstack(
        rx.text(row["name"], weight="bold"),
        rx.badge(row["sku"]),
        rx.spacer(),
        rx.button("Edit", on_click=ProductState.load(row["id"])),
        rx.button("Delete", on_click=ProductState.delete(row["id"]), color_scheme="red"),
    )


@page(route="/products", title="Products", on_load=ProductState.refresh)
def index() -> rx.Component:
    return products_page()
```

With `structured_errors = True`, per-field messages live in `ProductState.field_errors` (the default name when `list_var` is customized, assembly sets `field_errors_var` accordingly).

---

## Handlers and variables you get for free

| Handler | What it does |
|:---|:---|
| `refresh()` | Reload the list with current search, filter, and page |
| `create()` | Enter "new row" mode and save on next `save()` |
| `load(pk)` | Enter edit mode for one row |
| `save()` | Validate, create or update, reload list |
| `delete(pk)` | Delete one row and reload |
| `cancel_edit()` | Leave edit mode and clear the form |
| `filter(**kwargs)` | Apply ORM filter kwargs and reload |
| `clear_filter()` | Clear stored filter and reload |
| `paginate(page=..., page_size=...)` | Jump page when `paginate_by` is set |

| Variable | What it is |
|:---|:---|
| `products` (or `data`) | Current page of serialized rows |
| `editing_id` | PK being edited, or `-1` for new |
| `error` | Top-level error message |
| `search` | Current search string |
| `form_reset_key` | Bump on `<form key=...>` to remount inputs |
| `field_errors` | Per-field errors when `structured_errors = True` |
| `page`, `page_size`, `total_count`, `page_count` | Pagination when enabled |

---

## Pagination and search

Set `paginate_by = 10` on the class body. That enables `page`, `page_size`, `total_count`, `page_count`, plus `paginate`, `next_page`, and `prev_page`.

Set `search_fields = ("name", "sku")` for case-insensitive `icontains` search combined with `OR`. Bind `ProductState.search` in the UI and call `refresh()` after the user searches.

For richer filters, override `filter_queryset`:

```python
class ProductState(ModelState):
    model = Product
    fields = ["name", "price", "is_active"]
    only_active: bool = True

    def filter_queryset(self, qs):
        qs = super().filter_queryset(qs)
        if self.only_active:
            qs = qs.filter(is_active=True)
        return qs
```

---

## Validation hooks

Every save runs three stages (opt in where noted):

```text
get_state_data()
     |
clean_<field>  (return an error string, or "" when valid)
     |
validate_state(ctx, data)  (return a dict of field errors)
     |
clean_state(data)  (normalize values before save)
     |
full_clean()  (when run_model_validation = True)
     |
await instance.asave()
```

Example:

```python
class ProductState(ModelState):
    model = Product
    fields = ["name", "price", "sku", "is_active"]
    structured_errors = True
    run_model_validation = True

    def clean_price(self, value) -> str:
        try:
            if float(value) < 0:
                return "Price cannot be negative."
        except (TypeError, ValueError):
            return "Price must be a number."
        return ""

    def clean_state(self, data: dict) -> dict:
        data = dict(data)
        if isinstance(data.get("sku"), str):
            data["sku"] = data["sku"].strip().upper()
        return data

    def validate_state(self, ctx, data: dict) -> dict[str, str]:
        errors: dict[str, str] = {}
        if data.get("is_active") and not data.get("sku"):
            errors["sku"] = "Active products need a SKU."
        return errors
```

Use `clean_<field>` for quick per-field checks. Use `clean_state` to normalize. Use `validate_state` for cross-field rules.

---

## User-scoped rows

Override three hooks, or use `UserScopedMixin`:

```python
from reflex_django.state.mixins import UserScopedMixin


class TodoState(UserScopedMixin, ModelState):
    model = Todo
    fields = ["title", "done"]
    scope_field = "owner_id"   # FK column name; use "owner" for the relation field
    list_var = "todos"
```

`UserScopedMixin` filters `get_queryset`, `get_object_lookup`, and `get_create_kwargs` by the logged-in user. See [Mixins](../guides/mixins.md) for manual composition.

---

## Read-only lists

When you only need a list (no form, no save), use `ModelListView`:

```python
from reflex_django.states import AppState
from reflex_django.state import ModelListView


class CatalogState(AppState, ModelListView):
    model = Product
    fields = ["name", "price", "sku"]
    search_fields = ("name",)
    paginate_by = 20
    list_var = "products"
```

---

## When ModelState is not the right fit

- Multi-model forms or wizards
- Lists built from heavy aggregations
- Pages where CRUD is not the main job

For those, stay with plain `AppState` as in [CRUD the manual way](../guides/crud.md#manual). If you need an explicit serializer class or named handlers like `save_post`, see [ModelCRUDView](../guides/crud.md#modelcrudview).

---

## Troubleshooting

| Symptom | Likely cause |
|:---|:---|
| List stays empty after save | Check `list_var` matches what the UI binds (`data` is the default). |
| Field errors do not show | Set `structured_errors = True` and bind `field_errors`. |
| Form keeps stale values | Put `key=State.form_reset_key` on `rx.form`. |
| Users see each other's rows | Add scoping hooks or `UserScopedMixin`. |

---

## What just happened?

You declared `model` and `fields` once, got generated handlers and reactive vars, and learned the validation and scoping hooks you will override in real projects. That is the recommended default for standard CRUD pages.

**Next up:** [ModelCRUDView with serializers →](../guides/crud.md#modelcrudview)