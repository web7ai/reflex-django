---
level: beginner
tags: [database, orm]
---

# Database integration

**What you'll learn:** How to use the Django ORM inside Reflex event handlers, why async methods matter, and the habits that keep queries fast and state JSON-safe.

**When you need this:**

- You are loading or saving Django models from an `@rx.event` handler.
- You hit `SynchronousOnlyOperation`, JSON serialization errors, or slow pages.

---

Inside a reflex-django event handler, the Django ORM works the way it always has, with one rule: **use the async methods**. The unified ASGI server runs an event loop. A blocking query stalls every connection on that worker.

---

## Async ORM cheat sheet

Modern Django ships an async counterpart for common ORM methods:

| Sync (avoid in handlers) | Async (use these) |
|:---|:---|
| `Model.objects.get(...)` | `await Model.objects.aget(...)` |
| `Model.objects.create(...)` | `await Model.objects.acreate(...)` |
| `Model.objects.get_or_create(...)` | `await Model.objects.aget_or_create(...)` |
| `instance.save()` | `await instance.asave()` |
| `instance.delete()` | `await instance.adelete()` |
| `Model.objects.filter(...).first()` | `await Model.objects.filter(...).afirst()` |
| `Model.objects.filter(...).count()` | `await Model.objects.filter(...).acount()` |
| `list(Model.objects.all())` | `[m async for m in Model.objects.all()]` |
| `Model.objects.bulk_create(items)` | `await Model.objects.abulk_create(items)` |

Rule of thumb: if the method name does not start with `a`, do not call it inside an `async def` event handler.

---

## Load and display a list

```python
import reflex as rx
from reflex_django.states import AppState


class CatalogState(AppState):
    products: list[dict] = []
    loading: bool = False
    error: str = ""

    @rx.event
    async def load(self):
        from shop.models import Product

        self.loading = True
        yield
        try:
            self.products = [
                {"id": p.id, "name": p.name, "price": str(p.price)}
                async for p in Product.objects.filter(is_active=True).order_by("-created_at")[:50]
            ]
        except Exception as e:
            self.error = f"Could not load products: {e}"
        finally:
            self.loading = False
```

Three habits:

1. **`yield` after setting `loading`** so the spinner appears before the query finishes.
2. **Slice the queryset** (`[:50]`) even on small tables.
3. **Convert to plain dicts** before assigning to state fields.

Because `CatalogState` inherits from `AppState`, `self.request.user` is available for scoped queries. See [AppState bridge](state.md).

---

## Create, update, and delete

```python
@rx.event
async def add_product(self):
    from shop.models import Product

    name = self.new_name.strip()
    if not name:
        self.error = "Name is required."
        return
    await Product.objects.acreate(
        name=name,
        price=self.new_price,
        owner=self.request.user,
    )
    self.new_name = ""
    await self.load()


@rx.event
async def rename(self, product_id: int, new_name: str):
    from shop.models import Product

    p = await Product.objects.aget(pk=product_id, owner=self.request.user)
    p.name = new_name
    await p.asave()
    await self.load()


@rx.event
async def delete(self, product_id: int):
    from shop.models import Product

    try:
        p = await Product.objects.aget(pk=product_id, owner=self.request.user)
        await p.adelete()
    except Product.DoesNotExist:
        return
    await self.load()
```

The `owner=self.request.user` filter on `aget` is both a query filter and a permission check.

---

## Do not store model instances in state

```python
# wrong, crashes on JSON serialization
self.product = product

# right, primitives only
self.product = {
    "id": product.id,
    "name": product.name,
    "price": str(product.price),
    "created_at": product.created_at.isoformat(),
}
```

For many fields, use a [serializer](serializers.md):

```python
from reflex_django.serializers import ReflexDjangoModelSerializer

class ProductSerializer(ReflexDjangoModelSerializer):
    class Meta:
        model = Product
        fields = ("id", "name", "price", "created_at")

# in a handler:
self.products = await ProductSerializer(qs, many=True).adata()
```

---

## Avoiding N+1 queries

```python
# bad, one query per row
self.rows = [
    {"name": p.name, "author": p.author.username}
    async for p in Product.objects.all()
]

# good, join in one query
self.rows = [
    {"name": p.name, "author": p.author.username}
    async for p in Product.objects.select_related("author").all()
]
```

For many-to-many or reverse foreign keys, use `prefetch_related`. With [`ModelCRUDView`](crud.md#modelcrudview), declare these in `Meta`:

```python
class Meta:
    queryset_select_related = ("author",)
    queryset_prefetch = ("tags",)
```

---

## Import models inside handlers

Pages import during early bootstrap, before Django's app registry is always ready. Top-level model imports in `views.py` can cause `AppRegistryNotReady`:

```python
class CatalogState(AppState):
    @rx.event
    async def load(self):
        from shop.models import Product   # safe: runs after Django is ready
        ...
```

Once your project boots cleanly, top-of-file imports often work. The inside-handler pattern is bulletproof for shared library code.

---

## Optional `reflex_django.django.model.Model` base

Plain `django.db.models.Model` works fine. reflex-django also ships an optional base:

```python
from reflex_django.django.model import Model
from django.db import models

class Product(Model):
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
```

It adds `BigAutoField` PK by default, safe idempotent Django setup on import, and auto-registered Reflex serializers. Use it or do not. Both work.

---

## Migrations

Standard Django:

```bash
python manage.py makemigrations
python manage.py migrate
```

reflex-django adds zero tables of its own.

---

## Transactions in async code

Use `sync_to_async` wrapping `transaction.atomic` for multi-row consistency:

```python
from asgiref.sync import sync_to_async
from django.db import transaction

@rx.event
async def transfer(self, from_id: int, to_id: int, amount: int):
    @sync_to_async
    def do_transfer():
        with transaction.atomic():
            src = Account.objects.select_for_update().get(pk=from_id)
            dst = Account.objects.select_for_update().get(pk=to_id)
            src.balance -= amount
            dst.balance += amount
            src.save()
            dst.save()
    await do_transfer()
```

Single-row `asave()` is usually enough without explicit transactions.

---

## Quick decision tree

| You need to… | Use |
|:---|:---|
| Read one row | `await Model.objects.aget(...)` |
| Read a list | `[m async for m in Model.objects.filter(...)]` (with slicing) |
| Create | `await Model.objects.acreate(...)` |
| Update | mutate instance, then `await instance.asave()` |
| Delete | `await instance.adelete()` |
| Count | `await qs.acount()` |
| Multi-row consistency | `sync_to_async` + `transaction.atomic` |
| Skip N+1 | `select_related` / `prefetch_related` |

---

## When to use `ModelState` instead

If the page is mostly list/edit/save/delete for one model, `ModelState` handles the boilerplate:

```python
from reflex_django.states import ModelState

class ProductState(ModelState):
    model = Product
    fields = ["name", "price"]

    class Meta:
        list_var = "products"
```

`ModelState` is an `AppState`, so you keep `self.request.user`. See [Reactive model state](crud.md#modelstate).

For custom validation, joins, or business logic, drop back to plain `AppState` and write handlers by hand. Both styles coexist in one project.

!!! tip "One light habit"
    If your handler does more than one await on the database, ask whether a serializer or `ModelState` already solved that shape of problem.

---

## What just happened?

You saw the async ORM methods to use in handlers, how to keep state JSON-safe with dicts, and when `ModelState` saves boilerplate. The Django ORM is unchanged; only the calling convention (async + no model instances in state) is different.

---

**Next up:** [Login and sessions](authentication.md)