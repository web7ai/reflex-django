# Using Django context processors

In a Django template, you can write `{{ user }}`, `{{ messages }}`, `{{ site_name }}`, and they "just work" — because of **context processors**. A context processor is a small function that returns a dict, and the dict gets merged into every template's context automatically.

`reflex-django` reuses this idea for Reflex events. Your context processors run on every WebSocket event, the resulting dict is JSON-sanitized, and it becomes available on `self.request.context` (and as attributes on `self.request`).

This page covers when to use this, how to wire it up, and the small set of gotchas.

---

## What it looks like

```python
# settings.py
REFLEX_DJANGO_CONTEXT_PROCESSORS = (
    "myapp.context.site_info",
    "myapp.context.feature_flags",
)
```

```python
# myapp/context.py
def site_info(request):
    return {
        "site_name": "My Shop",
        "support_email": "help@example.com",
    }

def feature_flags(request):
    return {
        "checkout_v2": True,
        "experimental_dashboard": request.user.is_authenticated and request.user.is_staff,
    }
```

```python
# anywhere in a Reflex handler
class HomeState(AppState):
    @rx.event
    async def on_load(self):
        self.title = self.request.SITE_NAME              # attribute style
        self.support = self.request.context["support_email"]   # dict style
        if self.request.context.get("checkout_v2"):
            ...
```

Both attribute access (`self.request.SITE_NAME`) and dict access (`self.request.context["key"]`) work. Pick whichever reads better.

---

## When you'd want this

- A value computed once per request and used in many handlers (current site, locale, feature flags).
- Cleanly exposing a few global facts to your states without subclassing `AppState` everywhere.
- Sharing the same context with Django templates and Reflex events.

If you only need it in one or two handlers, just compute it inline. Context processors are for cross-cutting concerns.

---

## How it's wired

When `REFLEX_DJANGO_AUTO_LOAD_CONTEXT = True` (the default), the bridge calls every processor in `REFLEX_DJANGO_CONTEXT_PROCESSORS` on each event, with the synthetic `HttpRequest` as the argument:

```text
event arrives
  │
  ▼
bridge builds HttpRequest
  │
  ▼
for each entry in REFLEX_DJANGO_CONTEXT_PROCESSORS:
    result = processor(request)
    merge result into a context dict
  │
  ▼
JSON-sanitize the dict
  │
  ▼
attach to self.request.context
  │
  ▼
your handler runs
```

The dict is **JSON-sanitized** before it's attached. That means:

- `Decimal`, `datetime`, `date`, `UUID` → strings.
- Model instances → dropped (with a warning) — return the fields you actually need.
- `request`, `perms`, `messages` keys → silently removed (those have first-class state vars).
- Anything that can't be serialized → dropped.

---

## Use Django's template context processors as a starting point

If your existing project already has `TEMPLATES[0]["OPTIONS"]["context_processors"]`, you can reuse the same processors for free:

```python
REFLEX_DJANGO_USE_TEMPLATE_CONTEXT_PROCESSORS = True   # default
```

When that's on (and `REFLEX_DJANGO_CONTEXT_PROCESSORS` is empty), the bridge runs your template context processors. So if you've already written a `myapp.context.site_info`, it's available in Reflex too.

