# Model Serializers & Data Translation

Because Reflex states are synchronized between the Python backend and the client browser using WebSockets, any data exposed to the frontend must be strictly **JSON-serializable**. 

Rich, database-backed Django models contain non-serializable fields (such as `Decimal`, `datetime`, or `UUID` objects) and complex relational lookup chains that cannot be sent natively over the wire.

To bridge this, **reflex-django** provides **`ReflexDjangoModelSerializer`**. Inspired by Django REST Framework (DRF), it allows you to declare a simple, highly productive serialization schema that translates complex database rows into clean, flat, and JSON-safe Python dictionaries without requiring external dependencies like DRF.

---

## 1. Declaring a Serializer

To define a serialization schema, subclass `ReflexDjangoModelSerializer` and declare a nested `Meta` class defining the target database model and the specific list of fields to include:

```python
# shop/serializers.py
from reflex_django.serializers import ReflexDjangoModelSerializer
from shop.models import Product

class ProductSerializer(ReflexDjangoModelSerializer):
    """Declarative schema mapping Product models to JSON-safe dictionaries."""
    class Meta:
        model = Product
        
        # 1. Explicitly list the database columns to include
        fields = ("id", "name", "description", "price", "sku", "created_at")
        
        # 2. Prevent the automatic form generator from rendering these fields
        read_only_fields = ("id", "created_at")
        
        # 3. Custom format strings for date/time fields
        datetime_format = "%Y-%m-%d %H:%M:%S"
```

---

## 2. Configurable `Meta` Options

The `Meta` configuration block supports several parameters to fine-tune field parsing and form rendering:

| Meta Option | Data Type | Purpose / Behavior |
|:---|:---|:---|
| **`model`** | `Model` | The database model class to serialize. |
| **`fields`** | `tuple` or `list` | Specific fields to serialize. If declared, the primary key `id` is always automatically included. |
| **`exclude`** | `tuple` or `list` | Fields to omit. (Use either `fields` or `exclude`, not both). |
| **`read_only_fields`** | `tuple` or `list` | Fields to serialize to the frontend but protect from writes. `ModelCRUDView` will omit these from forms and update queries. |
| **`datetime_format`** | `str` | Formatting rule for `DateTimeField` values (e.g., `"%Y-%m-%d"`). |
| **`date_format`** | `str` | Formatting rule for `DateField` values. |

---

## 3. Ingesting Data: `.data` vs `.adata()`

Once declared, you pass your models or querysets into your serializer instance. To compile the output, the serializer exposes two primary APIs:

### 1. The Synchronous `.data` Property
Use `.data` when serializing a single, pre-evaluated database row, or in synchronous helper code.

```python
# Sync single-row serialization
product_record = Product.objects.get(pk=1)
serializer = ProductSerializer(product_record)

# Returns a flat dictionary
result_dict = serializer.data 
```

### 2. The Asynchronous `.adata()` Method (Recommended)
Always use `await serializer.adata()` inside your Reflex event handlers. This method is fully non-blocking and asynchronously iterates querysets:

```python
# frontend/states/catalog.py
import reflex as rx
from shop.models import Product
from shop.serializers import ProductSerializer

class CatalogState(rx.State):
    products: list[dict] = []

    @rx.event
    async def load_products(self):
        # 1. Build a database query
        qs = Product.objects.all().order_by("-price")
        
        # 2. Asynchronously serialize the entire queryset
        # .adata() handles async iteration over the database connection
        self.products = await ProductSerializer(qs, many=True).adata()
```

---

## 4. Integration with `ModelCRUDView`

If you are using reflex-django's automated form builders, your serializer class acts as the primary layout blueprint.

When you declare a serializer on your reactive state, the framework dynamically inspects the schema at boot time and maps flat variables for each writable field:

```python
# frontend/states/crud.py
from reflex_django.state import AppState, ModelCRUDView
from shop.models import Product
from shop.serializers import ProductSerializer

class ProductCRUDState(AppState, ModelCRUDView):
    class Meta:
        model = Product
        serializer = ProductSerializer
        list_var = "products"
```

### How fields map under the hood:
* **UI Variable Injection**: The framework scans the serializer's writable fields (`name`, `description`, `price`, `sku`) and automatically injects reactive string variables (`self.name`, `self.description`, etc.) into your state class.
* **Form Auto-population**: Interactive Reflex inputs map directly to these dynamic fields.
* **Protection Controls**: Any fields declared under `read_only_fields` (such as `id` or `created_at`) are automatically skipped during form validation and creation pipelines.

---

## 5. Low-Level Serialization Helper

If you need to serialize a single database row quickly inside an event handler and do not want to declare a full serializer class, use the low-level utility **`serialize_model_row`**:

```python
# frontend/states/quick_view.py
import reflex as rx
from reflex_django.serialization import serialize_model_row
from shop.models import Product

class QuickState(rx.State):
    active_product: dict = {}

    @rx.event
    async def view_product(self, product_id: int):
        product = await Product.objects.aget(pk=product_id)
        
        # Converts a single model row to a JSON-safe dictionary
        # Automatically parses decimals and datetime columns
        self.active_product = serialize_model_row(product)
```

---

## 6. Performance Optimization Tips

* **Scope your Querysets**: If you are serializing a large queryset, use Django's `.only()` or `.defer()` methods to prevent loading unnecessary text fields from the database:
  ```python
  qs = Product.objects.only("name", "price")
  self.products = await ProductSerializer(qs, many=True).adata()
  ```
* **Dynamic Exclusions**: You can exclude specific fields at runtime by passing `exclude_fields` into your serializer constructor:
  ```python
  # Dynamic runtime field stripping
  serializer = ProductSerializer(
      queryset, many=True, exclude_fields=("description",)
  )
  self.products = await serializer.adata()
  ```
* **Minimize State Payload Size**: Reflex syncs state mutations to the browser on every click. Keep your serialized dictionaries compact—only include columns that are directly rendered in the active UI views.

---

**Navigation:** [← Database Integration](database_integration.md) | [Next: CRUD (No Mixins) →](crud_without_mixins.md)
