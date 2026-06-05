# Routing & URL dispatching

There are three different "URL resolvers" inside a `reflex-django` process. They run in this order:

1. **The outer ASGI dispatcher** — chooses Django or Reflex for each incoming scope.
2. **Django's `urls.py`** — matches an HTTP request to a Django view or to the SPA catch-all.
3. **The Reflex client router** — handles SPA navigation in the browser (no server round-trip).

This page explains all three, the rules that connect them, and the common pitfalls.

If you read [Architecture overview](architecture.md), this is the same picture from the perspective of "where does this URL go?".

---

## The three layers

```text
Incoming ASGI scope (HTTP or WebSocket)
   │
   ▼
[1] DjangoOuterDispatcher
       ├── reserved Reflex prefix (/_event, /_upload, /_health, /ping, …)? → Reflex inner ASGI
       └── everything else                                                 → Django ASGI handler
                                                                                │
                                                                                ▼
                                                                  [2] settings.MIDDLEWARE
                                                                                │
                                                                                ▼
                                                                          Django urls.py
                                                                                ├── /admin/, /api/, …  → Django view
                                                                                └── catch-all          → ReflexMountView (SPA)
                                                                                                          │
                                                                                                          ▼
                                                                                              [3] Reflex client router
                                                                                                  (in-browser navigation)
```

Layer 1 is at the network boundary. Layer 2 is inside Django. Layer 3 is in the user's browser.

---

## Layer 1 — the outer dispatcher

`reflex_django.django_outer_dispatcher.DjangoOuterDispatcher` is the very first thing every ASGI scope hits. It's a thin function that asks one question: *is this a path Reflex needs to handle directly?*

```text
incoming ASGI scope
  │
  ▼
scope["type"] == "lifespan"  ──►  Reflex lifespan tasks
scope["type"] == "websocket" ──►  reserved Reflex path?
                                       ├── yes → Reflex inner _api
                                       └── no  → close gracefully
scope["type"] == "http"      ──►  reserved Reflex path?
                                       ├── yes → Reflex inner _api
                                       └── no  → Django ASGI handler
```

### Reserved Reflex prefixes

These are *always* claimed by Reflex, even if you added a Django route for them:

| Prefix | What it is |
|:---|:---|
| `/_event` | Socket.IO state channel (the WebSocket carrying every UI event) |
| `/_upload` | Reflex file upload endpoint |
| `/_health`, `/ping` | Liveness probes |
| `/_all_routes` | Internal route enumeration |
| `/auth-codespace` | Reflex dev tooling |

Don't add Django `path()` entries under these prefixes — Reflex's WebSocket will stop working. If you need extra reserved paths (uncommon), set `REFLEX_DJANGO_RESERVED_REFLEX_PREFIXES`.

### Lifespan scopes

ASGI servers send a `"lifespan"` scope at startup and shutdown so apps can run setup/teardown tasks. The dispatcher forwards lifespan to Reflex's inner ASGI (where Reflex's event processor and background tasks live).

### Unknown WebSocket scopes

WebSocket connections to anything other than the reserved paths are closed gracefully — Django itself never sees WebSocket scopes by default. If you want WebSocket access for non-Reflex paths, you'd typically reach for Django Channels, but `reflex-django` doesn't include it; Reflex owns the one WebSocket on `/_event`.

---

## Layer 2 — Django's `urls.py`

For HTTP requests that aren't reserved, Django takes over. Your `urls.py` controls what happens next:

```python
# config/urls.py
from django.contrib import admin
from django.urls import include, path
from reflex_django.urls import reflex_mount


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("shop.api_urls")),
]

urlpatterns += [reflex_mount(app_name="shop")]
```

Two things happen here:

- Django routes go **first**.
- `reflex_mount()` appends a final wildcard pattern that points at `ReflexMountView`.

`django_prefix` is inferred automatically from those routes (first segment of each top-level `path()`). Pass an explicit tuple only when you use `re_path()` or need to override. Reflex ports and `redis_url` belong in `REFLEX_DJANGO_RX_CONFIG` in settings.

### The SPA catch-all

The final pattern `reflex_mount()` adds is roughly:

```python
re_path(r".*", ReflexMountView.as_view())
```

It's intentionally permissive. Anything that didn't match `/admin/` or `/api/` (or your other explicit prefixes) ends up at `ReflexMountView`, which serves the compiled SPA's `index.html`.

The SPA then takes over and does client-side routing.

### What `ReflexMountView` does

1. Looks for the compiled SPA index at `STATIC_ROOT/_reflex/index.html`, falling back to `.web/build/client/index.html`, then `.web/_static/index.html`.
2. If `REFLEX_DJANGO_RENDER_SPA_VIA_TEMPLATE_ENGINE = True` (the default), runs the HTML through Django's template engine first — so `{{ request.user }}`, `{% csrf_token %}`, `{{ messages }}`, and any context-processor key work inside `index.html`.
3. Streams non-HTML assets (JS, CSS, images, source maps) untouched.

If the bundle is missing, the view returns a 404 with a hint pointing at `manage.py export_reflex`.

---

## Layer 3 — the Reflex client router

Once the SPA is loaded, in-page navigation between `/`, `/about`, `/cart`, etc. happens **entirely in the browser**. Reflex generates a React router from your `@page(route=...)` declarations and intercepts link clicks.

The browser doesn't make an HTTP request to the server when the user clicks `<a href="/about">`. It just changes the URL and re-renders.

That has two consequences:

- **Don't add Django `path()` entries for SPA routes.** The client router handles `/about`. Django would never see the request.
- **A hard refresh (Ctrl+R) on `/about` does hit the server** — and the server's URL resolver falls through to `ReflexMountView`, serves the SPA again, and the SPA navigates to `/about` client-side. The user sees the same page either way.

