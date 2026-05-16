# Django middleware to Reflex

How **`DjangoEventBridge`** exposes Django session and user context to Reflex **events**—and what it does **not** do.

---

## Prerequisites

- [Architecture](architecture.md)

---

## The problem

Django **`MIDDLEWARE`** runs on HTTP requests. Reflex button clicks and `on_load` handlers use **Socket.IO events**, not Django views. Without a bridge, `request.user` and `request.session` are unavailable in `@rx.event` code.

---

## What the bridge runs

On each event, `DjangoEventBridge.preprocess` (`src/reflex_django/middleware.py`):

1. `end_event_request()` — clear stale contextvar  
2. Build `HttpRequest` from `event.router_data` (path, query string, cookies, headers, client IP)  
3. `_attach_session(request)` via `SESSION_ENGINE`  
4. `_activate_i18n_for_request(request)` when `USE_I18N` and `REFLEX_DJANGO_I18N_EVENT_BRIDGE`  
5. `await _attach_user(request)` using **`aget_user`** (async)  
6. `begin_event_request(request)`  
7. When `REFLEX_DJANGO_AUTH_AUTO_SYNC` is true, `await state.refresh_django_user_fields()` for **`AppState`** subclasses

Returns `None` (never short-circuits the event).

---

## What the bridge does not run

- `CsrfViewMiddleware`  
- `SecurityMiddleware`  
- Custom middleware chains  
- Full Django HTTP request/response cycle  

For CSRF on Django HTTP forms under a prefix, use normal Django views. For Reflex mutations, enforce authorization in handlers (`current_user()`, permissions).

---

## Using the bound request

**Option A — `request` proxy (recommended, Django-familiar)** — any `rx.State`:

```python
from reflex_django import request

@rx.event
async def my_handler(self):
    user = request.user
    session = request.session
    page = request.GET.get("page")
    token = request.headers.get("authorization")
    path = request.path
```

Works in every `@rx.event` handler while `DjangoEventBridge` is enabled (default). Outside an event, `request.user` is anonymous and `request.GET` is empty.

**Do not use `request.user` in component trees** (`rx.text(request.user)` fails — Reflex only accepts primitives, vars, or components). For navbar labels use **`DjangoAuthState.username`** / **`AppState.username`**, or primitive `request.username` only inside handlers (not as a reactive var on the client).

**Invalid:** `from reflex_django.state import request` — use `from reflex_django import request`.

**Option B — context helpers** (explicit):

```python
from reflex_django import current_user, current_request, current_session

@rx.event
async def my_handler(self):
    user = current_user()
    http = current_request()
    session = current_session()
```

**Option C — `AppState`** (auth + reactive UI snapshot):

```python
from reflex_django.state import AppState

class MyState(AppState):
    @rx.event
    async def my_handler(self):
        user = self.user           # same as current_user() for this event
        self.session["key"] = "x"  # persisted session store
```

Enable with `install_event_bridge=True` (default on `ReflexDjangoPlugin`). See [Authentication](authentication.md).

---

## HTTP vs event comparison

| | HTTP (Django prefix) | Reflex event |
|---|---------------------|--------------|
| Entry | Dispatcher → Django ASGI | Reflex → `DjangoEventBridge` |
| Middleware | Full `MIDDLEWARE` | Bridge only |
| Session | `SessionMiddleware` | Session engine on synthetic request |
| User | `AuthenticationMiddleware` | `aget_user` in bridge |

---

## `postprocess`

`postprocess` calls `end_event_request()`. Reflex’s processor may only invoke `preprocess` reliably; the next event’s preprocess clears stale bindings anyway (documented in source comments).

---

## Advanced usage

Call a specific middleware manually inside a handler if you truly need one-off behavior—pattern only; not a supported extension API:

```python
# Illustrative — adapt to your middleware
from django.middleware.locale import LocaleMiddleware
mw = LocaleMiddleware(lambda r: None)
mw.process_request(request)
```

Prefer `REFLEX_DJANGO_I18N_EVENT_BRIDGE` for locale.

---

## Common mistakes

- Expecting `CsrfViewMiddleware` on Reflex POST events.  
- Disabling the bridge and calling `current_user()` expecting a logged-in user.

---

## Developer notes

- Tests: `reflex_django_tests/test_event_bridge.py` (stub events, cookies, user).

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Always `AnonymousUser` | Cookies not sent; session not synced after login — [Authentication](authentication.md) |
| Wrong language | `REFLEX_DJANGO_I18N_EVENT_BRIDGE`, `USE_I18N` |

---

## See also

- [Django context to Reflex](django_context_to_reflex.md)  
- [Authentication](authentication.md)

---

**Navigation:** [← Routing](routing.md) | [Next: Django context to Reflex →](django_context_to_reflex.md)
