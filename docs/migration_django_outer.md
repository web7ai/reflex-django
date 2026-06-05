# Migrating from older versions

If you're starting a new project, you can skip this page entirely. This is for people upgrading an existing `reflex-django` project to the current architecture.

The current architecture — **Django outer, single port, full middleware chain on events** — is the default. Older versions used a different layout where Reflex was outer and Django was mounted underneath, on a different port. This page walks through the upgrade.

If you've never used the older versions, [How the two fit together](how_they_fit.md) is the current picture from scratch.

---

## TL;DR

Three steps:

1. Replace `config/asgi.py` with a one-liner pointing at `reflex_django.asgi_entry`.
2. Replace `rxconfig.py` usage with a `reflex_mount()` call in `urls.py`.
3. Use `python manage.py run_reflex` (or any ASGI server) instead of `reflex run`.

You get: one port, one origin, full middleware on Reflex events, and Django-first routing.

---

## What changes

| | Before | After |
|:---|:---|:---|
| **Ports** | Two (Reflex frontend + Django backend) | One (everything on `8000`) |
| **Outer app** | Reflex | Django |
| **Config** | `rxconfig.py` with plugin kwargs | `reflex_mount()` in `urls.py` + `REFLEX_DJANGO_*` settings |
| **Pages** | `{app}/{app}.py` with `app = rx.App()` | `{app}/views.py` with `@page` |
| **Middleware on events** | Limited subset (Session, Auth, Locale) | Full `settings.MIDDLEWARE` chain |
| **Bound context** | `self.request`, `self.user`, `self.session` | Above + `self.response`, `self.messages`, `self.csrf_token` |
| **Middleware redirects** | Ignored | Auto-converted to `rx.redirect(...)` |
| **Dev server** | `reflex run` + separate Django runner | `python manage.py run_reflex` |
| **Production** | Two services behind one proxy | One ASGI process |

---

## What stays the same

- `AppState`, `ModelState`, `ModelCRUDView` — same classes, same API.
- `DjangoUserState` reactive fields — still work.
- `self.request.user`, `self.session`, `self.login()`, `self.logout()` — all same.
- The Django ORM, the admin, migrations — untouched.
- Your existing models, views, and admin registrations — untouched.

---

## Step-by-step

### Step 1 — replace `config/asgi.py`

Old:

```python
# config/asgi.py — old
import os
import django

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
application = get_asgi_application()
```

New:

```python
# config/asgi.py — new
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
from reflex_django.asgi_entry import application  # noqa: E402,F401
```

That's the single ASGI callable for both dev and production now. Reflex's `/_event`, `/_upload`, etc. are mounted *inside* Django automatically.

---

### Step 2 — move config from `rxconfig.py` to `urls.py`

Old:

```python
# rxconfig.py — old
import reflex as rx
from reflex_django import ReflexDjangoPlugin

config = rx.Config(
    app_name="shop",
    backend_port=8000,
    frontend_port=3000,
    plugins=[ReflexDjangoPlugin(settings_module="config.settings")],
)
```

New:

```python
# rxconfig.py — delete this file (or keep an empty stub if you have build tooling that requires it)

# config/settings.py — ports, app_name, redis_url live here now
REFLEX_DJANGO_RX_CONFIG = {
    "app_name": "shop",
    "backend_port": 8000,
}

# config/urls.py — new
import shop.views  # noqa: F401

from django.contrib import admin
from django.urls import path

urlpatterns = [path("admin/", admin.site.urls)]
# catch-all: automatic (REFLEX_DJANGO_AUTO_MOUNT=True)
# Legacy manual mount (migration only): urlpatterns += [reflex_mount(app_name="shop")]
```

If you have build/CI tooling that absolutely requires a `rxconfig.py` file on disk, you can set `REFLEX_DJANGO_MATERIALIZE_RXCONFIG = True` to have one written out automatically. Most projects don't need this.

