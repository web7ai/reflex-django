# Custom middleware in events

> **Development HTTP middleware** (Vite port, admin CSRF, synthetic request bodies) is separate from the event bridge. See [Local development](local_development.md) for `reflex_django.django_dev_middleware`.

You've probably written a custom Django middleware at some point — for multi-tenancy, rate limiting, request logging, audit trails, or "if `request.user.is_banned` then return 403". In a normal Django project, those middlewares only run on HTTP requests.

In `reflex-django`, **your middleware also runs on every Reflex event**, with no extra wiring on your side. This page explains how that works, what's skipped on purpose, and how to control which middleware runs where.

---

## The default behavior

`reflex-django` ships a small piece called the `DjangoEventBridge`. On every Reflex event, it:

1. Builds a synthetic `HttpRequest` from the WebSocket payload.
2. Walks your full `settings.MIDDLEWARE` list, in order.
3. Each middleware's `__call__` (or `process_request`/`process_response`) runs, just like for an HTTP request.
4. The resulting `request` and `response` are bound to your `AppState` handler.

So if you wrote `MultiTenantMiddleware` that sets `request.tenant`, then inside your `@rx.event` handler, `self.request.tenant` is set. No changes to your middleware.

---

## What's intentionally skipped

A few middlewares don't make sense on WebSocket events. The bridge skips them by default:

| Middleware | Why it's skipped |
|:---|:---|
| `django.middleware.csrf.CsrfViewMiddleware` | CSRF protects HTML form submissions from third-party origins. Reflex events come from the SPA on the same origin and can't be triggered cross-site. |
| `reflex_django.streaming_middleware.AsyncStreamingMiddleware` | It only adjusts streaming HTTP responses. WebSocket events don't produce one. |

The skip list is configurable:

```python
REFLEX_DJANGO_EVENT_MIDDLEWARE_SKIP = (
    "django.middleware.csrf.CsrfViewMiddleware",
    "reflex_django.streaming_middleware.AsyncStreamingMiddleware",
    "myapp.middleware.SomeMiddlewareYouDontWantOnEvents",
)
```

To get the absolute-default skip list back, omit the setting.

---

## A worked example — multi-tenant scoping

Suppose every user has a `tenant_id` and you want every query — HTTP, admin, Reflex — to be scoped to it.

```python
# common/middleware.py
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
# settings.py
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "common.middleware.TenantMiddleware",          # <-- your middleware
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "reflex_django.streaming_middleware.AsyncStreamingMiddleware",
]
```

Now inside any Reflex handler:

```python
class OrderState(AppState):
    @rx.event
    async def list_orders(self):
        tenant_id = self.request.tenant_id
        self.orders = [
            {"id": o.id, "total": str(o.total)}
            async for o in Order.objects.filter(tenant_id=tenant_id)
        ]
```

Same `request.tenant_id` your admin sees. Zero extra wiring.

---

## Middleware that redirects → `rx.redirect(...)`

A Django middleware that short-circuits with a 3xx normally returns an `HttpResponseRedirect`. On a Reflex event, that doesn't make sense — there's no response to send. The bridge converts it for you.

```python
class LoginRequiredEverywhereMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    async def __call__(self, request):
        public_paths = ("/login", "/register", "/about")
        if not request.user.is_authenticated and request.path not in public_paths:
            return HttpResponseRedirect("/login")
        return await self.get_response(request)
```

When this middleware fires on a Reflex event, the bridge sees the redirect response, doesn't call your handler, and instead returns `rx.redirect("/login")` — which the SPA respects and navigates. Same behavior as Django.

You can disable that auto-translation:

```python
REFLEX_DJANGO_AUTO_REDIRECT_FROM_MIDDLEWARE = False
```

Then redirects from middleware become `self.response` on the handler instead of an auto-navigation. Rarely useful, but available.

---

## Middleware that raises → handler doesn't run

