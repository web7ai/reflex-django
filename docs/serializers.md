# Model serializers

A serializer turns a Django model instance into a plain dict — strings, numbers, booleans, lists, dicts. That matters because Reflex state fields get JSON-encoded and shipped to the browser. Model instances, `Decimal`, and `datetime` objects don't survive JSON. Serializers handle the conversion.

`reflex-django` ships `ReflexDjangoModelSerializer`, a small DRF-style class with no DRF dependency. If you've used DRF, it'll feel familiar. If you haven't, it's only about three concepts.

---

## The shape

```python
# shop/serializers.py
from reflex_django.serializers import ReflexDjangoModelSerializer
from shop.models import Product


class ProductSerializer(ReflexDjangoModelSerializer):
    class Meta:
        model = Product
        fields = ("id", "name", "price", "is_active", "created_at")
        read_only_fields = ("id", "created_at")
```

Three things:

- **`model`** — which Django model.
- **`fields`** — tuple of field names to include in the output.
- **`read_only_fields`** — fields that appear in the output but can't be set from input.

That's it. No `serializer_method_field`, no nested writable serializers — just a fast way to project a model onto a JSON-safe dict.

---

## Using a serializer

### Async (in event handlers)

This is the one you'll use most:

```python
qs = Product.objects.filter(is_active=True)
self.products = await ProductSerializer(qs, many=True).adata()
```

`adata()` runs the queryset and returns a list of dicts, asynchronously. Single-instance version:

```python
product = await Product.objects.aget(pk=42)
self.product = await ProductSerializer(product).adata()
```

### Sync (in scripts, tests, management commands)

```python
products = list(Product.objects.filter(is_active=True))
data = ProductSerializer(products, many=True).data
```

`.data` is the sync version. Use it outside async contexts.

---

## What gets converted automatically

| Field type | Goes to JSON as |
|:---|:---|
| `CharField`, `TextField`, `SlugField`, `EmailField` | `str` |
| `IntegerField`, `BigIntegerField`, `SmallIntegerField` | `int` |
| `FloatField` | `float` |
| `DecimalField` | `str` (preserves precision) |
| `BooleanField` | `bool` |
| `DateField` | `str` (ISO 8601, e.g. `"2026-01-15"`) |
| `DateTimeField` | `str` (ISO 8601 with timezone) |
| `TimeField` | `str` |
| `UUIDField` | `str` |
| `JSONField` | the underlying dict/list as-is |
| `ForeignKey` | the related `id` (you opt in to full nested rendering via `select_related` + custom logic) |

You almost never have to write conversion code yourself.

---

## Customizing date and decimal formats

```python
class OrderSerializer(ReflexDjangoModelSerializer):
    class Meta:
        model = Order
        fields = ("id", "total", "placed_at")
        datetime_format = "%Y-%m-%d %H:%M"   # default is ISO 8601
        date_format = "%d %b %Y"
```

For per-instance formatting that needs runtime logic, override the serializer:

```python
class OrderSerializer(ReflexDjangoModelSerializer):
    class Meta:
        model = Order
        fields = ("id", "placed_at_pretty")

    def serialize_placed_at_pretty(self, instance):
        return instance.placed_at.strftime("%A, %B %d")
```

Any method named `serialize_<field>` overrides the auto-generated value for that field.

---

## Excluding fields at runtime

Sometimes you want different shapes in different contexts (a public list vs. an admin detail view). Pass `exclude_fields`:

```python
self.public_view = await ProductSerializer(qs, many=True, exclude_fields={"cost", "supplier"}).adata()
self.admin_view  = await ProductSerializer(qs, many=True).adata()
```

The serializer drops those fields before returning. Useful for hiding internal data from non-staff users without writing a second serializer class.

---

## Integration with `ModelCRUDView`

When you pass a `serializer_class` to a `ModelCRUDView`:

```python
class ProductState(AppState, ModelCRUDView):
    model = Product
    serializer_class = ProductSerializer
```

The CRUD machinery uses it for:

- The list view (calls `.adata()` per page).
- The detail view (when entering edit mode).
- Knowing which fields are writable vs read-only (via `read_only_fields`).

You don't have to manually serialize anywhere. The class wires it up.

For `ModelState`, the serializer is auto-built from `fields = [...]` — usually that's enough and you don't need a separate `*Serializer` class.

---

## Performance tips

### Only fetch what you serialize

If your serializer has 4 fields but your model has 20, narrow the SQL:

```python
qs = Product.objects.only("id", "name", "price", "is_active")
data = await ProductSerializer(qs, many=True).adata()
```

`only(...)` tells Django to fetch only those columns. For wide tables, this can dramatically cut query time.

### Avoid N+1 on related rows

If your serializer indirectly accesses related rows (via a `serialize_<field>` method, or a denormalized field), use `select_related` / `prefetch_related`:

```python
qs = Product.objects.select_related("category").prefetch_related("tags")
```

For `ModelCRUDView`, set these in `Meta`:

```python
class Meta:
    queryset_select_related = ("category",)
    queryset_prefetch = ("tags",)
```

### Don't ship enormous payloads to the browser

`AppState` fields go to every connected client. A 10MB list is a 10MB upload + 10MB JSON parse on every page transition. Paginate, narrow fields, and prefer many small responses over one huge one.

---

## The low-level helper: `serialize_model_row`

If you only need to convert one or two rows and don't want a class, use the module-level helper:

```python
from reflex_django.serialization import serialize_model_row

row = serialize_model_row(product, fields=("id", "name", "price"))
```

Returns a single dict. There's no `adata()` equivalent — for async, prefer the class.

---

## Sharing with DRF (if you have it)

If your project already has DRF and you've written `BlogPostSerializer(ModelSerializer)`, you have two reasonable options:

**Option A** — use both. DRF's `ModelSerializer` for HTTP endpoints, `ReflexDjangoModelSerializer` for Reflex states. They're compatible — both can target the same model with the same field list. You write two classes, but they're tiny.

**Option B** — write a thin adapter. `ReflexDjangoModelSerializer` doesn't depend on DRF, so an adapter that calls DRF's `.data` from your Reflex state works fine. The trade-off is dragging DRF into your event handler path.

For new projects, option A is simpler. For projects where DRF is already deep in the codebase, option B avoids duplication.

---

## Summary

- A serializer converts a model instance to a JSON-safe dict.
- Use `await Serializer(qs, many=True).adata()` in event handlers.
- Use `.data` (sync) in management commands and tests.
- Customize per-field with `serialize_<field>` methods.
- Hide fields at runtime with `exclude_fields=`.
- Always pair with `only()` / `select_related()` / `prefetch_related()` for performance.

---

**Next:** [i18n & translations →](i18n.md)
