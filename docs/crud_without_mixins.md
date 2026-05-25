# CRUD the manual way

`reflex-django` ships a declarative CRUD helper (`ModelState`) that generates list/save/delete handlers for you. But sometimes you want every step in front of you — for an unusual workflow, for clearer reading, or just because you like writing the code yourself.

This page walks through a complete user-scoped product inventory page using plain `AppState` and the async ORM. By the end you'll have list + search + pagination + create + edit + delete in one file you wrote line by line.

If you want the same thing in a third as much code, jump to [CRUD with ModelState](reactive_model_state.md) when you're done here.

---

## What we're building

A page at `/inventory` that lets a logged-in user manage their own products. Each user only sees their own rows. Features:

- List with pagination
- Search by name / SKU / category
- Create new product
- Edit existing product (form switches to "edit mode")
- Delete with ownership check

Every database call uses the async ORM (`acreate`, `aget`, `asave`, `adelete`, `async for`).

---

## 1. The model

```python
# inventory/models.py
from django.conf import settings
from django.db import models


class Product(models.Model):
    owner       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inventory_products",
    )
    name        = models.CharField(max_length=128)
    sku         = models.CharField(max_length=64, unique=True)
    price       = models.DecimalField(max_digits=10, decimal_places=2)
    category    = models.CharField(max_length=64, blank=True)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.sku})"
```

Standard Django. `owner` is the per-user scope; everything else is regular fields.

Run the migration:

```bash
python manage.py makemigrations inventory
python manage.py migrate
```

---

## 2. The serializer

Reflex state fields get JSON-encoded before they're shipped to the browser. Decimal and datetime aren't JSON-friendly, so we convert. A serializer is the easiest way:

```python
# inventory/serializers.py
from reflex_django.serializers import ReflexDjangoModelSerializer
from inventory.models import Product


class ProductSerializer(ReflexDjangoModelSerializer):
    class Meta:
        model = Product
        fields = ("id", "name", "sku", "price", "category", "is_active", "created_at")
        read_only_fields = ("id", "created_at")
```

`await ProductSerializer(qs, many=True).adata()` turns a queryset into a JSON-safe list of dicts. More on serializers in [Model serializers](serializers.md).

---

## 3. The state shell

We'll fill in the methods step by step. Here's the skeleton:

```python
# inventory/views.py
import reflex as rx
from django.db.models import Q
from reflex_django.state import AppState
from inventory.models import Product
from inventory.serializers import ProductSerializer


class InventoryState(AppState):
    # what the UI renders
    products: list[dict] = []
    error: str = ""

    # form bindings
    name: str = ""
    sku: str = ""
    price: str = ""
    category: str = ""
    is_active: bool = True

    # which row are we editing? -1 = creating new
    editing_id: int = -1

    # search and pagination
    search_query: str = ""
    page: int = 1
    page_size: int = 8
    total_pages: int = 1
```

`InventoryState(AppState)` is what gives us `self.request.user` later. The fields are reactive — assigning to them on the server updates the browser automatically.

---

## 4. Build the queryset (scoped, searched, paginated)

This helper centralizes the "scope to current user + apply search" logic. Every other method calls it, so we only get the scope right once:

```python
    def _filtered_qs(self):
        user = self.request.user
        if not user.is_authenticated:
            raise PermissionError("Sign in first.")
        qs = Product.objects.filter(owner=user)
        q = self.search_query.strip()
        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(sku__icontains=q)
                | Q(category__icontains=q)
            )
        return qs.order_by("-created_at")
```

`filter(owner=user)` is the security boundary. As long as every read/write goes through this queryset, a user can't touch another user's rows even by forging IDs.

---

## 5. Load and paginate

```python
    @rx.event
    async def load(self):
        self.error = ""
        try:
            qs = self._filtered_qs()
            total = await qs.acount()
            self.total_pages = max(1, (total + self.page_size - 1) // self.page_size)
            self.page = min(self.page, self.total_pages)
            start = (self.page - 1) * self.page_size
            page_qs = qs[start : start + self.page_size]
            self.products = await ProductSerializer(page_qs, many=True).adata()
        except PermissionError as e:
            self.error = str(e)
            self.products = []
        except Exception as e:
            self.error = f"Couldn't load: {e}"
```

