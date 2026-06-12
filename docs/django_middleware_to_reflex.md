---
level: advanced
tags: [middleware, events]
---

# Custom middleware in events

**What you'll learn:** How reflex-django runs your `settings.MIDDLEWARE` chain on every Reflex event, what is skipped by default, and how to customize that behavior.

**When you need this:**

- You wrote Django middleware (tenant, audit, feature flags) and need it inside `@rx.event` handlers.
- A middleware redirect or error should behave correctly for SPA navigation, not only HTTP.

> Development HTTP middleware (Vite port, admin CSRF, synthetic bodies) is separate. See [Local development](local_development.md) for `reflex_django.dev.django_middleware`.

---

## Default behavior

The `DjangoEventBridge` runs on every Reflex event. It:

1. Builds a synthetic `HttpRequest` from WebSocket router data (cookies, path, headers).
2. Walks `settings.MIDDLEWARE` in order.
3. Binds the resulting `request` (and `response`) to your `AppState` handler.

If `TenantMiddleware` sets `request.tenant_id` on HTTP, `self.request.tenant_id` is set in handlers too. No extra wiring.

```python
--8<-- "snippets/minimal_settings.py"
```

Your middleware list in settings is the same list that runs on events (minus the skip list below).

---

## What is skipped by default

| Middleware | Why skipped on events |
|:---|:---|
| `CsrfViewMiddleware` | Reflex events come from your SPA on the same origin, not cross-site form posts. |
| `AsyncStreamingMiddleware` | Adjusts streaming HTTP responses; events do not produce one. |

Override the skip list:

```python
REFLEX_DJANGO_EVENT_MIDDLEWARE_SKIP = (
    "django.middleware.csrf.CsrfViewMiddleware",
    "reflex_django.bridge.streaming.AsyncStreamingMiddleware",
    "myapp.middleware.SomeMiddlewareYouDontWantOnEvents",
)
```

Import defaults from `reflex_django.bridge.event_handler.DEFAULT_EVENT_MIDDLEWARE_SKIP` if you want to extend rather than replace.

---

## Example: multi-tenant scoping

```python
# common/middleware.py
from asgiref.sync import sync_to_async


class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    async def __call__(self, request):
        request.tenant_id = None
        if request.user.is_authenticated:
            request.tenant_id = await sync_to_async(
                lambda: request.user.profile.tenant_id
            )()
        return await self.get_response(request)
```

```python
# settings.py (excerpt)
MIDDLEWARE = [
    # ...
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "common.middleware.TenantMiddleware",
    # ...
    "reflex_django.bridge.streaming.AsyncStreamingMiddleware",
]
```

```python
from reflex_django.states import AppState


class OrderState(AppState):
    @rx.event
    async def list_orders(self):
        tenant_id = self.request.tenant_id
        self.orders = [
            {"id": o.id, "total": str(o.total)}
            async for o in Order.objects.filter(tenant_id=tenant_id)
        ]
```

---

## Middleware redirects become `rx.redirect`

A middleware that returns `HttpResponseRedirect` on an event does not leave the SPA stuck. The bridge converts it to `rx.redirect(url)` so the client navigates.

Disable that translation:

```python
REFLEX_DJANGO_AUTO_REDIRECT_FROM_MIDDLEWARE = False
```

---

## Middleware exceptions skip the handler

If middleware raises, the bridge catches it, skips your handler, and (by default) surfaces an error in the UI. Useful for banned-user or hard-stop patterns.

---

## Optional: POST from event payload

Reflex events have no HTTP body by default. Opt in to stuffing handler kwargs into `request.POST`:

```python
REFLEX_DJANGO_EVENT_POST_FROM_PAYLOAD = True
```

Most projects read action data from the handler instead.

---

## `process_view` is not called

The chain runs `process_request`, `get_response`, `process_response`, and `process_exception`. `process_view` is skipped because no Django view is dispatched for events.

---

## Disable the chain entirely

```python
REFLEX_DJANGO_RUN_MIDDLEWARE_CHAIN = False
```

Uncommon. You lose session, auth, and custom middleware context on events. Occasionally useful for high-frequency telemetry states.

---

## What lands on `self`

After the chain:

| Attribute | Contents |
|:---|:---|
| `self.request` | Populated `HttpRequest` (plus anything your middleware added) |
| `self.user` | Resolved `request.user` |
| `self.session` | Async-safe session |
| `self.messages` | Message framework snapshot |
| `self.csrf_token` | CSRF token for the synthetic request |
| `self.response` | `HttpResponse` from the chain |

Custom attributes (`request.tenant`, `request.feature_flags`, ...) appear on `self.request` the same way.

---

## Access without AppState

```python
from reflex_django import current_user, request


class FilterState(rx.State):
    @rx.event
    async def apply(self):
        q = request.GET.get("q", "")
        if request.user.is_authenticated:
            user = current_user()
```

The proxy delegates to the same per-event request the bridge built.

---

## Performance

The full chain on every event is usually cheap (session + auth). For very high-frequency states:

1. Skip heavy middleware via `REFLEX_DJANGO_EVENT_MIDDLEWARE_SKIP`.
2. Use plain `rx.State` when you do not need Django context.
3. Last resort: `REFLEX_DJANGO_RUN_MIDDLEWARE_CHAIN = False`.

---

## What just happened?

You learned that Reflex events reuse Django middleware by default, which middleware is skipped, and which settings tune redirects, POST payload, and performance.

**Next up:** [Architecture overview →](architecture.md)