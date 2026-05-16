# Django context to Reflex

Pass **JSON-safe context** from Django into Reflex state via context processors and **`DjangoContextState`**.

---

## Prerequisites

- [Django middleware to Reflex](django_middleware_to_reflex.md)  
- [State management](state_management.md)

---

## Per-event context variables

`reflex_django.context` binds the synthetic request for the current event:

| Function | Returns |
|----------|---------|
| `current_request()` | `HttpRequest` |
| `current_user()` | User (live, for authorization) |
| `current_session()` | Session store |
| `current_language()` | Active language code when i18n bridge ran |

`begin_event_request(request)` / `end_event_request()` — used by the bridge; tests may call directly.

---

## Context processors

`collect_reflex_context(request)` merges:

1. **`REFLEX_DJANGO_CONTEXT_PROCESSORS`** — your dotted callables (exclusive when non-empty).  
2. Or, when empty and `REFLEX_DJANGO_USE_TEMPLATE_CONTEXT_PROCESSORS=True`, template processors with **sanitization** (drops `request`, `perms`, `messages`; converts `user` to snapshot).

Builtins:

- `builtin_user_context`  
- `builtin_i18n_context`

---

## `DjangoContextState`

Load processor output into Reflex state:

```python
from reflex_django import DjangoContextState

# Typical pattern: on_load calls load_django_context @rx.event
```

Anything assigned to Reflex vars must be **JSON-serializable**.

---

## `DjangoStateRequest` (model CRUD)

On `ModelCRUDView`, each `dispatch` binds:

| Attribute | Value |
|-----------|--------|
| `self.django_request` | `current_request()` |
| `self.request` | `DjangoStateRequest` wrapper |
| `self.request.user` | Live user for ORM scoping |
| `self.request.context` | Full processor dict |

Processor `user` snapshots live in `self.request.context["user"]`, not `self.request.user`.

Set `Meta.load_context_processors = False` to skip processor collection while still binding the request.

---

## Example: filter by language

*Example application code.*

```python
class NotesState(AppState, ModelCRUDView):
    def filter_queryset(self, qs):
        if self.request.LANGUAGE_CODE == "ar":
            qs = qs.filter(locale="ar")
        return qs
```

---

## Submodule helpers

From `reflex_django.reflex_context` (not all re-exported on package root):

- `template_context_processor_paths()`  
- `reflex_context_processor_paths()`  
- `reflex_context_processors_use_template_sanitization()`

---

## Advanced usage

Custom processor:

```python
def site_settings(request):
    return {"site_name": "My Shop"}

REFLEX_DJANGO_CONTEXT_PROCESSORS = (
    "myapp.context.site_settings",
)
```

---

## Performance tips

- Set `load_context_processors=False` on CRUD states that do not need template context.  
- Keep processor payloads small.

---

## Common mistakes

- Returning ORM objects or `HttpRequest` from processors.  
- Using `self.request.context["user"]` for authorization instead of `self.request.user`.

---

## Developer notes

- Sanitization: `src/reflex_django/reflex_context.py`  
- Tests: `reflex_django_tests/test_reflex_context.py`

---

## See also

- [State management](state_management.md)  
- [CRUD with mixins](crud_with_mixins_and_states.md)

---

**Navigation:** [← Django middleware to Reflex](django_middleware_to_reflex.md) | [Next: State management →](state_management.md)
