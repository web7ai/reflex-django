# Introduction

**reflex-django** runs [Django](https://www.djangoproject.com/) and [Reflex](https://reflex.dev) as a single ASGI application on a single port. You keep Django for the ORM, admin, sessions, migrations, and HTTP APIs. Reflex provides the reactive Python UI and the WebSocket event channel. One process, one entry point — `reflex_django.asgi_entry:application` — handles both.

This package is **Django-first**: configuration lives in Django (`settings.py`, `urls.py`), not in a hand-maintained `rxconfig.py`. Reflex settings are declared on `reflex_mount()` in your root URLconf and synthesised into a runtime `rx.Config` in memory.

---

## The problem it solves

Reflex sends UI updates over **WebSockets** (`/_event`), not through Django's normal HTTP middleware stack. Without a bridge, `request.user`, sessions, messages, CSRF tokens, and locale are unavailable inside `@rx.event` handlers — and Reflex's React bundle is normally served by a separate frontend dev server on a different port.

`reflex-django` fixes both:

1. **One ASGI app, one port.** Django is the outer server. Reflex's Socket.IO event channel, upload endpoint, and health endpoints are mounted as ASGI sub-applications. The compiled Reflex SPA is served from disk by Django.
2. **Full middleware chain on every event.** Each WebSocket event is wrapped in a synthetic `HttpRequest`, walked through your `settings.MIDDLEWARE`, and the resulting `request`, `response`, `user`, `session`, `messages`, and `csrf_token` are bound to the active `@rx.event` handler.
3. **Django-first layout.** Pages in `{app}/views.py`. Config in `reflex_mount()`. No `{app}/{app}.py`, no `rxconfig.py`, no `frontend/`/`backend/` split.

---

## How the pieces fit together

```text
┌──────────────────────────────────────────────────────────────────┐
│                Single ASGI process — port 8000                   │
│                                                                  │
│   Browser HTTP                                                   │
│        │                                                         │
│        ▼                                                         │
│   DjangoOuterDispatcher                                          │
│        │                                                         │
│        ├── /_event /_upload /_health …  →  Reflex inner ASGI     │
│        │                                                         │
│        └── everything else  →  Django ASGI                       │
│                                     │                            │
│                                     ├── /admin /api /static      │
│                                     └── /  …  → ReflexMountView  │
│                                                  (SPA from disk) │
│                                                                  │
│   Browser WebSocket  →  /_event  →  DjangoEventBridge            │
│                                       (full middleware chain,    │
│                                        binds request/user/…)     │
└──────────────────────────────────────────────────────────────────┘
```

| Piece | Role |
|:---|:---|
| **`reflex_mount()`** | Registers Reflex `rx.Config` (ports, app name, plugins) and appends the SPA catch-all URL pattern. |
| **`reflex_django.asgi_entry:application`** | The outer ASGI callable. Composes Django + Reflex behind `DjangoOuterDispatcher`. |
| **`django_led_app`** | Built-in module Reflex imports for `app`. Replaces `{app_name}/{app_name}.py`. |
| **`{app}/views.py`** | Reflex pages (`@template` / `@page`) — auto-discovered from `INSTALLED_APPS`. |
| **`ReflexDjangoPlugin`** | Wires the dispatcher, the event bridge, and the prefix lists. Always enabled. |
| **`DjangoEventBridge`** | Runs `settings.MIDDLEWARE` on each Reflex event and binds the result to `AppState`. |
| **`ReflexMountView`** | Catch-all Django view that serves the compiled SPA bundle from `STATIC_ROOT/_reflex/`. |
| **`manage.py run_reflex`** | Dev loop: auto-export + serve + watch. |
| **`manage.py export_reflex`** | Build the SPA bundle for CI / deployment. |

---

## What this is (and is not)

### It is

- A **Django project** with a Reflex SPA mounted as a catch-all under Django's URL resolver.
- A **single ASGI process** that handles HTTP, WebSockets, and ASGI lifespan together.
- **100% Python** for UI and backend — no separate React/Vue repo, no parallel dev server in your daily loop.
- **Shared sessions and middleware.** Logging in via `/admin/` and reading `request.user` from a Reflex event use the same cookies, the same session store, and the same middleware stack.

### It is not

- A way to register Reflex routes inside Django `urls.py` per page. SPA routing happens client-side; the SPA catch-all owns `/`, `/about`, `/notes`, etc.
- A replacement for Django templates on existing server-rendered views. Those keep working under your API / admin prefixes.
- A wrapper around Django Channels. Reflex's lifespan and Socket.IO endpoint are first-class ASGI sub-apps; Channels is not used.

---

## Configuration in one place: `reflex_mount()`

All Reflex options that would normally scatter across `rxconfig.py` and Django settings are passed here:

```python
# project/urls.py
from reflex_django.urls import reflex_mount

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("myapp.api_urls")),
]

urlpatterns += [
    reflex_mount(
        app_name="myapp",
        django_prefix=("/admin", "/api"),
        rx_config={"backend_port": 8000},
    ),
]
```

Importing `urls.py` at startup registers this config in memory. `manage.py run_reflex`, `manage.py export_reflex`, and your production ASGI server all read the same values.

---

## The `django_led_app` module

Classic Reflex expects `demo/demo.py` with `app = rx.App()`. In reflex-django you use a Django app label (e.g. `demo`) for pages in `demo/views.py`, but Reflex loads the app instance from:

```text
reflex_django.django_led_app:app
```

That module lazily:

1. Imports page modules from `INSTALLED_APPS` (`demo/views.py`, `billing/views.py`, …)
2. Creates `rx.App()` via the built-in factory.
3. Registers routes from `@template` / `@page` decorators.

You do not create `demo/demo.py`. See [Django-led URL routing](django_urls.md).

---

## The dev loop in one command

```bash
python manage.py run_reflex
```

What happens:

1. The reflex-django integration bootstraps in the current Python process.
2. The Reflex SPA is auto-built (`export_reflex --frontend-only --no-zip --stage-to-static-root`) and staged into `STATIC_ROOT/_reflex/`.
3. `uvicorn` boots as a subprocess pointing at `reflex_django.asgi_entry:application` on port `8000`.
4. A parent-side `watchfiles` loop watches the project for `.py` changes. Each change cleanly stops uvicorn, re-exports the SPA, and respawns uvicorn.

Open `http://localhost:8000/`. That's it — one port, one origin, one Python process.

---

## When to use reflex-django

**Good fit:**

- Brownfield Django apps adding a modern SPA.
- Teams that want Django's ORM/admin with Reflex's reactive UI in pure Python.
- Single-origin deploys (one container, one systemd unit, one ASGI server).
- Server-side logic — auth, permissions, multi-tenancy, audit logging, rate limiting — that should apply uniformly to HTTP and Reflex events.

**Less ideal:**

- Static sites with only Django templates and no interactive UI.
- Architectures that require Reflex and Django on completely separate hosts with token-only APIs.

---

## Next steps

| Goal | Guide |
|:---|:---|
| New project in 15 minutes | [Quickstart](quickstart.md) |
| Add Reflex to existing Django | [Existing Django project](existing_django_project.md) |
| `reflex_mount` and URL ownership | [Django-led URL routing](django_urls.md) |
| All settings | [Configuration](configuration.md) |
| Pages in `views.py` | [Pages in views.py](pages_in_views.md) |
| Runtime details | [Architecture](architecture.md) |
| Ship it | [Deployment](deployment.md) |

---

**Navigation:** [← Docs Index](index.md) | [Next: Installation →](installation.md)
