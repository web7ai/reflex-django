# Migrating to reflex-django v1.0

**What you will learn:** How to upgrade from reflex-django 0.x (or legacy routing layouts) to v1.0 with a verification checklist.

**When you need this:**

- You pinned `<1.0` and want to move forward.
- Release notes or warnings mention removed `django_led`, `reflex_led`, `ReflexDjangoPlugin`, or `make_dispatcher`.

Work through the sections in order. Most projects finish in one sitting.

---

## 1. Upgrade the package

```bash
uv add "reflex-django>=1.0"
# or: pip install -U "reflex-django>=1.0"
```

Confirm Python 3.12+, Django 6.0+, Reflex 0.9.2+.

---

## 2. Pick a routing mode

v1.0 supports exactly two modes:

| Mode | When to use |
|:---|:---|
| **`django_outer`** (default) | New projects and most brownfield Django apps. One ASGI process. |
| **`reflex_outer`** | Reflex must own the public port; Django admin/API run in a sidecar HTTP worker. |

```python
# settings.py: only if you need reflex_outer
REFLEX_DJANGO_URL_ROUTING = "reflex_outer"
REFLEX_DJANGO_DJANGO_PREFIX = ("/admin", "/api", "/static")
```

Remove legacy values:

```python
# REMOVED. Will error or warn
REFLEX_DJANGO_URL_ROUTING = "django_led"   # use django_outer
REFLEX_DJANGO_URL_ROUTING = "reflex_led"   # use reflex_outer
```

Read the comparison: [Routing (choosing a mode)](../routing.md#choosing-a-mode-django_outer-vs-reflex_outer).

---

## 3. Move Reflex config into Django settings

**Before (0.x):** `rxconfig.py` at the repo root, optional `ReflexDjangoPlugin` in plugins list.

**After (v1.0):** settings-driven config and bootstrap.

```python
# config/settings.py
REFLEX_DJANGO_RX_CONFIG = {
    "app_name": "myshop",
    "backend_port": 8000,
    "frontend_port": 3000,
}
REFLEX_DJANGO_PLUGINS = [
    "reflex.plugins.RadixThemesPlugin",
]
```

Delete `rxconfig.py` when you no longer need it for external tooling. Temporary bridge: `REFLEX_DJANGO_USE_RXCONFIG_FILE = True`.

Remove plugin wiring that only existed to inject reflex-django:

```python
# REMOVED. Bootstrap installs the event bridge automatically
plugins=[ReflexDjangoPlugin(), ...]
```

Details: [Configuration](../configuration.md), [Add to an existing Reflex project](../existing_reflex_project.md).

---

## 4. Update ASGI entry

**Before:**

```python
from reflex_django.asgi.app import make_dispatcher
application = make_dispatcher()
```

**After:**

```python
from reflex_django.asgi.entry import application  # noqa: F401
```

Or, for explicit django_outer construction in custom hosting:

```python
from reflex_django.asgi.entry import build_django_outer_application
application = build_django_outer_application()
```

See [Installation](../installation.md) and [Architecture](../architecture.md).

---

## 5. Update imports (pages and state)

| Old (0.x top-level) | New (v1.0) |
|:---|:---|
| `from reflex_django import page` | `from reflex_django.pages.decorators import page` |
| `from reflex_django import AppState` | `from reflex_django.states import AppState` |
| `from reflex_django import template` | `from reflex_django.pages.decorators.templates import centered_template` |

Replace `rx.State` with `AppState` when you need `self.request.user`, sessions, or messages.

---

## 6. URLs and auto-mount

v0.5+ already introduced `REFLEX_DJANGO_AUTO_MOUNT=True` (default). In v1.0 you should **not** duplicate a catch-all unless you have a special layout.

```python
# config/urls.py
import myshop.views  # noqa: F401, registers @page routes

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("myshop.api_urls")),
]
# SPA catch-all appended at startup when REFLEX_DJANGO_AUTO_MOUNT=True
```

Call `reflex_mount()` only for prefix overrides. See [Pages in views.py](../pages_in_views.md).

---

## 7. Dev workflow and ports

Default dev is unchanged in spirit: **`python manage.py run_reflex`**, browse **`http://localhost:3000/`**, backend on **`http://localhost:8000/`**.

Changes to know:

| Topic | v1.0 note |
|:---|:---|
| CLI flags | `--single-port` removed. Use `--env dev` for compile-only single port. |
| Proxies | Vite proxy plugin supports **multi-target** routes in `reflex_outer`. |
| Env | `REFLEX_DJANGO_SEPARATE_DEV_PORTS=1` set automatically by `run_reflex`. |

If admin CSRF fails from `:3000`, add trusted origins. [Local development](../local_development.md).

---

## 8. Rename deprecated app module (if present)

`reflex_django.django_led_app` was removed in v2.0. User code should use:

```python
from reflex_django import app
```

The implementation module is `reflex_django.runtime.reflex_app` if you need an explicit import.

---

## 9. Verification checklist

Run these after migration:

- [ ] `python manage.py check` passes.
- [ ] `python manage.py run_reflex` starts Vite `:3000` and backend `:8000`.
- [ ] SPA loads on `:3000`, hot reload works.
- [ ] `/admin/` works (from `:8000` or proxied via `:3000`).
- [ ] A logged-in Reflex handler sees `self.request.user.is_authenticated`.
- [ ] `/_event` connects (no Socket.IO errors in the browser console).
- [ ] Production smoke: `uvicorn config.asgi:application` serves the exported SPA.

If something fails, use [Troubleshooting](../troubleshooting.md).

---

## Removed APIs reference

| Removed | Replacement |
|:---|:---|
| `reflex_led`, `django_led` routing | `django_outer`, `reflex_outer` |
| `ReflexDjangoPlugin` | Django-first bootstrap in `reflex_django.bootstrap` |
| `reflex_django.asgi.make_dispatcher` | `reflex_django.asgi.entry.application` |
| `reflex_django.decorators` | `reflex_django.pages.decorators` |
| Context processor bridge (0.5+) | Middleware-backed `AppState` fields |

Full list: [CHANGELOG.md](https://github.com/web7ai/reflex-django/blob/main/CHANGELOG.md)

---

## What just happened?

You retargeted routing, settings, ASGI, imports, and dev commands to the v1.0 layout and have a checklist to confirm behavior.

**Next up:** [What's new](../whats_new.md) for release highlights, or [Routing](../routing.md) for mode details.
