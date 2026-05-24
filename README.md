<p align="center">
  <a href="https://github.com/mohannadirshedat/reflex-django">
    <img src="https://raw.githubusercontent.com/mohannadirshedat/reflex-django/main/logo.png" alt="reflex-django" width="200">
  </a>
</p>

<h1 align="center">reflex-django</h1>

<p align="center">
  <strong>Run Django and Reflex in one process — one command, zero glue.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/reflex-django"><img src="https://img.shields.io/pypi/v/reflex-django?color=%2334D058&label=pypi" alt="PyPI"></a>
  <a href="https://pypi.org/project/reflex-django"><img src="https://img.shields.io/pypi/pyversions/reflex-django.svg" alt="Python"></a>
  <a href="https://mohannadirshedat.github.io/reflex-django/"><img src="https://img.shields.io/badge/docs-online-blue" alt="Docs"></a>
  <a href="https://github.com/mohannadirshedat/reflex-django/blob/main/LICENSE"><img src="https://img.shields.io/github/license/mohannadirshedat/reflex-django.svg" alt="License"></a>
</p>

<p align="center">
  <a href="https://mohannadirshedat.github.io/reflex-django/">📖 Full Documentation</a> ·
  <a href="https://github.com/mohannadirshedat/reflex-django">GitHub</a> ·
  <a href="https://pypi.org/project/reflex-django">PyPI</a>
</p>

---

