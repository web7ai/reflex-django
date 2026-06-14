---
level: beginner
tags: [architecture, onboarding]
---

# How the two fit together

**What you'll learn:** How Django and Reflex share runtime in dev and production, and what happens from HTTP request to UI update.

**When you need this:**

- You read the primers and want the bridge with real piece names (AppState, dispatcher, event bridge).
- You are about to install or integrate and want the runtime picture before touching `settings.py`.

---

You have seen [why reflex-django exists](../overview/concepts.md) and the [Django](../overview/concepts.md) and [Reflex](../overview/concepts.md) primers. Now we stitch them together with the actual pieces.

For the short map, read [The three knobs](../overview/concepts.md) first. You will meet `REFLEX_DJANGO_RX_CONFIG`, `AppState`, `DjangoEventBridge`, and `make_dispatcher`. No need to memorize them yet.

---

## Dev vs production

| Phase | Django | Reflex | Browser URL |
|:---|:---|:---|:---|
| **Dev (default)** | Mounted **in-process** inside Reflex backend | Vite `:3000` + backend `:8000` | `:3000` for SPA |
| **Dev (split, optional)** | Separate `runserver` + `RXDJANGO_PROXY_SERVER` | Same as above | `:3000` for SPA |
| **Production** | Plain Django ASGI + `reflex_mount()` | Separate backend or static export | Your domain (one origin via proxy) |

Legacy **`django_outer`** and **`reflex_outer`** routing modes were removed in v3. See [Migrating to mount-only](migration/v3_mount_only.md).

---

## The runtime picture (default dev)

```text
Browser :3000 (Vite)
        │  proxy admin, api, /_event, …
        ▼
Reflex backend :8000
        │
        ├── make_dispatcher ──► /admin, /api, /static → Django ASGI (same process)
        ├── /_event, /_upload → Reflex inner ASGI
        └── SPA routes        → Reflex inner ASGI
```

When a WebSocket event arrives on `/_event`:

```text
Reflex inner ASGI
        ▼
DjangoEventBridge
        ├── build synthetic HttpRequest
        ├── run settings.MIDDLEWARE
        └── call your @rx.event handler (self.request, self.user, …)
```

---

## Optional: separate Django in dev

If you prefer `runserver` for Django debugging:

```python
--8<-- "snippets/proxy_server_settings.py"
```

Vite proxies Django prefixes to that URL instead of the Reflex backend. See [Routing](../internals/routing.md).

---

## The four pieces you'll touch

| Piece | What it is | Where you see it |
|:---|:---|:---|
| **`REFLEX_DJANGO_RX_CONFIG`** | Reflex ports, `app_name`, redis | `config/settings.py` |
| **`AppState`** | Your Reflex state class | `{app}/views.py` |
| **`DjangoEventBridge`** | Middleware replay on events | Installed automatically at bootstrap |
| **`make_dispatcher`** | Routes Django URL prefixes inside Reflex backend | Attached when `run_reflex` loads the app |

---

## Production picture

```text
Edge proxy (Nginx, Caddy, …)
    ├── /_event, /_upload, … ──► Reflex backend
    └── everything else ───────► Django ASGI
                                      ├── /admin, /api
                                      └── catch-all → ReflexMountView (SPA shell)
```

Django uses plain `get_asgi_application()`  -  not a composed reflex-django ASGI entry. See [Deployment](../operations/deployment.md).

---

## What just happened?

You saw how dev keeps one browser origin on `:3000` while the Reflex backend serves both Reflex and Django traffic in-process, and how production splits processes at your reverse proxy instead.

**Next up:** [The three knobs](../overview/concepts.md) or [Local development](../getting-started/local_development.md).
