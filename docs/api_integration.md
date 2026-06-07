---
level: intermediate
tags: [api, http]
---

# HTTP APIs alongside Reflex

**What you'll learn:** How to add plain Django HTTP endpoints beside your Reflex SPA in the same process, sharing models, sessions, and users.

**When you need this:**

- A mobile app, CLI, or third party needs REST or JSON over HTTP.
- Webhooks (Stripe, GitHub, etc.) must hit Django views, not WebSocket events.

Reflex events power the SPA in the browser. Everything else still wants HTTP. In reflex-django both surfaces run in one Django process on one origin.

---

## Three surfaces in one project

| Surface | Handled by | Used by |
|:---|:---|:---|
| Reflex events on `/_event` | `@rx.event` in `views.py` | Your SPA in this browser |
| Django HTTP under `/api/` etc. | Django or DRF views | Mobile, scripts, partners |
| Webhooks | Django views, often `@csrf_exempt` | External servers |

All three share the database, models, and session when called from the same origin.

---

## Plain Django JSON view

```python
# shop/views.py
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse


@login_required
async def my_orders(request):
    orders = [
        {"id": o.id, "total": str(o.total)}
        async for o in Order.objects.filter(customer=request.user)
    ]
    return JsonResponse({"orders": orders})
```

```python
# config/urls.py
import shop.views  # noqa: F401

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/orders/", my_orders),
]
# Reflex catch-all: automatic when REFLEX_DJANGO_AUTO_MOUNT=True
```

`GET /api/orders/` runs your Django view. The SPA on the same origin shares the session cookie.

---

## Django REST Framework

No special reflex-django setup. Add DRF to `INSTALLED_APPS`, register a viewset, include the router:

```python
# shop/api.py
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user)
```

```python
# config/urls.py
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("shop.api_urls")),
]
```

Your mobile client calls `GET /api/orders/`. Your SPA can still load the same rows through a Reflex `ModelState` queryset without an HTTP round trip.

---

## When to use HTTP vs Reflex events

| Caller | Use |
|:---|:---|
| Your SPA in the same tab | Reflex `@rx.event` |
| Mobile app | Django HTTP or DRF |
| Third-party webhook | Django HTTP view |
| Cron or CLI | `manage.py` command or HTTP |

The SPA already has `self.request.user` over the WebSocket. HTTP from the same page only adds latency.

---

## Webhooks

External POSTs usually have no session. Verify signatures in the view:

```python
# shop/webhooks.py
import json
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST


@csrf_exempt
@require_POST
async def stripe_webhook(request):
    sig = request.headers.get("Stripe-Signature", "")
    payload = request.body
    if not verify_stripe_signature(payload, sig):
        return HttpResponseBadRequest("invalid signature")

    event = json.loads(payload)
    if event["type"] == "checkout.session.completed":
        await mark_order_paid(event["data"]["object"]["client_reference_id"])
    return HttpResponse(status=200)
```

List webhook paths in `urlpatterns` so Django handles them before the SPA catch-all.

---

## Two serializer types

| Class | Used for |
|:---|:---|
| `ReflexDjangoModelSerializer` | Reflex state (`.adata()` over WebSocket) |
| DRF `ModelSerializer` | HTTP JSON responses |

Keep parallel small classes with the same `fields`. Do not pass DRF serializers to `ModelCRUDView`.

---

## Same user in HTTP and Reflex

```python
# HTTP
async def my_view(request):
    user = request.user

# Reflex
@rx.event
async def my_handler(self):
    user = self.request.user
```

Same `is_authenticated`, same permissions, same session on one origin (no CORS for the SPA's own calls).

---

## Combined example

```python
# shop/views.py
import reflex as rx
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from reflex_django.pages.decorators import page
from reflex_django.states import ModelState


class OrderState(ModelState):
    model = Order
    fields = ["status", "total"]
    list_var = "orders"

    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user)


@page(route="/orders", title="Orders", on_load=OrderState.refresh)
def my_orders_page() -> rx.Component:
    return rx.foreach(OrderState.orders, lambda o: rx.text(o["status"], " - ", o["total"]))


@login_required
async def my_orders_json(request):
    orders = [
        {"id": o.id, "status": o.status, "total": str(o.total)}
        async for o in Order.objects.filter(customer=request.user)
    ]
    return JsonResponse({"orders": orders})
```

Browser uses `/orders` (Reflex). Mobile uses `/api/orders/` (HTTP). Same rows, same user scope.

---

## Async HTTP views

Use `async def` when you `await` the ORM or external I/O. Django runs them on the ASGI event loop. Wrap unavoidable sync libraries with `sync_to_async` from `asgiref`.

---

## What just happened?

You added HTTP endpoints next to Reflex without a second server, and you know when to call HTTP versus firing a WebSocket event.

**Next up:** [Custom middleware in events →](django_middleware_to_reflex.md)