`reflex-django` is a **Django-first** bridge to [Reflex](https://reflex.dev): configure Reflex in **`urls.py`** via `reflex_mount()`, define pages in **`{app}/views.py`**, and run **`python manage.py run_reflex`**. Django serves `/admin`, `/api`, and static paths; Reflex serves the SPA and WebSocket events — one ASGI process.

---


## Table of Contents

1. [Why reflex-django?](#why-reflex-django)
2. [Quick start](#quick-start)
3. [Configure with `reflex_mount()`](#configure-with-reflex_mount)
4. [Pages in `views.py`](#pages-in-viewspy)
5. [Accessing the logged-in user with AppState](#accessing-the-logged-in-user-with-appstate)
6. [Simple CRUD without mixins](#simple-crud-without-mixins)
7. [Architecture overview](#architecture-overview)
8. [Commands](#commands)
9. [Documentation](#documentation)

---

## Why reflex-django?

Reflex sends UI events over **WebSocket**, not normal HTTP requests. This means Django's session middleware, authentication, and locale detection don't run for Reflex events by default.

`reflex-django` fixes this with an **event bridge** that:

- Reconstructs a synthetic `HttpRequest` from WebSocket cookies and headers on every event.
- Loads the Django session and resolves `request.user` automatically.
- Exposes `self.request` directly inside your Reflex state classes.

You get Django's full ORM, Admin, auth, and migrations — plus Reflex's reactive UI — without running two separate servers.

| Django | Python |
|--------|--------|
| 6.0.x  | 3.12+  |

---

## Quick start

```bash
uv init && uv add django reflex reflex-django
uv run django-admin startproject config .
uv run python manage.py startapp shop
# Add reflex_mount() to config/urls.py and pages to shop/views.py (see docs)
uv run python manage.py migrate
uv run python manage.py run_reflex
```

Full tutorial: [Quickstart](https://mohannadirshedat.github.io/reflex-django/quickstart/).

---

## Django settings

Open `config/settings.py` and configure the minimum required settings.

```python
# backend/settings.py

INSTALLED_APPS = [
    # Django built-ins (required)
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # reflex-django helpers (required)
    "reflex_django",

    # Your own apps
    "myapp",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",   # required for sessions
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "backend.urls"

# Database — SQLite for local dev, swap for PostgreSQL in production
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Sessions — stored in the database by default (required for the event bridge)
SESSION_ENGINE = "django.contrib.sessions.backends.db"

# Static files
STATIC_URL = "/static/"

# Optional: built-in auth pages (login, register, password reset)
REFLEX_DJANGO_AUTH = {
    "SIGNUP_ENABLED": True,
    "LOGIN_URL": "/login",
    "LOGIN_REDIRECT_URL": "/dashboard",
}
```

> **Tip:** `python manage.py migrate` after updating `INSTALLED_APPS`.

---

## Configure with `reflex_mount()`

Reflex ports, app name, and URL prefixes are set in **`urls.py`** (not `settings.py`):

```python
# config/urls.py
from django.contrib import admin
from django.urls import path
from reflex_django.urls import reflex_mount

urlpatterns = [path("admin/", admin.site.urls)]

urlpatterns += [
    reflex_mount(
        app_name="shop",
        django_prefix=("/admin", "/api"),
        rx_config={"frontend_port": 3000, "backend_port": 8000},
    ),
]
```

`ReflexDjangoPlugin` is enabled automatically. Reflex loads the app from `reflex_django.django_led_app` — you do **not** create `shop/shop.py`.

---

## Pages in `views.py`

```python
# shop/views.py
import reflex as rx
from reflex_django import template

@template(route="/", title="Home")
def index() -> rx.Component:
    return rx.text("Hello from shop/views.py")
```

See [Pages in views.py](https://mohannadirshedat.github.io/reflex-django/pages_in_views/).

---

## Accessing the Logged-In User with AppState

`AppState` is the recommended base class for any state that needs to know **who is logged in**. It binds `self.request` (a proxy to the synthetic Django `HttpRequest`) on every WebSocket event, giving you the authenticated user, session, and query params.

```python
# frontend/state.py
import reflex as rx
from reflex_django.state import AppState


class DashboardState(AppState):
    """Example state that reads the logged-in user."""

    greeting: str = ""

    @rx.event
    async def load_greeting(self):
        # self.request.user is the real Django User object — use it for
        # permissions, ownership checks, and any server-side logic.
        if not self.request.user.is_authenticated:
            return rx.redirect("/login")

        username = self.request.user.get_username()
        self.greeting = f"Welcome back, {username}!"

    @rx.event
    async def save_preference(self, theme: str):
        # Read/write the Django session directly
        self.request.session["theme"] = theme
        await self.request.session.asave()
```

```python
# frontend/pages/dashboard.py
import reflex as rx
from frontend.state import DashboardState


def dashboard_page() -> rx.Component:
    return rx.vstack(
        rx.heading(DashboardState.greeting),
        rx.button("Load", on_click=DashboardState.load_greeting),
    )


# app.add_page(dashboard_page, route="/dashboard", on_load=DashboardState.load_greeting)
```

### AppState at a glance

| Inside event handlers | For UI components (`rx.cond`, etc.) |
|---|---|
| `self.request.user` — live Django `User` object | `self.is_authenticated` — bool var |
| `self.request.session` — read/write session data | `self.username`, `self.email` — string vars |
| `self.request.GET` — query string params | `self.user_id` — int var |
| `await self.has_perm("app.action")` — permission check | Auto-synced on every event |
| `await self.login(username, password)` | |
| `await self.logout()` | |

> **Security:** Always check `self.request.user.is_authenticated` (or `await self.has_perm(...)`) inside event handlers before reading or mutating data. Client-side state vars are for display only.

---

## Simple CRUD Without Mixins

This example shows how to build a full **Create, Read, Update, Delete** task manager using plain `AppState` and async Django ORM — no mixins, no code generation, no magic. This is the most transparent and customizable approach.

### 1. The Model

```python
# myapp/models.py
from django.conf import settings
from django.db import models


class Task(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    title = models.CharField(max_length=200)
    done = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
```

```bash
uv run reflex django makemigrations myapp
uv run reflex django migrate
```

### 2. The State

```python
# frontend/state.py
import reflex as rx
from reflex_django.state import AppState

from myapp.models import Task


class TaskState(AppState):
    # --- reactive vars synced to the browser ---
    tasks: list[dict] = []
    title: str = ""
    editing_id: int = -1
    error: str = ""

    # ── helpers ────────────────────────────────────────────────────────────

    def _require_user(self):
        """Return the logged-in user, or raise a redirect."""
        if not self.request.user.is_authenticated:
            raise PermissionError("login required")
        return self.request.user

    async def _serialize_tasks(self, qs) -> list[dict]:
        """Turn a queryset into a plain list of dicts for the UI."""
        return [
            {"id": t.id, "title": t.title, "done": t.done}
            async for t in qs
        ]

    # ── CRUD event handlers ────────────────────────────────────────────────

    @rx.event
    async def load_tasks(self):
        """Load all tasks for the current user."""
        self.error = ""
        try:
            user = self._require_user()
        except PermissionError:
            return rx.redirect("/login")

        qs = Task.objects.filter(user=user)
        self.tasks = await self._serialize_tasks(qs)

    @rx.event
    async def create_task(self):
        """Create a new task from the title input."""
        self.error = ""
        if not self.title.strip():
            self.error = "Title cannot be empty."
            return

        try:
            user = self._require_user()
        except PermissionError:
            return rx.redirect("/login")

        await Task.objects.acreate(user=user, title=self.title.strip())
        self.title = ""
        return TaskState.load_tasks

    @rx.event
    async def start_edit(self, task_id: int):
        """Populate the input for editing an existing task."""
        task = await Task.objects.aget(pk=task_id, user=self.request.user)
        self.title = task.title
        self.editing_id = task_id

    @rx.event
    async def save_edit(self):
        """Persist the edited title."""
        self.error = ""
        if not self.title.strip():
            self.error = "Title cannot be empty."
            return

        await Task.objects.filter(
            pk=self.editing_id,
            user=self.request.user,
        ).aupdate(title=self.title.strip())

        self.title = ""
        self.editing_id = -1
        return TaskState.load_tasks

    @rx.event
    async def toggle_done(self, task_id: int):
        """Flip the done flag on a task."""
        task = await Task.objects.aget(pk=task_id, user=self.request.user)
        task.done = not task.done
        await task.asave(update_fields=["done"])
        return TaskState.load_tasks

    @rx.event
    async def delete_task(self, task_id: int):
        """Permanently delete a task."""
        await Task.objects.filter(
            pk=task_id,
            user=self.request.user,
        ).adelete()
        return TaskState.load_tasks

    @rx.event
    def cancel_edit(self):
        """Discard the current edit."""
        self.title = ""
        self.editing_id = -1
```

### 3. The Page

```python
# frontend/pages/tasks.py
import reflex as rx
from frontend.state import TaskState


def task_row(task: dict) -> rx.Component:
    return rx.hstack(
        rx.checkbox(
            checked=task["done"],
            on_change=TaskState.toggle_done(task["id"]),
        ),
        rx.text(
            task["title"],
            text_decoration=rx.cond(task["done"], "line-through", "none"),
            flex="1",
        ),
        rx.button("Edit", on_click=TaskState.start_edit(task["id"]), size="1"),
        rx.button(
            "Delete",
            on_click=TaskState.delete_task(task["id"]),
            color_scheme="red",
            size="1",
        ),
        width="100%",
        align="center",
    )


def tasks_page() -> rx.Component:
    return rx.container(
        rx.heading("My Tasks", size="5", margin_bottom="4"),

        # Error banner
        rx.cond(
            TaskState.error != "",
            rx.callout(TaskState.error, color_scheme="red", margin_bottom="3"),
        ),

        # Create / edit form
        rx.hstack(
            rx.input(
                value=TaskState.title,
                on_change=TaskState.set_title,
                placeholder="What needs doing?",
                flex="1",
            ),
            rx.cond(
                TaskState.editing_id >= 0,
                rx.hstack(
                    rx.button("Save", on_click=TaskState.save_edit),
                    rx.button("Cancel", on_click=TaskState.cancel_edit, variant="soft"),
                ),
                rx.button("Add", on_click=TaskState.create_task),
            ),
            width="100%",
            margin_bottom="4",
        ),

        # Task list
        rx.vstack(
            rx.foreach(TaskState.tasks, task_row),
            width="100%",
            spacing="2",
        ),

        max_width="600px",
        padding="6",
    )


# In your app module:
# app.add_page(tasks_page, route="/tasks", on_load=TaskState.load_tasks)
```

---

## Architecture Overview

```text
Browser
  │
  │  HTTP  (/admin, /api, /static, ...)
  ├──────────────────────────────► Django ASGI
  │                                  ↳ ORM · Admin · Sessions · Auth
  │
  │  HTTP + WebSocket  (Reflex SPA, /_event/...)
  └──────────────────────────────► Reflex ASGI
                                         │
                                         ▼
                             Reflex event arrives
                                         │
                                         ▼
                             DjangoEventBridge runs
                             ┌─────────────────────────────────┐
                             │ Reads session cookie            │
                             │ Loads Django session from DB    │
                             │ Resolves request.user           │
                             │ Binds synthetic HttpRequest     │
                             └─────────────────────────────────┘
                                         │
                                         ▼
                             Your @rx.event handler
                             (self.request.user is ready)
```

### The three things the plugin does

1. **`reflex_mount()`** — Registers Reflex config when `urls.py` loads; `get_config()` reads mount data.
2. **`django_led_app`** — Builds `rx.App`, imports `{app}/views.py`, applies `@template` pages.
3. **HTTP dispatcher** — `django_prefix` paths → Django; SPA + WebSockets → Reflex.
4. **Event bridge** — Synthetic `HttpRequest` per WebSocket event with session and `request.user`.

---

## Commands

```bash
python manage.py run_reflex       # unified dev server (preferred)
python manage.py migrate
python manage.py createsuperuser
```

Configure Reflex in **`urls.py`** via `reflex_mount()` — see [configuration](docs/configuration.md).

Optional: `uv run reflex django migrate` when using the Reflex CLI entry point.

---

## Documentation

| Topic | Link |
|-------|------|
| 📖 Full documentation | [mohannadirshedat.github.io/reflex-django](https://mohannadirshedat.github.io/reflex-django/) |
| ⚡ Quickstart guide | [docs/quickstart.md](docs/quickstart.md) |
| 🏗 Architecture deep-dive | [docs/architecture.md](docs/architecture.md) |
| 🔐 Session authentication | [docs/authentication.md](docs/authentication.md) |
| 🗃 Declarative CRUD (ModelState) | [docs/reactive_model_state.md](docs/reactive_model_state.md) |
| 🔌 ModelState vs ModelCRUDView | [docs/model_state_and_crud_view.md](docs/model_state_and_crud_view.md) |
| 🚀 Deployment guide | [docs/deployment.md](docs/deployment.md) |
| ❓ FAQ | [docs/faq.md](docs/faq.md) |

---

**Author:** Mohannad Irshedat · [GitHub](https://github.com/mohannadirshedat/reflex-django)
