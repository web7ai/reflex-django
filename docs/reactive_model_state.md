# CRUD with ModelState

`ModelState` is the declarative version of the CRUD page you wrote in [CRUD the manual way](crud_without_mixins.md). You tell it what model to manage and which fields to expose; it generates the state variables, the `load`/`save`/`delete` handlers, the pagination, and the validation hooks for you.

This page walks through a complete product catalog page using `ModelState`, then explains every override you'll reach for: validation, scoping, search, custom hooks.

---

## The smallest possible CRUD state

```python
# shop/views.py
from reflex_django.state import ModelState
from shop.models import Product


class ProductState(ModelState):
    model = Product
    fields = ["name", "price", "sku", "is_active"]
    ordering = ("-created_at",)

    class Meta:
        list_var = "products"
```

That's it. From those six lines you get, for free:

- A reactive list variable: `ProductState.products`
- Reactive form fields: `name`, `price`, `sku`, `is_active` (with auto-generated setters: `set_name`, etc.)
- Handlers: `load`, `save`, `create`, `delete`, `refresh`, `filter`, `paginate`, `cancel_edit`
- Tracking: `editing_id` (the PK of the row being edited, or `-1` for "new"), `form_reset_key`, `error`

You write the UI; `ModelState` writes the wiring.

---

## How it does it (briefly)

`ModelState` has a small metaclass that runs at **class definition time** — meaning the moment Python parses your `class ProductState(ModelState):` line, the following happens:

1. **Build a serializer.** Either uses your `serializer_class`, or auto-builds a `ReflexDjangoModelSerializer` from `model` + `fields`.
2. **Declare state fields.** For each entry in `fields`, add a reactive variable to the class with the matching Python type (`str` for `CharField`, `Decimal` for `DecimalField`, `bool` for `BooleanField`, …) and an auto-generated `set_<field>` setter.
3. **Inject default handlers.** If you didn't define `load`, `save`, etc. yourself, the metaclass adds canonical implementations.
4. **Register helper vars.** `editing_id`, `form_reset_key`, `error`, optional pagination/search fields.

Then at **runtime**, when an event fires, `ModelState` runs the handler through a small **dispatch pipeline**: bind the request context (so `self.request.user` works), run permission checks, run validation hooks, hit the database, update the reactive vars, send diff back to the browser.

You can hook into any stage of that pipeline by overriding methods. We'll see how below.

---

## A complete product catalog page

### 1. The model

```python
# shop/models.py
from django.db import models


class Product(models.Model):
    name        = models.CharField(max_length=120)
    sku         = models.CharField(max_length=32, unique=True)
    price       = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.sku})"
```

### 2. The state — about 8 lines

```python
# shop/views.py
import reflex as rx
from reflex_django import template
from reflex_django.state import ModelState
from shop.models import Product


class ProductState(ModelState):
    model = Product
    fields = ["name", "price", "sku", "is_active"]
    ordering = ("-created_at",)
    search_fields = ("name", "sku")    # enables full-text-ish search across these columns

    class Meta:
        list_var = "products"           # generated list is `self.products`
        reset_after_save = True         # clear the form once a save succeeds
        run_model_validation = True     # call Django's full_clean() before save
        structured_errors = True        # populate `products_field_errors` for per-field UI
```

### 3. The UI — your job, but small

```python
def field(label: str, input_: rx.Component, err: rx.Var) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="2", weight="medium"),
        input_,
        rx.cond(err != "", rx.text(err, size="1", color="red")),
        spacing="1",
    )


def products_page() -> rx.Component:
    errs = ProductState.products_field_errors
    return rx.vstack(
        rx.heading("Catalog"),

        # toolbar
        rx.hstack(
            rx.input(
                placeholder="Search…",
                value=ProductState.search,
                on_change=ProductState.set_search,
            ),
            rx.button("Search", on_click=ProductState.refresh),
            rx.button("Clear",  on_click=ProductState.clear_filter, variant="outline"),
            rx.spacer(),
            rx.button("Add new", on_click=ProductState.create),
        ),

        # form (only visible while creating/editing)
        rx.cond(
            ProductState.editing_id != -1,
            rx.form(
                rx.vstack(
                    field("Name",  rx.input(value=ProductState.name,  on_change=ProductState.set_name),  errs["name"]),
                    field("SKU",   rx.input(value=ProductState.sku,   on_change=ProductState.set_sku),   errs["sku"]),
                    field("Price", rx.input(value=ProductState.price, on_change=ProductState.set_price), errs["price"]),
                    rx.hstack(
                        rx.text("Active"),
                        rx.switch(checked=ProductState.is_active, on_change=ProductState.set_is_active),
                    ),
                    rx.hstack(
                        rx.button("Save",   on_click=ProductState.save),
                        rx.button("Cancel", on_click=ProductState.cancel_edit, variant="ghost"),
                    ),
                ),
                key=ProductState.form_reset_key,    # remount on reset
            ),
        ),

        # list
        rx.foreach(ProductState.products, product_row),

        spacing="4",
        padding="2em",
    )


def product_row(row: dict) -> rx.Component:
    return rx.hstack(
        rx.text(row["name"], weight="bold"),
        rx.badge(row["sku"]),
        rx.text(f"${row['price']}"),
        rx.spacer(),
        rx.button("Edit",   on_click=ProductState.load(row["id"])),
        rx.button("Delete", on_click=ProductState.delete(row["id"]), color_scheme="red"),
        padding="0.5em",
        border_bottom="1px solid rgba(0,0,0,0.08)",
    )


@template(route="/products", title="Products", on_load=ProductState.refresh)
def index() -> rx.Component:
    return products_page()
```

