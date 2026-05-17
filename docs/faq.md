# FAQ

Frequently asked questions about reflex-django.

---

## General

### What is reflex-django?

A Reflex **plugin** that runs Django and Reflex in **one process** with an HTTP prefix dispatcher and an optional **event bridge** for session/user context. See [Introduction](introduction.md).

### Is it a merged URL router?

No. Reflex UI and `/_event/…` stay on Reflex; Django serves configured HTTP prefixes only. [Architecture](architecture.md).

### I already have Django — where do I start?

[Existing Django project](existing_django_project.md).

---

## Authentication and sessions

### Why is `current_user()` AnonymousUser in my handler?

- Event bridge disabled (`install_event_bridge=False`).  
- No session cookie on the Socket.IO connection.  
- After login, cookie not synced — use `session_auth_mixin` or canned auth (`session_js`). [Authentication](authentication.md).

### Why doesn’t Django middleware run when I click a button?

Reflex events are not HTTP requests. Only `DjangoEventBridge` runs (session, user, optional locale). [Django middleware to Reflex](django_middleware_to_reflex.md).

### Can I trust `DjangoUserState.is_authenticated`?

No—for authorization use `current_user()` or `require_login_user()` on the server.

---

## Configuration and routing

### Admin or API returns 404

Prefix mismatch between `ReflexDjangoPlugin` (`admin_prefix`, `backend_prefix`) and `ROOT_URLCONF`. [Routing](routing.md).

### Plugin `settings_module` seems ignored

`DJANGO_SETTINGS_MODULE` in the environment **wins** over the plugin argument. [Configuration](configuration.md).

### Difference between `ModelState` and `ModelCRUDView`?

They use the **same CRUD pipeline**; configuration differs:

| | **`ModelState`** | **`AppState, ModelCRUDView`** |
|---|------------------|-------------------------------|
| **Includes auth** | Yes (`AppState` built in) | You must add `AppState` |
| **Serializer** | Auto from `model` + `fields` | You set `serializer_class` |
| **List var** | `data` (override with `Meta.list_var`) | Pluralized (`posts`, `products`, …) |
| **Handlers** | `load`, `save`, `refresh`, … (+ legacy aliases) | Legacy (`save_post`, `on_load_posts`) + canonical by default |
| **When to use** | New CRUD screens (default) | Custom serializers, legacy names |

**`ModelState` already subclasses `ModelCRUDView`.** You do not pick one instead of the other for CRUD—you pick convenience vs explicit control.

Examples and migration: **[ModelState and ModelCRUDView](model_state_and_crud_view.md)**. Deep dives: [Reactive ModelState](reactive_model_state.md), [CRUD with mixins](crud_with_mixins_and_states.md).

---

## CRUD

### Is pagination built in?

**Yes, opt-in.** Set `Meta.paginate_by = 20` (or `paginate_by = 20` on the state class body) on `ModelState` / `ModelCRUDView` / `ModelListView` to get `page`, `page_size`, pagination totals, `next_page`, `prev_page`, and related handlers. On **`ModelState`**, defaults are `total_count`, `page_count`, and `search` (not `{list_var}_search`). `page_size` is initialized from `paginate_by`. Default is `paginate_by = None` (load all rows). See [README](../README.md#list-pagination-search-and-sorting) and [Reactive ModelState](reactive_model_state.md#pagination-metapaginate_by). Manual pagination is still documented in [CRUD without mixins](crud_without_mixins.md).

### Where did `crud_mixin()` go?

Removed. Use `ModelCRUDView`. [CHANGELOG](../CHANGELOG.md), [llm.txt](../llm.txt).

### Where did `reflex_django.authz` go?

Removed. Use `reflex_django.auth.shortcuts` and `reflex_django.auth.decorators`. [CHANGELOG](../CHANGELOG.md).

---

## API and integrations

### Can I use DRF only?

reflex-django does not depend on DRF. You may mount DRF under `backend_prefix` yourself. Reflex states can still use the ORM directly. [API integration](api_integration.md).

### Can I use httpx from Reflex to call my API?

That is application code. The framework does not provide an HTTP client for Reflex → Django calls in-process ORM is preferred.

---

## CLI and deploy

### `reflex django` vs `manage.py`?

`reflex django` loads `rxconfig` first so settings match `reflex run`. [CLI](cli.md).

### How do I use `self.request` on `AppState`?

Subclass **`AppState`** (or **`ModelState`**) and use **`self.request`** inside **`@rx.event`** handlers after the event bridge is enabled:

```python
class MyState(AppState):
    @rx.event
    async def on_load(self):
        if self.request.user.is_authenticated:
            page = self.request.GET.get("page", "1")
```

- **`self.request.user`** — live Django user (ORM scoping, permissions).
- **`self.request.GET`**, **`.path`**, **`.COOKIES`**, **`.META`** — synthetic `HttpRequest` from `router_data`.
- **`self.django_request`** — raw `HttpRequest` when a library needs it.
- **`self.username`** / **`self.is_authenticated`** — Reflex vars for UI only (not for authorization).

Plain **`rx.State`**: use **`from reflex_django import request`** instead. Full examples: [Authentication — Accessing the Django request on AppState](authentication.md#accessing-the-django-request-on-appstate).

---

## Troubleshooting quick links

| Topic | Page |
|-------|------|
| Event bridge | [Django middleware to Reflex](django_middleware_to_reflex.md) |
| Context processors | [Django context to Reflex](django_context_to_reflex.md) |
| Deploy | [Deployment](deployment.md) |
| Tests | [Testing](testing.md) |

---

**Navigation:** [← Best practices](best_practices.md) | [Docs index](index.md)
