# reflex-django

## Table of contents

1. [About reflex-django](#about-reflex-django)
2. [Architecture](#architecture)
3. [How to set up](#how-to-set-up)
4. [Commands](#commands)
5. [States, context, and bridges](#states-context-and-bridges)
6. [Declarative session login (mixins)](#declarative-session-login-mixins)
7. [Declarative model CRUD (mixins)](#declarative-model-crud-mixins)

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

This section walks through Reflex state, Django’s per-event request context (context variables), the two bridges, and the helper states that mirror Django into Reflex UI state—each with a small example. For **declarative Django session login/logout** as a generated `rx.State` subclass, see [Declarative session login (mixins)](#declarative-session-login-mixins). For **declarative Django model CRUD**, see [Declarative model CRUD (mixins)](#declarative-model-crud-mixins) below.

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

**Development vs production routing**

- **Development** (`reflex run`): Reflex runs Vite on `frontend_port` and the ASGI backend on `backend_port`. The plugin injects matching `server.proxy` rules into `.web/vite.config.js` so Django prefixes (`/admin`, `/api`, `extra_prefixes`, etc.) work from the **frontend URL** (for example `http://localhost:3000/admin`). You can also use the backend URL directly (`http://localhost:8000/admin`).
- **Production** (`reflex run --env prod`): A single server serves the compiled frontend and the backend. The same path-prefix dispatcher applies. The plugin also patches Reflex's catch-all `StaticFiles` mount so WebSocket connections (for example Socket.IO at `/_event`) are not routed into `StaticFiles`, which only accepts HTTP.

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

---

## Canned authentication pages

Inspired by [reflex-local-auth](https://github.com/masenf/reflex-local-auth), **reflex-django** ships ready-made login, registration, and password-reset pages backed by **Django sessions** and the stock **`User`** model.

### Quick start

In **`django_settings.py`** (or your settings module):

```python
REFLEX_DJANGO_AUTH = {
    "SIGNUP_ENABLED": True,
    "PASSWORD_RESET_ENABLED": True,
    "LOGIN_URL": "/login",
    "SIGNUP_URL": "/register",
    "LOGIN_REDIRECT_URL": "/",
    # "LOGIN_FIELDS": ["username"],           # default
    # "LOGIN_FIELDS": ["email"],              # email only
    # "LOGIN_FIELDS": ["username", "email"],  # username or email
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "noreply@localhost"
```

In your Reflex app module:

```python
import reflex as rx
from reflex_django.auth import add_auth_pages, login_required, routes
from reflex_django.auth.state import DjangoAuthState

app = rx.App()
add_auth_pages(app)

@rx.page()
@login_required
def dashboard():
    return rx.heading("Members only")
```

### Settings (`REFLEX_DJANGO_AUTH`)

| Key | Default | Purpose |
|-----|---------|---------|
| `ENABLED` | `True` | Master switch for canned pages |
| `SIGNUP_ENABLED` | `True` | Register page at `SIGNUP_URL` |
| `PASSWORD_RESET_ENABLED` | `True` | Forgot-password flow |
| `LOGIN_URL` | `/login` | Login route (also used by `login_required` on event handlers) |
| `SIGNUP_URL` | `/register` | Registration route |
| `PASSWORD_RESET_URL` | `/password-reset` | Request reset email |
| `PASSWORD_RESET_CONFIRM_URL` | `/password-reset/confirm/[uid]/[key]` | Set new password (`[key]` avoids clashing with Reflex's session `token`; `[token]` still supported) |
| `LOGIN_REDIRECT_URL` | `/` | After successful login |
| `LOGOUT_REDIRECT_URL` | `/login` | After logout |
| `SIGNUP_REDIRECT_URL` | `/login` | After registration (auto sign-in) |
| `REDIRECT_AUTHENTICATED_USER` | `/` | When visiting login/register while signed in |
| `LOGIN_FIELDS` | `["username"]` | Login identifier(s): `"username"`, `"email"`, or both (e.g. `["username", "email"]`) |
| `EMAIL_REQUIRED` | `False` | Require email on signup |
| `PASSWORD_MIN_LENGTH` | `8` | Minimum password length |
| `MESSAGES` | (built-in dict) | User-facing copy |

Legacy **`REFLEX_DJANGO_LOGIN_URL`** is still read when `LOGIN_URL` is omitted from the dict.

### Security notes

- **`@login_required`** on pages only redirects in the UI (like reflex-local-auth). Use **`@login_required`** on event handlers or **`require_login_user()`** when handlers return private data.
- Password-reset emails use Django’s token generator; use a stable **`SECRET_KEY`** in production.
- Registration creates active users immediately; set **`SIGNUP_ENABLED=False`** if only admins should create accounts.

### Customization

- Import **`reflex_django.auth.pages`** and register your own components on the same routes.
- Subclass or extend **`DjangoAuthState`** (built from session login + registration + reset mixins).
- For hand-built forms, keep using **`session_auth_mixin`** (see below).

---

## Declarative session login (mixins)

**`reflex_django.mixins.session_auth`** (re-exported from **`reflex_django.mixins`**) builds a Reflex **`rx.State`** subclass from a frozen **`SessionAuthConfig`**: username/password/error string fields, input setters, an **`on_load`**-style handler that refreshes **`DjangoUserState`** and optionally redirects already-authenticated users, **`submit_login`** (async **`aauthenticate`** / **`alogin`** on **`current_request()`**), optional **`submit_login_form`** (same flow using **`form_data`** from **`rx.form.root`** — avoids stale bound fields on fast submit), and **`logout`** (**`alogout`** then navigation).

Successful login calls **`await request.session.asave()`** then mirrors the new session key into **`document.cookie`** via **`rx.call_script`** (see **`reflex_django.session_js`**) and performs a short deferred full-page navigation. Reflex’s synthetic request path does not run Django’s **`SessionMiddleware`**, so **`rx.redirect`** alone often leaves the browser without an updated **`sessionid`**; **`logout`** clears the cookie the same way before navigating.

**Requirements.** The **event bridge** must be enabled so **`current_request()`** carries the session for each Reflex event. Django 6+ async auth (**`django.contrib.auth`**) is used inside handlers.

### How it works

1. Define **`SessionAuthConfig`** with redirect paths (for example **`post_login_redirect`**, **`post_logout_redirect`**, **`redirect_when_authenticated`** or `None` to skip).
2. Call **`session_auth_mixin(cfg, base=DjangoUserState)`** (or **`base=`** your app state that already subclasses **`DjangoUserState`**). The returned class is named **`SessionAuthState`** by default (see **`state_class_name`** in config).
3. Subclass it if you want a stable app-specific name (for example **`LoginState`**).

**`state_module=`** defaults to the caller’s **`__name__`** so the generated class is registered on **`sys.modules`** for Reflex pickling.

### Example

```python
import reflex as rx
from reflex_django.auth_state import DjangoUserState
from reflex_django.mixins.session_auth import SessionAuthConfig, session_auth_mixin

_LOGIN_CFG = SessionAuthConfig(
    post_login_redirect="/notes",
    post_logout_redirect="/login",
    redirect_when_authenticated="/notes",
)


class LoginState(session_auth_mixin(_LOGIN_CFG, base=DjangoUserState)):
    """Login page; wire ``on_load=LoginState.on_load_login``, etc."""

# app.add_page(login_page, route="/login", on_load=LoginState.on_load_login)
```

Configurable **`SessionAuthConfig`** fields include **`username_var`**, **`password_var`**, **`error_var`**, event names (**`on_load_event`**, **`submit_event`**, **`logout_event`**, optional **`submit_form_event`** defaulting to **`submit_login_form`** — set to **`None`** to omit), **`form_username_key`** / **`form_password_key`** (HTML field names for the form submit handler, default **`username`** / **`password`**), message strings **`session_unavailable_message`** / **`invalid_credentials_message`**, and **`state_class_name`** (defaults to **`SessionAuthState`**; set a unique value if you generate more than one session-auth state under the same **`base=`** parent, since Reflex disallows duplicate substate names).

---

## Model serializers (DRF-style, no DRF)

**`reflex_django.serializers.ReflexDjangoModelSerializer`** turns Django models into JSON-friendly row dicts for Reflex state—same ergonomics as DRF’s `Serializer(queryset, many=True).data`, without `djangorestframework`.

```python
from reflex_django.auth.shortcuts import require_login_user
from reflex_django.serializers import ReflexDjangoModelSerializer

class NoteSerializer(ReflexDjangoModelSerializer):
    class Meta:
        model = Note
        fields = ("id", "title", "content", "created_at")
        # or: exclude = ("user",)

async def _load_notes(self) -> None:
    self.notes_error = ""
    user = require_login_user()
    qs = Note.objects.filter(user=user).order_by("-created_at")
    self.notes = await NoteSerializer(qs, many=True).adata()
```

- **One assignment** — the serializer iterates the queryset internally (no manual `async for` + `append`).
- **`NoteSerializer(note).data`** for a single instance.
- **`row_serializer_class=NoteSerializer`** on **`ModelCRUDConfig`** wires the same serializer into **`crud_mixin`** refresh.
- Low-level **`serialize_model_row`** remains available in **`reflex_django.serialization`**.

---

## Declarative model CRUD (mixins)

**`reflex_django.mixins.crud`** (also re-exported from **`reflex_django.mixins`**) builds a Reflex **`rx.State`** subclass from a small declarative config so you can list, create, edit, and delete rows of a Django model without hand-writing the same event wiring each time.

**Requirements.** Django must be configured (plugin + `INSTALLED_APPS` including your app and auth/session as usual). The **event bridge** must be enabled so `login_required` and `require_login_user()` see the session user. CRUD handlers use the default **`login_required`** wrapper (anonymous users are redirected; login URL from `REFLEX_DJANGO_LOGIN_URL` unless you customize handlers yourself—see **`reflex_django.auth.decorators`**).

### How it works

1. You define a frozen **`ModelCRUDConfig`** pointing at your **`models.Model`**, the state attribute names you want on the client (`list_var`, `error_var`), which model fields appear in create/edit forms (`form_fields`), and optional **`owner_field`** (for example `"user"`) so queries and writes are scoped to **`require_login_user()`**.
2. You call **`crud_mixin(cfg, base=…)`**. It returns a new class named **`{Model.__name__}CRUDState`** with:
   - A **list** of row dicts under `list_var` (default serializer includes all concrete fields—`created_at`, `updated_at`, etc.—even when Django 6+ `model_to_dict` omits non-editable auto fields; values are JSON-friendly strings for datetimes/dates).
   - String fields **`form_<name>`** and **`edit_<name>`** for each entry in `form_fields`, plus **`editing_id`** (`-1` when not editing).
   - **`refresh_method`**: async reload from the ORM (respects `owner_field`, `ordering`).
   - **`on_load_event`**: async `on_load` target to call your refresh (login required).
   - **`add_event`** / **`delete_event`**: create and delete (login required).
   - **`start_edit`**, **`save_edit`**, **`cancel_edit`**: edit lifecycle (`cancel_edit` clears local edit state only and is not login-gated).
   - **`set_form_<field>`** / **`set_edit_<field>`**: `@rx.event` setters for inputs.
3. You **subclass** that generated class when you need a stable app-specific name or extra state:

   ```python
   from reflex_django.states import AppState

   class MyAppState(AppState):
       pass

   class NotesState(crud_mixin(_NOTE_CRUD_CONFIG, base=MyAppState)):
       """Domain CRUD; shared routing lives on ``MyAppState``."""
   ```

**`base=`** should be your app’s shared :class:`~reflex_django.states.AppState` subclass (domain/routing). Use :class:`~reflex_django.DjangoUserState` for auth snapshots, not as the CRUD base.

**`state_module=`** defaults to the **calling module’s** `__name__` so the dynamic class is registered on **`sys.modules`** for Reflex pickling. Pass it explicitly if you build state from a helper function in another module.

### Example

```python
from django.conf import settings
from django.db import models

import reflex as rx
from reflex_django.mixins.crud import ModelCRUDConfig, crud_mixin


class Note(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    content = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


_NOTE_CRUD_CONFIG = ModelCRUDConfig(
    model=Note,
    list_var="notes",
    form_fields=("title", "content"),
    error_var="notes_error",
    owner_field="user",
    ordering=("-created_at",),
    required_for_create=("title",),
    refresh_method="_refresh_note_rows",
    on_load_event="on_load_notes",
    add_event="add_note",
    delete_event="delete_note",
)


from reflex_django.states import AppState


class MyAppState(AppState):
    """Shared app base (routing, domain fields)."""
    pass


class NotesState(crud_mixin(_NOTE_CRUD_CONFIG, base=MyAppState)):
    """Notes CRUD; list lives in ``notes``, errors in ``notes_error``."""

# Typical page wiring (names match config):
# app.add_page(notes_page, route="/notes", on_load=NotesState.on_load_notes)
```

In your page component, bind inputs to **`NotesState.form_title`**, **`NotesState.set_form_title`**, and so on; call **`NotesState.add_note`**, **`NotesState.start_edit`**, **`NotesState.save_edit`**, **`NotesState.cancel_edit`**, **`NotesState.delete_note`** as `on_click` / table actions; render **`NotesState.notes`** (list of dicts, each with **`id`**) with **`rx.foreach`**.

Configurable **`ModelCRUDConfig`** fields include **`row_serializer_class`** (declarative **`ReflexDjangoModelSerializer`** subclass), **`row_serializer`** (callable override), **`row_datetime_format`** (default `"%Y-%m-%d %H:%M"`), **`row_date_format`** (default `"%Y-%m-%d"`), **`exclude_from_row`**, **`owner_field=None`** (no user scoping), and the default event names **`refresh_method`**, **`on_load_event`**, **`add_event`**, **`delete_event`** when you do not want the stock `on_load_items` / `add_item` names.

**Timestamps in list rows.** Django 6+ [`model_to_dict`](https://docs.djangoproject.com/en/stable/ref/forms/models/#django.forms.models.model_to_dict) skips non-editable fields such as `auto_now_add` / `auto_now`. The built-in row serializer merges those from the model instance and formats them for Reflex state, so table cells like `note["created_at"]` work without a custom **`row_serializer`**.