---

## Path ownership cheat sheet

| Path | Who handles it |
|:---|:---|
| `/_event`, `/_upload`, `/_health`, `/ping`, `/_all_routes`, `/auth-codespace` | Reflex (reserved) |
| `/admin/...`, `/api/...`, anything in `django_prefix` | Django views |
| `/static/...` | Django (`ASGIStaticFilesHandler` in dev, Nginx/Caddy in prod) |
| `/static/_reflex/...` | Django (serves the compiled SPA assets from `STATIC_ROOT`) |
| `/` and any other unknown path | `ReflexMountView` → compiled SPA |

Everything happens on one port. Same origin. Same cookies. Same session.

---

## The cardinal rules

1. **Django routes go above `reflex_mount()`** in `urls.py`.
2. **Django prefixes are auto-detected** from those routes (first segment of each top-level `path()`). Override with `django_prefix=(...)` only when needed.
3. **Don't `path()` for SPA pages.** Use `@page(route=...)` in `views.py` instead.
4. **Don't add Django routes under reserved Reflex prefixes.**

If you stick to these, routing just works.

---

## WebSocket scopes

Every WebSocket connection lands on the outer dispatcher:

| Scope path | Behavior |
|:---|:---|
| `/_event/...` | Forwarded to Reflex Socket.IO (the state channel) |
| `/_upload/...` | Forwarded to Reflex's upload endpoint |
| Anything else | Closed politely (no Channels needed) |

Django itself never sees a WebSocket scope, so your `urls.py` doesn't need to know about WebSockets at all.

For the full trace of what happens when a Reflex event arrives on `/_event` — handshake, synthetic `HttpRequest`, middleware chain, handler dispatch — see [The WebSocket event pipeline](websocket_event_pipeline.md).

---

## Built-in auth routes

The built-in authentication SPA pages register in one line:

```python
# shop/views.py
from reflex_django.auth import add_auth_pages

add_auth_pages()    # registers /login, /register, /password_reset, /password_reset_confirm
```

These are SPA routes — they live in the Reflex client router, not in `urls.py`. Customize via `REFLEX_DJANGO_AUTH` in settings. ([Details](authentication.md).)

---

## Common pitfalls

### Prefix drift (404 on a Django URL)

**Symptom:** `GET /api/orders/` returns 404 (or worse, returns the SPA shell).

**Cause:** Your Django route uses a different first segment than you expect — e.g. `path("v1/", include(...))` instead of `path("api/", ...)`. Auto-detection reserves `/v1`, not `/api`.

**Fix:** Rename the Django `path()` or pass `django_prefix=("/api", "/v1", ...)` explicitly so the catch-all and dev proxy stay aligned with your real routes.

### Catch-all shadowing (blank SPA pages)

**Symptom:** SPA pages return blank screens or raw Django 404s.

**Cause:** You added a permissive Django pattern (e.g. `re_path(r"^.*$", some_view)`) **above** `reflex_mount()`. It captures `/`, `/about`, etc. before the SPA catch-all gets a chance.

**Fix:** Keep Django routes under explicit prefixes (`/api/`, `/admin/`). Let the SPA catch-all own the root.

### Missing SPA bundle

**Symptom:** `GET /` returns 404 with a "compiled SPA not found" message.

**Cause:** The SPA was never built or never staged into `STATIC_ROOT/_reflex/`.

**Fix:** Run `python manage.py export_reflex --frontend-only --no-zip --stage-to-static-root`, or use `python manage.py run_reflex` which auto-exports before serving.

### Hijacking a reserved prefix

**Symptom:** Reflex events stop arriving after you added a Django route under `/_event/...`.

**Cause:** Reserved Reflex prefixes are always claimed by Reflex — but Django will still try to resolve them in admin / DRF routers if you add such routes by accident.

**Fix:** Don't add Django routes under reserved prefixes. Customize `REFLEX_DJANGO_RESERVED_REFLEX_PREFIXES` if you need extra space.

### "SPA route renders, then 404s on refresh"

**Symptom:** Visiting `/cart` via a link works. Hitting Ctrl+R returns 404.

**Cause:** Your reverse proxy (Nginx, etc.) isn't forwarding unknown paths to the ASGI process — it tries to serve a static file from disk and fails.

**Fix:** In Nginx, the catch-all `try_files $uri $uri/ @django;` (or `proxy_pass`) ensures every URL falls back to Django, which then serves the SPA.

---

## Helpers for common setups

`reflex_django.urls` exposes a couple of convenience wrappers:

```python
from reflex_django.urls import admin_urlpatterns, reflex_mount

urlpatterns = admin_urlpatterns("/admin")    # path("/admin", admin.site.urls) + a redirect
urlpatterns += [path("api/", include("shop.api_urls"))]
urlpatterns += [reflex_mount(app_name="shop")]   # /admin and /api inferred from lines above
```

`admin_urlpatterns(prefix)` saves you a couple of lines if you're using a non-default admin prefix.

---

## Configuration knob: `REFLEX_DJANGO_URL_ROUTING`

This setting selects the routing mode. You almost never set it.

| Value | Behavior |
|:---|:---|
| `"auto"` (default → `"django_outer"`) | The current architecture described on this page. |
| `"reflex_led"` | Legacy two-port layout. Reflex is outer, Django is mounted as sub-paths. Kept for backwards compat. |

New projects should leave this alone. The default is the right answer.

---

**Next:** [The WebSocket event pipeline →](websocket_event_pipeline.md)
