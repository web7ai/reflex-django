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

1. Reflex backend on `:8000` is not running yet (Vite started before the backend).
2. `RX_PROXY_SERVER` points at a Django server that is not running.
3. Stale or missing proxy block in `.web/vite.config.js` after a compile.

**Fix:**

1. Stop all `reflex run` / Vite processes. Start fresh:

```bash
reflex run
```

2. Wait for both lines in the log: Vite ready on `:3000` and Reflex backend on `:8000`.
3. If using `RX_PROXY_SERVER`, confirm Django is running at that URL.
4. If proxies disappeared after compile, restart `reflex run` so `ensure_vite_django_dev_proxy_from_config()` repatches Vite.

**Related:** [Local development](../getting-started/local_development.md), [Routing](../internals/routing.md)

---

## CSRF verification failed (admin or forms from `:3000`)

**Symptoms:** Django admin login or POST from the SPA returns **403 CSRF**. Often only when browsing `:3000`, not `:8000`.

**Likely causes:**

1. `CSRF_TRUSTED_ORIGINS` missing `http://localhost:3000`.
2. Dev middleware not prepended (forwarded host / body stubs).
3. Session cookie set on one port but form POST goes through another without trusted origins.

**Fix:**

```python
from reflex_django.dev.django_middleware import DEFAULT_DEV_MIDDLEWARE

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
    "reflex_django.bridge.streaming.AsyncStreamingMiddleware",
]
```

Restart `reflex run` and hard-refresh the browser.

