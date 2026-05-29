# HTTP APIs alongside Reflex

Reflex events are great for the SPA your user is looking at. They're a terrible fit for everything else — mobile apps, server-to-server webhooks, CLIs, third-party integrations. Those need plain HTTP.

The good news: in `reflex-django`, both surfaces live in the same Django process, on the same port, sharing the same models and session. You add HTTP endpoints with the same `urls.py` / `views.py` you've always used. This page covers the patterns.

---

## The three flavors of "API" in a `reflex-django` project

| Surface | Handled by | Used by |
|:---|:---|:---|
| **Reflex events** on `/_event` | `@rx.event` handlers in `views.py` | Your SPA, in this browser |
| **Django HTTP views** under `/api/` (or wherever) | Django function/class views, or DRF `ModelViewSet` | Mobile apps, third parties, scripts |
| **Webhooks** | Django views with `@csrf_exempt` | Stripe, GitHub, etc. |

All three see the same database, the same models, the same auth.

---

## A plain Django view

```python
# shop/views.py
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required


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
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/orders/", my_orders),
]

urlpatterns += [
    reflex_mount(
        app_name="shop",
        django_prefix=("/admin", "/api"),     # /api/ is Django, not Reflex
    ),
]
```

That's it. `GET /api/orders/` runs your Django view. The user's session is shared with the SPA on the same origin, so login state is consistent.

---

## DRF works out of the box

If your project already uses Django REST Framework, no special setup is needed. Add `rest_framework` to `INSTALLED_APPS`, drop in your `ModelViewSet`, and register the router:

```python
# shop/api.py
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from shop.models import Order
from shop.serializers_drf import OrderSerializer


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user)
```

```python
# shop/api_urls.py
from rest_framework.routers import DefaultRouter
from shop.api import OrderViewSet

router = DefaultRouter()
router.register("orders", OrderViewSet)

urlpatterns = router.urls
```

```python
# config/urls.py
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("shop.api_urls")),
]
urlpatterns += [
    reflex_mount(app_name="shop", django_prefix=("/admin", "/api")),
]
```

Your mobile app can call `GET /api/orders/`. Your SPA can read the same data via a Reflex event using `Order.objects.filter(customer=self.request.user)` directly — no need to round-trip through HTTP.

---

## When to use HTTP vs Reflex events

Both can read and write the same data. Pick based on the *caller*:

| The caller is… | Use |
|:---|:---|
| Your own SPA, in the same browser tab | Reflex `@rx.event` |
| A mobile app | Django HTTP / DRF |
| A third-party server (Stripe, Slack) | Django HTTP webhook |
| A CLI / cron / script | Django HTTP, or a `manage.py` command |
| A different web app | Django HTTP |

The SPA already has the `request.user` and the session over WebSocket. Going through HTTP from the SPA just adds latency.

---

## Webhooks

Webhooks are external HTTP requests, usually without a user session. Add a Django view with `@csrf_exempt` and verify the signature yourself:

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

```python
# config/urls.py
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("shop.api_urls")),
    path("webhooks/stripe/", stripe_webhook),
]

urlpatterns += [
    reflex_mount(
        app_name="shop",
        django_prefix=("/admin", "/api", "/webhooks"),
    ),
]
```

Remember the rule: add the prefix to `django_prefix`, otherwise the SPA catch-all will try to serve the SPA shell instead of routing to your webhook.

---

## Two serializer types, two purposes

`reflex-django` ships `ReflexDjangoModelSerializer` for state-side serialization. DRF ships `ModelSerializer` for HTTP-side serialization. They're not the same class, and they don't have to share definitions.

| Class | Lives in | Used by |
|:---|:---|:---|
| `ReflexDjangoModelSerializer` | `reflex_django.serializers` | Reflex states (`.adata()` over WebSocket) |
| `rest_framework.serializers.ModelSerializer` | DRF | HTTP endpoints (`GET /api/orders/`) |

In practice they often have the same fields and live next to each other:

```python
# shop/serializers.py — for Reflex
from reflex_django.serializers import ReflexDjangoModelSerializer
from shop.models import Order


class OrderReflexSerializer(ReflexDjangoModelSerializer):
    class Meta:
        model = Order
        fields = ("id", "total", "status", "placed_at")


# shop/serializers_drf.py — for DRF
from rest_framework import serializers


class OrderDRFSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ("id", "total", "status", "placed_at")
```

You can keep them in one file if you prefer. Just don't try to pass a DRF serializer to a `ModelCRUDView` (the field handling isn't compatible) or vice versa.

---

## Single origin, no CORS

Because the SPA, the API, the admin, and the WebSocket all share one origin, you don't need CORS configuration. The browser sees them as the same site.

If you're shipping a mobile app or letting another web app embed your API, that's a different story — add `django-cors-headers` and configure it. For the SPA's own usage, you're done.

---

## Reading the user in HTTP vs Reflex

The pattern is symmetrical:

```python
# Django HTTP view
async def my_view(request):
    user = request.user
    ...

# Reflex event handler
@rx.event
async def my_handler(self):
    user = self.request.user
    ...
```

Same user. Same `is_authenticated`. Same permissions.

---

## A combined example

A shop that exposes both HTTP and Reflex over the same data:

```python
# shop/views.py
import reflex as rx
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from reflex_django.pages.decorators import page
from reflex_django.states import ModelState

from shop.models import Order

# ── Reflex side ──────────────────────────────────────
class OrderState(ModelState):
    model = Order
    fields = ["status", "total"]

    class Meta:
        list_var = "orders"

    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user)


@page(route="/orders", title="Orders", on_load=OrderState.refresh)
def my_orders_page() -> rx.Component:
    return rx.foreach(OrderState.orders, lambda o: rx.text(o["status"], " — ", o["total"]))


# ── HTTP side ────────────────────────────────────────
@login_required
async def my_orders_json(request):
    orders = [
        {"id": o.id, "status": o.status, "total": str(o.total)}
        async for o in Order.objects.filter(customer=request.user)
    ]
    return JsonResponse({"orders": orders})
```

```python
# config/urls.py
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/orders/", my_orders_json),
]
urlpatterns += [
    reflex_mount(app_name="shop", django_prefix=("/admin", "/api")),
]
```

- The browser SPA sees `/orders` — calls Reflex.
- The mobile app calls `/api/orders/` — calls Django.
- Both read the same rows, scoped to the same `request.user`.

---

## A note on async views

Use `async def` for Django HTTP views when you'll be awaiting the ORM, calling external services, or doing anything I/O-bound. Django will run them on the ASGI server's event loop. Mixing sync and async views in the same project is fine — Django auto-adapts.

If you're stuck with a sync-only library, wrap the call with `sync_to_async`:

```python
from asgiref.sync import sync_to_async

async def my_view(request):
    @sync_to_async
    def do_work():
        return some_sync_library.fetch()
    result = await do_work()
    return JsonResponse(result)
```

---

## Summary

- HTTP and Reflex share the same Django process, same models, same user.
- Add `path(...)` lines to `urls.py` for HTTP endpoints; remember to list the prefix in `django_prefix`.
- DRF works untouched.
- Use `ReflexDjangoModelSerializer` for state serialization, DRF `ModelSerializer` for HTTP serialization. They're different libraries with different purposes.
- Same origin → no CORS for the SPA's own calls.
- Prefer Reflex events for SPA actions; prefer HTTP for everyone else.

---

**Next:** [Using Django context processors →](django_context_to_reflex.md)
