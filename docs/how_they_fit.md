---
level: beginner
tags: [architecture, onboarding]
---

# How the two fit together

**What you'll learn:** How Django and Reflex share one process, how `django_outer` and `reflex_outer` differ, and what happens from HTTP request to UI update.

**When you need this:**

- You read the primers and want the bridge with real piece names (AppState, dispatcher, event bridge).
- You are about to install or integrate and want the runtime picture before touching `settings.py`.

---

You have seen [why reflex-django exists](why_reflex_django.md) and the [Django](how_django_works.md) and [Reflex](how_reflex_works.md) primers. Now we stitch them together with the actual pieces.

For the short map, read [The three knobs](mental_model.md) first. You will meet `REFLEX_DJANGO_RX_CONFIG`, `AppState`, `DjangoEventBridge`, and `DjangoOuterDispatcher`. No need to memorize them yet.

---

## Routing modes (v1)

reflex-django v1 supports two modes. Both serve SPA, admin, and API on **one public port** (usually `:8000`). Both keep the ORM and event bridge in the same interpreter as Reflex.

| Mode | Outer app | Django HTTP | Reflex events |
|:---|:---|:---|:---|
| **`django_outer`** (default) | Django | Same process | Same process |
| **`reflex_outer`** | Reflex | Separate worker (proxied) | Main process |

**`django_outer`:** Django is the front door. Almost all HTTP (`/`, `/admin`, `/api`) goes through Django. Reflex gets reserved paths (`/_event`, `/_upload`, ...).

**`reflex_outer`:** Reflex is the front door. Django admin and API run in a dedicated HTTP worker that Reflex proxies to. Handlers and ORM still run in the main process.

```python
--8<-- "snippets/reflex_outer_settings.py"
```

See [Routing](routing.md) for production notes. Legacy modes (`reflex_led`, `django_led`) are removed in v1.

---

## The runtime picture (`django_outer`)

```text
                        Port 8000
                            │
                            ▼
                ┌───────────────────────┐
   HTTP  ─────► │   Django (outer)      │ ─► /admin, /api, /static, /
                └───────────────────────┘
                            │
                            ▼ catch-all for SPA routes
                ┌───────────────────────┐
                │   Reflex SPA shell    │ (served from disk)
                └───────────────────────┘

                        Port 8000
                            │
                            ▼
                ┌───────────────────────┐
   WebSocket ─► │   DjangoOuterDispatcher │ ─► /_event ─► Reflex
                └───────────────────────┘                   │
                                                            ▼
                                              build synthetic HttpRequest
                                              run settings.MIDDLEWARE
                                              bind self.request, self.user, ...
                                              call your @rx.event handler
```

Django is the **outer** app. The **outer dispatcher** decides: is this a Reflex-internal path? If yes, forward inward. Otherwise, normal Django.

---

## The four pieces you'll touch

| Piece | What it is | Where you see it |
|:---|:---|:---|
| **`REFLEX_DJANGO_RX_CONFIG`** | Reflex ports, `app_name`, redis | `config/settings.py` |
| **`import shop.views`** | Loads `@page` at import time | `config/urls.py` |
| **`AppState`** | Base state with Django context | `{app}/views.py` |
| **`@page`** | Registers a Reflex page with a URL | `{app}/views.py` |
| **`asgi.entry.application`** | ASGI callable that boots everything | `config/asgi.py` |

The SPA catch-all is appended automatically when `REFLEX_DJANGO_AUTO_MOUNT=True`. Call `reflex_mount()` only for URL prefix overrides.

In their natural habitat:

```python
--8<-- "snippets/minimal_settings.py"
```

```python
--8<-- "snippets/minimal_urls.py"
```

```python
--8<-- "snippets/minimal_asgi.py"
```

```python
--8<-- "snippets/minimal_views.py"
```

That is a complete (minimal) reflex-django app.

!!! tip "The shared app object"
    `from reflex_django import app` is the `rx.App()` singleton in `reflex_django.runtime.reflex_app`. Use `app.add_page()` for native Reflex-style registration.

---

## Life of an HTTP request

`GET /admin/login/`:

1. Request hits Django on port 8000.
2. Outer dispatcher: not a reserved Reflex path. Forward to Django.
3. Django runs `settings.MIDDLEWARE`.
4. URL resolver finds the admin login view. HTML returns.

`GET /`:

1. Request hits Django.
2. Middleware runs. URL resolver hits the SPA catch-all (`ReflexMountView`).
3. `ReflexMountView` serves `index.html` from `STATIC_ROOT/_reflex/`.
4. Browser loads the SPA and opens a WebSocket to `/_event`.

Same Django. Same middleware. Same cookies.

---

## Life of a Reflex event

User clicks "Add to cart":

1. SPA sends `{handler: "CartState.add_item", args: [42]}` over the WebSocket.
2. Frame goes to `/_event`. Dispatcher forwards to Reflex's inner ASGI.
3. **`DjangoEventBridge`** intercepts before your handler runs.
4. Bridge builds a **synthetic `HttpRequest`** from cookies, headers, path, and query string.
5. Bridge runs **full `settings.MIDDLEWARE`**. Session and auth middleware populate the user.
6. Bridge binds `self.request`, `self.user`, `self.session`, `self.messages`, `self.csrf_token` on `AppState`.
7. Your `@rx.event` handler runs. `self.user` is the real Django user.
8. State diffs go back over the WebSocket. UI updates.

You write step 7. The bridge does the rest.

---

## Config and app entry (v1)

In plain Reflex you might keep a root config file and `shop/shop.py` with `app = rx.App()`. In reflex-django v1:

- Put config in **`REFLEX_DJANGO_RX_CONFIG`**, **`REFLEX_DJANGO_PLUGINS`**, and **`REFLEX_DJANGO_PLUGIN`** in `settings.py`.
- Use **`from reflex_django import app`** (backed by `reflex_django.runtime.reflex_app`) instead of a local `shop.py` app module.
- Put pages in `{app}/views.py` with `@page`, or call `app.add_page()` directly.

At compile time, reflex-django imports your page modules, merges decorated pages onto `app`, and applies plugins. See [The three knobs](mental_model.md).

---

## The mental model, one more time

> Django is the outer app in `django_outer` mode. Reflex mounts inside Django for WebSocket and upload endpoints. When a Reflex event arrives, the event bridge builds a real `HttpRequest`, runs all your Django middleware, and hands you a fully-populated `AppState` before your handler runs.

Everything else is detail.

---

## What just happened?

You named the v1 routing modes, traced HTTP and WebSocket traffic through the outer dispatcher, and saw how AppState gets Django context on every event.

**Next up:** [Install →](installation.md)