That's a working CRUD page in something like 80 lines of Python total, including the UI.

---

## What you get for free

Once `ProductState` is defined, all of these are auto-generated. You can call them from your UI without writing them.

| Handler | What it does |
|:---|:---|
| `ProductState.refresh()` | Reload the list with current search/filter/page |
| `ProductState.create()` | Enter "new row" mode (sets `editing_id = -1`, clears the form) |
| `ProductState.load(pk)` | Enter "edit" mode for the row with this PK |
| `ProductState.save()` | Validate + create or update + reload |
| `ProductState.delete(pk)` | Delete the row + reload |
| `ProductState.cancel_edit()` | Leave edit mode, clear form |
| `ProductState.filter()` | Apply current search and reload |
| `ProductState.clear_filter()` | Clear search and reload |
| `ProductState.paginate(page)` | Jump to a specific page (if pagination is on) |

Variables you can bind in components:

| Variable | What it is |
|:---|:---|
| `ProductState.products` | List of dicts (the current page) |
| `ProductState.editing_id` | PK being edited, or `-1` |
| `ProductState.error` | Top-level error message |
| `ProductState.search` | Current search query string |
| `ProductState.form_reset_key` | Bump this on the `<form key=...>` to remount and reset |
| `ProductState.products_field_errors` | Dict of `{field: error_message}` when `structured_errors = True` |
| `ProductState.name`, `ProductState.price`, … | One per entry in `fields` |

---

## Pagination

Add one line to `Meta`:

```python
class Meta:
    list_var = "products"
    paginate_by = 10
```

That gives you four extra vars and three extra handlers:

| Var / handler | What it does |
|:---|:---|
| `ProductState.page` | Current page (1-indexed) |
| `ProductState.page_size` | Rows per page |
| `ProductState.total_count` | Total matching rows |
| `ProductState.page_count` | Total pages |
| `ProductState.next_page()` | Go to next page |
| `ProductState.prev_page()` | Go to previous page |
| `ProductState.paginate(page)` | Jump to a specific page |

---

## Search

Add `search_fields` at the class level:

```python
class ProductState(ModelState):
    model = Product
    fields = ["name", "price", "sku", "is_active"]
    search_fields = ("name", "sku", "category__name")    # ORM lookups OK
```

That gives you `ProductState.search` (a string) and the `filter()` handler. Search is case-insensitive `icontains` across the listed fields combined with `OR`.

For richer filtering, override `filter_queryset` (see below).

---

## Validation

`ModelState` runs validation in three stages on every save:

1. **`clean_<field>(self, value)`** — per-field cleaning. Return the cleaned value or raise `ValueError`.
2. **`validate_state(self)`** — cross-field checks on the in-memory state. Add issues to `self.error` or `self.<list_var>_field_errors`.
3. **`run_model_validation`** — call Django's `Model.full_clean()` on the instance. Django's own `validators=[...]` and `unique=True` checks run here.

```python
class ProductState(ModelState):
    model = Product
    fields = ["name", "price", "sku"]

    class Meta:
        list_var = "products"
        run_model_validation = True
        structured_errors = True

    def clean_sku(self, value: str) -> str:
        return value.strip().upper()

    def clean_price(self, value):
        try:
            n = float(value)
        except (TypeError, ValueError):
            raise ValueError("Price must be a number")
        if n < 0:
            raise ValueError("Price can't be negative")
        return value

    def validate_state(self):
        if self.is_active and not self.sku:
            self.products_field_errors["sku"] = "Active products need a SKU"
```

Field-level errors land in `<list_var>_field_errors`. Bind them in your form (see the UI above).

---

## User-scoped CRUD ("only show my rows")

This is the most common override. Two ways:

