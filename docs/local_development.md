# Local development

This page explains how the dev server actually works — which URL to open, what the two ports mean, and how to fix the problems people run into most often.

---

## The short version

```bash
python manage.py run_reflex
```

Open **`http://localhost:8000/`** in your browser.

That's it. One URL for everything: your Reflex pages, Django admin, API, and the Reflex WebSocket (`/_event`).

Vite still runs in the background on port **3000** for hot reload, but you don't need to visit it. Django reverse-proxies SPA traffic to Vite for you.

---

## How the two ports fit together

In the default **DJANGO_OUTER** layout (what you get out of the box):

```text
Browser  →  http://localhost:8000/     (this is what you open)
                │
                ├─ /admin, /api, /static  →  Django handles these directly
                ├─ /_event, /ping, …      →  Reflex backend (same process)
                └─ /, /@vite/client, …    →  Django proxies to Vite on :3000
```

| Port | Who listens | Do you open it? |
|:---|:---|:---|
| **8000** (backend) | Django + Reflex ASGI | **Yes** — your dev URL |
| **3000** (frontend) | Vite (HMR) | No — internal only |

This is different from the older **two-port** layout (`reflex_led`), where you opened `:3000` and Vite proxied Django routes back to `:8000`. That mode still exists for legacy projects, but it is not the default anymore.

---

## What `run_reflex` does for you

When you run the default command (no extra flags):

1. **Compiles** the Reflex SPA into `.web/`
2. **Starts Vite** on the frontend port (default `3000`)
3. **Waits** until Vite is actually serving the SPA (not just listening on a socket)
4. **Starts uvicorn** on the backend port (default `8000`) with `reflex_django.asgi_entry:application`
5. **Watches** your `.py` files — frontend edits hot-reload through Vite; backend edits need a restart

You should see something like:

```text
reflex-django: Vite ready on port 3000 (reverse-proxied by Django on port 8000).
    Open http://localhost:8000/ — frontend edits hot-reload via Vite; ...
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### What you should *not* use for local dev

| Command | Why it breaks the SPA |
|:---|:---|
| `python manage.py runserver` | WSGI only — no Vite, no dev proxy |
| `uvicorn ...:application` alone | No Vite unless you start it separately and set `REFLEX_DJANGO_DEV_PROXY=1` |

If you hit either of those, you'll likely see **"Reflex SPA bundle not found"** or a static-asset reload loop. Use `run_reflex` instead.

---

## Configuring ports

Set ports in `reflex_mount()` — they propagate everywhere automatically:

```python
urlpatterns += [
    reflex_mount(
        app_name="myapp",
        django_prefix=("/admin", "/api"),
        rx_config={"frontend_port": 3000, "backend_port": 8000},
    ),
]
```

Optional overrides in development settings:

```python
REFLEX_DJANGO_DEV_PROXY = True
REFLEX_DJANGO_FRONTEND_PORT = 3000
REFLEX_DJANGO_BACKEND_PORT = 8000
```

Or via environment variables: `REFLEX_DJANGO_FRONTEND_PORT`, `REFLEX_DJANGO_BACKEND_PORT`.

---

## Django dev middleware (recommended)

Even though you browse `:8000`, keep the dev middleware in your **development** settings. It helps when tools or proxies forward requests with unusual `Host` headers:

```python
from reflex_django.django_dev_middleware import DEFAULT_DEV_MIDDLEWARE

DEBUG = True
USE_X_FORWARDED_HOST = True

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",   # harmless to keep for legacy / tooling
    "http://127.0.0.1:3000",
]

MIDDLEWARE = [
    *DEFAULT_DEV_MIDDLEWARE,
    # ... your existing middleware ...
]
```

### What the middleware does

| Middleware | Purpose |
|:---|:---|
| `EnsureRequestBodyAttrsMiddleware` | Sets Django 6 `_body` / `_read_started` on synthetic requests — only when there is no POST body |
| `DevViteProxyHostMiddleware` | Copies `Origin` / `Referer` into forwarded-host headers for local hosts |

> **Important:** `EnsureRequestBodyAttrsMiddleware` must **not** blank out real POST bodies — that breaks admin saves and CSRF.

---

## Frontend stability patches

After each compile, **reflex-django** patches `.web` to prevent common browser errors:

| File | Change |
|:---|:---|
| `utils/context.js` | Safe `EventLoopContext` default |
| `utils/components/*.jsx`, `app/root.jsx` | Guarded `useContext` (no destructuring on `null`) |
| `vite.config.js` | `resolve.dedupe`, `strictPort: true` |

Look for a log line like:

```text
reflex-django applied frontend stability patches: N files (e.g. utils/context.js, …)
```

In DJANGO_OUTER mode, reflex-django also **removes** stale Vite→Django proxy rules from `.web/` — those caused request loops when browsing `:8000`.

---

## Troubleshooting

### "Reflex SPA bundle not found"

The dev proxy is off and there's no compiled bundle on disk. Common causes:

- You started `runserver` or bare `uvicorn` instead of `run_reflex`
- A previous run disabled the proxy (`REFLEX_DJANGO_DEV_PROXY=0`)
- Vite never started

**Fix:** stop any stale servers, then:

```bash
python manage.py run_reflex
```

Open `http://localhost:8000/`.

### Port 3000 is already in use

`run_reflex` will tell you explicitly. Another Vite or `run_reflex` instance is probably still running.

**Fix (Windows):**

```powershell
netstat -ano | findstr ":3000"
Stop-Process -Id <PID> -Force
```

Then restart `run_reflex`.

### Static files reloading forever on `:8000`

Usually means Django fell back to a stale disk bundle while Vite wasn't reachable, or old bidirectional proxy rules were still in `.web/`.

**Fix:** stop all dev servers, delete `.web/vite-plugin-reflex-django-proxy.js` if it exists, restart `run_reflex` (it regenerates a clean `.web/`).

### Admin 403 CSRF

Include both `:8000` and `:3000` in `CSRF_TRUSTED_ORIGINS`, set `USE_X_FORWARDED_HOST = True`, and put `DEFAULT_DEV_MIDDLEWARE` at the top of `MIDDLEWARE`.

### `useContext is not a function or its return value is not iterable`

Restart `run_reflex` after compile, hard-refresh the browser (Ctrl+Shift+R), and confirm the stability-patch log line appeared. Do not add Vite aliases that map `react` to `react/index.js`.

### Backend changes not showing up

Expected in the default Vite mode — the ASGI server stays up for HMR. Restart `run_reflex` after editing states, event handlers, or models.

---

## HTTP middleware vs event middleware

| Layer | Module | Runs on |
|:---|:---|:---|
| Django HTTP (dev) | `reflex_django.django_dev_middleware` | Browser HTTP to Django (admin, API) |
| Django HTTP (streaming) | `reflex_django.streaming_middleware` | HTTP responses (admin changelist streaming) |
| Reflex events | `reflex_django.middleware.DjangoEventBridge` | WebSocket `/_event` handlers |

Dev middleware does **not** replace the event bridge. For middleware on button clicks, see [Custom middleware in events](django_middleware_to_reflex.md).

---

## Legacy two-port mode (`reflex_led`)

If you intentionally set `REFLEX_DJANGO_URL_ROUTING=reflex_led`, you open `http://localhost:3000/` and Vite proxies Django prefixes to `:8000`. That layout injects Vite `server.proxy` rules during compile. **Do not mix** this with the DJANGO_OUTER workflow — pick one routing mode and stick with it.

---

**See also:** [CLI — `run_reflex`](cli.md) · [FAQ — development](faq.md#development-vite-port-and-csrf) · [Settings reference](settings_reference.md)
