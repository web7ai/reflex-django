# Frequently Asked Questions (FAQ)

Here is a comprehensive compilation of frequently asked questions and troubleshooting scenarios compiled by the `reflex-django` developer community.

---

## 1. Core Architecture

### What exactly is reflex-django?
`reflex-django` is a high-performance integration engine that runs a **fully-featured Django backend** alongside a **Reflex reactive web application** within a **single, unified ASGI process**. 

It provides:
1. An **ASGI Path Dispatcher** that intercepts incoming traffic, forwarding admin panel and HTTP API requests to Django while routing client UI and WebSocket channels (`/_event`) to Reflex.
2. A secure **Event Bridge** that bridges request session cookies, authenticated users, and context variables over persistent WebSocket channels into your Reflex state event handlers.
3. A declarative, class-based **Reactive CRUD Engine** (`ModelState` and `ModelCRUDView`) that generates serializers, state variables, and event handlers automatically.

---

## 2. Authentication & Request Sessions

### Why is `self.request.user` returning AnonymousUser inside my event handlers?
This commonly happens for one of three reasons:
1. **Event Bridge Disabled**: Ensure `install_event_bridge=True` is active inside your `ReflexDjangoPlugin` configuration options in `rxconfig.py`.
2. **Missing Session Cookies**: The user's browser has not established a session cookie yet. Ensure the user is properly logged in or check their browser cookie state.
3. **Mismatched WebSocket Cookies**: When authenticating users, always synchronize browser session cookies to ensure the Socket.IO persistent connection aligns with the dynamic HTTP context.

---

### Why doesn't my custom Django middleware run when users click buttons?
Reflex events are **not standard HTTP requests**. When a user interacts with a Reflex page, the client browser communicates with the server via a persistent Socket.IO WebSocket channel. 

As a result, Django's standard HTTP middleware stack does not run. To solve this, `reflex-django` exposes a dedicated **`DjangoEventBridge`** which executes context setups (resolving users, sessions, and request profiles) specifically for WebSocket channels.

---

### Can I trust `DjangoUserState.is_authenticated` for security access controls?
**No. Never rely on client state variables for security.** 

Variables like `is_authenticated` or `username` are sent to the client browser and can be modified or spoofed. Use them exclusively for UI styling (e.g. wrapping a sidebar inside `rx.cond`). For any database mutations or private data queries, **always validate permissions on the server** inside your event handlers using `self.request.user` or by applying the `@login_required` decorator.

---

## 3. Configuration & Routing

### Why do my Django Admin or HTTP API endpoints return 404 errors?
This indicates a path prefix mismatch. The URL paths configured in your `ReflexDjangoPlugin` configuration must exactly match the prefixes declared inside your Django `urls.py` routing file:

```python
# In rxconfig.py
plugin = ReflexDjangoPlugin(
    admin_prefix="/admin/",
    backend_prefix="/api/",
)
```

```python
# In django_project/urls.py
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("shop.urls")),
]
```

---

### Why is the `settings_module` plugin parameter being ignored?
In `reflex-django`, **system environment variables always take precedence**. If you have `DJANGO_SETTINGS_MODULE` defined in your active environment shell (e.g. by running a terminal command), it will override the `settings_module` parameter declared in your `rxconfig.py` plugin configuration.

---

## 4. CRUD Engine & States

### What is the difference between `ModelState` and `ModelCRUDView`?
Both components execute the exact same reactive CRUD pipeline under the hood, but they are configured differently to support different project setups:

| Feature / Paradigm | `ModelState` (Recommended) | `ModelCRUDView` (Explicit) |
|:---|:---|:---|
| **Authentication Base** | Inherits `AppState` automatically. | Requires explicit inheritance from `AppState`. |
| **Data Schema** | Automatically builds a serializer from `model` and `fields`. | Requires an explicit `serializer_class` definition. |
| **Active List Variable** | `self.data` (Generic list) | Pluralized name (e.g. `self.posts`, `self.products`). |
| **Default Handlers** | Generic canonical methods (`load`, `save`, `refresh`, etc.). | Pluralized legacy handlers (`save_post`, `on_load_posts`). |
| **Best Used For** | Rapidly building new CRUD administration screens. | Integrating existing DRF schemas or custom relational joins. |

---

### Is pagination built into the CRUD engine?
**Yes, as an opt-in feature.** 

Simply declare `Meta.paginate_by = X` on your State class body. This automatically registers:
* Active pagination variables: `page`, `page_size`, `total_count`, and `page_count`.
* Event handlers: `next_page`, `prev_page`, and `paginate(page=X)` to handle page queries automatically.

---

### How do I access the Django `HttpRequest` inside an AppState subclass?
Subclass `AppState` (or `ModelState`) and call **`self.request`** inside any `@rx.event` handler. The engine provides three request variables:

```python
class MyState(AppState):
    @rx.event
    async def process_data(self):
        # 1. Access the authenticated user
        user = self.request.user
        
        # 2. Access query parameters
        page_num = self.request.GET.get("page", "1")
        
        # 3. Access cookie values
        theme = self.request.COOKIES.get("theme", "light")
```

* **`self.request.user`**: The active authenticated Django user (used for permissions and row-level scoping).
* **`self.request`**: A synthetic `HttpRequest` object populated with active browser router data (headers, pathnames, and queries).
* **`self.django_request`**: The raw, un-wrapped Django `HttpRequest` (useful when third-party libraries require a native Django request instance).

---

## 5. Development & Operations

### Why should I use `reflex django` instead of `python manage.py`?
Running `python manage.py` directly does not load your Reflex configurations. 

Calling **`reflex django <subcommand>`** instructs the CLI to boot Reflex first, load `rxconfig.py`, resolve environment variables, and then trigger Django. This guarantees that your migrations and database commands target the exact same database settings used during runtime.

---

### How do I troubleshoot unstyled Django Admin pages in production?
If the Django Admin panel boots but is missing CSS and JS styles, you have not compiled your static assets. Run the compilation command in your deployment pipeline before starting the web server:

```bash
uv run reflex django collectstatic --noinput
```

Ensure your reverse proxy (like Nginx) is configured to serve the `/static/` location directly from your compiled `STATIC_ROOT` folder.

---

**Navigation:** [← Best Practices](best_practices.md) | [Docs Index](index.md)
