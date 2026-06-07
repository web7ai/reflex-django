---
level: intermediate
tags: [crud, database]
---

# CRUD the manual way

**What you'll learn:** How to build a full list, create, edit, and delete page with plain `AppState` and the async ORM, so every query and check is visible in your code.

**When you need this:**

- The workflow is unusual (multi-step, conditional fields, or rules that do not fit declarative CRUD).
- You want to read every database call line by line before reaching for helpers.

<div class="rd-instructor" markdown>

Think of this page as writing Django views by hand, except the "view" is a Reflex state class and the browser updates reactively when you change state fields.

</div>

`reflex-django` ships declarative helpers (`ModelState`, `ModelCRUDView`) that generate most CRUD wiring for you. This page walks through the same product inventory feature without them. When you are done, you will know exactly what those helpers automate.

!!! tip "Prefer less code later?"
    After this page, [CRUD with ModelState](reactive_model_state.md) covers the same feature in a fraction of the lines.

---

## What we are building

A page at `/inventory` where a logged-in user manages their own products. Each user only sees their own rows.

- List with pagination
- Search by name, SKU, or category
- Create and edit (one form, edit mode toggled by `editing_id`)
- Delete with an ownership check on every read and write

Every database call uses the async ORM (`acreate`, `aget`, `asave`, `adelete`, `async for`, `acount`).

---

## 1. The model

```python
# inventory/models.py
from django.conf import settings
from django.db import models


class Product(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inventory_products",
    )
    name = models.CharField(max_length=128)
    sku = models.CharField(max_length=64, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=64, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.sku})"
```

Run migrations:

```bash
python manage.py makemigrations inventory
python manage.py migrate
```

---

## 2. The serializer

Reflex state fields are JSON-encoded before they reach the browser. `Decimal` and `datetime` need conversion. A serializer is the easiest path:

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

`await ProductSerializer(qs, many=True).adata()` turns a queryset into a JSON-safe list of dicts. More detail in [Model serializers](serializers.md).

---

## 3. The state shell

```python
# inventory/views.py
import reflex as rx
from django.db.models import Q
from reflex_django.pages.decorators import page
from reflex_django.states import AppState
from inventory.models import Product
from inventory.serializers import ProductSerializer


class InventoryState(AppState):
    products: list[dict] = []
    error: str = ""

    name: str = ""
    sku: str = ""
    price: str = ""
    category: str = ""
    is_active: bool = True

    editing_id: int = -1

    search_query: str = ""
    page: int = 1
    page_size: int = 8
    total_pages: int = 1
```

`InventoryState(AppState)` gives you `self.request.user` inside handlers. The fields above are reactive: assigning to them on the server updates the browser.

---

## 4. Scoped queryset helper

Centralize "current user plus search" once. Every other method calls this helper:

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

`filter(owner=user)` is the security boundary. As long as every read and write goes through this queryset (or repeats the same `owner=` filter), users cannot touch each other's rows by forging IDs.

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
            self.error = f"Could not load: {e}"

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

!!! warning "Stay async in handlers"
    Use `await qs.acount()`, not `qs.count()`. Blocking ORM calls inside `async def` handlers stall the event loop for every connected user.

---

## 6. Create and update

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
                product = await Product.objects.aget(pk=self.editing_id, owner=user)
                for k, v in data.items():
                    setattr(product, k, v)
                await product.asave()
                yield rx.toast.success(f"Updated '{product.name}'.")
            else:
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

On update, `aget(pk=..., owner=user)` ensures foreign IDs cannot be edited. On create, `owner=user` is always set server-side.

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

The form binds `price` as a string while the database stores `Decimal`. Convert at the boundary (`str(p.price)` when loading, string in `data` when saving).

---

## 8. The UI and page registration

```python
def inventory_page() -> rx.Component:
    return rx.container(
        rx.heading("My Inventory", size="8"),
        rx.cond(
            InventoryState.error != "",
            rx.callout(InventoryState.error, color_scheme="red"),
        ),
        rx.grid(form_card(), list_card(), columns="2", spacing="6"),
        padding="2rem",
    )


@page(route="/inventory", title="Inventory", on_load=InventoryState.load)
def index() -> rx.Component:
    return inventory_page()
```

Wire inputs with `value=` and `on_change=` to your state fields, and hook buttons to `InventoryState.save`, `start_editing`, and `delete`. That is the whole feature in one `views.py`.

---

## Manual vs declarative (preview)

| You write | Manual `AppState` | `ModelState` |
|:---|:---|:---|
| `load` handler | Yes | Generated |
| `save` / `delete` | Yes | Generated |
| Per-field state vars | Yes | Generated from `fields` |
| Pagination | Yes | `paginate_by = N` |
| Owner scoping | Yes (`_filtered_qs`) | `scope_field` or hooks |
| The UI components | Yes | Yes (still your job) |

Both styles can live in the same project. Use manual code when the page is unusual; use `ModelState` when it is standard CRUD.

---

## What just happened?

You built list, search, pagination, create, edit, and delete with explicit async ORM calls and per-user scoping. Every security check and validation path is in your file, which is the baseline the declarative CRUD helpers automate next.

**Next up:** [CRUD with ModelState →](reactive_model_state.md)