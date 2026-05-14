# reflex-django

## Table of contents

1. [About reflex-django](#about-reflex-django)
2. [Architecture](#architecture)
3. [How to set up](#how-to-set-up)
4. [Commands](#commands)
5. [States, context, and bridges](#states-context-and-bridges)

---

## About reflex-django

**reflex-django** is a [Reflex](https://reflex.dev) plugin that runs a **Django ASGI** application and your **Reflex** app in **one process** under a single dev command (`reflex run`). HTTP requests whose paths match configured prefixes (for example Django Admin, optional API routes, and path-based static URLs) are forwarded to Django. Everything else—including the compiled Reflex frontend and Reflex’s Socket.IO event channel under `/_event/…`—is handled by Reflex.

**Why it exists.** Reflex gives you a Python-first reactive UI. Django gives you the ORM, migrations, the admin, sessions, authentication, internationalization, and the ecosystem of HTTP views and middleware you already rely on. reflex-django lets you keep that Django surface area without standing up a separate HTTP server for local development or simple deployments, while still using Reflex for the interactive UI.

**Why Django developers need it.** Reflex user actions arrive over WebSocket events, not through Django’s normal request/response cycle, so Django’s HTTP middleware (sessions, auth, locale) does not run for those events by default. reflex-django adds an explicit **event bridge** that rebuilds a synthetic `HttpRequest` from the browser data Reflex provides, attaches the session and user, and exposes that request through small APIs your event handlers can call. A separate **HTTP bridge** routes ordinary browser HTTP traffic on selected path prefixes to Django’s ASGI app. Together, these bridges make Django session auth and related patterns usable from Reflex without pretending the two stacks share one router.

**Author.** This package is written by **Mohannad Irshedat**.

| Topic   | Versions |
|---------|----------|
| Django  | 6.0.x    |
| Python  | 3.12+    |

---

## Architecture

At a high level, reflex-django does three coordinated things:

1. **Plugin bootstrap** — When `rxconfig.py` is loaded, `ReflexDjangoPlugin` sets `DJANGO_SETTINGS_MODULE` (if you pass `settings_module`), exports path prefix environment variables used by Django settings, and calls `configure_django()` so Django is initialized before your Reflex app module imports models or translation helpers.

2. **HTTP ASGI composition** — After Reflex compiles your app, the plugin appends an `api_transformer` that wraps Reflex’s inner ASGI app. Incoming HTTP (and WebSocket upgrade traffic where applicable) is dispatched by **URL path prefix**: matching prefixes go to Django’s ASGI application (optionally wrapped for static files); non-matching traffic stays on Reflex. ASGI lifespan events are owned by Reflex.

3. **Per-event Django context** — When `install_event_bridge` is true (the default), Reflex registers `DjangoEventBridge` middleware. On each Reflex event, the bridge builds a synthetic `django.http.HttpRequest` from `event.router_data` (cookies, headers, client IP, path), loads the Django session, optionally applies the same locale negotiation as `LocaleMiddleware`, resolves `request.user` via Django’s async `aget_user`, and binds that request on a **context variable** for the duration of the event. Your handlers call `current_user()`, `current_request()`, and related helpers, which read that binding.

PyPI and other indexes **do not resolve relative image paths** in the project description. Use an **absolute URL** (below) and keep `img.png` on your GitHub default branch, or change the URL to match your fork and branch name.

![reflex-django architecture](https://raw.githubusercontent.com/mohannadirshedat/reflex-django/main/img.png)

ASCII overview (same idea everywhere, including plain-text viewers):

```text
Browser
  │ HTTP (paths under admin / api / static …)
  ├──────────────────────────────► Django ASGI
  │
  │ HTTP + Socket.IO (Reflex UI, /_event/ …)
  └──────────────────────────────► Reflex ASGI (prefix dispatcher)
                                           │
                                           ▼
                               Reflex event → DjangoEventBridge
                                           → contextvars (current_request, …)
                                           → your @rx.event handlers
```

---

## How to set up

Use **uv** to create a project, add dependencies, scaffold the Reflex frontend, create a Django project, then wire the plugin in `rxconfig.py`.

1. Initialize a Python project:

   ```bash
   uv init
   ```

2. Add Reflex and reflex-django:

   ```bash
   uv add reflex reflex-django
   ```

3. Initialize the Reflex frontend (app name and layout follow Reflex’s CLI):

   ```bash
   uv run reflex init frontend
   ```

4. Create a Django project package named `backend` (adjust the name if you prefer):

   ```bash
   uv run django-admin startproject backend .
   ```

   This typically produces `backend/settings.py`, `backend/urls.py`, and `manage.py` in the current directory.

5. Configure **`rxconfig.py`** so Reflex loads Django with your settings module. Import the plugin and pass `settings_module` as the dotted path to your Django settings (for example `backend.settings`):

   ```python
   import reflex as rx
   from reflex_django import ReflexDjangoPlugin

   config = rx.Config(
       app_name="myapp",
       plugins=[
           ReflexDjangoPlugin(settings_module="backend.settings"),
       ],
   )
   ```

**Minimal Django expectations.** Your `INSTALLED_APPS` should include the Django contrib apps you need (for example `django.contrib.auth`, `django.contrib.sessions`, and often `django.contrib.admin`) and **`reflex_django`** if you use bundled helpers. Set `ROOT_URLCONF` and mount admin (and any HTTP routes under an optional `backend_prefix`) so path-based routing matches what you configure on `ReflexDjangoPlugin`. Run the app with:

```bash
uv run reflex run
```

---

## Commands

reflex-django registers a **`django`** command group on the **`reflex`** CLI (via a small import hook installed with the package) and also ships a standalone console script **`reflex-django`**.

**Running Django management commands**

- Through Reflex:

  ```bash
  uv run reflex django migrate
  uv run reflex django makemigrations
  uv run reflex django createsuperuser
  uv run reflex django shell
  uv run reflex django collectstatic
  uv run reflex django help
  ```

- Through the standalone entry point (equivalent forwarding for normal manage.py subcommands):

  ```bash
  uv run reflex-django migrate
  uv run reflex-django help
  ```

Any subcommand name other than the special cases below is forwarded to Django’s `execute_from_command_line`. The wrapper first loads your **`rxconfig`** (so `ReflexDjangoPlugin` can set `DJANGO_SETTINGS_MODULE` and path prefixes) and then calls **`configure_django()`**, so the same settings module Reflex uses at runtime is used for migrations and other management commands.

**Init scaffolding (omitted here).** `reflex django init` and `reflex-django init` exist to scaffold a starter tree but are considered **beta**; this README does not document them. Prefer the manual flow in [How to set up](#how-to-set-up) above.

---

## States, context, and bridges

This section walks through Reflex state, Django’s per-event request context (context variables), the two bridges, and the helper states that mirror Django into Reflex UI state—each with a small example.

### Reflex `rx.State` (baseline)

In Reflex, a **State** class subclasses `rx.State`. Fields you declare are synchronized with the client where appropriate; values must be **JSON-serializable** when they cross the wire. You define event handlers with `@rx.event` (often `async def` when you call async Django APIs).

```python
import reflex as rx


class CounterState(rx.State):
    count: int = 0

    @rx.event
    def increment(self):
        self.count += 1
```

### Per-event Django context (`reflex_django.context`)

Reflex events do not carry a Django `HttpRequest` object. reflex-django stores the synthetic request built for the current event on a **context variable**. Public read helpers:

| Function | Role |
|----------|------|
| `current_request()` | Bound `HttpRequest` or `None` outside an event without the bridge |
| `current_user()` | Django user or `AnonymousUser` |
| `current_session()` | Session backend instance or `None` |
| `current_language()` | Active language code after locale activation |

Lower-level **`begin_event_request(request)`** and **`end_event_request()`** are used by the bridge and for tests or advanced scenarios; application code normally relies on the helpers above inside `@rx.event` handlers.

```python
import reflex as rx
from reflex_django import current_user


class WhoamiState(rx.State):
    label: str = ""

    @rx.event
    async def refresh(self):
        user = current_user()
        self.label = user.get_username() if user.is_authenticated else "anonymous"
```

### Bridge 1 — HTTP ASGI path dispatcher

`ReflexDjangoPlugin` installs an **`api_transformer`** that wraps Reflex’s ASGI app. Requests whose path starts with any configured prefix are sent to Django’s ASGI app; other paths stay on Reflex. Relevant plugin arguments:

| Argument | Meaning |
|----------|---------|
| `backend_prefix` | Optional prefix for your own Django HTTP routes (for example `"/api"`) |
| `admin_prefix` | Prefix for Django Admin (default `"/admin"`) |
| `extra_prefixes` | Additional path prefixes routed to Django |
| `install_event_bridge` | When `True`, registers `DjangoEventBridge` (default) |

```python
ReflexDjangoPlugin(
    settings_module="backend.settings",
    backend_prefix="/api",
    admin_prefix="/admin",
    extra_prefixes=("/billing",),
)
```

Your `ROOT_URLCONF` must define routes under those prefixes so Django can serve them.

### Bridge 2 — `DjangoEventBridge` (Reflex middleware)

**`DjangoEventBridge`** runs at the start of each Reflex event. It constructs a synthetic `HttpRequest`, attaches the session, optionally runs locale negotiation when `USE_I18N` and `REFLEX_DJANGO_I18N_EVENT_BRIDGE` allow it, and sets `request.user` using **`aget_user`**. It then calls `begin_event_request(request)` so `current_user()` and friends work in your handlers.

To disable this behavior (for example if you do not use Django session auth from Reflex):

```python
ReflexDjangoPlugin(settings_module="backend.settings", install_event_bridge=False)
```

### `DjangoUserState`

**`DjangoUserState`** is a `rx.State` subclass that mirrors a JSON-safe snapshot of the current user (`user_id`, `username`, `email`, names, `is_authenticated`, staff/superuser flags, optional `group_names`). Use it for navbar and conditional UI.

- Call **`sync_from_django`** from a page’s **`on_load`** (it is an `@rx.event`).
- After login or logout, call **`await self.refresh_django_user_fields()`** from an async handler so the snapshot updates without a full navigation when appropriate.

Server-side authorization must still use **`current_user()`** (or stricter checks); client-visible state is for display only.

```python
import reflex as rx
from reflex_django import DjangoUserState


class AuthState(DjangoUserState):
    pass


app = rx.App()

# app.add_page(index, on_load=AuthState.sync_from_django)
```

### `DjangoI18nState`

**`DjangoI18nState`** exposes **`django_language_code`** and **`django_language_bidi`**, aligned with Django’s active language after the event bridge. Use **`sync_from_django`** on `on_load`, or **`await self.refresh_django_i18n_fields()`** after the user changes language via a Django-served view.

```python
import reflex as rx
from reflex_django import DjangoI18nState


app = rx.App()

# app.add_page(home, on_load=DjangoI18nState.sync_from_django)
```

### Reflex-facing Django context (processors and `DjangoContextState`)

Reflex serializes state to the browser, so any dict you merge into Reflex state must be **JSON-serializable**.

**Two configuration modes** (see `reflex_django.reflex_context`):

1. **`REFLEX_DJANGO_CONTEXT_PROCESSORS`** — A non-empty tuple of dotted paths to callables `(request) -> dict` (or async). When this list is set, it is used exclusively. You are responsible for JSON-safe values.

2. **Template context processors** — If `REFLEX_DJANGO_CONTEXT_PROCESSORS` is empty and **`REFLEX_DJANGO_USE_TEMPLATE_CONTEXT_PROCESSORS`** is `True`, the same dotted paths as in `TEMPLATES[*].OPTIONS["context_processors"]` are run, with built-in sanitization (for example `user` becomes a snapshot; `request`, `perms`, `messages` are omitted; other values must pass plain `json.dumps`).

Built-in processor callables you can list explicitly:

- **`reflex_django.reflex_context.builtin_user_context`** — adds a template-shaped `user` key as a snapshot dict.
- **`reflex_django.reflex_context.builtin_i18n_context`** — adds `LANGUAGE_CODE`, `LANGUAGE_BIDI`, and `LANGUAGES`.

Example settings snippet:

```python
REFLEX_DJANGO_CONTEXT_PROCESSORS = (
    "reflex_django.reflex_context.builtin_user_context",
    "reflex_django.reflex_context.builtin_i18n_context",
)
```

**`collect_reflex_context(request)`** runs the configured processor list and returns one merged dict. You can await it inside a handler when `current_request()` is bound:

```python
from reflex_django import current_request
from reflex_django.reflex_context import collect_reflex_context


@rx.event
async def debug_context(self):
    merged = await collect_reflex_context(current_request())
    # use merged (e.g. assign JSON-safe keys to state)
```

**`DjangoContextState`** holds **`django_context`** and a stringified **`django_context_json`**. Call **`load_django_context`** from `on_load` to populate them from processors using the bound request:

```python
from reflex_django import DjangoContextState


# app.add_page(about, on_load=DjangoContextState.load_django_context)
```

Helper functions **`template_context_processor_paths()`** and **`reflex_context_processor_paths()`** introspect settings for tooling or documentation.

### `user_snapshot` vs `current_user`

**`user_snapshot(user)`** returns the same flat dict shape used by `DjangoUserState`, given a user instance. It is useful in custom context processors, tests, or logging—without touching Reflex state.

**`current_user()`** returns the live Django user (or anonymous) for the **current Reflex event** after the bridge runs. Use it for **permissions, ownership checks, and mutations** on the server.

**`DjangoUserState`** fields are a **UI snapshot**; always re-check authorization with `current_user()` (or equivalent) inside event handlers that change data.

```python
from reflex_django import current_user
from reflex_django.auth_state import user_snapshot


@rx.event
async def audit_banner(self):
    self.snapshot_json = user_snapshot(current_user())  # dict for display
    assert current_user().is_authenticated  # real check for protected actions
```
