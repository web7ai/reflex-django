# Migrating to the Django-outer, single-port architecture

`reflex-django` ships a new default routing mode (`UrlRoutingMode.DJANGO_OUTER`)
that makes Django the outer ASGI application on a single port. Existing
projects continue to work in the legacy `reflex_led` / `django_led` modes; this
guide explains how to upgrade.

## TL;DR

```python
# config/asgi.py
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
from reflex_django.asgi_entry import application  # noqa: E402,F401
```

Run with any ASGI server:

```bash
uvicorn config.asgi:application --host 0.0.0.0 --port 8000
```

Or use the new `manage.py run_reflex` (handles Vite for dev automatically):

```bash
python manage.py run_reflex
```

Open `http://localhost:8000/`.

## What changes

- **One port instead of two.** Vite still runs (for HMR), but only Django
  exposes a port. Django reverse-proxies `/` to Vite when `DEBUG=True`.
- **Django is the outer ASGI app.** Reflex's `_event`, `_upload`, `_health`,
  `ping`, and `_all_routes` endpoints are mounted under Django.
- **The full `settings.MIDDLEWARE` chain runs on every Reflex event.**
  Previously only `SessionMiddleware`, `AuthenticationMiddleware`, and
  `LocaleMiddleware` ran. Now all of your middleware (custom or built-in)
  sees Reflex events as Django requests.
- **`self.response` / `self.messages` / `self.csrf_token` are new.** Handlers
  can read the response produced by the middleware chain, the active Django
  messages list, and the request's CSRF token.
- **Middleware-driven redirects auto-translate to `rx.redirect`.** Custom
  `LoginRequiredMiddleware` style code can just return an `HttpResponseRedirect`
  and the SPA will navigate.

## What stays the same

- `self.request`, `self.user`, `self.session`, `self.has_perm`,
  `self.login`, `self.logout` all work as before.
- `DjangoUserState`'s existing fields (`is_authenticated`, `username`, etc.)
  still update each event.
- `rxconfig.py` does not need to change; the plugin auto-detects the routing
  mode.
- `reflex run --backend-only`, `reflex export`, and Reflex's other CLI
  commands are still available.

## Step-by-step migration

### 1. Update `config/asgi.py`

Replace the file with:

```python
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from reflex_django.asgi_entry import application  # noqa: E402,F401
```

If you keep `from django.core.asgi import get_asgi_application` lying around
elsewhere, that is fine — the new `application` already calls Django's ASGI
internally.

### 2. (Optional) Pin the routing mode

If you previously ran `REFLEX_LED` or `DJANGO_LED` deliberately and want to
keep them, set:

```python
# settings.py
REFLEX_DJANGO_URL_ROUTING = "reflex_led"   # or "django_led"
```

Otherwise, leave it on `"auto"`; the default is `django_outer`.

### 3. Production: collect the SPA

When running with `DEBUG=False`, Django serves the SPA bundle from
`STATIC_ROOT/_reflex/` (or `STATIC_ROOT/_static/`). The deploy sequence is:

```bash
reflex export                          # builds .web/_static
python manage.py collectstatic         # copies into STATIC_ROOT
uvicorn config.asgi:application \
    --host 0.0.0.0 --port 8000 \
    --workers 2
```

Add to `STATICFILES_DIRS`:

```python
import pathlib

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
STATICFILES_DIRS = [BASE_DIR / ".web" / "_static"]
```

…or copy the bundle manually from `.web/_static` to `STATIC_ROOT/_reflex/`.

### 4. Remove obsolete bits

If your `rxconfig.py` registered the plugin with `api_transformer=...`
manually, you can drop it — the plugin automatically skips
`api_transformer` wiring in `DJANGO_OUTER` mode (Django is no longer
mounted inside Reflex).

If you patched `.web/vite.config.js` by hand to add server proxies, you can
remove that patch. The new mode does not need Vite to proxy backend paths;
Django does the proxying.

### 5. Use the new APIs

In your event handlers:

```python
class HomeState(rx.AppState):
    @rx.event
    async def post_form(self):
        from django.contrib import messages
        messages.success(self.request, "Profile updated")
        # The new event will see this in self.messages and DjangoUserState.messages
```

In your UI:

```python
def message_banner():
    return rx.foreach(
        DjangoUserState.messages,
        lambda m: rx.callout(m.message, color_scheme=m.level_tag),
    )
```

For non-Reflex `<form>` posts to Django:

```python
def manual_django_form():
    return rx.box(
        rx.el.form(
            rx.el.input(type="hidden", name="csrfmiddlewaretoken",
                        value=DjangoUserState.csrf_token),
            ...,
            method="POST", action="/api/upload",
        ),
    )
```

## Rollback

If you hit a blocker, set:

```bash
REFLEX_DJANGO_URL_ROUTING=reflex_led
```

…or, in `settings.py`:

```python
REFLEX_DJANGO_URL_ROUTING = "reflex_led"
```

…and rerun `python manage.py run_reflex`. The legacy two-port flow is
preserved.

## Disabling specific behaviors

| Setting | Effect when set to `False` |
| --- | --- |
| `REFLEX_DJANGO_RUN_MIDDLEWARE_CHAIN` | Skip the full chain; only session/auth/locale run (legacy behavior). |
| `REFLEX_DJANGO_AUTO_REDIRECT_FROM_MIDDLEWARE` | Stop converting 3xx responses to `rx.redirect`. |
| `REFLEX_DJANGO_MIRROR_MESSAGES` | Stop populating `DjangoUserState.messages`. |
| `REFLEX_DJANGO_MIRROR_CSRF` | Stop populating `DjangoUserState.csrf_token`. |
| `REFLEX_DJANGO_MIRROR_LANGUAGE` | Stop populating `DjangoUserState.language*`. |
| `REFLEX_DJANGO_DEV_PROXY` | Disable Django's reverse-proxy of `/` to Vite. |
