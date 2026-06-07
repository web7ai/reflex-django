# Local development

This page explains how the dev server actually works — which URLs to open, what the two ports mean, and how to fix the problems people run into most often.

---

## The short version

```bash
python manage.py run_reflex
```

That **one command starts two servers** (default `django_outer` mode):

| Server | Port (default) | What you open it for |
|:---|:---|:---|
| **Vite** (frontend) | `3000` | **Reflex UI** — pages, hot reload, in-browser navigation |
| **uvicorn** (backend) | `8000` | **Django + Reflex backend** — admin, API, `/_event` WebSocket |

**For frontend work, open `http://localhost:3000/`** — same as native Reflex.

**For backend-only checks**, hit `http://localhost:8000/admin/` or your API directly on `:8000`.

---

## How the two ports fit together (default `django_outer`)

Default **two-port** dev matches native Reflex: UI on Vite, backend on Django/Reflex ASGI.

```text
Browser  →  http://localhost:3000/     (open this for the SPA)
                │
                └─ /, /about, …           →  Vite serves the Reflex SPA (HMR)

Browser  →  http://localhost:8000/     (admin, API, WebSocket — direct or via env.json)
                ├─ /admin, /api, …      →  Django
                └─ /_event              →  Reflex backend
```

In **`django_outer`** (the default), reflex-django does **not** inject Vite `server.proxy` rules. The compiled SPA's `env.json` tells the browser to reach admin, API, and `/_event` on **`http://localhost:8000`** while you browse the UI on `:3000`. Session cookies still work because both ports share `localhost`.

**Legacy modes** (`django_led`, `reflex_outer`) still inject Vite→Django proxy rules at compile time — see [Routing modes](routing.md#choosing-a-mode-django_outer-vs-reflex_outer).

| Port | Who listens | When you open it |
|:---|:---|:---|
| **3000** (frontend) | Vite (HMR) | **Yes** — your SPA dev URL |
| **8000** (backend) | Django + Reflex ASGI | Admin, API, WebSocket, or debugging backend routes |

---

## Optional: compile dev on one port (`--env dev`)

If you prefer **one browser URL** without running Vite, use compile dev:

```bash
python manage.py run_reflex --env dev
```

Then open **`http://localhost:8000/`** for everything. Each save recompiles into `.web/` and Django serves the bundle from disk (no HMR, no Node after the first compile).

```text
Browser  →  http://localhost:8000/
                ├─ /admin, /api, /static  →  Django handles these directly
                ├─ /_event, /ping, …      →  Reflex backend (same process)
                └─ /, /about, …           →  compiled SPA from .web/
```

For live Vite HMR on two ports again, pass **`--with-vite`** (or omit `--env dev` and use plain `run_reflex`).

### Optional: Django reverse-proxies Vite on one URL (advanced)

To browse **`http://localhost:8000/`** while Vite still runs on `:3000` for HMR (Django proxies SPA assets to Vite), set in development settings:

```python
REFLEX_DJANGO_DEV_PROXY = True
REFLEX_DJANGO_SEPARATE_DEV_PORTS = False
```

There is **no CLI flag** for this today — set the env vars or settings explicitly before starting the server. Default `run_reflex` keeps `DEV_PROXY=0` and two-port layout.

---

## What `run_reflex` does for you

When you run the default command (no extra flags):

1. **Compiles** the Reflex SPA into `.web/`
2. **Starts Vite** on the frontend port (default `3000`)
3. **Waits** until Vite is actually serving the SPA (not just listening on a socket)
4. **Starts uvicorn** on the backend port (default `8000`) with `reflex_django.asgi_entry:application`
5. **Watches** your `.py` files — page edits hot-reload through Vite; backend reloads on most Python changes (see [CLI reference](cli.md))

You should see something like:

```text
reflex-django: two-port dev (native Reflex layout).
    UI + hot reload: http://localhost:3000/
    Django + Reflex backend: http://localhost:8000/ (admin, API, /_event — not the SPA shell).
    Pass --env dev to compile-serve on :8000 only, or --from-build for disk bundle + watcher.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

With `--env dev`:

```text
reflex-django: single-port compile dev (--env dev) - compiles to `.web/` on each save
    and serves from Django on port 8000.
    Pass `--with-vite` for live Vite HMR on :3000 instead.
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
# Set by run_reflex in default two-port Vite mode:
REFLEX_DJANGO_SEPARATE_DEV_PORTS = True
REFLEX_DJANGO_DEV_PROXY = False

# For Django→Vite reverse-proxy on one URL (advanced — set manually):
# REFLEX_DJANGO_DEV_PROXY = True
# REFLEX_DJANGO_SEPARATE_DEV_PORTS = False

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

## Vite proxy rules (legacy routing modes only)

In **`django_outer`** (default), Vite **does not** proxy `/admin`, `/api`, or `/_event` — the SPA uses `env.json` to call `:8000` directly.

In **`django_led`** and **`reflex_outer`**, reflex-django injects Vite `server.proxy` rules at compile time so those paths reach the backend from `:3000`.

When **`REFLEX_DJANGO_DEV_PROXY=1`**, Django's catch-all reverse-proxies SPA routes to Vite on `:3000` while you browse `:8000` (advanced single-origin HMR).

---

## Troubleshooting

### "Reflex SPA bundle not found" on `:8000`

In **default two-port mode**, `:8000` does not serve the SPA shell — open **`http://localhost:3000/`** instead.

If you use **`--env dev`** or **`--from-build`**, browse **`http://localhost:8000/`** — those modes serve the compiled bundle from disk on the backend port.

### Port 3000 is already in use

```bash
# Windows
netstat -ano | findstr ":3000"
```

Stop the other Vite or `run_reflex` instance, then re-run `python manage.py run_reflex`.

### Static files reloading forever on `:8000`

Usually means you're on `runserver` instead of `run_reflex`, or `REFLEX_DJANGO_DEV_PROXY=1` without a running Vite. Use the default two-port command and browse `:3000`, or use `--env dev` for compile-only single port.

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
