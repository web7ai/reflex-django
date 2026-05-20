# Database Integration & ORM Mechanics

One of the greatest benefits of using **reflex-django** is the ability to leverage Django's industry-standard Object-Relational Mapper (ORM), transaction isolation controls, and automated migration schema engine directly inside your reactive frontend event handlers.

This guide details how database configurations boot, how to declare models, how to execute non-blocking asynchronous queries, and how to integrate standard Django Admin operations.

---

## 1. How Django ORM Boots

When your unified ASGI process starts, `reflex-django` must ensure the Django model registry is fully loaded and configured before Reflex compiles any state components.

### The `configure_django()` Bootstrap Hook
This is an idempotent setup function called automatically by the plugin during startup and CLI commands:

1. **Environment Overrides**: First, it respects any active environment variables. If `DJANGO_SETTINGS_MODULE` is defined in your shell, it uses that target module.
2. **Database Routing**: It maps database settings declared in your Django `settings.py` file. If no custom database is configured, it falls back to options parsed from your `rxconfig.py` plugin block (e.g., `REFLEX_DJANGO_DATABASE_URL` or an auto-generated local SQLite file).
3. **Registry Hydration**: It executes `django.setup()`, which registers all models under `INSTALLED_APPS` and builds SQL abstraction maps.

---

## 2. Declaring Models: The `Model` Base Class

While you are free to use standard `models.Model` from `django.db`, `reflex-django` provides a convenient abstract base class: **`reflex_django.model.Model`**.

```python
# shop/models.py
from django.db import models
from reflex_django.model import Model

class Product(Model):
    """A standard Django database model with a high-productivity base class."""
    name = models.CharField(max_length=128, db_index=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    sku = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} (${self.price})"
```

### Why use `reflex_django.model.Model`?
* **Modern PK Default**: It automatically binds a `BigAutoField` primary key (`id`), which is the recommended default for scalable production schemas.
* **Idempotent Bootstrapping**: Importing from `reflex_django.model` safely triggers `configure_django()` behind the scenes, preventing early registry import exceptions.
* **Auto-Serialization Hooks**: Model instances extending this base automatically register the custom `serialize_django_model` hooks, ensuring clean integration with states.

---

## 3. The Migration Workflow

Because your database schema is defined as Python code, you run standard Django migration management utilities to generate and run database alterations.

Always execute migrations using the custom **`reflex django`** wrapper. This ensures the execution context matches the exact configuration layout defined in `rxconfig.py`:

```bash
# 1. Inspect model files and generate SQL migration scripts
uv run reflex django makemigrations

# 2. Execute SQL changes against the target database
uv run reflex django migrate
```

---

## 4. Asynchronous Database Queries in State Handlers

The unified ASGI engine runs on an asynchronous event loop. Performing synchronous, blocking database transactions inside Reflex event handlers will block the thread, causing other user socket connections to lag.

### The Async ORM Rules:
1. **Define with `async def`**: Always mark your Reflex event handlers as asynchronous.
2. **Await Async ORM Methods**: Use Django's modern async query methods instead of their blocking equivalents.
3. **Never Store Models in State Fields**: Reflex state properties are serialized into JSON. Always serialize queries into dictionaries or primitive scalars before assigning them to state fields.

### Async Query Reference Table

| Blocking Method (Do NOT use) | Asynchronous Equivalent (Do use) |
|:---|:---|
| `Product.objects.create(...)` | `await Product.objects.acreate(...)` |
| `Product.objects.get(...)` | `await Product.objects.aget(...)` |
| `product.save()` | `await product.asave()` |
| `product.delete()` | `await product.adelete()` |
| `list(Product.objects.all())` | `[p async for p in Product.objects.all()]` |

### Production-Grade Async Query Example

Here is a complete, thread-safe implementation of a product search catalog:

```python
# frontend/states/catalog.py
import reflex as rx
from shop.models import Product

class CatalogState(rx.State):
    search_query: str = ""
    products: list[dict] = []
    total_matches: int = 0
    loading: bool = False

    @rx.event
    async def search_catalog(self):
        """Asynchronously queries products and serializes them to reactive state."""
        self.loading = True
        yield  # Yields state to trigger the loading indicator in the browser
        
        try:
            # 1. Build an asynchronous filtered queryset
            qs = Product.objects.filter(
                name__icontains=self.search_query.strip()
            ).order_by("-created_at")
            
            # 2. Fetch the total count asynchronously
            self.total_matches = await qs.acount()
            
            # 3. Asynchronously iterate and build a serialized list
            serialized_list = []
            async for p in qs[:20]:  # Limit output to 20 records
                serialized_list.append({
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "price": float(p.price),  # Convert Decimal to float for JSON
                    "sku": p.sku,
                })
            
            self.products = serialized_list
            
        except Exception as e:
            return rx.toast.error(f"Search failed: {str(e)}")
            
        finally:
            self.loading = False
```

---

## 5. Integrating the Django Admin Panel

You can manage your database tables using Django's powerful built-in administration dashboard.

Register your models inside your backend configuration using the **`register_admin`** decorator. This ensures the models are exposed under your configured `admin_prefix` (default: `/admin`):

```python
# shop/admin.py
from reflex_django import register_admin
from shop.models import Product

# Registers model and exposes it at http://localhost:3000/admin/
@register_admin(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "sku", "created_at")
    search_fields = ("name", "sku")
    list_filter = ("created_at",)
```

---

## 6. Performance & Query Optimization

If you are using automated CRUD views (`ModelCRUDView` or `ModelState`), reflex-django handles the database engine binding using the **`DjangoORMBackend`**.

To prevent "N+1 query" performance bottlenecks on your relational tables, declare optimization variables directly on your State `Meta` configurations:

```python
# frontend/states/orders.py
from reflex_django.state import ModelState
from shop.models import Order

class OrderState(ModelState):
    model = Order
    fields = ["id", "customer_name", "total_price"]
    
    class Meta:
        # Pre-select foreign key records in a single database JOIN query
        queryset_select_related = ("customer",)
        
        # Pre-fetch related many-to-many objects in a single batch query
        queryset_prefetch = ("items",)
```

---

## 7. Common Pitfalls

* **Circular Import Loop**: Importing a Django model globally at the root of a Reflex state file *before* the application plugin finishes bootstrapping can trigger a `django.core.exceptions.AppRegistryNotReady` crash. Always import models within your event handler methods or inside lazy loaders, or ensure your Reflex state file is imported after the plugin has finished setting up.
* **Blocking ORM Operations**: Running synchronous ORM calls (e.g., `Product.objects.count()`) in an `async def` handler will stall the ASGI worker thread. Always use `acount()` and prefix database writes with `await`.
* **Database Transactions in Async**: Wrapping multi-table asynchronous updates in standard synchronous `with transaction.atomic():` blocks will fail. Wrap async database operations in `async with sync_to_async(transaction.atomic)():` or leverage Django's async transaction hooks.

---

**Navigation:** [← Session Authentication](authentication.md) | [Next: Model Serializers →](serializers.md)
