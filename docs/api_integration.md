# API integration

Expose **Django HTTP APIs** alongside Reflex using **`backend_prefix`**—without merging routers.

---

## Prerequisites

- [Routing](routing.md)  
- [Architecture](architecture.md)

---

## Decision matrix

| Approach | When |
|----------|------|
| **ORM in Reflex events** | Same process, session user, low latency, no extra HTTP hop |
| **Django views under prefix** | Existing REST/HTML endpoints, webhooks, third-party clients |
| **Optional DRF** | If you install `djangorestframework` yourself—not a reflex-django dependency |

---

## Django views under `backend_prefix`

`rxconfig.py`:

```python
ReflexDjangoPlugin(
    settings_module="backend.settings",
    backend_prefix="/api",
)
```

`backend/urls.py`:

```python
urlpatterns = [
    path("api/", include("myapi.urls")),
]
```

Browser requests to `/api/...` hit Django ASGI with full middleware (CSRF, auth, etc.).

---

## Optional DRF (third-party)

*Only if you add `djangorestframework` to your project.*

```python
# myapi/urls.py
from rest_framework.routers import DefaultRouter
from .views import ProductViewSet

router = DefaultRouter()
router.register("products", ProductViewSet)
urlpatterns = router.urls
```

Reflex UI can:

1. **Prefer:** use ORM directly in states (same session user via event bridge).  
2. **Alternatively:** call HTTP from the browser or server with `httpx` / fetch—application code, not provided by reflex-django.

---

## CORS

Same-origin when UI and API share the host under `reflex run`. Separate hosts require normal CORS configuration on Django—outside reflex-django.

---

## Serializers

| Layer | Tool |
|-------|------|
| Reflex state wire format | `ReflexDjangoModelSerializer` |
| DRF responses | DRF serializers (your install) |

Do not confuse the two.

---

## Advanced usage

- `extra_prefixes` for webhooks (`/hooks/stripe/`).  
- Serve OpenAPI from Django under `/api` while Reflex serves `/`.

---

## Common mistakes

- `path("v1/api/", …)` but `backend_prefix="/api"`.  
- Expecting DRF to be installed by reflex-django.

---

## Developer notes

- Dispatcher: `make_dispatcher` in `asgi.py`.

---

## See also

- [CRUD without mixins](crud_without_mixins.md)  
- [CLI](cli.md)

---

**Navigation:** [← Authentication](authentication.md) | [Next: CLI →](cli.md)