If a middleware raises, the bridge catches it, skips your handler, and (by default) toasts an error to the user. Useful for "if user is banned, raise an exception in middleware" patterns:

```python
class BannedUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    async def __call__(self, request):
        if request.user.is_authenticated and request.user.banned:
            raise PermissionDenied("Account suspended.")
        return await self.get_response(request)
```

The handler doesn't run. The user sees an error in the UI.

---

## What about middleware that touches `request.body`?

Reflex events don't have an HTTP body. The synthetic request's `body` is empty by default. If your middleware reads `request.POST`, you can opt in to feeding the event payload into it:

```python
REFLEX_DJANGO_EVENT_POST_FROM_PAYLOAD = True
```

This stuffs the event's handler kwargs into `request.POST`. Useful for middleware that audits "what was the user trying to do" — though for most projects, reading the action from the handler itself is cleaner.

---

## What about `process_view` / `process_response` / `process_exception`?

The bridge runs the middleware chain by calling each middleware's `__call__` (or `process_request`/`process_response` for the old-style middleware API). That includes:

- `process_request` — runs before `get_response`.
- `process_response` — runs after `get_response` (with the response in hand).
- `process_exception` — runs if `get_response` raises.

`process_view` is **not** called on Reflex events, because there's no Django view being dispatched.

---

## Turning it off entirely

If you want to skip the middleware chain on events (and just have anonymous `request.user`):

```python
REFLEX_DJANGO_RUN_MIDDLEWARE_CHAIN = False
```

This is uncommon — most of the value of `reflex-django` is *because* the chain runs. But for high-throughput backend states that don't need auth or context, it's a perf knob.

---

## What `self.request` ends up being

After the middleware chain runs, the bridge binds:

- `self.request` — the populated `HttpRequest` (with everything your middleware added).
- `self.response` — the `HttpResponse` produced (200 if no short-circuit).
- `self.user` — `request.user`, eagerly resolved (no `SynchronousOnlyOperation`).
- `self.session`, `self.messages`, `self.csrf_token` — convenience shortcuts.

Anything you stuck on `request` from custom middleware (`request.tenant`, `request.feature_flags`, …) is on `self.request.tenant`, `self.request.feature_flags`, etc.

---

## Performance considerations

Running the full middleware chain on every event isn't free. For high-frequency states (telemetry, live cursor updates), you can:

1. Move the state to a `rx.State` subclass (skip `AppState` and its refresh).
2. Set `load_context_processors = False` on `ModelState` subclasses ([details](django_context_to_reflex.md)).
3. Skip specific middleware via `REFLEX_DJANGO_EVENT_MIDDLEWARE_SKIP`.
4. As a last resort, set `REFLEX_DJANGO_RUN_MIDDLEWARE_CHAIN = False`.

For normal apps, the per-event overhead is small (a few microseconds for session and auth lookups, milliseconds if your custom middleware does I/O).

---

## Reading the request from a plain `rx.State`

If your state doesn't inherit from `AppState`, you can still reach the bridged request:

```python
from reflex_django import request, current_user

class FilterState(rx.State):
    @rx.event
    async def apply(self):
        q = request.GET.get("q", "")
        if request.user.is_authenticated:
            ...
        user = current_user()    # same thing, functional style
```

The proxy delegates to the same per-event request the bridge built.

---

## Summary

- Your `settings.MIDDLEWARE` runs on every Reflex event by default.
- Two middleware are skipped on events (CSRF, async streaming) — configurable.
- 3xx redirects from middleware become `rx.redirect(...)` automatically.
- Exceptions from middleware skip the handler and toast an error.
- Disable per-class with `load_context_processors = False`, globally with `REFLEX_DJANGO_RUN_MIDDLEWARE_CHAIN = False`.
- Anything you put on `request.*` in custom middleware shows up on `self.request.*` in handlers.

---

**Next:** [Architecture overview →](architecture.md)
