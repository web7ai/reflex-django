---
level: beginner
tags: [architecture, onboarding]
---

# Why reflex-django exists

**What you'll learn:** The gap between Django's HTTP world and Reflex's WebSocket world, and the three concrete things reflex-django does to close it.

**When you need this:**

- You want the one-page story before installing anything or reading API reference.
- Someone asked "why not just run Reflex and Django side by side?" and you need a clear answer.

---

Let's start with the honest version. Django and Reflex are both wonderful frameworks. They just do not naturally talk to each other. reflex-django is the small layer that makes them talk.

This page is the *one place* where we explain the gap and how we close it. Everything else in the docs builds on this.

---

## Django, briefly

Django is a battle-tested Python web framework. The mental model is:

1. A browser sends an **HTTP request** to your server.
2. Django runs that request through **middleware** (security, sessions, authentication, messages, CSRF, your custom logic).
3. Middleware fills the request with useful things: `request.user`, `request.session`, `request.COOKIES`, a CSRF token, the user's language.
4. Django picks a **view** based on `urls.py`, calls it, and returns a response.

The pieces you love (the **ORM**, the **admin**, **migrations**, **`request.user`**) all sit inside that HTTP request/response cycle.

> One sentence: Django turns an HTTP request into an HTTP response, with `request.user` and friends handed to you for free.

For a longer refresher, see [How Django works in 5 minutes](../overview/concepts.md).

---

## Reflex, briefly

Reflex is a way to build web UIs in pure Python. You write a Python class (a **state**), declare methods as **event handlers**, and Reflex compiles a React app from your code.

The mental model is:

1. The browser loads a **single-page app** (SPA). JavaScript that Reflex generated from your Python.
2. The SPA opens a **WebSocket** to the server.
3. When the user clicks a button, the SPA sends an event: *"please run `add_task()` on the server"*.
4. Your `@rx.event` handler runs, changes state, and Reflex ships the diff back over the WebSocket.
5. The SPA updates the screen.

> One sentence: Reflex turns a button click into a Python function call over a WebSocket, then reflects the new state into the UI.

For a longer refresher, see [How Reflex works in 5 minutes](../overview/concepts.md).

---

## So where's the gap?

Look closely at those two sentences. Django speaks **HTTP**. Reflex speaks **WebSocket**. That difference is the entire problem.

When Reflex fires an event, it does not go through Django's HTTP pipeline by default. That means:

- There is no `HttpRequest`. No `request.user`, no `request.session`, no `request.COOKIES`.
- **No middleware runs.** Not session, not auth, not your custom multi-tenant or rate-limit middleware.
- Reflex does not know that the user logged into `/admin/` two seconds ago.
- Reflex wants its own dev server on its own port. reflex-django embraces that: `run_reflex` starts Vite on `:3000` and the backend on `:8000`, with `env.json` keeping cookies aligned.

So even though both frameworks are Python and could live in the same process, in practice they sit on opposite sides of a glass wall. You end up writing a token bridge, configuring CORS, running two terminals, and re-implementing auth twice.

That is the gap. It is not glamorous. It is just plumbing. (The kind of plumbing you are glad someone else already installed.)

---

## What reflex-django actually does

reflex-django is the plumbing. It does three concrete things:

### 1. One Reflex backend in dev; Django ASGI in production

**Default dev:** `run_reflex` runs Vite on `:3000` and the Reflex backend on `:8000`. Django admin and API are mounted **in-process** inside that backend via `make_dispatcher`. You browse `:3000`; Vite proxies all backend paths.

**Production:** Django ASGI serves admin, API, static, and the compiled SPA shell. Your edge proxy forwards `/_event` to a Reflex backend (or you serve static export only).

```text
  Dev  -  browse :3000
  Browser  →  Vite  →  Reflex backend (:8000)
                           ├── /admin, /api  → Django ASGI (in-process)
                           ├── /_event       → Reflex WebSocket
                           └── /, /about     → Reflex SPA

  Production
  Browser  →  edge proxy  →  Django (:8000) for admin, API, SPA shell
                         →  Reflex backend for /_event
```

Set `RXDJANGO_PROXY_SERVER` only when Django runs on a separate `runserver`. See [Routing](../internals/routing.md).

One cookie jar in the browser during dev. No CORS for the SPA.

### 2. Full middleware chain on every Reflex event

When a button fires a Reflex event, reflex-django builds a **synthetic `HttpRequest`** from the WebSocket payload and runs your **full `settings.MIDDLEWARE` chain** on it.

Then it binds the result onto your handler:

```python
import reflex as rx
from reflex_django.states import AppState

class CartState(AppState):
    @rx.event
    async def add_item(self, product_id: int):
        user     = self.request.user          # real Django user
        session  = self.request.session       # real session
        messages = self.messages              # django.contrib.messages
        csrf     = self.csrf_token            # CSRF token
        lang     = self.request.LANGUAGE_CODE # locale
```

If middleware returns a redirect (for example, login required), reflex-django turns that into `rx.redirect("/login")` automatically.

### 3. Django-shaped project layout

Configuration lives in **`settings.py`** (`REFLEX_DJANGO_RX_CONFIG`), not a separate config file at the project root. Pages live in your Django app's **`views.py`**:

```python
--8<-- "snippets/minimal_settings.py"
```

```python
--8<-- "snippets/minimal_urls.py"
```

You configure Reflex like a Django app, because in your project, it is one. See [The three knobs](../overview/concepts.md).

---

## Put visually

```text
┌──────────────────────────────────────────────────────────────────┐
│           Reflex backend (dev) or split at edge (prod)           │
│                                                                  │
│   HTTP (via Vite proxy in dev)                                   │
│        │                                                         │
│        ▼                                                         │
│   make_dispatcher → /admin, /api  →  Django urlpatterns          │
│                  → /, /about      →  Reflex SPA                  │
│                                                                  │
│   WebSocket /_event                                              │
│        │                                                         │
│        ▼                                                         │
│   DjangoEventBridge → synthetic HttpRequest + MIDDLEWARE         │
│                    → your @rx.event handler                      │
└──────────────────────────────────────────────────────────────────┘
```

That is the entire idea. The rest of the docs are details.

---

## What you keep, what you skip

| You keep | You do not have to think about |
|:---|:---|
| Django ORM, models, migrations | A separate frontend repo |
| Django admin | CORS configuration |
| `settings.MIDDLEWARE` (custom middleware too) | Token-based auth bridges |
| `request.user`, sessions, messages, CSRF | Re-implementing login for the SPA |
| `python manage.py ...` commands | Maintaining a standalone Reflex config file |
| Your existing `/api/` and templates | Two origins and two cookie jars in production |

---

## Good fit vs maybe not

**Good fit:**

- You have (or want) a Django backend and a reactive UI in Python.
- You want **one container, one process, one origin** in production.
- You want server-side checks (auth, permissions, multi-tenancy) on both HTTP and Reflex events.

**Maybe not:**

- You only need server-rendered Django templates.
- You explicitly want Reflex and Django on different hosts behind a token-only API.
- You need Django Channels for arbitrary WebSocket protocols. Reflex owns `/_event`.

---

## What just happened?

You saw why HTTP and WebSocket do not mix by default, and how reflex-django unifies them with one ASGI entry, middleware on every event, and Django-shaped configuration.

**Next up:** [How Django works in 5 minutes →](../overview/concepts.md)