Two small details:

- `await qs.acount()` is the async row count. Never call `qs.count()` in an async handler.
- The slice `qs[start : start + page_size]` becomes a `LIMIT/OFFSET` in SQL. It doesn't materialize the whole table.

Wire up search and page navigation:

```python
    @rx.event
    async def set_search(self, value: str):
        self.search_query = value
        self.page = 1
        await self.load()

    @rx.event
    async def next_page(self):
        if self.page < self.total_pages:
            self.page += 1
            await self.load()

    @rx.event
    async def prev_page(self):
        if self.page > 1:
            self.page -= 1
            await self.load()
```

---

## 6. Create / update — one handler for both

```python
    def _validation_error(self) -> str | None:
        if not self.name.strip():
            return "Name is required."
        if not self.sku.strip():
            return "SKU is required."
        try:
            if float(self.price) <= 0:
                return "Price must be positive."
        except ValueError:
            return "Price must be a number."
        return None

    @rx.event
    async def save(self):
        self.error = ""
        user = self.request.user
        if not user.is_authenticated:
            return rx.toast.error("Please log in.")

        err = self._validation_error()
        if err:
            self.error = err
            return

        data = {
            "name": self.name.strip(),
            "sku": self.sku.strip().upper(),
            "price": self.price,
            "category": self.category.strip(),
            "is_active": self.is_active,
        }

        try:
            if self.editing_id >= 0:
                # update — fetch with owner scope so users can't edit foreign rows
                product = await Product.objects.aget(pk=self.editing_id, owner=user)
                for k, v in data.items():
                    setattr(product, k, v)
                await product.asave()
                yield rx.toast.success(f"Updated '{product.name}'.")
            else:
                # create — owner is always the current user
                new = await Product.objects.acreate(owner=user, **data)
                yield rx.toast.success(f"Added '{new.name}'.")

            self.reset_form()
            await self.load()
        except Exception as e:
            self.error = f"Save failed: {e}"

    @rx.event
    def reset_form(self):
        self.name = ""
        self.sku = ""
        self.price = ""
        self.category = ""
        self.is_active = True
        self.editing_id = -1
        self.error = ""
```

The important bit: when we update, we fetch with `aget(pk=..., owner=user)`. If the user passes an ID they don't own, `aget` raises `DoesNotExist` and the row stays safe. Same on the create path — the owner is `user`, period; we never trust the client to tell us who owns the row.

---

## 7. Edit and delete

```python
    @rx.event
    async def start_editing(self, product_id: int):
        try:
            p = await Product.objects.aget(pk=product_id, owner=self.request.user)
        except Product.DoesNotExist:
            return rx.toast.error("Not found.")
        self.editing_id = p.id
        self.name = p.name
        self.sku = p.sku
        self.price = str(p.price)
        self.category = p.category
        self.is_active = p.is_active

    @rx.event
    async def delete(self, product_id: int):
        try:
            p = await Product.objects.aget(pk=product_id, owner=self.request.user)
            name = p.name
            await p.adelete()
            yield rx.toast.success(f"Deleted '{name}'.")
            await self.load()
        except Product.DoesNotExist:
            return rx.toast.error("Not found.")
```

Same ownership check pattern as before. Notice that `self.price = str(p.price)` — the form field is a string, but the DB value is `Decimal`. Convert at the boundary.

---

## 8. The UI

