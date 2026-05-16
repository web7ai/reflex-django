# Introduction

reflex-django connects **Reflex** (Python-first reactive UI) with **Django** (ORM, admin, sessions, auth, migrations) in a **single process** started by `reflex run`.

---

## What reflex-django is

A **Reflex plugin** (`ReflexDjangoPlugin`) that:

1. Calls `configure_django()` when `rxconfig.py` loads so Django is ready before your app imports models.
2. Appends an **HTTP path-prefix dispatcher** so selected URLs (admin, API, static) go to Django ASGI; everything else stays on Reflex.
3. Optionally installs **`DjangoEventBridge`** Reflex middleware, which builds a synthetic `HttpRequest` per Socket.IO event and exposes `current_user()`, `current_session()`, and related helpers.

---

## What reflex-django is not

| Misconception | Reality |
|---------------|---------|
| One merged URL router | Reflex UI and `/_event/…` are **not** Django views. |
| Django HTTP middleware on every button click | Only the **event bridge** runs for Reflex events (session, user, optional locale)—not your full `MIDDLEWARE` stack. |
| A replacement for Django templates on HTTP routes | Django still serves HTTP under configured prefixes; Reflex serves the SPA and events. |

---

## Why Django developers use it

Reflex user actions arrive over **WebSocket events**, not through Django’s request/response cycle. Without a bridge, `request.user` and the session are unavailable in `@rx.event` handlers. reflex-django makes session auth and ORM patterns usable from Reflex while keeping Django admin, migrations, and existing API routes.

---

## Comparison

| Approach | Pros | Cons |
|----------|------|------|
| Django + separate React/Vue SPA | Mature ecosystem | Two servers, CORS, duplicate auth wiring in dev |
| Django templates only | Simple | Limited interactivity without heavy JS |
| **reflex-django** | One dev command, shared session/ORM, admin on `/admin` | Learn Reflex event model; prefix alignment required |

---

## When to use it

- You want **Django ORM + migrations** with a **Reflex** UI.
- You need **Django admin** alongside a modern frontend.
- You prefer **one process** for local dev and simple deployments.

## When to skip it

- You only need server-rendered Django templates.
- You already run Reflex and Django on separate hosts with a token API and do not want a unified ASGI process.

---

## Ecosystem map

```text
reflex-django
├── Reflex — pages, components, rx.State, Socket.IO events
├── Django — models, admin, sessions, auth, HTTP views
└── Optional — DRF or plain Django views under backend_prefix (see API integration)
```

---

## Next steps

- New project: [Installation](installation.md) → [Quickstart](quickstart.md)  
- Existing Django: [Installation](installation.md) → [Existing Django project](existing_django_project.md)

---

**Navigation:** [← Docs index](index.md) | [Next: Installation →](installation.md)
