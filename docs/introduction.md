# Introduction

**reflex-django** connects [Django](https://www.djangoproject.com/) and [Reflex](https://reflex.dev) in a **single ASGI process**. You keep Django for the ORM, admin, sessions, migrations, and HTTP APIs. Reflex provides the reactive UI and WebSocket event channel. One dev command — `python manage.py run_reflex` — runs both.

This package is **Django-first**: configuration lives in Django (`settings.py`, `urls.py`), not in a hand-maintained `rxconfig.py`. Reflex settings are declared on `reflex_mount()` in your root URLconf.

---

## The problem it solves

Reflex sends UI updates over **WebSockets** (`/_event`), not through Django’s normal HTTP middleware stack. Without a bridge, `request.user`, sessions, and locale from Django are unavailable inside `@rx.event` handlers.

**reflex-django** provides:

1. **Unified ASGI routing** — Paths like `/admin`, `/api`, and `/static` go to Django; the SPA and WebSockets go to Reflex.
2. **Event bridge** — On each WebSocket event, a synthetic `HttpRequest` is built from cookies and headers so `self.request.user` works in Reflex state.
3. **Django-first project layout** — Pages in `{app}/views.py`, config in `reflex_mount()`, no `{app}/{app}.py` boilerplate.

---

## How the pieces fit together

```text
┌─────────────────────────────────────────────────────────────┐
│                    Single ASGI process                       │
│                                                              │
│   Browser HTTP  ──►  Path dispatcher                         │
│                         ├─ /admin, /api, …  ──►  Django      │
│                         └─ everything else  ──►  Reflex SPA  │
│                                                              │
│   Browser WS    ──►  Reflex /_event  ──►  DjangoEventBridge  │
│                                              (session + user)  │
└─────────────────────────────────────────────────────────────┘
```

| Piece | Role |
|:---|:---|
| **`reflex_mount()`** | Registers Reflex `rx.Config` (ports, `app_name`, plugins) and adds the SPA catch-all URL pattern |
| **`django_led_app`** | Built-in module Reflex imports for `app` (replaces `{app_name}/{app_name}.py`) |
| **`{app}/views.py`** | Reflex pages via `@template` / `@page` — auto-discovered from `INSTALLED_APPS` |
| **`ReflexDjangoPlugin`** | Wires Django ASGI, prefixes, and the event bridge (always enabled) |

---

## What this is (and is not)

### It is

- A **Django project** with a Reflex frontend mounted as a catch-all SPA
- **100% Python** for UI and backend (no separate React/Vue repo required)
- **Shared sessions** — log in via `/admin` or Django auth; Reflex sees the same user on the next event

### It is not

- A way to register Reflex routes inside Django `urls.py` per page (client-side routing owns `/`, `/about`, …)
- Full Django `MIDDLEWARE` on every button click (the event bridge loads session/auth selectively for speed)
- A replacement for Django templates on existing server-rendered views (those keep working under your API/admin prefixes)

---

## Configuration in one place: `reflex_mount()`

All Reflex options that used to scatter across `rxconfig.py` and Django settings are passed here:

```python
# project/urls.py
from reflex_django.urls import reflex_mount

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("myapp.api_urls")),
]
urlpatterns += [
    reflex_mount(
        app_name="myapp",           # optional; default = project folder name
        django_prefix=("/admin", "/api"),
        rx_config={
            "frontend_port": 3000,
            "backend_port": 8000,
        },
    ),
]
```

Importing `urls.py` at startup registers this config. `manage.py run_reflex` and Granian workers read the same values.

---

## The `django_led_app` module

Classic Reflex expects `demo/demo.py` with `app = rx.App()`. In reflex-django you use a **Django app label** (e.g. `demo`) for pages in `demo/views.py`, but Reflex loads the app instance from:

```text
reflex_django.django_led_app:app
```

That module lazily:

1. Imports page modules from `INSTALLED_APPS` (`demo/views.py`, …)
2. Creates `rx.App()` via the built-in factory
3. Registers routes from `@template` / `@page` decorators

You do **not** create `demo/demo.py`. See [Django-led URL routing](django_urls.md).

---

## When to use reflex-django

**Good fit:**

- Brownfield Django apps adding a modern SPA
- Teams that want Django’s ORM/admin with Reflex’s reactive UI
- Single-origin dev and simple deployments (one process, one port pair)

**Less ideal:**

- Static sites with only Django templates
- Architectures that require Reflex and Django on completely separate hosts with token-only APIs

---

## Next steps

| Goal | Guide |
|:---|:---|
| New project in 15 minutes | [Quickstart](quickstart.md) |
| Add Reflex to existing Django | [Existing Django project](existing_django_project.md) |
| `reflex_mount` and URL ownership | [Django-led URL routing](django_urls.md) |
| All settings | [Configuration](configuration.md) |
| Pages in `views.py` | [Pages in views.py](pages_in_views.md) |

---

**Navigation:** [← Docs Index](index.md) | [Next: Installation →](installation.md)