```python
def inventory_page() -> rx.Component:
    return rx.container(
        rx.heading("My Inventory", size="8"),
        rx.cond(
            InventoryState.error != "",
            rx.callout(InventoryState.error, color_scheme="red"),
        ),
        rx.grid(
            form_card(),
            list_card(),
            columns="2",
            spacing="6",
        ),
        padding="2rem",
    )


def form_card() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.heading(
                rx.cond(InventoryState.editing_id >= 0, "Edit product", "Add product"),
                size="4",
            ),
            rx.input(placeholder="Name",     value=InventoryState.name,     on_change=InventoryState.set_name),
            rx.input(placeholder="SKU",      value=InventoryState.sku,      on_change=InventoryState.set_sku),
            rx.input(placeholder="Price",    value=InventoryState.price,    on_change=InventoryState.set_price),
            rx.input(placeholder="Category", value=InventoryState.category, on_change=InventoryState.set_category),
            rx.hstack(
                rx.text("Active"),
                rx.switch(checked=InventoryState.is_active, on_change=InventoryState.set_is_active),
            ),
            rx.hstack(
                rx.button("Save", on_click=InventoryState.save),
                rx.cond(
                    InventoryState.editing_id >= 0,
                    rx.button("Cancel", on_click=InventoryState.reset_form, variant="ghost"),
                ),
            ),
            spacing="3",
        ),
        padding="1.5rem",
    )


def list_card() -> rx.Component:
    return rx.vstack(
        rx.input(
            placeholder="Search by name, SKU, or category…",
            value=InventoryState.search_query,
            on_change=InventoryState.set_search,
        ),
        rx.foreach(InventoryState.products, product_row),
        rx.hstack(
            rx.button("Previous", on_click=InventoryState.prev_page, disabled=InventoryState.page == 1),
            rx.text(f"Page {InventoryState.page} of {InventoryState.total_pages}"),
            rx.button("Next", on_click=InventoryState.next_page, disabled=InventoryState.page == InventoryState.total_pages),
            justify="between",
        ),
        spacing="3",
    )


def product_row(row: dict) -> rx.Component:
    return rx.hstack(
        rx.vstack(
            rx.text(row["name"], weight="bold"),
            rx.hstack(rx.badge(row["sku"]), rx.text(f"${row['price']}")),
            align_items="start",
        ),
        rx.spacer(),
        rx.button("Edit",   on_click=InventoryState.start_editing(row["id"]), variant="surface"),
        rx.button("Delete", on_click=InventoryState.delete(row["id"]),         color_scheme="red", variant="ghost"),
        padding="0.75rem",
        border_bottom="1px solid rgba(0,0,0,0.08)",
    )
```

Register the page with `@template`:

```python
from reflex_django import template

@template(route="/inventory", title="Inventory", on_load=InventoryState.load)
def index() -> rx.Component:
    return inventory_page()
```

That's the whole feature — list, search, paginate, create, edit, delete — in a single `views.py` file.

---

## Why you might prefer this style

- **Total visibility.** Every query, every check, every error path is right there. No hooks to override.
- **Custom workflows.** Multi-step forms, conditional fields, weird business rules — they all fit naturally.
- **Easy to learn.** It's just async Python and the Django ORM. Anyone who's seen Django can read it.

## And why you might prefer `ModelState`

- **Far less code.** The same feature can be ~25 lines instead of ~150.
- **Less to maintain.** Sensible defaults handle pagination, validation, scoping.
- **Consistent UX.** All your CRUD pages behave the same way.

Both styles work in the same project. Use the manual style when the page is unusual, and `ModelState` when it's standard. See [CRUD with ModelState](reactive_model_state.md) for the declarative version.

---

## Manual vs declarative cheat sheet

| You write | Manual | `ModelState` |
|:---|:---|:---|
| The `load` handler | Yes | Generated |
| The `save` handler | Yes | Generated |
| The `delete` handler | Yes | Generated |
| Per-field state vars | Yes | Generated from `fields = [...]` |
| Pagination | Yes | `paginate_by = X` in `Meta` |
| Owner scoping | Yes (`_filtered_qs`) | `UserScopedMixin` or override `get_queryset` |
| Custom validation | Yes | `clean_<field>` or `validate_state` |
| The UI components | Yes | Yes (still your job) |

---

**Next:** [CRUD with ModelState →](reactive_model_state.md)
