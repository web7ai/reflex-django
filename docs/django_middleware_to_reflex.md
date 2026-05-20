# Django Middleware in Reflex

In a standard Django application, request processing is managed by a pipeline of sequential classes defined in your `MIDDLEWARE` settings (such as `SessionMiddleware`, `AuthenticationMiddleware`, and `CsrfViewMiddleware`). These middleware classes run on traditional HTTP requests.

However, in a Reflex application, interactive user inputs (like button clicks, form typing, or page navigations) occur over a persistent **Socket.IO WebSocket connection**. Because WebSocket packets bypass Django's standard HTTP routing, your existing middleware stack does not run on these events.

To solve this, **reflex-django** introduces the **`DjangoEventBridge`**. It intercepts incoming WebSocket packets, extracts request context, and maps it directly onto your state handlers.

---

## What the Event Bridge Runs

On every socket event, the `DjangoEventBridge` intercepts the packet and executes a lightweight, optimized pre-processing routine to bridge the frameworks:

```text
[1] Incoming WebSocket Event Packet
      │
      ▼
[2] Extract router_data (Path, Query parameters, Cookies, Headers, IP Address)
      │
      ▼
[3] Build a Synthetic HttpRequest
      │
      ▼
[4] Load Django Session Store (using active SESSION_ENGINE)
      │
      ▼
[5] Resolve User (asynchronously using Django's aget_user)
      │
      ▼
[6] Bind request context to thread-safe current_request contextvar
      │
      ▼
[7] Execute State Event Handler (e.g., on_click)
```

1. **Context Cleanup**: Automatically clears out stale thread-local request and user contexts from previous events to prevent leaks.
2. **Rebuild Request**: Instantiates a mock Django `HttpRequest` and populates standard attributes (like `.path`, `.GET`, `.COOKIES`, and `.headers`) based on the client browser's active routing data.
3. **Session Hydration**: Loads the session data from your backend session engine (e.g., database, cache, or file-based session rows) matching the `sessionid` cookie value.
4. **User Authentication**: Asynchronously calls Django's native **`aget_user`** to authenticate the active user session against your configured database authentication backends.
5. **Thread-Safe Binding**: Binds this request context to thread-safe local variable containers, making functional helpers like `current_user()` and `current_request()` fully operational.
6. **State Synchronization**: Updates reactive snapshot fields for any active state inheriting from `AppState`.

---

## What the Event Bridge Does NOT Run

To keep WebSocket communication highly performant, certain security and routing middlewares are omitted:

* **`CsrfViewMiddleware`**: WebSockets are immune to standard cross-site request forgery attacks because the handshake is established under strict origin checks. CSRF middleware does not run on socket events.
* **`SecurityMiddleware` & `XFrameOptionsMiddleware`**: Because Starlette manages the outer connection, standard security headers are set during the initial handshake, and do not need to be re-evaluated on individual click events.
* **Custom HTTP Middlewares**: Any custom classes registered in your `settings.py` `MIDDLEWARE` block that expect to return a standard `HttpResponse` are skipped.

> [!TIP]
> **Form Security Best Practice:** If you are exposing traditional HTML forms on Django views under `/api/`, always include standard `{% csrf_token %}` tokens. For Reflex components, enforce security by checking `self.request.user.is_authenticated` or verifying model-level permissions inside your event handlers.

---

## Safely Accessing the Request Context

You can access the request context inside any Reflex event handler using one of three developer patterns:

### Pattern A: The Dotted Request Proxy (Recommended)
You can import the `request` proxy directly. This proxy behaves exactly like a traditional Django `request` object inside views:

```python
# frontend/states/search.py
import reflex as rx
from reflex_django import request  # Import the global request proxy
from shop.models import Product

class SearchState(rx.State):
    results: list[str] = []

    @rx.event
    async def perform_search(self):
        # 1. Access request headers
        auth_header = request.headers.get("authorization")
        
        # 2. Access URL query string parameters
        query = request.GET.get("q", "").strip()
        
        # 3. Access cookies
        session_cookie = request.COOKIES.get("sessionid")
        
        # 4. Access the active authenticated user
        if not request.user.is_authenticated:
            return rx.toast.error("Please log in to search our catalog.")
            
        # 5. Access the request path
        active_path = request.path
        
        # Query models scoped to the active user
        qs = Product.objects.filter(name__icontains=query)
        self.results = [p.name async for p in qs]
```

### Pattern B: Functional Context Helpers
If you prefer explicit functional declarations, use the built-in context accessors:

```python
# frontend/states/profile.py
import reflex as rx
from reflex_django import current_request, current_user, current_session

class ProfileState(rx.State):
    @rx.event
    async def load_profile(self):
        request = current_request()
        user = current_user()
        session = current_session()
        
        self.username = user.username if user.is_authenticated else "Guest"
```

### Pattern C: The `AppState` Base Class
If your state inherits from `AppState`, the request context is bound directly onto the class instance as **`self.request`**:

```python
# frontend/states/billing.py
import reflex as rx
from reflex_django.state import AppState

class BillingState(AppState):
    @rx.event
    async def process_payment(self):
        # self.request is an instance-bound DjangoStateRequest wrapper
        user = self.request.user
        client_ip = self.request.META.get("REMOTE_ADDR")
        
        if not user.is_authenticated:
            return rx.redirect("/login")
            
        # Write directly to the persistent Django session store
        self.session["last_payment_status"] = "pending"
```

---

## Comparison: HTTP Middleware vs Event Bridge

| Architectural Feature | Traditional Django HTTP Route (e.g., `/admin`) | Reactive Reflex WebSocket Event (e.g., `on_click`) |
|:---|:---|:---|
| **Entry Point** | Outer Dispatcher ──► Django ASGI Handler | Starlette Server ──► `DjangoEventBridge` |
| **Active Pipeline** | Evaluates full `MIDDLEWARE` settings list | Triggers bridge pre-processor only |
| **Session Engine** | Loaded via `SessionMiddleware` | Resolved via `SESSION_ENGINE` on synthetic request |
| **Authentication** | Loaded via `AuthenticationMiddleware` | Resolved via async `aget_user()` database call |
| **CORS / CSRF Controls** | Evaluated via standard headers and cookies | Origin is checked during WebSocket handshake |

---

**Navigation:** [← Django Context in Reflex](django_context_to_reflex.md) | [Next: Session Authentication →](authentication.md)
