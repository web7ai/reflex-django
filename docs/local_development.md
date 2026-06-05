# Local development (Vite port, Django admin, CSRF)

During `python manage.py run_reflex`, the Reflex frontend usually runs on **port 3000** (Vite with hot reload) while Django/ASGI listens on **port 8000**. The browser opens `http://localhost:3000/`; Vite proxies Django routes (`/admin`, `/api`, `/_event`, …) to the backend.

That two-port layout is convenient for HMR but needs a few integration pieces so Django admin, CSRF, and the Reflex event loop behave like a single site. **reflex-django** ships those pieces automatically where possible.

---

## What reflex-django does for you

### 1. Vite dev proxy (`pre_compile` / `post_compile`)

When `reflex_mount()` lists `django_prefix` entries (e.g. `/admin`, `/api`), the plugin:

- Injects **`reflexDjangoProxyPlugin()`** into `.web/vite.config.js` so proxied requests hit Django *before* React Router handles unknown paths.
- Adds **`server.proxy`** rules for each prefix plus Reflex internals (`/_event` with WebSocket, `/_upload`, `/static`, …).
- Forwards **`x-forwarded-host`** and **`x-forwarded-proto`** from the browser’s `Host` header so Django can build correct absolute URLs when `USE_X_FORWARDED_HOST = True`.

If `/admin` 404s on `:3000` after an export, re-run `run_reflex` once — `post_compile` rewrites the proxy block when it is missing.

See also: [Configuration](configuration.md), [CLI](cli.md).

### 2. Frontend stability patches (`post_compile`)

Reflex generates `EventLoopContext = createContext(null)` and components that destructure `useContext(EventLoopContext)`. Before the provider mounts (or when tooling loads a second React copy), the browser can throw:

```text
TypeError: useContext is not a function or its return value is not iterable
```

After each compile, **reflex-django** patches `.web` when needed:

| File | Change |
|:---|:---|
| `utils/context.js` | Safe default: `createContext([() => {}, []])` |
| `utils/components/*.jsx`, `app/root.jsx` | Guarded `useContext(EventLoopContext)` (no array destructuring on `null`) |
| `vite.config.js` | `resolve.dedupe: ["react", "react-dom", "@emotion/react"]` only — **no** `react` → `index.js` aliases (those break `react/jsx-runtime`) |

You should see a log line like:

```text
reflex-django applied frontend stability patches: N files (e.g. utils/context.js, …)
```

Patches are idempotent; re-running compile does not duplicate them.

### 3. Django dev HTTP middleware (optional, recommended for `:3000`)

For projects that open **Django admin on the Vite port** (`http://localhost:3000/admin/`), add the dev middleware near the **top** of `MIDDLEWARE` in your **development** settings:

```python
from reflex_django.django_dev_middleware import DEFAULT_DEV_MIDDLEWARE

MIDDLEWARE = [
    *DEFAULT_DEV_MIDDLEWARE,
    # ... your existing middleware ...
]
```

Or reference the classes explicitly:

```python
MIDDLEWARE = [
    "reflex_django.django_dev_middleware.EnsureRequestBodyAttrsMiddleware",
    "reflex_django.django_dev_middleware.DevViteProxyHostMiddleware",
    # ...
]
```

#### `EnsureRequestBodyAttrsMiddleware`

Reflex and the event bridge sometimes create synthetic requests without Django 6’s `_body` / `_read_started` attributes. This middleware sets them **only when there is no request body** (`CONTENT_LENGTH` is 0).

> **Important:** It must **not** set `_body = b""` on real POSTs (admin saves, forms). Doing so breaks CSRF verification and form parsing.

#### `DevViteProxyHostMiddleware`

When the Vite proxy does not send `X-Forwarded-Host`, Django would see `Host: localhost:8000` while the browser is on `:3000`. Admin forms and CSRF cookies would target the wrong origin.

This middleware copies `Origin` or `Referer` into `HTTP_X_FORWARDED_HOST` / `HTTP_X_FORWARDED_PROTO` for local hosts (`localhost`, `127.0.0.1`, `[::1]`).

Requires:

```python
USE_X_FORWARDED_HOST = True
```

#### CSRF trusted origins

Django 4+ compares the `Origin` header to `CSRF_TRUSTED_ORIGINS` **exactly** (scheme + host + port). Include **both** backend and frontend dev URLs:

```python
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
```

Extra origins can be appended via the `CSRF_TRUSTED_ORIGINS` environment variable (comma-separated).

---

## Example: development settings snippet

```python
# settings/dev.py (or base/dev.py)
from reflex_django.django_dev_middleware import DEFAULT_DEV_MIDDLEWARE

DEBUG = True
USE_X_FORWARDED_HOST = True

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

MIDDLEWARE = [
    *DEFAULT_DEV_MIDDLEWARE,
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # ...
    "reflex_django.streaming_middleware.AsyncStreamingMiddleware",
]
```

Keep `AsyncStreamingMiddleware` **last**. Dev middleware belongs **first** (before CSRF/session).

---

## Troubleshooting

| Symptom | What to check |
|:---|:---|
| Admin **403 CSRF** on `:3000` | `CSRF_TRUSTED_ORIGINS` includes `http://localhost:3000`; `USE_X_FORWARDED_HOST = True`; `DevViteProxyHostMiddleware` early in `MIDDLEWARE`; no middleware forcing empty `_body` on POST |
| Admin works on `:8000` but not `:3000` | Vite proxy present in `.web/vite.config.js`; restart `run_reflex` |
| `useContext is not a function` / **not iterable** | Restart dev server after compile; confirm `reflex-django` `post_compile` ran (log mentions stability patches); hard-refresh browser; clear `.web/node_modules/.vite` if needed |
| `Could not read … react/index.js/jsx-runtime` | Remove manual Vite aliases that map `react` to `index.js`; use **dedupe only** (reflex-django no longer adds file aliases) |
| `/admin` 404 on `:3000` | Re-run `run_reflex`; check `django_prefix` in `reflex_mount()` matches real URL prefixes |

---

## HTTP middleware vs event middleware

| Layer | Module | Runs on |
|:---|:---|:---|
| Django HTTP (dev) | `reflex_django.django_dev_middleware` | Browser HTTP to Django (admin, API) |
| Django HTTP (streaming) | `reflex_django.streaming_middleware` | HTTP responses (admin changelist streaming) |
| Reflex events | `reflex_django.middleware.DjangoEventBridge` | WebSocket `/_event` handlers |

Dev middleware does **not** replace the event bridge. For middleware on button clicks, see [Custom middleware in events](django_middleware_to_reflex.md).

---

**See also:** [FAQ — development](faq.md#development-vite-port-and-csrf) · [Public API — dev middleware](public_api.md#django-http-dev-middleware) · [Settings reference](settings_reference.md)