The opposite is also true: any processor you list in `REFLEX_DJANGO_CONTEXT_PROCESSORS` gets called for templates *and* events (you don't need to list it twice).

---

## What's already exposed

Even without any processors of your own, the bridge sets these built-in keys on `self.request`:

| Attribute / key | Source |
|:---|:---|
| `self.request.LANGUAGE_CODE` | `translation.get_language()` |
| `self.request.LANGUAGE_BIDI` | RTL flag |
| `self.request.user` | The live Django user (not a snapshot — this is the live object) |
| `self.request.context["user"]` | A JSON snapshot of the user (`is_authenticated`, `username`, `email`, …) |
| `self.request.path` | The page URL when the event was fired |
| `self.request.GET` | Query params from the URL |
| `self.request.COOKIES` | Cookies the browser sent |

`self.request.user` (no quotes around the attribute, no `.context`) is always the live Django user model — use it for ORM scoping and authorization. `self.request.context["user"]` is the JSON-friendly snapshot, useful for serializing into a state field.

---

## Disabling per-state context loading

For high-frequency states where you don't need the context, skip it for performance:

```python
class TelemetryState(ModelState):
    model = Event
    fields = ["payload"]

    load_context_processors = False    # skip on this state's events

    class Meta:
        list_var = "events"
```

The synthetic `HttpRequest` is still built and `self.request.user` still works — only the context-processor merging is skipped.

To disable globally:

```python
REFLEX_DJANGO_AUTO_LOAD_CONTEXT = False
```

---

## A worked example — feature flags

A common use: gate UI by feature flags computed from settings and user attributes.

```python
# flags/context.py
from django.conf import settings

def flags(request):
    return {
        "checkout_v2": settings.CHECKOUT_V2_ENABLED,
        "experimental_dashboard": (
            settings.CHECKOUT_V2_ENABLED
            and request.user.is_authenticated
            and request.user.email.endswith("@example.com")
        ),
        "max_cart_items": 25 if request.user.is_authenticated else 5,
    }
```

```python
# settings.py
REFLEX_DJANGO_CONTEXT_PROCESSORS = ("flags.context.flags",)
```

```python
# shop/views.py
class CheckoutState(AppState):
    @rx.event
    async def proceed(self):
        if self.request.context.get("checkout_v2"):
            return rx.redirect("/checkout/v2")
        return rx.redirect("/checkout/v1")
```

Now every Reflex event has the feature-flag dict, computed once per event, JSON-safe, ready to read.

---

## Functional accessors (no state subclass needed)

If you'd rather not subclass `AppState`, the same data is available via module-level helpers:

```python
from reflex_django import current_request, current_user, current_language

class FilterState(rx.State):
    @rx.event
    async def apply(self):
        req = current_request()
        if req is None:
            return    # outside an event, no request
        site = getattr(req, "SITE_NAME", None)
        lang = current_language()
```

These return the same values as `self.request` / `self.user` would, just without the inheritance.

---

## Common bumps

**My processor's value is missing**
JSON sanitization may have dropped it. If you returned a model instance, a `Decimal`, or a `datetime`, convert to a string or primitive first.

**`self.request.SITE_NAME` is `None`**
Check that:
1. The processor is in `REFLEX_DJANGO_CONTEXT_PROCESSORS` (or in `TEMPLATES[0]['OPTIONS']['context_processors']` with `REFLEX_DJANGO_USE_TEMPLATE_CONTEXT_PROCESSORS = True`).
2. `REFLEX_DJANGO_AUTO_LOAD_CONTEXT = True`.
3. The state hasn't set `load_context_processors = False`.

**The processor crashes the page**
Wrap risky lookups defensively. A processor that raises blocks the request:

```python
def site_info(request):
    try:
        return {"site_name": Site.objects.aget_current().name}
    except Exception:
        return {"site_name": "Unknown"}
```

(Use the sync version of any lookup that can run in both HTTP and event contexts, or guard with `try/except` in the processor.)

---

## Summary

- Context processors are functions `f(request) -> dict` that run on every Reflex event.
- The result merges into `self.request.context` (and attributes on `self.request`).
- Configure via `REFLEX_DJANGO_CONTEXT_PROCESSORS`, or reuse Django template processors.
- The dict is JSON-sanitized; drop model instances, `Decimal`, `datetime` first.
- Use `self.request.user` for the *live* user, `self.request.context["user"]` for the JSON snapshot.
- Disable per-state with `load_context_processors = False` if you don't need it.

---

**Next:** [Custom middleware in events →](django_middleware_to_reflex.md)
