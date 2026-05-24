# Django-led URL routing

Django-first reflex-django uses **`django_led`** routing: Django owns explicit HTTP routes; Reflex serves the SPA and client-side navigation through a **catch-all** mount.

---

## Mental model

| Layer | Responsibility |
|:---|:---|
| **`urls.py`** | Lists Django routes first; **`reflex_mount()` last** |
| **ASGI dispatcher** | Sends `/admin`, `/api`, … to Django; other HTTP to Reflex |
| **`@template` / `@page` in `views.py`** | Client routes (`/`, `/about`) — **not** duplicated in `path()` |
| **WebSockets `/_event`** | Always Reflex; event bridge attaches Django session |

This is **not** server-side rendering. The browser loads the Reflex SPA; navigation after load is client-side unless the user hits a Django-owned prefix.

```text
  GET /admin/     ──►  Django admin
  GET /api/foo/   ──►  Django view
  GET /about      ──►  Reflex SPA (route registered in demo/views.py)
  WS  /_event     ──►  Reflex + DjangoEventBridge
```

---

## `reflex_mount()` — the single configuration point

```python
from django.contrib import admin
from django.urls import include, path
from reflex_django.urls import reflex_mount

# Optional: ensure pages register (auto-discovery usually enough)
import myapp.views  # noqa: F401

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("myapp.api_urls")),
]

urlpatterns += [
    reflex_mount(
        app_name="myapp",
        mount_prefix="/",
        django_prefix=("/admin", "/api"),
        rx_config={"frontend_port": 3000, "backend_port": 8000},
    ),
]
```

### Rules

1. **Django `path()` entries first** — admin, API, webhooks, static routes you own.
2. **`reflex_mount()` last** — one catch-all `re_path` for the SPA.
3. **`django_prefix` must match** — every prefix listed must have a corresponding Django route above the mount.
4. **`ReflexDjangoPlugin` is automatic** — pass other Reflex plugins via `plugins=[...]` only.

### Optional helpers

```python
from reflex_django.urls import admin_urlpatterns, reflex_mount

urlpatterns = admin_urlpatterns("/admin")  # redirect + admin.site.urls
urlpatterns += [path("api/", include("api.urls"))]
urlpatterns += [reflex_mount(django_prefix=("/admin", "/api"))]
```

---

## `django_led_app` — where Reflex loads `app`

Classic Reflex:

```text
rxconfig: app_name="demo"
Import:   demo.demo:app   →  requires demo/demo.py
```

reflex-django:

```text
reflex_mount: app_name="demo"
Pages:        demo/views.py
Import:       reflex_django.django_led_app:app   →  no demo/demo.py
```

The module `reflex_django.django_led_app` is a thin lazy loader:

1. `import_page_packages()` — imports `{app}.views` from `INSTALLED_APPS`
2. `create_app()` — builds `rx.App()`
3. `_apply_decorated_pages()` — applies `@template` / `@page` registrations

Your **Django app label** (`demo`) names where pages live. **`django_led_app`** is the fixed Reflex entry module.

---

## Pages: `views.py`, not `urls.py`

```python
# demo/views.py
import reflex as rx
from reflex_django import template

@template(route="/", title="Home")
def index() -> rx.Component:
    return rx.text("Home")

@template(route="/about", title="About")
def about() -> rx.Component:
    return rx.text("About")
```

With `demo` in `INSTALLED_APPS`, reflex-django imports `demo.views` at startup. You do **not** add:

```python
path("about/", ...)  # wrong for SPA routes
```

See [Pages in views.py](pages_in_views.md).

---

## Running the dev server

```bash
python manage.py run_reflex
```

| URL | Served by |
|:---|:---|
| `http://localhost:3000/` | Reflex frontend (Vite dev) |
| `http://localhost:8000/` | Unified ASGI backend |
| `/admin/` | Django (via dispatcher + dev proxy) |

**Avoid** `python manage.py runserver` on the Reflex backend port while using `run_reflex` — WebSockets will not reach the unified app.

---

## `REFLEX_DJANGO_URL_ROUTING`

| Value | Behavior |
|:---|:---|
| **`django_led`** (default) | Django prefixes + SPA catch-all; use `reflex_mount()` |
| **`reflex_led`** | Reflex-first path split (legacy); rarely needed in new projects |

Set in settings or env:

```python
REFLEX_DJANGO_URL_ROUTING = "django_led"
```

---

## Reserved paths

Do not register Reflex client routes that collide with:

- Django prefixes in `django_prefix`
- Reflex internals: `/_event`, `/_upload`, `/_health`, `/_all_routes`, `/ping`

---

## Limitations

- **No per-page Django views** for SPA screens — use `@template(route=...)`.
- **`ReflexMountView`** returns 501 if hit directly; normal traffic is handled by the ASGI dispatcher.
- **Catch-all must stay last** in `urlpatterns`.

---

**Navigation:** [← Configuration](configuration.md) | [Pages in views.py →](pages_in_views.md)
