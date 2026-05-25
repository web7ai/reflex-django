# Why reflex-django exists

Let's start with the honest version of the story. Django and Reflex are both wonderful frameworks. They just don't naturally talk to each other. `reflex-django` is the small layer that makes them talk.

This page is the *one place* where we explain the gap and how we close it. Everything else in the docs builds on this. If you read nothing else, read this.

---

## Django, briefly

Django is a battle-tested Python web framework. The mental model is:

1. A browser sends an **HTTP request** to your server.
2. Django runs that request through a list of **middleware** — security, sessions, authentication, messages, CSRF, your custom logic.
3. Middleware fills the request with useful things: `request.user`, `request.session`, `request.COOKIES`, a CSRF token, the user's language.
4. Django picks a **view** (a Python function) based on `urls.py`, calls it, and returns an HTML response.

The pieces you love — the **ORM**, the **admin**, **migrations**, **`request.user`** — all sit comfortably inside that HTTP request/response cycle.

> One sentence: Django turns an HTTP request into an HTTP response, with `request.user` and friends handed to you for free.

If you'd like a slightly longer refresher, see [How Django works in 5 minutes](how_django_works.md).

---

## Reflex, briefly

Reflex is a way to build web UIs in pure Python. You write a Python class (a **state**), declare some methods as **event handlers**, and Reflex compiles a React app out of your code.

The mental model is:

1. The browser loads a small **single-page app** (SPA) — JavaScript that Reflex generated from your Python.
2. The SPA opens a **WebSocket** to the server. (A WebSocket is one connection that stays open, instead of a new HTTP request for every click.)
3. When the user clicks a button, the SPA sends an event over that WebSocket: *"please run `add_task()` on the server"*.
4. Your `@rx.event` handler runs on the server, changes some state, and Reflex ships the diff back over the same WebSocket.
5. The SPA updates the screen.

The pieces you love — **pure Python**, **reactive vars**, **no JavaScript** — all sit inside that WebSocket event cycle.

> One sentence: Reflex turns a button click into a Python function call over a WebSocket, then reflects the new state into the UI.

If you'd like a slightly longer refresher, see [How Reflex works in 5 minutes](how_reflex_works.md).

---

## So where's the gap?

Look closely at those two sentences. Django speaks **HTTP**. Reflex speaks **WebSocket**. That difference is the entire problem.

When Reflex fires an event, it doesn't go through Django's HTTP pipeline. By default, that means:

- There's no `HttpRequest`. So no `request.user`, no `request.session`, no `request.COOKIES`.
- **No middleware runs.** None of it. Not the session middleware, not the auth middleware, not your custom multi-tenant or rate-limit middleware.
- Reflex doesn't know that the user logged into `/admin/` two seconds ago, because it never saw the session cookie.
- And by default, Reflex wants its own dev server on its own port — which means the SPA at `localhost:3000` can't easily share cookies with Django at `localhost:8000`.

So even though both frameworks are written in Python and could happily live in the same process, in practice they sit on opposite sides of a glass wall. You end up writing a token bridge, configuring CORS, running two terminals, and re-implementing auth twice.

That's the gap. It's not glamorous. It's just *plumbing*.

---

## What `reflex-django` actually does

`reflex-django` is the plumbing. It does three concrete things:

### 1. One process, one port

Django becomes the outer ASGI app. Reflex's internal endpoints — `/_event` (the WebSocket), `/_upload` (file uploads), `/_health` (health probes) — are mounted *inside* Django. Your compiled Reflex SPA is served straight from disk by Django.

```text
  Browser  →  port 8000  →  Django  →  /admin/   → Django admin
                                    →  /api/     → your DRF views
                                    →  /         → Reflex SPA shell
                                    →  /_event   → Reflex WebSocket
```

One port. One origin. One set of cookies. No CORS.

### 2. Full middleware chain on every Reflex event

This is the important one. When a button fires a Reflex event, `reflex-django` quietly builds a **synthetic `HttpRequest`** from the WebSocket payload (cookies, headers, path, query string, the lot) and runs your **full `settings.MIDDLEWARE` chain** on it.

