# Local development

This page explains how the dev server actually works — which URLs to open, what the two ports mean, and how to fix the problems people run into most often.

---

## The short version

```bash
python manage.py run_reflex
```

That **one command starts two servers**:

| Server | Port (default) | What you open it for |
|:---|:---|:---|
| **Vite** (frontend) | `3000` | **Reflex UI** — pages, hot reload, in-browser navigation |
| **uvicorn** (backend) | `8000` | **Django + Reflex backend** — admin, API, `/_event` WebSocket |

**For frontend work, open `http://localhost:3000/`** — same as native Reflex. Vite proxies Django-owned paths (`/admin`, `/api`, …) and the Reflex backend (`/_event`) to `:8000` for you.

**For backend-only checks**, you can also hit `http://localhost:8000/admin/` or your API directly on `:8000`.

---

## How the two ports fit together

Default **two-port** dev (native Reflex layout — no extra flags):

```text
Browser  →  http://localhost:3000/     (open this for the SPA)
                │
                ├─ /, /about, …           →  Vite serves the Reflex SPA (HMR)
                ├─ /admin, /api, …      →  Vite proxies to Django on :8000
                └─ /_event                →  Vite proxies to Reflex backend on :8000

Backend  →  http://localhost:8000/     (Django + Reflex ASGI — admin, API, WebSocket)
```

| Port | Who listens | When you open it |
|:---|:---|:---|
| **3000** (frontend) | Vite (HMR) | **Yes** — your SPA dev URL |
| **8000** (backend) | Django + Reflex ASGI | Admin, API, or debugging backend routes |

Cookie sharing still works: Vite's proxy forwards session cookies to the backend on the same paths you'd use in production.

---

## Optional: single-port mode (`--single-port`)

If you prefer **one browser URL**, pass `--single-port`:

```bash
python manage.py run_reflex --single-port
```

Then open **`http://localhost:8000/`** for everything. Django reverse-proxies SPA traffic to Vite on `:3000`; you don't browse `:3000` yourself.

```text
Browser  →  http://localhost:8000/
                ├─ /admin, /api, /static  →  Django handles these directly
                ├─ /_event, /ping, …      →  Reflex backend (same process)
                └─ /, /@vite/client, …    →  Django proxies to Vite on :3000
```

Use this when you want a single origin in the address bar. Default remains two-port (`:3000` for UI) because it matches native Reflex and gives the best HMR experience.

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
reflex-django: two-port dev (native Reflex layout).
    UI + hot reload: http://localhost:3000/
    Django + Reflex backend: http://localhost:8000/ (admin, API, /_event — not the SPA shell).
    Pass --single-port to browse only the backend port.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

With `--single-port`:

```text
reflex-django: Vite ready on port 3000 (reverse-proxied by Django on port 8000).
    Open http://localhost:8000/ — frontend edits hot-reload via Vite; ...
```

### What you should *not* use for local dev

| Command | Why it breaks the SPA |
|:---|:---|
| `python manage.py runserver` | WSGI only — no Vite, no dev proxy |
| `uvicorn ...:application` alone | No Vite unless you start it separately |

If you hit either of those, you'll likely see **"Reflex SPA bundle not found"** or a static-asset reload loop. Use `run_reflex` instead.

---

## Configuring ports

Set ports in `REFLEX_DJANGO_RX_CONFIG` — they propagate everywhere automatically:

```python
# settings.py
REFLEX_DJANGO_RX_CONFIG = {
    "frontend_port": 3000,
    "backend_port": 8000,
}
```

```python
# urls.py — import pages; Django prefixes (/admin, /api, …) are auto-detected from routes
import myapp.views  # noqa: F401

urlpatterns = [path("admin/", admin.site.urls)]
# catch-all: automatic (REFLEX_DJANGO_AUTO_MOUNT=True)
```

Optional overrides in development settings:

```python
REFLEX_DJANGO_DEV_PROXY = True   # set by run_reflex; only for --single-port
REFLEX_DJANGO_SEPARATE_DEV_PORTS = True  # set by run_reflex in default two-port mode
REFLEX_DJANGO_FRONTEND_PORT = 3000
REFLEX_DJANGO_BACKEND_PORT = 8000
```

Or via environment variables: `REFLEX_DJANGO_FRONTEND_PORT`, `REFLEX_DJANGO_BACKEND_PORT`.

---

## Django dev middleware and CSRF

Keep the dev middleware in your **development** settings. It helps when tools or proxies forward requests with unusual `Host` headers:

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
]
```

Include **both** `:3000` and `:8000` in `CSRF_TRUSTED_ORIGINS` — you browse the SPA on `:3000`, and admin/API may be reached on either port depending on how you navigate.

---

## Frontend stability patches

After each compile, reflex-django patches a few generated `.web` files (EventLoopContext, etc.) so the SPA boots reliably under Vite. You should see a line in the compile log about **frontend stability patches**. If the browser throws `useContext is not a function`, restart `run_reflex` and hard-refresh (Ctrl+Shift+R).

Do **not** add Vite aliases that map `react` to `react/index.js` — that breaks `react/jsx-runtime`.

---

## Vite proxy rules (two-port mode)

In default two-port dev, reflex-django injects Vite `server.proxy` rules at compile time so `/admin`, `/api`, and `/_event` reach Django on `:8000`. In `--single-port` mode those rules are **removed** — Django owns the outer port and reverse-proxies to Vite instead (avoids request loops).

---

## Troubleshooting

### "Reflex SPA bundle not found" on `:8000`

In **default two-port mode**, `:8000` does not serve the SPA shell — open **`http://localhost:3000/`** instead.

If you use `--single-port` and still see this, the dev proxy is off and there's no compiled bundle. Start dev with `python manage.py run_reflex --single-port` (not `runserver`). If port `3000` is already taken, free it and restart.

### Port 3000 is already in use

```bash
# Windows
netstat -ano | findstr ":3000"
```

Stop the other Vite or `run_reflex` instance, then re-run `python manage.py run_reflex`.

### Static files reloading forever on `:8000`

Usually means you're in single-port mode without a working Vite proxy, or you're on `runserver` instead of `run_reflex`. Use the default two-port command and browse `:3000`.

### Django admin returns 403 CSRF

Include both `:8000` and `:3000` in `CSRF_TRUSTED_ORIGINS`, set `USE_X_FORWARDED_HOST = True`, and put `DEFAULT_DEV_MIDDLEWARE` at the top of `MIDDLEWARE`.

### `useContext is not a function or its return value is not iterable`

Restart `run_reflex`, hard-refresh the browser, and check the compile log for "frontend stability patches". See above.

### Legacy `reflex_led` routing mode

If you intentionally set `REFLEX_DJANGO_URL_ROUTING=reflex_led`, routing differs from DJANGO_OUTER — see [Migration: django_outer](migration_django_outer.md). **Do not mix** routing modes. New projects should leave `REFLEX_DJANGO_URL_ROUTING` at its default.

### `reflex_outer` — two processes in dev

If you set `REFLEX_DJANGO_URL_ROUTING = "reflex_outer"`, `run_reflex` starts a Django HTTP worker on port `8001` (by default) **and** Reflex on `:8000`. Browse `:8000` as usual — admin and API are proxied internally. You do not need to open `:8001` in the browser.

See [django_outer vs reflex_outer](routing.md#choosing-a-mode-django_outer-vs-reflex_outer) for the full picture.

---

**Next:** [Deployment →](deployment.md) · [CLI reference](cli.md)