If you want the old `rxconfig.py` merged in (for unusual values that aren't in `rx_config={...}`):

```python
REFLEX_DJANGO_USE_RXCONFIG_FILE = True
```

---

### Step 3 — move pages from `{app}/{app}.py` to `{app}/views.py`

Old:

```python
# shop/shop.py — old
import reflex as rx
from shop.pages.home import home

app = rx.App()
app.add_page(home, route="/", title="Home")
```

New:

```python
# shop/views.py — new
import reflex as rx
from reflex_django.pages.decorators import page


@page(route="/", title="Home")
def home() -> rx.Component:
    return rx.heading("Hi")
```

Delete `{app}/{app}.py`. The Reflex `App` instance is now loaded from `reflex_django.django_led_app`, which auto-imports `views.py` from every entry in `INSTALLED_APPS`.

You can also keep multi-file pages — `views/__init__.py` re-exporting from `views/home.py`, `views/cart.py`, etc. — the discovery still works.

---

### Step 4 — add `AsyncStreamingMiddleware`

Add this at the bottom of `MIDDLEWARE`:

```python
MIDDLEWARE = [
    ...,
    "reflex_django.streaming_middleware.AsyncStreamingMiddleware",
]
```

It fixes streaming HTTP responses (like the admin's) under ASGI. ([Details](async_streaming_middleware.md).)

---

### Step 5 — update CI / Dockerfile

Old:

```bash
reflex run --env prod &
gunicorn config.wsgi:application &
```

New:

```bash
python manage.py export_reflex --frontend-only --no-zip --stage-to-static-root
python manage.py collectstatic --noinput
uvicorn reflex_django.asgi_entry:application --host 0.0.0.0 --port 8000 --workers 4
```

One ASGI process serves everything. ([Full deployment guide](deployment.md).)

---

## What custom code may break

### Middleware that didn't run on events before

Now it does. If you had a custom middleware that did something side-effect-y (rate limiting, logging, audit) it now runs on every Reflex event too. That's usually what you want, but:

- If it's expensive, consider adding it to `REFLEX_DJANGO_EVENT_MIDDLEWARE_SKIP`.
- If it was raising/redirecting for HTTP requests, you'll now see those raises/redirects translate to Reflex toasts/redirects. Verify the UX.

### Custom `rxconfig.py` plugins

If you had your own `plugins=[...]` list in `rxconfig.py`, move them into the `plugins=` argument of `reflex_mount()`:

```python
reflex_mount(
    app_name="shop",
    plugins=[YourPlugin(), AnotherPlugin()],
)
```

Do **not** include `ReflexDjangoPlugin` in that list — it's added automatically. To customize its kwargs, use `django_plugin={...}`:

```python
reflex_mount(
    app_name="shop",
    django_plugin={"install_auth_pages": False},
)
```

### CORS

You probably had CORS configured before because the SPA and Django were on different origins. With one port, **delete the CORS config**. It's not needed. (If you still have non-SPA clients hitting your API from other origins, keep it for those routes only.)

### Two ASGI app callables

If your production setup had two separate services (one for the SPA, one for Django) behind a reverse proxy, **consolidate to one**. The reverse proxy now points at a single ASGI process on one port. WebSocket and HTTP both terminate there.

### Token-based auth bridges

If you had a custom system to mint a JWT in Django, pass it to the SPA, and re-authenticate inside Reflex — **delete it**. With one origin, the session cookie does the job natively. Test with a fresh browser session to confirm.

---

## Keeping the legacy mode

If you need to stay on the old layout for now:

```python
# settings.py
REFLEX_DJANGO_URL_ROUTING = "reflex_led"
```

This pins the routing mode to the legacy two-port layout. New features (full middleware on events, message mirroring, etc.) won't apply, but your existing setup keeps working.

The legacy mode is supported for backwards compatibility. New projects should use the default `"auto"` (which resolves to `"django_outer"`).

---

## Verification checklist

After migrating, walk through these and make sure each one is true:

- [ ] `python manage.py run_reflex` starts without errors and you can open `http://localhost:8000/` (single dev URL; Vite hot-reloads on `:3000` behind the scenes).
- [ ] `/admin/` works and you can log in.
- [ ] After logging in at `/admin/`, a Reflex page that uses `self.request.user.is_authenticated` reports `True`.
- [ ] A custom Django middleware you previously had (if any) shows its effects inside a Reflex event handler.
- [ ] WebSocket connects on the same port as the HTTP traffic (check Network tab in DevTools).
- [ ] Production build: `python manage.py export_reflex ... && collectstatic && uvicorn` boots cleanly.
- [ ] `/static/_reflex/...` URLs serve the SPA assets.

If everything checks out, you're done.

---

## When to do this migration

- **You're starting a new feature** — easy to do as part of normal work.
- **You're hitting CORS / token-bridge complexity** — the migration removes the cause.
- **You want full middleware on Reflex events** — multi-tenancy, audit logging, custom auth.
- **You want a smaller deploy footprint** — one ASGI process instead of two.

If your existing setup works and you don't have any of the above pains, there's no urgency. The legacy mode is supported.

---

**Next:** [REFLEX_DJANGO_* settings →](settings_reference.md)
