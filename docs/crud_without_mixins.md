# CRUD without mixins

Build **create, read, update, delete** flows with plain **`rx.State`**, Django async ORM, and **`ReflexDjangoModelSerializer`**—no `ModelCRUDView`, no `AppState`.

> Tutorial code below is **example application code** (not shipped with reflex-django). For the declarative stack, see [CRUD with mixins](crud_with_mixins_and_states.md).

> **Start here for mindset:** [State management — Part A (plain `rx.State` + bridges)](state_management.md#part-a--plain-rxstate-no-reflex-django-mixins-or-helper-states) explains why Django is already available in handlers without reflex-django mixins.

---

## Prerequisites

- [State management](state_management.md) — plain state vs helper states  
- [Serializers](serializers.md)  
- [Forms and validation](forms_and_validation.md)

---

## Model and serializer

*Example `catalog` app.*

```python
# catalog/models.py
from django.conf import settings
from django.db import models

class Product(models.Model):
    name = models.CharField(max_length=128)
    sku = models.CharField(max_length=64, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=32, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
```

```python
# catalog/serializers.py
from reflex_django.serializers import ReflexDjangoModelSerializer
from catalog.models import Product

class ProductSerializer(ReflexDjangoModelSerializer):
    class Meta:
        model = Product
        fields = ("id", "name", "sku", "price", "category", "is_active", "created_at")
        read_only_fields = ("id", "created_at")
```

Run migrations with `reflex django makemigrations` / `migrate`.

---

## State design

```python
# myapp/states/products.py
import reflex as rx
from django.db.models import Q
from reflex_django import current_user, require_login_user
from reflex_django.state import AppState
from catalog.models import Product
from catalog.serializers import ProductSerializer

class ProductsState(AppState):
    products: list[dict] = []
    products_error: str = ""

    # Form fields
    name: str = ""
    sku: str = ""
    price: str = ""
    category: str = ""
    is_active: bool = True
    editing_id: int = -1

    # Pagination / search / filters (not built into framework)
    page: int = 1
    page_size: int = 10
    search_query: str = ""
    filter_category: str = ""
    filter_active_only: bool = False
```

---

## List with pagination, search, and filters

```python
    def _filtered_qs(self):
        user = require_login_user()
        qs = Product.objects.filter(owner=user)
        q = self.search_query.strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(sku__icontains=q))
        if self.filter_category:
            qs = qs.filter(category=self.filter_category)
        if self.filter_active_only:
            qs = qs.filter(is_active=True)
        return qs.order_by("-created_at")

    @rx.event
    async def load_products(self):
        self.products_error = ""
        try:
            qs = self._filtered_qs()
            start = (self.page - 1) * self.page_size
            end = start + self.page_size
            page_qs = qs[start:end]
            self.products = await ProductSerializer(page_qs, many=True).adata()
        except Exception as exc:
            self.products_error = str(exc)

    @rx.event
    def set_search_query(self, value: str):
        self.search_query = value
        self.page = 1

    @rx.event
    async def next_page(self):
        self.page += 1
        await self.load_products()

    @rx.event
    async def prev_page(self):
        if self.page > 1:
            self.page -= 1
            await self.load_products()
```

> **Note:** reflex-django mixins provide `filter_queryset()` but **no** built-in `page` / `search_query` vars—you own pagination and search in manual or extended states.

---

## Create and update

```python
    def _validate(self) -> str | None:
        if not self.name.strip():
            return "Name is required."
        if not self.sku.strip():
            return "SKU is required."
        try:
            price = float(self.price)
            if price < 0:
                return "Price must be non-negative."
        except ValueError:
            return "Invalid price."
        return None

    @rx.event
    async def save_product(self):
        self.products_error = ""
        err = self._validate()
        if err:
            self.products_error = err
            return
        user = require_login_user()
        data = {
            "name": self.name.strip(),
            "sku": self.sku.strip(),
            "price": self.price,
            "category": self.category.strip(),
            "is_active": self.is_active,
        }
        try:
            if self.editing_id >= 0:
                product = await Product.objects.aget(
                    pk=self.editing_id, owner=user
                )
                for key, val in data.items():
                    setattr(product, key, val)
                await product.asave()
            else:
                await Product.objects.acreate(owner=user, **data)
            self._reset_form()
            await self.load_products()
        except Exception as exc:
            self.products_error = str(exc)

    def _reset_form(self):
        self.name = ""
        self.sku = ""
        self.price = ""
        self.category = ""
        self.is_active = True
        self.editing_id = -1
```

Optional: call `full_clean()` on the model inside `save` for Django field validation.

---

## Edit and delete

```python
    @rx.event
    async def start_edit(self, product_id: int):
        user = require_login_user()
        product = await Product.objects.aget(pk=product_id, owner=user)
        row = ProductSerializer(product).data
        self.editing_id = int(row["id"])
        self.name = row["name"]
        self.sku = row["sku"]
        self.price = str(row["price"])
        self.category = row.get("category") or ""
        self.is_active = bool(row.get("is_active", True))

    @rx.event
    async def delete_product(self, product_id: int):
        self.products_error = ""
        user = require_login_user()
        try:
            product = await Product.objects.aget(pk=product_id, owner=user)
            await product.adelete()
            await self.load_products()
        except Exception as exc:
            self.products_error = str(exc)

    @rx.event
    def cancel_edit(self):
        self._reset_form()
```

---

## Page wiring

```python
def products_page() -> rx.Component:
    return rx.vstack(
        rx.cond(
            ProductsState.products_error != "",
            rx.callout(ProductsState.products_error, color_scheme="red"),
        ),
        rx.input(
            placeholder="Search",
            value=ProductsState.search_query,
            on_change=ProductsState.set_search_query,
        ),
        rx.button("Search", on_click=ProductsState.load_products),
        rx.input(value=ProductsState.name, on_change=ProductsState.set_name),
        rx.input(value=ProductsState.sku, on_change=ProductsState.set_sku),
        rx.input(value=ProductsState.price, on_change=ProductsState.set_price),
        rx.button("Save", on_click=ProductsState.save_product),
        rx.hstack(
            rx.button("Prev", on_click=ProductsState.prev_page),
            rx.button("Next", on_click=ProductsState.next_page),
        ),
        rx.foreach(
            ProductsState.products,
            lambda row: rx.hstack(
                rx.text(row["name"]),
                rx.button("Edit", on_click=ProductsState.start_edit(row["id"])),
                rx.button("Delete", on_click=ProductsState.delete_product(row["id"])),
            ),
        ),
        width="100%",
    )

# app.add_page(products_page, route="/products", on_load=ProductsState.load_products)
```

---

## Error handling

| Layer | Approach |
|-------|----------|
| Client display | `products_error` string |
| Field-level | Add `field_errors: dict[str, str]` and set per field in `_validate` |
| Integrity errors | Catch `IntegrityError` on duplicate `sku` |

---

## Manual vs mixin CRUD

| | Manual (this page) | `ModelCRUDView` |
|---|-------------------|-----------------|
| Boilerplate | You write every `@rx.event` | Assembly generates handlers |
| Pagination/search | Full control | Add state vars + `filter_queryset` |
| Learning curve | Lower magic | Faster for standard CRUD |

---

## Advanced usage

- Extract `_filtered_qs` into a service class for unit tests without Reflex.  
- Use `rx.form` + `form_data` like `Meta.use_form_submit` in mixins — [Forms](forms_and_validation.md).

---

## Performance tips

- Count total pages with `await qs.acount()` only when needed.  
- Index `sku`, `owner_id`, `created_at` in the database.

---

## Common mistakes

- Forgetting `owner=user` on `aget` / `filter` (IDOR risk).  
- Storing `Decimal` in Reflex state—serialize to `str` or `float` for display.

---

## Developer notes

- Requires event bridge for `require_login_user()` / session.

---

## See also

- [CRUD with mixins](crud_with_mixins_and_states.md)  
- [reflex-django mixins](reflex_django_mixins.md)

---

**Navigation:** [← Database integration](database_integration.md) | [Next: reflex-django mixins →](reflex_django_mixins.md)
