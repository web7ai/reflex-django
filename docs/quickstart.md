# Quickstart

A minimal **reflex-django** app in four steps: Django `settings.py`, `urls.py`, Reflex pages in `views.py`, and `AppState` for the logged-in user.

**Time:** ~10 minutes · **Command:** `python manage.py run_reflex` · **Port:** `8000` (Django + Reflex on one port)

---

## 1. Create the project

```bash
mkdir myshop && cd myshop
uv init
uv add django reflex reflex-django
uv run django-admin startproject config .
uv run python manage.py startapp shop
```

```text
myshop/
├── manage.py
├── config/
│   ├── settings.py    ← step 2
│   ├── urls.py        ← step 3
│   └── asgi.py        ← step 4
└── shop/
    └── views.py       ← step 5 (pages + state)
```

---

## 2. `settings.py` — register Django + reflex-django

Three things matter:

1. **`reflex_django` and your app** in `INSTALLED_APPS`
2. **Session + auth middleware** (so `AppState` can see the user)
3. **`AsyncStreamingMiddleware` last** (ASGI-safe admin/static streaming)

```python
# config/settings.py
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = "change-me-in-production"
DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "reflex_django",
    "shop",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "reflex_django.streaming_middleware.AsyncStreamingMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
```

Every middleware listed here runs on every Reflex event too — `request.user`, `request.session`, `request._messages`, locale, and your custom middleware all populate before each `@rx.event` handler executes. See [AsyncStreamingMiddleware](async_streaming_middleware.md) for why the streaming middleware sits at the end.

---

## 3. `urls.py` — wire Reflex with `reflex_mount()`

Django routes come **first**. `reflex_mount()` last.

```python
# config/urls.py
from django.contrib import admin
from django.urls import path

from reflex_django.urls import reflex_mount

urlpatterns = [
    path("admin/", admin.site.urls),
]

urlpatterns += [
    reflex_mount(
        app_name="shop",
        django_prefix=("/admin",),
        rx_config={"backend_port": 8000},
    ),
]
```

| Argument | Meaning |
|:---|:---|
| `app_name="shop"` | Pages live in `shop/views.py` |
| `django_prefix` | Path prefixes Django owns (must match `path("admin/", ...)` above) |
| `rx_config` | Reflex ports and other allowed `rx.Config` keys |

You do **not** create `shop/shop.py`. Reflex loads the app from `reflex_django.django_led_app`.

---

## 4. `asgi.py` — single ASGI entry point

```python
# config/asgi.py
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
from reflex_django.asgi_entry import application  # noqa: E402,F401
```

`reflex_django.asgi_entry.application` is the outer dispatcher: it sends Reflex's `/_event`, `/_upload`, and `/_health` paths to Reflex's inner ASGI, and everything else to Django. Both deployment and `manage.py run_reflex` point at this same callable.

---

## 5. `views.py` — pages and `AppState`

### Pages with `@template`

`@template` registers a route and wraps content in a layout.

```python
# shop/views.py
import reflex as rx
from reflex_django import template
from reflex_django.state import AppState


class HomeState(AppState):
    greeting: str = "Hello!"

    @rx.event
    async def on_load(self):
        if self.request.user.is_authenticated:
            self.greeting = f"Hi, {self.request.user.get_username()}!"
        else:
            self.greeting = "Hello, guest — log in at /admin/"


@template(route="/", title="Home", on_load=HomeState.on_load)
def index() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.heading("My Shop"),
            rx.text(HomeState.greeting),
            rx.link("About", href="/about"),
            spacing="4",
        ),
        min_height="70vh",
    )


@template(route="/about", title="About")
def about() -> rx.Component:
    return rx.text("This page lives in shop/views.py — not a Django path().")
```

### How `AppState` exposes Django

| In event handlers (`@rx.event`) | In the UI |
|:---|:---|
| `self.request` — synthetic `HttpRequest` from the full middleware chain | `self.is_authenticated` |
| `self.user` — `request.user` (already resolved, async-safe) | `self.username`, `self.email` |
| `self.session` — async session (`await session.aget(...)` / `asave()`) | — |
| `self.messages` — JSON-safe snapshot of `django.contrib.messages` | `DjangoUserState.messages` (reactive) |
| `self.csrf_token` — CSRF token for the current request | `DjangoUserState.csrf_token` (reactive) |
| `self.response` — `HttpResponse` produced by middleware | — |
| `self.django_context` — context-processor keys | Copy into reactive vars in `on_load` |
| `await self.has_perm("app.change_model")` | `DjangoUserState.perms` |