Then it binds the result onto your handler:

```python
class CartState(AppState):
    @rx.event
    async def add_item(self, product_id: int):
        # All of these just work, exactly like in a Django view:
        user      = self.request.user          # real Django user
        session   = self.request.session       # real session
        messages  = self.messages              # django.contrib.messages
        csrf      = self.csrf_token            # CSRF token
        lang      = self.request.LANGUAGE_CODE # locale
```

If a middleware in the chain decides to redirect — for example, `LoginRequiredMiddleware` returning a 302 to `/login` — `reflex-django` turns that into a Reflex `rx.redirect("/login")` automatically. Your custom middleware applies to Reflex events too, for free.

### 3. Django-shaped project layout

Configuration lives in **`urls.py`**, not in a separate `rxconfig.py`. Pages live in your Django app's **`views.py`**, not in some new `{app}/{app}.py` file. One call sets it all up:

```python
# config/urls.py
from reflex_django.urls import reflex_mount

urlpatterns = [path("admin/", admin.site.urls)]
urlpatterns += [
    reflex_mount(app_name="shop", django_prefix=("/admin",)),
]
```

You configure Reflex like a Django app, because in your project, it kind of is one.

---

## Put visually

```text
┌──────────────────────────────────────────────────────────────────┐
│                  One Python process — port 8000                  │
│                                                                  │
│   HTTP request                                                   │
│        │                                                         │
│        ▼                                                         │
│   Django (outer)                                                 │
│        ├── /admin, /api, /static  →  your Django views           │
│        └── /, /about, ...         →  serve the Reflex SPA shell  │
│                                                                  │
│   WebSocket event (button click)                                 │
│        │                                                         │
│        ▼                                                         │
│   /_event  →  build synthetic HttpRequest                        │
│            →  run settings.MIDDLEWARE (the whole chain)          │
│            →  bind self.request, self.user, self.session, ...   │
│            →  run your @rx.event handler                         │
└──────────────────────────────────────────────────────────────────┘
```

That's the entire idea. The rest of the docs are details.

---

## What you keep, what you don't have to think about

| You keep | You don't have to think about |
|:---|:---|
| Django ORM, models, migrations | A separate frontend dev server |
| Django admin | CORS configuration |
| `settings.MIDDLEWARE` (custom middleware too) | Token-based auth bridges |
| `request.user`, sessions, messages, CSRF | Re-implementing login for the SPA |
| `python manage.py ...` commands | `rxconfig.py` (it's optional now) |
| Your existing `/api/` and templates | Two ports, two origins, two cookie jars |

---

## When `reflex-django` is a good fit

- You have (or want) a Django backend, and you want a reactive UI in Python.
- You want **one container, one process, one origin** in production.
- You want server-side checks — auth, permissions, multi-tenancy, audit logs — to apply uniformly to both HTTP requests and Reflex events.
- You're tired of running two dev servers and copying tokens around.

## When it might not be the right fit

- You only need server-rendered Django templates. There's nothing to reactify.
- You explicitly want Reflex and Django on different hosts behind a token-only API. That's fine — just don't add this library.
- You need Django Channels for arbitrary WebSocket protocols. `reflex-django` doesn't use Channels; Reflex owns the WebSocket on `/_event`.

---

## Where to go next

If this clicked, you can jump straight into building:

- **[Install](installation.md)** — `uv add django reflex reflex-django`, then register one app.
- **[Your first app](quickstart.md)** — a 15-minute todo list that exercises pages, state, auth, and the database.

Or, if you want to firm up your mental model first:

- **[How Django works in 5 minutes](how_django_works.md)** — short refresher for non-Django folks.
- **[How Reflex works in 5 minutes](how_reflex_works.md)** — short refresher for Reflex newcomers.
- **[How the two fit together](how_they_fit.md)** — the bridge in plain English, with the exact pieces named.

---

**Next:** [How Django works in 5 minutes →](how_django_works.md)
