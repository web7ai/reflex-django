# The WebSocket event pipeline

When a user clicks a button in your Reflex app, what *actually happens* between the click and your handler running? This page is the end-to-end trace.

You don't need this page to use `reflex-django`. You need it when something goes wrong on the WebSocket and you have to debug it.

---

## The 30,000-foot view

```text
1. Browser: user clicks a button
2. Browser: send Socket.IO event over WebSocket → /_event
3. Dispatcher: sees /_event, forwards to Reflex inner ASGI
4. Reflex:    receives event, calls registered middleware (preprocess)
5. Bridge:    builds synthetic HttpRequest from event.router_data
6. Bridge:    runs settings.MIDDLEWARE on it
7. Bridge:    eagerly resolves request.user
8. Bridge:    binds context (request, user, session, csrf, messages, language)
9. Reflex:    calls your @rx.event handler
10. Handler:  mutates state, returns events/redirects
11. Reflex:   ships state diff back over WebSocket
12. Browser:  re-renders
```

Steps 5 through 8 are the part `reflex-django` adds. The rest is normal Reflex + ASGI.

---

## Step 1-3: from click to dispatcher

The Reflex SPA opens a single WebSocket to `/_event` when the page loads. Every UI action is sent as a Socket.IO event over that connection.

The outer dispatcher (`DjangoOuterDispatcher`) sees that `/_event` is a [reserved Reflex prefix](routing.md#reserved-reflex-prefixes) and forwards the scope straight to Reflex's inner ASGI app (`rx_app._api`). Django middleware does **not** run on this path — there's nothing for it to do; the request isn't going to a Django view.

Source files involved:

- `reflex_django/django_outer_dispatcher.py` — the dispatcher.
- `reflex_django/asgi_entry.py` — the assembly into one ASGI app.

---

## Step 4: Reflex's preprocess hook

Reflex supports "preprocess" middleware — a callable that runs *before* the event handler. `reflex-django` registers `DjangoEventBridge.preprocess` as one of these middlewares when the integration is installed (via `ReflexDjangoPlugin`, which is always on).

```python
# roughly, in reflex_django/plugin.py
rx_app.event_middleware.append(DjangoEventBridge().preprocess)
```

When Reflex receives a `/_event` payload, it walks through registered preprocess middleware in order. The `DjangoEventBridge.preprocess` call is where everything below happens.

---

## Step 5: building the synthetic `HttpRequest`

Reflex events carry a `router_data` dict that describes the page the event came from. The bridge unpacks it:

| Field in `router_data` | What it becomes |
|:---|:---|
| `pathname` | `request.path` |
| `query` | `request.GET` (a `QueryDict`) |
| `headers` | `request.META["HTTP_*"]` entries |
| `cookies` | `request.COOKIES` (parsed from the WebSocket handshake's `Cookie` header) |
| Connection metadata | `request.META["REMOTE_ADDR"]`, etc. |

It then constructs a real `django.http.HttpRequest` with those fields filled in. From this point on, the request looks like a normal Django GET to Django's middleware — except the body is empty (events don't have HTTP bodies) and the method is `GET` by default.

Source: `reflex_django/middleware.py:DjangoEventBridge.preprocess`.

---

## Step 6: running `settings.MIDDLEWARE`

The bridge passes the request through a thin handler called `EventMiddlewareHandler` — a subclass of Django's `BaseHandler` that exposes the middleware chain without trying to dispatch to a view.

```python
# Effectively:
handler = EventMiddlewareHandler()
response = await handler.handle_async(request)
```

Every middleware in `settings.MIDDLEWARE` runs in order, each calling the next. `SessionMiddleware` loads the session row. `AuthenticationMiddleware` resolves `request.user`. Your custom middleware runs too.

### What's skipped

A few middlewares are intentionally bypassed because they don't apply to WebSocket events:

| Middleware | Why |
|:---|:---|
| `django.middleware.csrf.CsrfViewMiddleware` | CSRF is for cross-origin HTML form posts; doesn't apply here. |
| `reflex_django.streaming_middleware.AsyncStreamingMiddleware` | Adapts streaming HTTP responses; no streaming on WebSockets. |

Override the skip list with `REFLEX_DJANGO_EVENT_MIDDLEWARE_SKIP`.

### Skipped phases

`process_view` is not called (there's no Django view to dispatch). `process_request`, `process_response`, and `process_exception` all run normally.

Source: `reflex_django/event_handler.py`.

---

## Step 7: eager `request.user` resolution

Django's `request.user` is normally a `SimpleLazyObject` that triggers a DB query the first time you access it. That works in sync HTTP views, but in an async event handler it can raise `SynchronousOnlyOperation`.

The bridge dodges that by *eagerly* resolving the user before your handler runs:

```python
# In the bridge:
user = await aget_user(request)
request._cached_user = user
request.user = user
```

By the time your handler sees `self.request.user`, it's a real `User` instance, not a lazy proxy. You can call `await user.aget_all_permissions()`, check `user.is_staff`, etc., without surprises.

Source: `reflex_django/middleware.py:DjangoEventBridge._resolve_user`.

---

## Step 8: binding context onto the handler

The bridge uses Python's `ContextVar` primitives to attach the per-event request to the current async task. Every helper you've seen — `self.request`, `self.user`, `current_request()`, `current_user()` — reads from this context.

Three layers of access work:

| Access pattern | Where it reads from |
|:---|:---|
| `self.request` on `AppState` | The ContextVar, wrapped in `DjangoStateRequest` |
| `current_request()` / `current_user()` | The ContextVar directly |
| `from reflex_django import request; request.user` | A `RequestProxy` that delegates to the ContextVar |

All three return the *same* request for the current event. Outside an event (at import time, in a background thread), they return None / an anonymous default.

Source: `reflex_django/context.py`, `reflex_django/request.py`.

---

## Step 9: calling your handler

After the bridge finishes, Reflex calls your handler the normal way. Inside the handler:

```python
class CartState(AppState):
    @rx.event
    async def add_item(self, product_id: int):
        # everything below is real and live:
        user      = self.request.user
        session   = self.session
        csrf      = self.csrf_token
        messages  = self.messages
        language  = self.request.LANGUAGE_CODE

        product = await Product.objects.aget(pk=product_id)
        await Cart.objects.aget_or_create(owner=user, defaults={"product": product})
```

---

## Step 10-12: state diff and re-render

The handler mutates `self`-level reactive variables. Reflex notices, computes the diff, and ships it back over the same WebSocket. The browser applies the diff to the React store and re-renders the affected components.

You wrote step 9. Steps 1-8 and 10-12 are framework work.

---

## What happens on middleware redirects

If any middleware short-circuits the request with a 3xx — for example, a `LoginRequiredMiddleware` returning `HttpResponseRedirect("/login")` — the bridge catches it.

By default (`REFLEX_DJANGO_AUTO_REDIRECT_FROM_MIDDLEWARE = True`), the bridge converts that 3xx into a Reflex `rx.redirect(location)` event. Your handler is **not** called. The SPA navigates to the new URL.

If you set the flag to `False`, the redirect response is exposed on `self.response` instead and your handler runs normally.

---

## What happens on middleware exceptions

If a middleware raises:

1. The bridge catches the exception.
2. Your handler is **not** called.
3. By default, an `rx.toast.error(...)` is emitted to the user.
4. The exception is logged.

You can short-circuit your own logic this way:

```python
class BannedUserMiddleware:
    async def __call__(self, request):
        if request.user.is_authenticated and request.user.is_banned:
            raise PermissionDenied("Account suspended.")
        return await self.get_response(request)
```

The handler doesn't run, the user sees a toast, and your audit log gets a record. ([More on middleware](django_middleware_to_reflex.md).)

---

## Other reserved Reflex endpoints

`/_event` is the big one, but Reflex's inner ASGI also handles:

| Endpoint | Purpose |
|:---|:---|
| `/_upload` | Multipart file uploads from `rx.upload()` |
| `/_health`, `/ping` | Liveness probes |
| `/_all_routes` | Internal route enumeration |
| `/auth-codespace` | Reflex dev tooling |

`/_upload` is interesting because it's the only Reflex endpoint that *does* receive a full HTTP request with a body. `reflex-django` patches the upload handler to also inject `router_data` (cookies, session) into the event so file uploads carry auth context.

Source: `reflex_django/upload_patch.py`.

---

## Other WebSocket scopes (besides `/_event`)

What if the browser tries to open a WebSocket to a path that isn't `/_event` (or `/_upload`)? Two things can happen:

1. **`--with-vite` mode is active** — the bridge proxies the WebSocket to the Vite dev server, so Reflex's HMR works.
2. **Normal mode** — the dispatcher closes the WebSocket politely (Close code 1011).

Django itself never sees these scopes. There's no Channels in this stack.

---

## Lifespan handling

ASGI servers send a `"lifespan"` scope at startup and shutdown. The dispatcher forwards lifespan straight to Reflex's inner ASGI, which uses it to:

- Start Reflex's event processor.
- Start background tasks (`@rx.background`).
- Tear them down on shutdown.

Django doesn't have a `lifespan` handler by default, so Reflex handles it cleanly without interference.

---

## State serialization between events

Between events, Reflex periodically pickles `BaseState` instances to its state manager (memory by default, Redis if you configure it). Django's `HttpRequest` and `ResolverMatch` aren't picklable, so `reflex-django` patches `BaseState.__getstate__` to strip the transient `_django_led_request_wrapper` and `_django_led_response` attributes before serialization.

The next event rebuilds them from the incoming `router_data`. You never lose `self.request` between events; you just don't pay to ship a synthetic request across processes.

Source: `reflex_django/state/__init__.py` (the patch).

---

## Tracing a real event

If something feels off, the fastest debug path is:

1. **Check the browser console.** Reflex logs WebSocket events. You should see one event per click.
2. **Print in your handler.** Drop a `print(self.request.user, self.request.path)` at the top. If it doesn't print, the bridge or middleware short-circuited before your handler.
3. **Check the server logs.** Middleware exceptions and bridge errors are logged at WARNING level. Look for stack traces near the event timestamp.
4. **Add `REFLEX_DJANGO_RUN_MIDDLEWARE_CHAIN = False` temporarily.** If your handler runs now but didn't before, a custom middleware is short-circuiting. Add prints to each middleware until you find which one.

---

## Source map

If you want to read the code:

| File | What it does |
|:---|:---|
| `reflex_django/django_outer_dispatcher.py` | Outer ASGI dispatcher |
| `reflex_django/asgi_entry.py` | Builds the full ASGI application |
| `reflex_django/middleware.py` | `DjangoEventBridge` — preprocess hook |
| `reflex_django/event_handler.py` | `EventMiddlewareHandler` — runs `settings.MIDDLEWARE` |
| `reflex_django/context.py` | ContextVars (current_request, current_user, …) |
| `reflex_django/request.py` | `RequestProxy` for non-AppState access |
| `reflex_django/upload_patch.py` | Injects router_data into uploads |
| `reflex_django/plugin.py` | `ReflexDjangoPlugin` — wires the bridge into Reflex |

---

**Next:** [AsyncStreamingMiddleware explained →](async_streaming_middleware.md)
