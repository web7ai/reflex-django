# Django Context in Reflex

In standard Django, **Context Processors** are callables that dynamically inject global or request-specific data (such as the active user, site-wide configuration, current language, or navigation links) into templates before they are rendered into HTML.

Because Reflex uses a Single Page Application (SPA) architecture operating over WebSocket events, traditional HTML rendering pipelines are bypassed. To bridge this gap, **reflex-django** provides a high-productivity context-sharing framework. This allows you to collect server-side variables using your existing Django context processors, sanitize them into JSON-safe snapshots, and expose them directly inside your reactive Reflex states.

---

## 1. Per-Event Context Utilities

When an event (such as a click or form submission) is dispatched from the browser, the `DjangoEventBridge` establishes a thread-safe environment variable context. Inside any Reflex event handler, you can import and call these helper functions to fetch live Django request structures:

| Function | Returns | Purpose |
|:---|:---|:---|
| **`current_request()`** | `HttpRequest` | Retrieves the synthetic, request-bound object representing the active client connection. |
| **`current_user()`** | `User` or `AnonymousUser` | Fetches the live, authenticated Django User instance (directly from `aget_user()`). |
| **`current_session()`** | `SessionStore` | Provides direct read/write access to the persistent backend Django session row. |
| **`current_language()`** | `str` | Returns the active language code derived from browser headers or custom middleware routing. |

> [!NOTE]
> These functions pull from thread-local/coroutine-local context variables. They are fully live and operational **only** during the execution of an event handler. Outside of event handlers (e.g., at module import time or in background tasks), they will return `None` or anonymous structures.

---

## 2. Context Processors & Sanitization

To populate your reactive frontend with server-side context variables, `reflex-django` exposes a central utility called **`collect_reflex_context(request)`**. This function aggregates and processes variables from two primary sources, depending on your configuration:

### Configuration Options

You can control context aggregation behavior inside your Django `settings.py` file:

```python
# backend/settings.py

# 1. Custom Dotted Path Processors (Recommended for Reflex)
REFLEX_DJANGO_CONTEXT_PROCESSORS = (
    "shop.context.site_metadata",
    "shop.context.feature_flags",
)

# 2. Or, Fallback to standard Django Template Processors
REFLEX_DJANGO_USE_TEMPLATE_CONTEXT_PROCESSORS = True
```

### The Sanitization Pipeline

Reflex reactive states are transferred to the client browser as serialized JSON payloads. Since traditional Django context processors often return rich, non-serializable objects (like class-based forms, complex database querysets, or raw request handles), `collect_reflex_context` passes all generated payloads through a strict **sanitization filter**:

1. **Automatic Dropping**: Heavy, complex, or potentially unsafe objects are automatically stripped. For security, `request`, `perms`, and `messages` are never passed to the frontend.
2. **User Object Translation**: Instead of passing the live, database-backed `User` model, the pipeline automatically translates it into a simplified, flat JSON dictionary snapshot representing core fields (e.g., username, authentication state, email).
3. **Strict Serialization Enforcement**: Any custom variables returned by your processors must be JSON-serializable (strings, booleans, integers, floats, lists, or flat dictionaries). Returning un-serializable objects (such as `Decimal` or `datetime` values) will trigger state serialization errors.

---

## 3. Consuming Context in Plain Reflex States

To ingest your sanitized context dictionary into a reactive Reflex state, inherit from **`DjangoContextState`** or subclass **`AppState`** (which includes context management out of the box).

When your page loads, or during an explicit user action, call the state's asynchronous method **`self.load_django_context()`** to hydrate reactive fields.

### Solid Example: Custom Theme & Feature Flags

Here is how you can set up a custom context processor and consume its JSON values on a dashboard page:

#### Step 1: Define the Context Processor

Create a standard Python function that accepts a Django `request` and returns a flat, JSON-safe dictionary:

```python
# shop/context.py

def site_metadata(request):
    """Inject site-wide settings and basic configurations."""
    return {
        "site_name": "Premium Gadgets Corp",
        "maintenance_mode": False,
        "support_email": "support@gadgetscorp.com",
    }

def feature_flags(request):
    """Determine dynamic frontend flags based on the logged-in user."""
    user = request.user
    return {
        "enable_beta_ui": user.is_authenticated and user.is_staff,
        "discount_percent": 15 if user.groups.filter(name="VIP").exists() else 0,
    }
```

Register them in your `settings.py`:

```python
# backend/settings.py

REFLEX_DJANGO_CONTEXT_PROCESSORS = (
    "shop.context.site_metadata",
    "shop.context.feature_flags",
)
```

#### Step 2: Bind to your Reflex State

Subclass `AppState` (or `DjangoContextState`) to automatically expose context loading methods. By invoking `self.load_django_context()` in your page's `on_load` lifecycle hook, the fields are fetched and bound:

```python
# frontend/states/dashboard.py
import reflex as rx
from reflex_django.state import AppState

class DashboardState(AppState):
    # Declare reactive fields to receive the context processor variables
    site_name: str = ""
    support_email: str = ""
    enable_beta_ui: bool = False
    discount_percent: int = 0
    
    @rx.event
    async def on_load(self):
        # 1. First, hydrate the Django user and session contexts
        await self.refresh_django_user_fields()
        
        # 2. Trigger context processors and populate state properties
        # This executes your custom callables and applies sanitization
        context = await self.load_django_context()
        
        # 3. Assign the returned JSON-safe variables to reactive fields
        self.site_name = context.get("site_name", "My App")
        self.support_email = context.get("support_email", "")
        self.enable_beta_ui = context.get("enable_beta_ui", False)
        self.discount_percent = context.get("discount_percent", 0)
```

#### Step 3: Draw the UI Component

Bind your state variables directly into standard Reflex components:

```python
# frontend/pages/dashboard.py
import reflex as rx
from frontend.states.dashboard import DashboardState

def dashboard_view() -> rx.Component:
    return rx.vstack(
        rx.heading(DashboardState.site_name),
        rx.cond(
            DashboardState.enable_beta_ui,
            rx.badge("Beta Tester Enabled", color_scheme="purple"),
            rx.badge("Standard Interface", color_scheme="gray")
        ),
        rx.text(f"Your exclusive discount: {DashboardState.discount_percent}%"),
        rx.link(f"Contact Support ({DashboardState.support_email})", href=f"mailto:{DashboardState.support_email}"),
        padding="2rem",
    )
```

---

## 4. Context Processors in Reactive CRUD (`ModelCRUDView`)

If you are using `ModelCRUDView` or `ModelState` to automate database operations, context integration is managed automatically. 

During every CRUD database transaction (such as listing, creation, or deletion), the framework wraps the current event in a **`DjangoStateRequest`** container, which is exposed to your hooks as **`self.request`**.

### The `DjangoStateRequest` Schema

The request wrapper binds several keys designed to let your database methods act like standard Django class-based views:

| Attribute | Return Type | Role / Content |
|:---|:---|:---|
| **`self.request.django_request`** | `HttpRequest` | The underlying raw synthetic HTTP request. |
| **`self.request.user`** | `User` | **Live database User object**. Always use this for scoping database filters and authorization. |
| **`self.request.context`** | `dict` | Flat dictionary containing the processed outputs of all active context processors. |
| **`self.request.LANGUAGE_CODE`** | `str` | Direct attribute proxy mapping to values in `request.context`. |

> [!CAUTION]
> **Authorization Security Trap:** Do not use `self.request.context["user"]` to perform security checks or database queries. The context dictionary contains a *snapshot dictionary* representing user parameters (designed for rendering text in views). For database mutations, row filters, and credential checks, always use **`self.request.user`** (the live ORM model).

### Example: Multi-Lingual Product Catalog Filtering

You can customize the underlying database queryset using context attributes. In this example, we read the active `LANGUAGE_CODE` context variable from a processor and filter the catalog items:

```python
# frontend/states/products.py
from reflex_django.state import ModelState
from shop.models import Product

class CatalogState(ModelState):
    model = Product
    fields = ["name", "description", "price"]
    
    def get_queryset(self):
        # Obtain base queryset
        qs = super().get_queryset()
        
        # Access the context-processor variable LANGUAGE_CODE
        # self.request is a DjangoStateRequest wrapper
        current_lang = getattr(self.request, "LANGUAGE_CODE", "en")
        
        # Scope the products based on the active browser language
        return qs.filter(language=current_lang)
```

### Performance Tuning: `load_context_processors`

Executing context processors on every CRUD call can trigger redundant background database queries (such as checking user roles or fetching site metadata) which may slow down high-frequency socket events.

If your CRUD state does not need context-processor variables (e.g., it only scopes database records using the live `self.request.user`), you can skip processor collection entirely:

```python
class QuickNotesState(ModelState):
    model = Note
    fields = ["text"]
    
    # Skips executing context processors during dispatch
    # self.request.user remains fully populated and authenticated
    load_context_processors = False 
    
    def get_queryset(self):
        return Note.objects.filter(owner=self.request.user)
```

---

## 5. Common Architectural Pitfalls

* **Returning Rich Classes**: Avoid returning forms, model objects, or complex querysets from custom context processors. If they cannot be parsed by `json.dumps`, they will trigger server serialization crashes.
* **Accessing Context at Module Level**: Never call `current_request()` or attempt to read context processors at the root level of your python files. They must only be accessed inside active event handlers (methods wrapped with `@rx.event` or CRUD hooks).
* **Using Snapshots for Database Actions**: Never base database insertions or deletions on values inside `self.request.context`. These represent serialized snapshots of the past. Always execute permissions validation against `self.request.user` or call `require_login_user()`.

---

**Navigation:** [← State Management](state_management.md) | [Next: Django Middleware in Reflex →](django_middleware_to_reflex.md)
