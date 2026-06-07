---
level: beginner
tags: [dev, debug]
---

# Troubleshooting

**What you will learn:** Symptom-first fixes for the issues that show up most often in local dev and first deploys.

**When you need this:**

- A proxy returns 502, admin 404s, CSRF blocks a form, or `/_event` will not connect.
- Ports or prefix settings do not match what the browser expects.

Start with the symptom below. Each section points to the long guide when you need background.

---

## Vite proxy returns 502 Bad Gateway

**Symptoms:** Browser on `:3000` shows 502 for `/admin`, `/api`, or `/_event`. Vite terminal may log `ECONNREFUSED`.

**Likely causes:**

1. Backend on `:8000` is not running yet (Vite started before uvicorn).
2. Wrong upstream in `reflex_outer` (Django HTTP worker not on `:8001`).
3. Stale or missing proxy block in `.web/vite.config.js` after a compile.

**Fix:**

1. Stop all `run_reflex` / Vite processes. Start fresh:

```bash
python manage.py run_reflex
```

2. Wait for both lines in the log: Vite ready on `:3000` and uvicorn on `:8000`.
3. In `reflex_outer`, confirm the Django HTTP worker is up on `REFLEX_DJANGO_HTTP_PORT` (default `8001`). See [Routing](routing.md#choosing-a-mode-django_outer-vs-reflex_outer).
4. If proxies disappeared after compile, restart `run_reflex` so `ensure_vite_django_dev_proxy_from_config()` repatches Vite.

**Related:** [Local development](local_development.md), [Routing](routing.md)

---

## CSRF verification failed (admin or forms from `:3000`)

**Symptoms:** Django admin login or POST from the SPA returns **403 CSRF**. Often only when browsing `:3000`, not `:8000`.

**Likely causes:**

1. `CSRF_TRUSTED_ORIGINS` missing `http://localhost:3000`.
2. Dev middleware not prepended (forwarded host / body stubs).
3. Session cookie set on one port but form POST goes through another without trusted origins.

**Fix:**

```python
from reflex_django.django_dev_middleware import DEFAULT_DEV_MIDDLEWARE

USE_X_FORWARDED_HOST = True
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

MIDDLEWARE = [
    *DEFAULT_DEV_MIDDLEWARE,
    # ... your middleware ...
    "reflex_django.streaming_middleware.AsyncStreamingMiddleware",
]
```

Restart `run_reflex` and hard-refresh the browser.

**Related:** [Local development (CSRF)](local_development.md#django-dev-middleware-and-csrf), [Authentication](authentication.md)

---

## Django admin 404 on `:3000` or `:8000`

**Symptoms:** `/admin/` returns 404, or the SPA catch-all serves HTML instead of Django admin.

**Likely causes:**

1. `path("admin/", admin.site.urls)` missing from `urlpatterns`.
2. Custom API route registered **after** the SPA catch-all (catch-all wins).
3. Browsing `:8000` in default two-port mode expecting the Vite shell (admin still works on `:8000`, but `/` may not be the SPA).
4. `REFLEX_DJANGO_DJANGO_PREFIX` omits `/admin`, so Vite proxies admin to the wrong upstream.

**Fix:**

1. Put explicit Django routes **first** in `urlpatterns`:

```python
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("shop.api_urls")),
]
# catch-all appended by REFLEX_DJANGO_AUTO_MOUNT
```

2. Open admin directly at `http://localhost:8000/admin/` to isolate routing from Vite.
3. If auto-detection misses a prefix, set env or settings:

```bash
export REFLEX_DJANGO_DJANGO_PREFIX="/admin,/api,/static"
python manage.py run_reflex
```

**Related:** [Pages in views.py (URL split)](pages_in_views.md#the-url-split-django-routes-vs-reflex-routes), [Settings reference](settings_reference.md#reflex_django_django_prefix)

---

## `/_event` fails or WebSocket disconnects

**Symptoms:** Browser console shows Socket.IO errors, "WebSocket connection failed", or events never reach handlers.

**Likely causes:**

1. Proxy missing `ws: true` for `/_event` (fixed by reflex-django's Vite plugin in two-port dev).
2. Reverse proxy in production strips `Upgrade` headers or times out idle sockets.
3. Reserved prefix collision: a Django route registered under `/_event`.
4. Stale `.web/` bundle (`dispatch is not a function`).

**Fix:**

1. Default dev: browse `:3000` and confirm `.web/vite.config.js` lists `/_event` with WebSocket proxy to `:8000` (`django_outer`) or `:8000` Reflex outer (`reflex_outer`).
2. Production nginx (example):

```nginx
location /_event {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 300s;
}
```

3. Clean rebuild: stop server, delete `.web/`, run `python manage.py run_reflex` again.
4. Read the event path in [WebSocket event pipeline](websocket_event_pipeline.md).

**Related:** [Deployment](deployment.md), [Routing (reserved prefixes)](routing.md#reserved-reflex-prefixes-both-modes)

---

## Wrong routes after changing `REFLEX_DJANGO_DJANGO_PREFIX`

**Symptoms:** API hits the SPA shell, or Reflex pages load Django 404 JSON. Typo `DANAGO_PREFIX` in env has no effect.

**Likely causes:**

1. Env var misspelled. The real name is `REFLEX_DJANGO_DJANGO_PREFIX`.
2. Prefix list out of sync with `urlpatterns` (auto-detection skipped a `re_path`).
3. `reflex_outer`: Django prefixes must include every admin/API root the browser can hit.

**Fix:**

1. Set the correct env var (comma-separated, leading slashes):

```bash
export REFLEX_DJANGO_DJANGO_PREFIX="/admin,/api,/internal"
```

2. Or pass explicit prefixes to `reflex_mount(django_prefix=(...))`.
3. Restart `run_reflex` so compile re-exports prefixes into `env.json` and Vite.

**Related:** [Routing](routing.md#django-prefix-detection), [Settings reference](settings_reference.md#reflex_django_django_prefix)

---

## Port confusion (`:3000` vs `:8000` vs `:8001`)

**Symptoms:** Blank page, wrong app, or "port already in use".

| Symptom | Fix |
|:---|:---|
| Blank UI on `:8000` in default dev | Open `:3000` for the SPA. `:8000` is backend-only unless you use `--env dev`. |
| Vite silently on `:3001` | Stop the process holding `:3000`. reflex-django sets `strictPort: true`. |
| API works on `:8000` but not `:3000` | Confirm two-port mode: `REFLEX_DJANGO_SEPARATE_DEV_PORTS=1` (default for `run_reflex`). |
| `reflex_outer` admin fails from `:3000` | Django HTTP must run on `REFLEX_DJANGO_HTTP_PORT` (default `:8001`). Do not browse `:8001` directly. |

**Fix:** Use `python manage.py run_reflex` (not bare `runserver` or lone uvicorn) for SPA dev. Override ports with `REFLEX_DJANGO_RX_CONFIG` or `REFLEX_DJANGO_FRONTEND_PORT` / `REFLEX_DJANGO_BACKEND_PORT`.

**Related:** [Local development](local_development.md), [CLI](cli.md)

---

## Other quick fixes

| Symptom | Fix |
|:---|:---|
| `Reflex SPA bundle not found` | Run `run_reflex` or `export_reflex`. In two-port dev, use `:3000`. |
| `AppRegistryNotReady` | Import models inside handlers, not at module top in `views.py`. |
| `SynchronousOnlyOperation` | Use `await Model.objects.aget(...)` in async handlers. |
| White page / `dispatch is not a function` | Delete `.web/`, restart `run_reflex`. |
| Anonymous user in handlers | Subclass `AppState`, ensure session middleware runs. See [State management](state_management.md). |

---

## What just happened?

You matched common dev failures to concrete checks: proxies, CSRF origins, URL order, WebSocket headers, `REFLEX_DJANGO_DJANGO_PREFIX`, and port layout.

**Next up:** [FAQ](faq.md) for short answers, or [Routing](routing.md) to understand how paths are chosen.
