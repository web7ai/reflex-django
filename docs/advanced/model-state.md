# Model state

Declarative CRUD for one Django model. `ModelState` extends `AppState` and wires list, search, pagination, save, create, and delete handlers from your `model` and `fields` declaration.

## Quick example

```python
--8<-- "snippets/model_state_example.py"
```

```python
# shop/shop.py
import reflex as rx
from shop.views import ProductState, catalog

app = rx.App()
app.add_page(catalog, route="/products", title="Products", on_load=ProductState.load)
```

## Declaration

| Class attribute | Purpose |
|:---|:---|
| `model` | Django model class |
| `fields` | Model fields exposed to state and forms |
| `paginate_by` | Page size (enables pagination vars) |
| `search_fields` | Fields for text search |

Built-in reactive vars include `data`, `error`, `search`, `editing_id`, `page`, `page_count`, `total_count`, and `field_errors`.

## Handlers

Call these from UI events or `on_load`:

| Handler | Purpose |
|:---|:---|
| `load` | Refresh list (respects search and pagination) |
| `refresh` | Alias for reload |
| `save` | Update row from form fields |
| `create` | Insert new row |
| `delete` | Remove row by id |
| `filter` | Apply search text |
| `paginate` | Change page |

Handlers are `async def` and use the async ORM internally.

## Serializers

When you omit an explicit serializer, reflex-django builds one from `model` and `fields`. For custom shapes, set `Meta.serializer` or `serializer_class`:

```python
from reflex_django.serializers import ReflexDjangoModelSerializer

class ProductSerializer(ReflexDjangoModelSerializer):
    class Meta:
        model = Product
        fields = ("id", "name", "price")

class ProductState(ModelState):
    model = Product
    fields = ["name", "price"]

    class Meta:
        serializer = ProductSerializer
```

See [Serializers](serializers.md).

## User-scoped rows

Filter by the logged-in user in a custom `get_queryset` or use scoping mixins in advanced setups. Always authorize with `self.request.user` in overrides.

## Advanced: ModelCRUDView

For fine-grained Meta (`list_var`, custom event names, mixins), subclass `AppState` with `ModelCRUDView` instead of `ModelState`. Same serializer and handler machinery, more configuration. Most apps should start with `ModelState`.

**Next:** [Database](database.md) for when to pick manual ORM vs serializers vs model state.
