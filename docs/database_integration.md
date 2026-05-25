# Talking to the database

Inside a `reflex-django` event handler, the Django ORM works the way it always has — with one important rule: **use the async methods**. The unified ASGI server runs an event loop, and a blocking query stalls every user's connection for the duration of that query.

This page covers the patterns to use, the patterns to avoid, and a few small tools `reflex-django` adds on top.

---

## The async ORM in 60 seconds

Modern Django ships an async counterpart for every common ORM method:

| Sync (don't use in handlers) | Async (use these) |
|:---|:---|
| `Model.objects.get(...)` | `await Model.objects.aget(...)` |
| `Model.objects.create(...)` | `await Model.objects.acreate(...)` |
| `Model.objects.get_or_create(...)` | `await Model.objects.aget_or_create(...)` |
| `Model.objects.update_or_create(...)` | `await Model.objects.aupdate_or_create(...)` |
| `instance.save()` | `await instance.asave()` |
| `instance.delete()` | `await instance.adelete()` |
| `Model.objects.filter(...).first()` | `await Model.objects.filter(...).afirst()` |
| `Model.objects.filter(...).count()` | `await Model.objects.filter(...).acount()` |
| `list(Model.objects.all())` | `[m async for m in Model.objects.all()]` |
| `Model.objects.bulk_create(items)` | `await Model.objects.abulk_create(items)` |

There are more (`aexists`, `aupdate`, `abulk_update`, …). The rule of thumb: if the method name doesn't start with `a`, don't use it inside an `async def` event handler.

---

## A complete pattern

A typical "load and display a list" handler:

```python
import reflex as rx
from reflex_django.state import AppState
from shop.models import Product


class CatalogState(AppState):
    products: list[dict] = []
    loading: bool = False
    error: str = ""

    @rx.event
    async def load(self):
        self.loading = True
        yield   # send the loading flag to the UI immediately
        try:
            self.products = [
                {"id": p.id, "name": p.name, "price": str(p.price)}
                async for p in Product.objects.filter(is_active=True).order_by("-created_at")[:50]
            ]
        except Exception as e:
            self.error = f"Couldn't load products: {e}"
        finally:
            self.loading = False
```

Three small habits that pay off:

1. **`yield` to flush a partial update** — set the spinner, yield, then do the slow work. The browser shows the spinner without waiting for the query.
2. **Slice the queryset** (`[:50]`) — even on small tables. It prevents pathological loads.
3. **Convert to plain dicts** — never assign a model instance directly to a state field. JSON serialization will fail.

---

## Creating and updating

```python
@rx.event
async def add_product(self):
    name = self.new_name.strip()
    price = self.new_price
    if not name:
        self.error = "Name is required."
        return
    await Product.objects.acreate(
        name=name,
        price=price,
        owner=self.request.user,
    )
    self.new_name = ""
    await self.load()
```

Notice how `self.request.user` is the authenticated Django user, available because `CatalogState` inherits from `AppState`. ([Why](state_management.md).)

For an update, fetch with `aget`, mutate, then `asave`:

```python
@rx.event
async def rename(self, product_id: int, new_name: str):
    p = await Product.objects.aget(pk=product_id, owner=self.request.user)
    p.name = new_name
    await p.asave()
    await self.load()
```

The `owner=self.request.user` filter on `aget` is doing double duty: it's both a query filter and a permission check. If the user tries to rename someone else's product, `aget` raises `DoesNotExist` instead of returning the row.

---

## Deleting safely

Same pattern as updating:

```python
@rx.event
async def delete(self, product_id: int):
    try:
        p = await Product.objects.aget(pk=product_id, owner=self.request.user)
        await p.adelete()
    except Product.DoesNotExist:
        return
    await self.load()
```

---

## Don't store model instances in state

This is the same rule from the `AppState` page, but it bears repeating because it's the most common bug:

```python
# wrong — will crash on JSON serialization
self.product = product

# right — extract primitives
self.product = {
    "id": product.id,
    "name": product.name,
    "price": str(product.price),     # Decimal → str
    "created_at": product.created_at.isoformat(),  # datetime → str
}
```

`Decimal` and `datetime` objects aren't JSON-serializable either. Convert them with `str(...)` or `.isoformat()`.

If you have more than a couple of fields, use a [serializer](serializers.md):

```python
from reflex_django.serializers import ReflexDjangoModelSerializer

class ProductSerializer(ReflexDjangoModelSerializer):
    class Meta:
        model = Product
        fields = ("id", "name", "price", "created_at")
```

```python
qs = Product.objects.filter(is_active=True)
self.products = await ProductSerializer(qs, many=True).adata()
```

---

## Avoiding N+1 queries

If you display a list of products with their author, this naive loop runs one extra query per row:

```python
# bad — N+1 queries
self.rows = [
    {"name": p.name, "author": p.author.username}    # p.author hits the DB each time
    async for p in Product.objects.all()
]
```

Pull related rows in a single join with `select_related`:

```python
self.rows = [
    {"name": p.name, "author": p.author.username}
    async for p in Product.objects.select_related("author").all()
]
```

For many-to-many or reverse foreign keys, use `prefetch_related`:

```python
async for cat in Category.objects.prefetch_related("products").all():
    ...
```

If you use [`ModelCRUDView`](crud_with_mixins_and_states.md), declare these in `Meta`:

```python
class Meta:
    queryset_select_related = ("author",)
    queryset_prefetch = ("tags",)
```

---

## Don't import models at module top

Pages get imported during early bootstrap, before Django's app registry is necessarily ready. Importing models there causes `AppRegistryNotReady`:

```python
# views.py — risky at import time
from shop.models import Product

class CatalogState(AppState):
    @rx.event
    async def load(self):
        ...
```

Safer pattern — import inside the handler:

```python
class CatalogState(AppState):
    @rx.event
    async def load(self):
        from shop.models import Product   # imported on first call, after Django is ready
        self.products = [...]
```

Once your project boots cleanly, top-of-file imports usually work. But the inside-handler version is bulletproof and we recommend it for shared library code.

---

## The optional `reflex_django.model.Model` base class

You're free to use plain `django.db.models.Model`. `reflex-django` also ships an optional base class that smooths a couple of edge cases:

```python
from reflex_django.model import Model
from django.db import models


class Product(Model):
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
```

What it does that the plain `Model` doesn't:

1. **`BigAutoField` PK by default** — a modern, scalable choice.
2. **Idempotent Django setup** — importing `reflex_django.model` triggers `configure_django()` safely, dodging some import-order pitfalls in scripts and tests.
3. **Auto-registered Reflex serializer** — model instances of this base have a JSON serializer registered with Reflex out of the box. (You still shouldn't assign instances to state fields, but the registration helps in a few internal places.)

Use it or don't. Both work.

---

## Migrations

Standard Django:

```bash
python manage.py makemigrations
python manage.py migrate
```

No special steps. `reflex-django` doesn't introduce its own migrations; it adds zero new tables.

---

## Transactions in async code

Use `django.db.transaction.atomic` with an async-friendly wrapper. Django's `atomic` is sync, so you need `sync_to_async`:

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

For most apps you won't need this — single-row writes with `asave()` are atomic at the row level. Use `atomic` when you need multi-row consistency.

---

## A quick decision tree

| You need to… | Use |
|:---|:---|
| Read a single row | `await Model.objects.aget(...)` |
| Read a list | `[m async for m in Model.objects.filter(...)]` (with slicing) |
| Create a row | `await Model.objects.acreate(...)` |
| Update an existing row | `await instance.asave()` after mutating |
| Delete a row | `await instance.adelete()` |
| Count rows | `await qs.acount()` |
| Bulk insert | `await Model.objects.abulk_create([...])` |
| Bulk update | `await Model.objects.abulk_update([...], fields=[...])` |
| Multi-row consistency | `sync_to_async` wrapping `transaction.atomic` |
| Skip the N+1 | `select_related` / `prefetch_related` on the queryset |

---

## When you should use `ModelState` instead

If your page is *mostly* "list rows, edit one, save, delete", you can hand the boilerplate to `ModelState` and reduce a CRUD page to about 5 lines:

```python
class ProductState(ModelState):
    model = Product
    fields = ["name", "price"]
    class Meta:
        list_var = "products"
```

`ModelState` is itself an `AppState`, so you keep `self.request.user`, `self.session`, and all the rest. ([Full walkthrough](reactive_model_state.md).)

When you need custom validation, joins, or fancy business logic, drop back to plain `AppState` and write the handlers by hand. Both styles work in the same project.

---

**Next:** [Login & sessions →](authentication.md)
