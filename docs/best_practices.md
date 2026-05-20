# Best Practices & Architecture Guide

Building production-ready, unified applications requires adhering to reliable design patterns. Because `reflex-django` bridges two distinct software models—Django's synchronous, request-response, database-centric model and Reflex's asynchronous, reactive, state-driven model—it is important to configure your code for security, execution performance, and circular import prevention.

This manual presents production-tested guidelines and architecture patterns for writing secure, performant, and maintainable unified applications.

---

## 1. Domain Separation & The Data Flow

To keep your codebase clean and scalable as it grows, enforce a strict separation of concerns between your business logic layer and your presentation layer.

```text
    ┌────────────────────────────────────────────────────────┐
    │                      DATABASE LAYER                    │
    │  • Django models.py (Field schemas, db constraints)    │
    │  • Django managers.py (Custom SQL querysets)           │
    └──────────────────────────┬─────────────────────────────┘
                               │
                               ▼
    ┌────────────────────────────────────────────────────────┐
    │                    SERIALIZATION LAYER                 │
    │  • ReflexDjangoModelSerializer (JSON schemas, read-only)│
    └──────────────────────────┬─────────────────────────────┘
                               │
                               ▼
    ┌────────────────────────────────────────────────────────┐
    │                     CONTROLLER LAYER                   │
    │  • ProductState (Validation hooks, permission checks)  │
    └──────────────────────────┬─────────────────────────────┘
                               │
                               ▼
    ┌────────────────────────────────────────────────────────┐
    │                     PRESENTATION LAYER                 │
    │  • product_catalog_page (Reflex component components)  │
    └────────────────────────────────────────────────────────┘
```

### Key Architectural Guidelines
1. **Define Domain Rules in Django**: Place constraints, default values, database relationship controls, and custom query scopes inside Django models, managers, and fields.
2. **Handle Mappings in Serializers**: Restrict client read/write access and define computed properties using `ReflexDjangoModelSerializer` schemas.
3. **Orchestrate Events in States**: Use Reflex States solely as controllers to parse client inputs, evaluate permissions, and invoke underlying services.
4. **Build Pure UI in Pages**: Restrict Reflex page components strictly to visual layouts, layout alignments, and bindings to State variables.

---

## 2. Import Hygiene & The Startup Lifecycle

Because Django models require a booted registry to operate, importing models or database-bound states at the module level before `django.setup()` executes will trigger `AppRegistryNotReady` exceptions.

### Stage 1: Load Configuration
Reflex parses `rxconfig.py` at startup. No Django imports should exist at this level.
              │
              ▼
### Stage 2: Initialize Settings & App Registry
`ReflexDjangoPlugin` resolves environment configurations and boots `django.setup()`.
              │
              ▼
### Stage 3: Load Application States
Your state files (`state.py`) can now safely import Django models and serializers.

### Import Best Practices
* **Avoid Module-Level Database Imports in Configs**: Never import Django models inside `rxconfig.py` or any utilities imported by it.
* **Defer Submodule Loading**: If you have helper functions that import models or execute queries, place imports inside the function body rather than at the top of the file:

```python
# Avoid top-level module imports for database models in utility scripts
# from shop.models import Product  <-- Can cause AppRegistryNotReady

def calculate_discount(product_id: int) -> float:
    # Safely import inside the function context
    from shop.models import Product
    ...
```

---

## 3. Server-Side Security & Mutation Traps

When building reactive UIs, it is easy to assume that hiding a button in the frontend is enough to secure an action. **This is a dangerous misconception.** Reflex state variables are transmitted to and stored on the client browser. An attacker can inspect the client-side state and trigger events directly.

> [!CAUTION]
> Never rely on client state flags (like `State.is_authenticated` or `State.is_staff`) inside critical event handlers to determine authorization. Always validate permissions on the server using `self.request.user` or auth decorators during the event call.

### The Secure Event Pattern (Server-Side Checks)
```python
# Correct, secure implementation
class CatalogState(ModelState):
    model = Product
    fields = ["name", "price"]

    @rx.event
    @login_required # Enforces active session validation on every call
    async def save(self):
        # 1. Perform server-side role check
        if not self.request.user.is_staff:
            self.error = "Permission denied: Staff access required."
            return
            
        # 2. Proceed with database mutations
        await self.dispatch(ACTION_SAVE)
```