### Way 1 — override `get_queryset` and friends

```python
class TodoState(ModelState):
    model = Todo
    fields = ["title", "done"]

    class Meta:
        list_var = "todos"

    def get_queryset(self):
        return Todo.objects.filter(owner=self.request.user)

    def get_object_lookup(self, pk: int) -> dict:
        return {"pk": pk, "owner": self.request.user}

    def get_create_kwargs(self, state_data: dict) -> dict:
        return {**state_data, "owner": self.request.user}
```

Three hooks, one rule each:

- `get_queryset` — what rows are visible in the list and lookups
- `get_object_lookup` — how to find one row by ID (the ownership check on edit/delete)
- `get_create_kwargs` — extra fields injected when creating a new row

### Way 2 — use `UserScopedMixin`

```python
from reflex_django.mixins import UserScopedMixin

class TodoState(UserScopedMixin, ModelState):
    model = Todo
    fields = ["title", "done"]

    class Meta:
        list_var = "todos"
        owner_field = "owner"     # the FK field name on the model
```

The mixin does all three hooks for you. ([More on mixins](reflex_django_mixins.md).)

---

## Custom query filtering

Override `filter_queryset` to add filters beyond simple search:

```python
class ProductState(ModelState):
    model = Product
    fields = ["name", "price", "category"]
    search_fields = ("name",)

    only_active: bool = True

    def filter_queryset(self, qs):
        qs = super().filter_queryset(qs)
        if self.only_active:
            qs = qs.filter(is_active=True)
        return qs
```

Wire `only_active` to a toggle in the UI; bumping it re-triggers `filter()` and reloads.

---

## Custom save logic

The default `save` does: validate → instantiate or fetch → set fields → `asave()` → reload. If you need different behavior, override:

```python
class OrderState(ModelState):
    model = Order
    fields = ["customer", "amount", "status"]

    class Meta:
        list_var = "orders"

    async def save(self):
        # do something custom — then call the standard dispatch:
        from reflex_django.state import ACTION_SAVE
        await self.dispatch(ACTION_SAVE)
        # ...post-save side effects, e.g. send an email
```

For finer control, you can also override `before_save`, `after_save`, `before_delete`, `after_delete`. The full list lives in the [Mixins reference](reflex_django_mixins.md).

---

## Read-only model lists

If you just want a list, no editing, use `ModelListView` (a subset of `ModelState`):

```python
from reflex_django.state import ModelListView

class CatalogState(ModelListView):
    model = Product
    fields = ["name", "price", "sku"]
    search_fields = ("name",)

    class Meta:
        list_var = "products"
        paginate_by = 20
```

No form fields, no `save`/`delete` handlers. Just `refresh`, `filter`, `paginate`.

---

## Refresh after each event automatically

If you want the list to refresh on every event the page processes (not just after saves), set:

```python
class Meta:
    auto_refresh = True
```

For most apps, the explicit `await self.refresh()` after save/delete is enough.

---

## When `ModelState` isn't the right fit

`ModelState` is best for "this page is mostly one model, with standard list + edit + delete". It struggles a bit with:

- Multi-model forms (one form that creates a `User` and a `Profile` together).
- Wizards / multi-step flows.
- Pages where the "list" is computed from a complex aggregation.
- Anything where the page's primary job isn't CRUD.

For those, write plain `AppState` handlers as shown in [CRUD the manual way](crud_without_mixins.md). Mix freely — some pages can use `ModelState`, others can be hand-rolled.

If you specifically want explicit serializers (e.g. you're sharing a DRF schema), see [ModelCRUDView with serializers](crud_with_mixins_and_states.md).

---

## Troubleshooting

| Symptom | Likely cause |
|:---|:---|
| Save silently succeeds but the list doesn't refresh | Forgot `class Meta: list_var = "..."` — the default is `data`. |
| Field errors not showing | `structured_errors = True` is required, and bind to `<list_var>_field_errors`. |
| Form doesn't clear after save | Set `reset_after_save = True`, and bump `form_reset_key` on the `<form>` element. |
| `validate_state` runs but errors don't appear | Check whether you assigned to `self.error` (global) or `self.<list_var>_field_errors[field]` (per-field). |
| Edits to one user's row affect others | You didn't scope. Override `get_queryset` / `get_object_lookup` / `get_create_kwargs`, or use `UserScopedMixin`. |
| Decimal/datetime serialization errors | The auto-built serializer handles those; if you provide a custom `serializer_class`, make sure `datetime_format` and `decimal` handling are configured. |

---

**Next:** [ModelCRUDView with serializers →](crud_with_mixins_and_states.md) · [Or compare side-by-side →](model_state_and_crud_view.md)