Reflex events run over WebSocket. The bridge builds a Django request, walks `settings.MIDDLEWARE`, eager-resolves `request.user`, and binds everything before your handler runs. You do not need `await self.load_django_context()` unless you want a mid-handler refresh — context processors load automatically.

**Do not** read `request.user` in class-level defaults (import-time crash with `AppRegistryNotReady`):

```python
message: str = f"Hi {request.user}"           # wrong — runs at import time

@rx.event
async def on_load(self):                      # right — runs on every event
    if self.request.user.is_authenticated:
        self.message = f"Hi, {self.request.user.get_username()}"
```

### Django template tags in the SPA shell

The compiled `index.html` is piped through Django's template engine before it leaves the server (`REFLEX_DJANGO_RENDER_SPA_VIA_TEMPLATE_ENGINE = True` by default). Inside the shell you can use `{{ request.user }}`, `{% csrf_token %}`, `{% load i18n %}`, and any context-processor key. Inside Reflex components (`.py` files compiled to React) use reactive vars instead — `DjangoUserState.username`, `DjangoUserState.csrf_token`, `self.django_context[...]`.

---

## 6. Run

```bash
uv run python manage.py migrate
uv run python manage.py run_reflex
```

`run_reflex` will:

1. Auto-export the Reflex SPA into `STATIC_ROOT/_reflex/` (frontend-only, no zip).
2. Start `uvicorn` as a subprocess on port `8000` pointed at `reflex_django.asgi_entry:application`.
3. Watch your project tree for `.py` changes — every change triggers a clean re-export + uvicorn restart.

```text
http://localhost:8000/           Home page (SPA)
http://localhost:8000/about      About page (SPA)
http://localhost:8000/admin/     Django admin
http://localhost:8000/_event     Reflex Socket.IO endpoint
```

Optional — test login:

```bash
uv run python manage.py createsuperuser
```

Log in at `/admin/`, then refresh `/` — `HomeState.greeting` should show your username.

---

## 7. Speed up the dev loop

If your edits are Python/Django-only and don't touch Reflex pages, skip the SPA re-export on each restart:

```bash
python manage.py run_reflex --skip-rebuild
```

If you prefer the legacy hot-module-reload experience with a Vite dev server proxied through Django:

```bash
python manage.py run_reflex --with-vite
```

---

## Cheat sheet

| File | Responsibility |
|:---|:---|
| `settings.py` | Django apps, middleware, database |
| `urls.py` | `reflex_mount(...)` — app name, Django prefixes, ports |
| `config/asgi.py` | Points at `reflex_django.asgi_entry:application` |
| `{app}/views.py` | `@template` pages + `AppState` classes |
| `manage.py run_reflex` | Auto-export + serve + watch (the dev loop) |
| `manage.py export_reflex` | Build the SPA bundle (CI / pre-deploy) |

No hand-maintained `rxconfig.py` required — `reflex_mount()` provides the runtime config in memory.

---

## Troubleshooting

| Problem | Fix |
|:---|:---|
| 404 on `/` after first run | Re-run `python manage.py run_reflex` so the auto-export stages the bundle into `STATIC_ROOT/_reflex/`; or run `python manage.py export_reflex --frontend-only --no-zip --stage-to-static-root` explicitly. |
| Guest after admin login | Keep `SessionMiddleware` + `AuthenticationMiddleware` in `MIDDLEWARE`. |
| `AppRegistryNotReady` on startup | Don't use `request.user` in class-level state defaults; move it into `@rx.event` / `on_load`. |
| `ModuleNotFoundError: shop.shop` | Don't add `shop/shop.py`; `reflex_mount(app_name="shop")` uses `shop/views.py`. |
| Admin warnings about streaming responses | Add `reflex_django.streaming_middleware.AsyncStreamingMiddleware` at the end of `MIDDLEWARE`. |
| `{{ request.user }}` not rendering | That syntax only works in the SPA shell `index.html` (server-side). Use `DjangoUserState.username` inside Reflex components. |
| Re-export feels slow | Pass `--skip-rebuild` if your edits don't touch Reflex pages, or `--with-vite` to use the Vite HMR loop. |

---

**Navigation:** [← Configuration](configuration.md) | [AsyncStreamingMiddleware →](async_streaming_middleware.md) | [Existing Django Project →](existing_django_project.md)
