---
level: beginner
tags: [tutorial, auth, orm]
---

# Your first app

**What you will learn:** How to build a small todo app with `@page`, `AppState`, Django auth, and the async ORM in about 15 minutes.

**When you need this:**

- You want a guided first project instead of wiring pieces from the install page alone.
- You want to see why each step exists before you adapt the pattern to your own models.

We will build a todo list at `/`, backed by Django models, scoped per user. You log in through `/admin/` like any Django site. One Python process, two dev ports by default.

---

## What we are building

A page at `/` that lists todos, lets you add one, and lets you tick them off. Signed-in users see only their own rows. Django admin keeps working at `/admin/`. Everything shares session cookies.

---

## 1. Create the project

**Why:** reflex-django is a Django app. You need `manage.py`, settings, and a feature app before pages or models.

```bash
mkdir myshop && cd myshop
uv init
uv add django reflex reflex-django
uv run django-admin startproject config .
uv run python manage.py startapp shop
```

You should now have:

```text
myshop/
├── manage.py
├── config/
│   ├── settings.py
│   ├── urls.py
│   └── asgi.py
└── shop/
    ├── models.py
    ├── views.py
    └── admin.py
```

`config/` is the Django project (settings, URLs, ASGI). `shop/` is where your feature code lives.

---

## 2. Edit `settings.py`

**Why:** reflex-django must be in `INSTALLED_APPS`. Session and auth middleware must run on every Reflex event so `AppState` can read `request.user`.

Add the reflex-django bits to your existing settings (paths, `SECRET_KEY`, database, and so on):

```python
--8<-- "snippets/minimal_settings.py"
```

Also set the usual dev defaults:

```python
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = "dev-only-change-me"
DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
ROOT_URLCONF = "config.urls"
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

Every middleware in that list runs when you click a Reflex button, not only on normal HTTP. Session middleware loads the cookie. Auth middleware turns it into `request.user`.

---

## 3. Add `rxconfig.py` and the app module

**Why:** v4 configures Reflex through on-disk `rxconfig.py` with `ReflexDjangoPlugin`. Your `app` lives in `{app_name}/{app_name}.py`.

Create `rxconfig.py` at the project root:

```python
--8<-- "snippets/minimal_rxconfig.py"
```

Create `shop/shop.py`:

```python
import reflex as rx

app = rx.App()
```

---

## 4. Wire `urls.py` and ASGI

**Why:** `@page` routes register when Python imports your views module. ASGI must boot through reflex-django so Django and Reflex share one process.

```python
--8<-- "snippets/minimal_urls.py"
```

```python
--8<-- "snippets/minimal_asgi.py"
```

---

## 5. Define a `Todo` model

**Why:** This tutorial uses the real Django ORM, not an in-memory list. `owner` scopes rows per user.

```python
# shop/models.py
from django.conf import settings
from django.db import models


class Todo(models.Model):
    title = models.CharField(max_length=200)
    done = models.BooleanField(default=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
```

Register it with admin (handy while testing):

```python
# shop/admin.py
from django.contrib import admin
from shop.models import Todo

admin.site.register(Todo)
```

Run migrations and create a superuser:

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

---

## 6. Write the page and state

**Why:** Reflex UI lives in Python components. `AppState` (not plain `rx.State`) gives you `self.request.user` inside handlers.

```python
# shop/views.py
import reflex as rx
from reflex_django.pages.decorators import page
from reflex_django.states import AppState
from shop.models import Todo


class TodoState(AppState):
    todos: list[dict] = []
    new_title: str = ""
    error: str = ""

    @rx.event
    async def on_load(self):
        if not self.request.user.is_authenticated:
            self.todos = []
            return
        self.todos = [
            {"id": t.id, "title": t.title, "done": t.done}
            async for t in Todo.objects.filter(owner=self.request.user)
        ]

    @rx.event
    async def add_todo(self):
        self.error = ""
        title = self.new_title.strip()
        if not title:
            self.error = "Type something first."
            return
        if not self.request.user.is_authenticated:
            self.error = "Please log in at /admin/ first."
            return
        await Todo.objects.acreate(owner=self.request.user, title=title)
        self.new_title = ""
        await self.on_load()

    @rx.event
    async def toggle(self, todo_id: int):
        if not self.request.user.is_authenticated:
            return
        todo = await Todo.objects.aget(pk=todo_id, owner=self.request.user)
        todo.done = not todo.done
        await todo.asave()
        await self.on_load()


def todo_row(todo: dict) -> rx.Component:
    return rx.hstack(
        rx.checkbox(
            checked=todo["done"],
            on_change=lambda _: TodoState.toggle(todo["id"]),
        ),
        rx.text(
            todo["title"],
            text_decoration=rx.cond(todo["done"], "line-through", "none"),
        ),
        spacing="3",
    )


@page(route="/", title="My Todos", on_load=TodoState.on_load)
def index() -> rx.Component:
    return rx.vstack(
        rx.heading("My Todos"),
        rx.cond(
            TodoState.is_authenticated,
            rx.vstack(
                rx.hstack(
                    rx.input(
                        placeholder="What needs doing?",
                        value=TodoState.new_title,
                        on_change=TodoState.set_new_title,
                    ),
                    rx.button("Add", on_click=TodoState.add_todo),
                ),
                rx.cond(TodoState.error != "", rx.callout(TodoState.error, color_scheme="red")),
                rx.foreach(TodoState.todos, todo_row),
                spacing="3",
                align="start",
            ),
            rx.text("Please log in at ", rx.link("/admin/", href="/admin/"), " first."),
        ),
        spacing="4",
        padding="2em",
    )
```

Three things to notice:

- **`TodoState` extends `AppState`** so handlers get `self.request.user`. See [AppState](../guides/state.md).
- **Handlers are `async def`** and use the async ORM (`acreate`, `aget`, `asave`). Blocking calls would freeze the event loop for other users.
- **`on_load` runs on every visit** and after mutations, so the list always matches the database.

---

## 7. Run it

**Why:** `reflex run` is the supported dev entry. It compiles the SPA, starts Vite, and boots the ASGI backend with Django mounted in-process.

--8<-- "snippets/reflex_run_command.md"

Try this flow:

1. Visit `/` without logging in. You see the login prompt.
2. Open `/admin/`, sign in with your superuser.
3. Return to `/`. Add "Buy milk", then tick the checkbox.

!!! tip "Faster reloads"
    Python-only edits may skip full recompile depending on Reflex version. See [Local development](local_development.md).

---

## Quick troubleshooting

| Symptom | Likely fix |
|:---|:---|
| `/` returns 404 on first run | Wait for the first compile to finish, or run `reflex run` again. |
| Still "Please log in" after admin | Check `SessionMiddleware` and `AuthenticationMiddleware` in `MIDDLEWARE`. |
| `AppRegistryNotReady` | Move model imports inside handlers. |
| `ModuleNotFoundError: shop.shop` | Create `shop/shop.py` with `app = rx.App()`; set `app_name="shop"` in `rxconfig.py`. |
| Admin 403 CSRF on `:3000` | Add both `:3000` and `:8000` to `CSRF_TRUSTED_ORIGINS`. See [Local development](local_development.md). |

---

## What just happened?

When you clicked **Add**, the browser sent a WebSocket event. reflex-django built a synthetic `HttpRequest`, ran your full `MIDDLEWARE` chain, bound `self.request` on `TodoState`, and ran `add_todo`. Django wrote a row. Reflex pushed the updated list back over the socket. You did not write that plumbing. That is the point.

---

**Next up:** [AppState and Django context](../guides/state.md)