**Related:** [Local development (CSRF)](../getting-started/local_development.md#django-dev-middleware-and-csrf), [Authentication](../guides/authentication.md)

---

## Blank SPA or missing home route {#blank-spa-or-missing-home-route}

**Symptoms:** Browser shows a blank page at `/`, or the console reports `dispatch is not a function`. The dev server runs but no Reflex routes appear in the compiled bundle.

**Likely causes:**

1. A `@page` module was never imported before compile (common after v3 removed INSTALLED_APPS scanning).
2. Pages live in another app (e.g. `blog.views`) but `{app_name}/views.py` does not import them.
3. `RX_PAGE_PACKAGES` lists a module that does not re-import all page submodules.
4. Missing `import {app_name}.views` in `urls.py`.

**Fix:**

1. Use one **page registry hub** in `{app_name}/views.py` that imports every `@page` module:

```python
# shop/views.py  ({app_name}/views.py)
import blog.views  # noqa: F401
import frontend.pages.home  # noqa: F401
```

2. Import the hub from `urls.py`:

```python
import shop.views  # noqa: F401
```

3. Optionally document compile imports in settings:

```python
RX_PAGE_PACKAGES = ["shop.views"]
```

4. Keep `{app_name}/{app_name}.py` as a thin entry stub (do not rely on it alone for multi-app pages).
5. Restart `reflex run`. If still broken, delete `.web/` and run again.

**Related:** [App entry module and page registration](../guides/app_entry_and_pages.md), [Pages in views.py](../guides/pages.md)

---

## `KeyError: No registered handler found for event`

**Symptoms:** Server log shows `KeyError` with a long handler name containing segments like `reflex_django___auth_state___` or other old module paths after upgrading reflex-django.

**Likely causes:**

1. Stale compiled frontend in `.web/` from before a v2 upgrade (handler keys baked in at compile time).
2. Backend restarted but Vite still serving an old client bundle.

**Fix:**

1. Stop `reflex run` / uvicorn and Vite.
2. Delete the compiled frontend cache and recompile:

```bash
rmdir /s /q .web
reflex run
```

On Linux/macOS: `rm -rf .web` then `reflex run`.

3. Hard-refresh the browser (or open a private window).

If you only changed Python code and are on reflex-django 2.0+, restarting the backend is usually enough when `DjangoUserState` still resolves under `reflex_django.auth_state`.

**Related:** [Public API](../reference/api.md)

---

## Django admin 404 on `:3000` or `:8000`

**Symptoms:** `/admin/` returns 404, or the SPA catch-all serves HTML instead of Django admin.

**Likely causes:**

1. `path("admin/", admin.site.urls)` missing from `urlpatterns`.
2. Custom API route registered **after** the SPA catch-all (catch-all wins).
3. Browsing `:8000` in default two-port mode expecting the Vite shell (admin still works on `:8000`, but `/` may not be the SPA).
4. `RX_DJANGO_PREFIX` omits `/admin`, so Vite proxies admin to the wrong upstream.
5. **After saving a Reflex page**, Vite restarted on a stripped ``vite.config.js`` before the proxy plugin was re-applied (fixed in recent releases - restart ``reflex run`` if you still see this on an older build).

**Fix:**

1. Put explicit Django routes **first** in `urlpatterns`:

```python
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("shop.api_urls")),
]
# catch-all appended by RX_AUTO_MOUNT
```

2. Open admin directly at `http://localhost:8000/admin/` to isolate routing from Vite.
3. If auto-detection misses a prefix, set env or settings:

```bash
export RX_DJANGO_PREFIX="/admin,/api,/static"
reflex run
```

**Related:** [Pages in views.py (URL split)](../guides/pages.md#the-url-split-django-routes-vs-reflex-routes), [Settings reference](../reference/settings.md#rx_django_prefix)

---

## `/_event` fails or WebSocket disconnects

**Symptoms:** Browser console shows Socket.IO errors, "WebSocket connection failed", or events never reach handlers.

**Likely causes:**

1. Proxy missing `ws: true` for `/_event` (fixed by reflex-django's Vite plugin in two-port dev).
2. Reverse proxy in production strips `Upgrade` headers or times out idle sockets.
3. Reserved prefix collision: a Django route registered under `/_event`.
4. Stale `.web/` bundle (`dispatch is not a function`).

**Fix:**

1. Default dev: browse `:3000` and confirm `.web/vite.config.js` lists `/_event` with WebSocket proxy to the Reflex backend (`:8000` by default).
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

3. Clean rebuild: stop server, delete `.web/`, run `reflex run` again.
4. Read the event path in [WebSocket event pipeline](../internals/event_pipeline.md).

**Related:** [Deployment](deployment.md), [Routing (reserved prefixes)](../internals/routing.md#reserved-reflex-prefixes)

---

## Wrong routes after changing `RX_DJANGO_PREFIX`

**Symptoms:** API hits the SPA shell, or Reflex pages load Django 404 JSON. Typo `DANAGO_PREFIX` in env has no effect. **Or:** `/admin` on `:3000` worked at startup but returns SPA 404 right after you save a Reflex page (hot-reload recompile).

**Likely causes:**

1. Env var misspelled. The real name is `RX_DJANGO_PREFIX`.
2. Prefix list out of sync with `urlpatterns` (auto-detection skipped a `re_path`).
3. Ensure Django prefixes (`/admin`, `/api`, …) are in `urlpatterns` and listed in `django_prefix` (auto-detected or explicit).
4. Vite restarted on a stripped ``vite.config.js`` before reflex-django re-applied the proxy plugin. Recent releases patch proxy generation on every ``App._compile`` (including backend hot reload), not only the initial startup compile.

**Fix:**

1. Set the correct env var (comma-separated, leading slashes):

```bash
export RX_DJANGO_PREFIX="/admin,/api,/internal"
```

2. Or pass explicit prefixes to `reflex_mount(django_prefix=(...))`.
3. Restart `reflex run` so compile re-exports prefixes into `env.json` and Vite.

**Related:** [Routing](../internals/routing.md#django-prefix-detection), [Settings reference](../reference/settings.md#rx_django_prefix)

---

## Port confusion (`:3000` vs `:8000` vs `:8001`)

**Symptoms:** Blank page, wrong app, or "port already in use".

| Symptom | Fix |
|:---|:---|
| Blank UI on `:8000` in default dev | Open `:3000` for the SPA. `:8000` is backend-only unless you use `--env dev`. |
| Vite silently on `:3001` | Stop the process holding `:3000`. reflex-django sets `strictPort: true`. |
| API works on `:8000` but not `:3000` | Confirm two-port mode: `RX_SEPARATE_DEV_PORTS=1` (default for `reflex run`). |
| Admin/API 404 from `:3000` or `:8000` | Confirm admin is in `urlpatterns`, `django_prefix` includes `/admin`, and you restarted `reflex run` after URL changes. |
| Split-process dev 502 | When using `RX_PROXY_SERVER`, confirm Django is running at that URL. |

**Fix:** Use `reflex run` (not bare `runserver` or lone uvicorn) for SPA dev. Override ports in `rxconfig.py` or `RX_FRONTEND_PORT` / `RX_BACKEND_PORT`.

**Related:** [Local development](../getting-started/local_development.md), [CLI](cli.md)

---

## Other quick fixes

| Symptom | Fix |
|:---|:---|
| `Reflex SPA bundle not found` | Run `reflex run` or `reflex export`. In two-port dev, use `:3000`. |
| `AppRegistryNotReady` | Import models inside handlers, not at module top in `views.py`. |
| `SynchronousOnlyOperation` | Use `await Model.objects.aget(...)` in async handlers. |
| White page / `dispatch is not a function` | Delete `.web/`, restart `reflex run`. |
| Anonymous user in handlers | Subclass `AppState`, ensure session middleware runs. See [State management](../guides/state.md). |
| Slow or high-frequency events | `RX_EVENT_BRIDGE_MODE = "smart"`; `_rx_bridge = "none"` on hot `rx.State` classes. See [Scaling](scaling.md). |

---

## What just happened?

You matched common dev failures to concrete checks: proxies, CSRF origins, URL order, WebSocket headers, `RX_DJANGO_PREFIX`, and port layout.

**Next up:** [FAQ](../reference/faq.md) for short answers, or [Routing](../internals/routing.md) to understand how paths are chosen.