### The Browser Cookie Synchronization Pattern
When authenticating users (via `alogin()` or custom endpoints), always synchronize the browser session cookies. This ensures that Django session cookies are updated across both HTTP and WebSocket channels:

```python
from reflex_django.middleware import collect_reflex_context

@rx.event
async def login_user(self):
    user = await aauthenticate(username=self.username, password=self.password)
    if user:
        await alogin(self.django_request, user)
        # Force browser cookie sync to align WebSocket sessions
        return rx.call_script("document.cookie = ...")
```

---

## 4. Thread-Safe, Non-Blocking Async Execution

Reflex event loops run asynchronously. If you execute synchronous database queries inside an event handler, you will **block the entire ASGI execution loop**, causing other users' requests to queue up and freeze.

### The Golden Rule of Database Queries
Always use `async def` for handlers that execute database queries, and use Django's modern async ORM helpers:

```python
# Bad, blocking implementation
@rx.event
def save_item(self):
    # BLOCKS the ASGI thread!
    Product.objects.create(name=self.name, price=self.price)

# Good, thread-safe implementation
@rx.event
async def save_item(self):
    # Runs asynchronously without blocking other users
    await Product.objects.acreate(name=self.name, price=self.price)
```

Use the following async ORM equivalents:
* Use `acreate()` instead of `create()`.
* Use `aget()` instead of `get()`.
* Use `asave()` instead of `save()`.
* Use `adelete()` instead of `delete()`.
* Iterate over querysets using `async for`:

```python
async for product in Product.objects.filter(is_active=True):
    print(product.name)
```

---

## 5. State Serialization & Client Leakage Rules

Reflex state variables (defined in your State class) are serialized to JSON and sent to the client browser. 

### What You Can Put in State Variables
* **Safe Types**: Strings, integers, floats, booleans, lists, and dictionaries.
* **Serialized Models**: Dictionaries containing raw field values returned by your serializer (`serializers.data` or `await serializer.adata()`).

### What You Must Never Put in State Variables
* **Django Model Instances**: Raw model instances (e.g. `product = Product()`) are not JSON-serializable and will crash the Reflex serializer.
* **Database Connection Handlers**: Raw database connection pointers or cursor pools.
* **System Request Objects**: Raw `HttpRequest` or `WSGIRequest` instances.
* **Sensitive Secrets**: Unhashed passwords, private security tokens, or customer billing details.

---

## 6. Query Performance Optimization

To prevent high-volume database queries from slowing down your application, leverage `ModelCRUDView`'s relational optimization fields.

### Database Joins & Prefetching
For tables with foreign key relationships, set `Meta.queryset_select_related` and `Meta.queryset_prefetch` to execute database joins in a single query:

```python
class PostState(ModelState):
    model = BlogPost
    fields = ["title", "content"]

    class Meta:
        list_var = "posts"
        
        # Executes SQL join for the foreign key, preventing N+1 queries
        queryset_select_related = ("author",)
        
        # Prefetches many-to-many tag relationships in a single batch
        queryset_prefetch = ("tags",)
```

---

## 7. Production Readiness Checklist

Before launching your unified application in production, verify that the following configurations are applied:

- [ ] **Production Settings**: Ensure `DJANGO_SETTINGS_MODULE` is explicitly set to point to your production configuration file.
- [ ] **Debug Disabled**: Verify that `DEBUG = False` is set in your active settings file.
- [ ] **Persistent Secret Keys**: Confirm that your production `SECRET_KEY` is loaded from a secure environment variable.
- [ ] **Allowed Hosts**: Ensure `ALLOWED_HOSTS` is restricted to your production domain names.
- [ ] **Static Assets Compiled**: Verify that `collectstatic` was executed during the build stage.
- [ ] **Database Migrations Applied**: Ensure database migrations run successfully in your deployment pipeline before the application boots.
- [ ] **Server-Side Checks Enabled**: Verify that every mutating state handler evaluates permissions and validates input fields on the server.

---

**Navigation:** [← Deployment Guide](deployment.md) | [Next: FAQ →](faq.md)
