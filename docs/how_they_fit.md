# How the two fit together

You've seen the [why](why_reflex_django.md), and you have a working picture of [Django](how_django_works.md) and [Reflex](how_reflex_works.md). Now let's stitch them together. This page names the actual pieces — what they're called, what they do, and how a request becomes a UI update.

You'll meet a handful of names: `reflex_mount()`, `AppState`, `DjangoEventBridge`, `DjangoOuterDispatcher`, `django_led_app`. Don't worry about memorizing them. We introduce each one once, in context.

---

## The runtime picture

Everything lives in **one Python process**, listening on **one port** (default `8000`). There are two flavors of traffic:

```text
                        Port 8000
                            │
                            ▼
                ┌───────────────────────┐
   HTTP  ─────► │   Django (outer)      │ ─► /admin, /api, /static, /
                └───────────────────────┘
                            │
                            ▼ catch-all for unknown paths
                ┌───────────────────────┐
                │   Reflex SPA shell    │ (served from disk)
                └───────────────────────┘

                        Port 8000
                            │
                            ▼
                ┌───────────────────────┐
   WebSocket ─► │   Django dispatcher   │ ─► /_event ─► Reflex
                └───────────────────────┘                   │
                                                            ▼
                                              build synthetic HttpRequest
                                              run settings.MIDDLEWARE
                                              bind self.request, self.user, ...
                                              call your @rx.event handler
```

Django is the **outer** app — every byte that hits port 8000 lands on Django first. A small piece of code called the **outer dispatcher** then decides: does this look like a Reflex-internal path (`/_event`, `/_upload`, `/_health`)? If yes, send it inward to Reflex. Otherwise, let Django handle it normally.

That's the whole layout.

---

## The four pieces you'll touch

Most of the time, you only interact with four things:

| Piece | What it is | Where you see it |
|:---|:---|:---|
| **`reflex_mount()`** | One function call that wires Reflex into Django | `config/urls.py` |
| **`AppState`** | Base class for Reflex states that need Django context | `{app}/views.py` |
| **`@page`** | Decorator that registers a Reflex page with a URL | `{app}/views.py` |
| **`asgi_entry.application`** | The ASGI callable that boots everything | `config/asgi.py` |

Here they are in their natural habitat:

```python
# config/urls.py
from reflex_django.urls import reflex_mount

urlpatterns = [path("admin/", admin.site.urls)]
urlpatterns += [
    reflex_mount(app_name="shop", django_prefix=("/admin",)),
]
```

```python
# config/asgi.py
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
from reflex_django.asgi_entry import application
```

```python
# shop/views.py
import reflex as rx
from reflex_django.pages.decorators import page
from reflex_django.states import AppState

class HomeState(AppState):
    @rx.event
    async def on_load(self):
        self.greeting = f"Hi, {self.request.user.get_username() or 'guest'}"

@page(route="/", title="Home")
def home() -> rx.Component:
    return rx.heading(HomeState.greeting)
```

That's a complete (if minimal) `reflex-django` app.

---

## The five-second life of an HTTP request

When the browser asks for `GET /admin/login/`, here's the sequence:

1. The request hits Django on port 8000.
2. The outer dispatcher looks at the path. It's not `/_event` or another Reflex-internal path. Forward to normal Django.
3. Django runs `settings.MIDDLEWARE` over the request.
4. Django's URL resolver finds the admin login view and returns the rendered HTML.
5. The browser receives the response.

You wrote nothing. This is just Django doing its thing.

Now `GET /`:

1. Request hits Django, not a Reflex-internal path.
2. Django runs middleware, then the URL resolver.
3. The URL resolver hits the catch-all that `reflex_mount()` registered, which points at `ReflexMountView`.
4. `ReflexMountView` serves the compiled SPA's `index.html` from `STATIC_ROOT/_reflex/`.
5. The browser loads the SPA. The SPA opens a WebSocket to `/_event`.

Same Django. Same middleware. Same cookies. The SPA is just another response Django served.

---

## The five-second life of a Reflex event

This is the part that makes `reflex-django` interesting. Suppose the user clicks "Add to cart":

1. The SPA sends an event over the WebSocket: `{handler: "CartState.add_item", args: [42]}`.
2. The WebSocket frame goes to `/_event`. The outer dispatcher sees a reserved Reflex path and forwards to Reflex's inner ASGI.
3. Before Reflex calls your handler, the **`DjangoEventBridge`** intercepts the event.
4. The bridge builds a **synthetic `HttpRequest`** using the cookies, headers, path, and query string from the event's `router_data`.
5. The bridge runs your **full `settings.MIDDLEWARE` chain** on that request. `SessionMiddleware` loads the session. `AuthenticationMiddleware` resolves the user. Your custom middleware runs too.
6. The bridge binds the result onto your `AppState` instance: `self.request`, `self.user`, `self.session`, `self.messages`, `self.csrf_token`, `self.response`.
7. Your `@rx.event async def add_item(self, product_id)` runs. `self.user` is the real Django user.
8. State changes are sent back over the WebSocket. The UI updates.

Most of this is invisible. You write step 7 — the handler. The bridge does the rest.

---

## "Wait, where did `rxconfig.py` go?"

In a normal Reflex project, there's a `rxconfig.py` file at the root that configures ports, app name, plugins, and so on. In `reflex-django`, you don't write that file. Instead, the runtime config is built in memory from two sources:

1. **`reflex_mount(app_name=..., rx_config={...})`** in your `urls.py` — Reflex options (ports, etc.) and the SPA catch-all URL pattern.
2. **`REFLEX_DJANGO_*` settings** in your `settings.py` — integration tunables.

Importing `urls.py` is enough to register the config. `manage.py run_reflex`, your production ASGI server, and CI all read the same in-memory config.

If you have an existing `rxconfig.py` and want to keep it, set `REFLEX_DJANGO_USE_RXCONFIG_FILE = True` and `reflex-django` will merge it in.

---

## "And `shop/shop.py`?"

In a normal Reflex project, you'd have `shop/shop.py` containing `app = rx.App()`. In `reflex-django`, that file doesn't exist either. Pages live in `shop/views.py`, and Reflex loads the app from a built-in module called `reflex_django.django_led_app`.

That module quietly does three things at startup:

1. Imports `{app}/views.py` for every app in `INSTALLED_APPS`.
2. Builds `rx.App()`.
3. Registers any pages it found from `@page` decorators.

You don't import it. You don't see it. It just makes "pages in `views.py`" work.

---

## The mental model, one more time

If you remember nothing else, remember this paragraph:

> Django is the outer app on one port. Reflex is mounted inside Django for its internal WebSocket and upload endpoints. When a Reflex event arrives, a small bridge builds a real `HttpRequest`, runs all your Django middleware on it, and hands you a fully-populated `AppState` — same `request.user`, same session, same everything — before your handler runs.

Everything else is detail.

---

## Where to go next

You now have the full conceptual picture. From here, most people pick one of these:

- **[Install](installation.md)** and **[Your first app](quickstart.md)** — if you want to write code now.
- **[Adding reflex-django to an existing Django project](existing_django_project.md)** — if you already have a Django app.
- **[Configuration](configuration.md)** — if you want to know every knob.
- **[Architecture](architecture.md)** — if you want the full plumbing details (dispatcher, lifespan, bootstrap order, state pickling).

---

**Next:** [Install →](installation.md)
