# API & HTTP Integration

While **reflex-django** allows you to perform database queries directly inside reactive frontend states using the Django ORM, there are times when you need to expose traditional HTTP REST APIs, receive third-party webhooks, or integration-test endpoints.

This guide explains how to build and expose Django APIs alongside your Reflex Single Page Application (SPA).

---

## Choosing Your Data Fetching Strategy

Before building an API endpoint, choose the architectural approach that best fits your immediate requirement:

| Integration Strategy | Execution Environment | Best For | Advantages |
|:---|:---|:---|:---|
| **Direct ORM Queries** | Run inside Reflex WebSocket Event Handlers (`@rx.event`) | Standard UI grids, forms, user actions, dashboard charts. | **Zero HTTP Latency:** No REST overhead, direct DB connection, automatic user auth context. |
| **Traditional Django Views** | Exposed as HTTP endpoints under `backend_prefix` | Webhook endpoints (e.g., Stripe, SendGrid), file downloads, legacy template pages. | **Standard HTTP Lifecycle:** Supports raw payloads, multipart forms, and direct file streaming. |
| **REST APIs (DRF)** | Exposed as structured REST endpoints under `backend_prefix` | Mobile apps, public developer portals, integrations with third-party web clients. | **Structured Payload Controls:** Standardized CRUD actions, authentication schemes, and automatic docs. |

---

## 1. Traditional Django Views under `backend_prefix`

To expose standard HTTP views, configure the plugin with a prefix and map the corresponding paths inside your Django project:

### 1. Configure the Plugin Prefix
Define your API route path namespace in `rxconfig.py`:

```python
# rxconfig.py
from reflex_django import ReflexDjangoPlugin

config = rx.Config(
    app_name="frontend",
    plugins=[
        ReflexDjangoPlugin(
            settings_module="backend.settings",
            backend_prefix="/api",  # Matches our API routes namespace
        ),
    ],
)
```

### 2. Map the URL Patterns
Add the endpoint in your main Django backend routing file:

```python
# backend/urls.py
from django.urls import path, include

urlpatterns = [
    # Include application views under the matching prefix
    path("api/shop/", include("shop.urls")),
]
```

### 3. Write a Standard Django View
Now, implement a standard Django view that returns JSON data:

```python
# shop/views.py
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from shop.models import Product

@require_GET
def active_products_view(request):
    """Exposes active products as a standard JSON payload."""
    products = Product.objects.filter(is_active=True).order_by("-id")
    
    data = [
        {
            "id": p.id,
            "name": p.name,
            "price": float(p.price),
        }
        for p in products
    ]
    return JsonResponse({"results": data}, safe=False)
```

---

## 2. Integrating Django REST Framework (DRF)

> [!NOTE]
> **Third-Party Dependency:** `djangorestframework` is **not** installed by `reflex-django`. If you want to use DRF, you must add it to your project dependencies manually (e.g., `uv add djangorestframework`).

Once DRF is installed and added to your `INSTALLED_APPS`, you can build REST ViewSets exactly as you would in a traditional Django API project:

```python
# shop/serializers.py
from rest_framework import serializers
from shop.models import Product

class DRFProductSerializer(serializers.ModelSerializer):
    """Standard Django REST Framework Serializer."""
    class Meta:
        model = Product
        fields = ["id", "name", "price", "sku", "is_active"]
```

```python
# shop/views.py
from rest_framework import viewsets
from shop.models import Product
from shop.serializers import DRFProductSerializer

class ProductViewSet(viewsets.ModelViewSet):
    """DRF ViewSet exposed under the backend prefix."""
    queryset = Product.objects.all()
    serializer_class = DRFProductSerializer
```

Register this viewset inside your application routing module:

```python
# shop/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from shop.views import ProductViewSet

router = DefaultRouter()
router.register(r"products", ProductViewSet, basename="product")

urlpatterns = [
    path("", include(router.urls)),
]
```

This registers standard CRUD routes at `http://localhost:3000/api/shop/products/` using DRF's standard rendering and authorization stack.

---

## CORS & Single-Origin Architecture

One of the greatest benefits of **reflex-django** is the **Single-Origin Architecture**.

* **Under Development / Production**: Because `reflex run` hosts both the Reflex frontend SPA and Django under the same network origin (sharing ports and domains), the browser treats them as a single application. 
* **No CORS Needed**: You do **not** need to install or configure `django-cors-headers` to make requests from your frontend components to your API views. This eliminates standard preflight request overhead and configuration complexities.

---

## Serializers Clarification: Reflex vs DRF

It is important not to confuse the two distinct serializer interfaces used in this stack:

```text
+--------------------------------------------------------------------------------+
|                             Serialization Choices                              |
+--------------------------------------------------------------------------------+
                                       │
        ┌──────────────────────────────┴──────────────────────────────┐
        ▼                                                             ▼
+─────────────────────────────────+         +──────────────────────────────────+
|  ReflexDjangoModelSerializer     |         |   DRF ModelSerializer            |
|  (Included in reflex-django)     |         |   (Optional, requires DRF install) |
+─────────────────────────────────+         +──────────────────────────────────+
        │                                             │
        ▼                                             ▼
* Runs inside WebSocket state events         * Runs inside standard HTTP Views
* Converts models to serializable dicts      * Converts models to REST API responses
* Binds results to rx.State variables        * Handles JSON input parsing & validation
```

* **`ReflexDjangoModelSerializer`**: Provided natively by `reflex-django`. It is designed specifically to convert Django models into JSON-safe dictionaries to bind them directly onto Reflex states.
* **DRF `ModelSerializer`**: Part of `djangorestframework`. It should only be used inside traditional HTTP endpoints and views served under your backend prefixes.

---

## Advanced Routing: Exposing Webhooks

If you are integrating third-party webhooks (like Stripe checkout events), these endpoints must bypass CSRF verification and handle raw POST payloads. Add them to `extra_prefixes` in `rxconfig.py` to route them directly to Django ASGI:

```python
# rxconfig.py
ReflexDjangoPlugin(
    settings_module="backend.settings",
    extra_prefixes=("/webhooks",),
)
```

Map them inside your Django backend routing, using the `@csrf_exempt` decorator:

```python
# shop/urls.py
from django.urls import path
from shop.views import stripe_webhook_view

urlpatterns = [
    path("webhooks/stripe/", stripe_webhook_view),
]
```

---

**Navigation:** [← Routing & URL Dispatching](routing.md) | [Next: State Management →](state_management.md)
