---
level: intermediate
tags: [serializers, crud]
---

# Model serializers

**What you'll learn:** How `ReflexDjangoModelSerializer` turns Django model rows into JSON-safe dicts for Reflex state, and how that ties into `ModelState` and `ModelCRUDView`.

**When you need this:**

- You load model data into reactive list vars or form fields.
- You use `ModelCRUDView` and need an explicit `serializer_class`.

Reflex state fields are JSON-encoded before they reach the browser. Model instances, `Decimal`, and `datetime` do not survive that trip unchanged. Serializers handle the conversion.

`ReflexDjangoModelSerializer` is a small DRF-style helper with no DRF dependency.

---

## Basic shape

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

- **`model`**: which Django model.
- **`fields`**: names included in output.
- **`read_only_fields`**: appear in output but are not writable from state.

---

## Using a serializer in handlers

### Async (typical in `@rx.event`)

```python
qs = Product.objects.filter(is_active=True)
self.products = await ProductSerializer(qs, many=True).adata()
```

Single instance:

```python
product = await Product.objects.aget(pk=42)
self.product = await ProductSerializer(product).adata()
```

### Sync (scripts, tests, management commands)

```python
products = list(Product.objects.filter(is_active=True))
data = ProductSerializer(products, many=True).data
```

Use `.data` outside async contexts. Use `.adata()` inside event handlers.

---

## Automatic type conversion

| Field type | JSON output |
|:---|:---|
| `CharField`, `TextField`, `SlugField` | `str` |
| `IntegerField` | `int` |
| `FloatField` | `float` |
| `DecimalField` | `str` (preserves precision) |
| `BooleanField` | `bool` |
| `DateField` / `DateTimeField` | ISO 8601 `str` |
| `UUIDField` | `str` |
| `JSONField` | dict or list as-is |
| `ForeignKey` | related `id` by default |

---

## Custom formats and fields

```python
class OrderSerializer(ReflexDjangoModelSerializer):
    class Meta:
        model = Order
        fields = ("id", "total", "placed_at")
        datetime_format = "%Y-%m-%d %H:%M"

    def serialize_placed_at_pretty(self, instance):
        return instance.placed_at.strftime("%A, %B %d")
```

Methods named `serialize_<field>` override auto serialization for that field.

---

## Hide fields at runtime

```python
self.public_rows = await ProductSerializer(
    qs, many=True, exclude_fields={"cost", "supplier"}
).adata()
```

Useful when staff and public views share one serializer class.

---

## Integration with declarative CRUD

**`ModelCRUDView`**: pass `serializer_class`. The stack uses it for list rows, edit population, and writable field detection.

**`ModelState`**: omit `serializer_class` and set `fields = [...]`. A serializer is auto-built at class definition time.

You rarely call `.adata()` by hand on declarative CRUD states; the mixins do it on refresh and edit.

---

## Performance tips

Narrow SQL to serialized columns:

```python
qs = Product.objects.only("id", "name", "price", "is_active")
```

Avoid N+1 when custom `serialize_<field>` touches relations:

```python
qs = Product.objects.select_related("category").prefetch_related("tags")
```

On `ModelCRUDView` / `ModelState`, set:

```python
queryset_select_related = ("category",)
queryset_prefetch = ("tags",)
```

!!! tip "Paginate large lists"
    State vars ship to the browser. Prefer paginated list vars over one giant payload.

---

## Low-level helper

```python
from reflex_django.serialization import serialize_model_row

row = serialize_model_row(product, fields=("id", "name", "price"))
```

For async handlers, prefer the serializer class and `.adata()`.

---

## Sharing with DRF

If you also run Django REST Framework, keep two small classes:

- `ReflexDjangoModelSerializer` for Reflex state (WebSocket path)
- DRF `ModelSerializer` for HTTP `/api/` endpoints

Same `fields` tuple, two libraries. Do not pass a DRF serializer to `ModelCRUDView`.

---

## What just happened?

You learned how serializers make model rows JSON-safe, when to call `.adata()`, and how declarative CRUD classes wire serialization for you.

**Next up:** [i18n and translations →](i18n.md)