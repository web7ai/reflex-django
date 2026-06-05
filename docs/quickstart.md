# Your first app

In this tutorial you'll build a tiny todo list. By the time you're done, you'll have touched every important part of `reflex-django`:

- Pages and routes (`@page`)
- State and event handlers (`AppState`, `@rx.event`)
- The Django ORM from inside an event handler
- Authentication — only logged-in users see their own todos
- The Django admin, still working at `/admin/`

It takes about 15 minutes. We'll go slowly and explain *why* at each step.

---

## What we're building

A page at `/` that lists your todos, lets you add one, and lets you tick them off. You sign in at `/admin/` (Django's normal login). Each user only sees their own todos. Everything runs in one Python process on one port.

---

## 1. Create the project

```bash
mkdir myshop && cd myshop
uv init
uv add django reflex reflex-django
uv run django-admin startproject config .
uv run python manage.py startapp shop
```

You should now have a layout like this:

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

`config/` is the Django project package (settings, top-level URLs, ASGI entry). `shop/` is a Django "app" — a small feature module. Your code goes in `shop/`.

---

## 2. Edit `settings.py`

Three things we care about: add `reflex_django` and `shop` to `INSTALLED_APPS`, make sure session and auth middleware are present (so `AppState` can see the user), and add `AsyncStreamingMiddleware` at the end.

```python
# config/settings.py
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = "dev-only-change-me"
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

Why those middlewares matter: every middleware in that list runs on every Reflex button click too. The session middleware loads the session from the cookie. The auth middleware turns that session into `request.user`. Without them, your Reflex handlers couldn't tell who the user is.

---

## 3. Wire `urls.py`

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

Three pieces:

- `app_name="shop"` — Reflex will look for pages in `shop/views.py`.
- `django_prefix=("/admin",)` — Django owns anything under `/admin/`. Everything else falls through to the Reflex SPA.
- `rx_config={"backend_port": 8000}` — what port to bind on.

---

## 4. Point ASGI at `reflex_django`

```python
# config/asgi.py
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
from reflex_django.asgi_entry import application  # noqa: E402,F401
```

This is the single entry point both the dev server and your future production server will use.

---

## 5. Define a `Todo` model

```python
# shop/models.py
from django.conf import settings
from django.db import models


class Todo(models.Model):
    title       = models.CharField(max_length=200)
    done        = models.BooleanField(default=False)
    owner       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
```

Standard Django. `owner` ties each todo to a user so each person only sees their own.

Register it with the admin (optional, but useful while we're here):

```python
# shop/admin.py
from django.contrib import admin
from shop.models import Todo

admin.site.register(Todo)
```

Now run migrations and create yourself a user:

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

---

## 6. Write the page and the state

This is the part that's unique to `reflex-django`. We'll build it in three layers: state, page function, then wire them together.

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
```

Three things to notice:

**`TodoState` inherits from `AppState`**, not plain `rx.State`. That's what gives us `self.request.user` inside the handlers. `AppState` is the bridge between Reflex events and Django. ([More on AppState](state_management.md).)

**Handlers are `async def`** and use Django's async ORM (`acreate`, `aget`, `asave`, async iteration). If you used the blocking versions (`create`, `get`, `save`), you'd freeze the event loop for every other user.

**We re-query in `on_load` and re-call it after mutations**, so the UI always shows the current truth. This is simple and correct. Once you have lots of rows, you can move to the [`ModelState` helper](reactive_model_state.md) which does this for you.

Now the UI:

```python
# shop/views.py — continued

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

A few small things:

- `@page(route="/", on_load=...)` registers the page and tells Reflex to run `TodoState.on_load` whenever the user visits this URL.
- `TodoState.is_authenticated` is a reactive variable that `AppState` exposes for free — it mirrors `request.user.is_authenticated`.
- `rx.foreach` iterates over the `todos` list and renders one `todo_row` per item.
- `TodoState.set_new_title` is auto-generated by Reflex for the `new_title: str` field. You didn't write it.

---

## 7. Run it

```bash
python manage.py run_reflex
```

The first time, this will:

1. Build the Reflex SPA (a one-time compile step).
2. Start `uvicorn` on port 8000 (the backend) and the Vite dev server on port 3000 (the frontend, with hot reload).
3. Watch your Python files for changes and hot-reload the frontend on edit.

Open it (the Vite dev server — hot reload on save):

- `http://localhost:3000/` — the todo page.
- `http://localhost:3000/admin/` — the Django admin (log in with the superuser you created).

Try this flow:

1. Visit `/` without logging in. You see "Please log in at /admin/".
2. Visit `/admin/`, log in.
3. Go back to `/`. You see the input box.
4. Type "Buy milk", hit Add. The row appears.
5. Click the checkbox. The text goes line-through.

That's a full reactive CRUD page in about 80 lines of Python, with real Django auth, in one process, on one port.

---

## What just happened?

When you clicked "Add", here's the actual sequence inside the server:

1. The browser sent a WebSocket event: *"call `TodoState.add_todo`"*.
2. `reflex-django` saw the event, built a synthetic `HttpRequest` from the cookies, and ran `settings.MIDDLEWARE` over it.
3. `SessionMiddleware` loaded your session row. `AuthenticationMiddleware` resolved `request.user`.
4. `reflex-django` bound `self.request` and `self.user` onto your `TodoState` instance.
5. Your handler ran. `self.request.user` was the real you, so `Todo.objects.acreate(owner=self.request.user, ...)` worked.
6. Reflex shipped the updated `todos` list back over the WebSocket.
7. The browser re-rendered the list.

Most of that you didn't write. That's the whole point of `reflex-django`.

---

## Faster reloads

When you only changed `models.py` or `admin.py`, you don't need to rebuild the Reflex SPA. Skip it:

```bash
python manage.py run_reflex --skip-rebuild
```

If you want the classic Reflex hot-reload experience (a Vite dev server proxied through Django), use:

```bash
python manage.py run_reflex --with-vite
```

More flags in the [CLI reference](cli.md).

---

## What to read next

You now have a working app. From here:

- **[AppState — your bridge to Django](state_management.md)** — what `self.request`, `self.user`, `self.session` actually are, and how to use them well.
- **[Talking to the database](database_integration.md)** — the async ORM patterns to remember (and the blocking ones to avoid).
- **[CRUD with ModelState](reactive_model_state.md)** — the same todo app, but with `ModelState` generating most of the handlers for you.
- **[Login & sessions](authentication.md)** — built-in login/register pages, decorators, and the live-vs-snapshot rules.

---

## Quick troubleshooting

| Symptom | Likely cause and fix |
|:---|:---|
| `/` returns 404 on first run | The SPA wasn't built. Run `python manage.py run_reflex` once and wait for the export to finish; it stages the bundle into `STATIC_ROOT/_reflex/`. |
| You see "Please log in" even after logging into `/admin/` | `SessionMiddleware` or `AuthenticationMiddleware` missing from `MIDDLEWARE`. Check step 2. |
| `AppRegistryNotReady` at startup | You're touching a Django model at class definition time. Move model access into your `@rx.event` handlers. |
| `ModuleNotFoundError: shop.shop` | A leftover `rxconfig.py` is referencing the old layout. Delete `rxconfig.py` — `reflex_mount()` is the only config you need. |
| Admin complains about streaming | Add `reflex_django.streaming_middleware.AsyncStreamingMiddleware` at the **end** of `MIDDLEWARE`. |
| Admin **403 CSRF** on `:3000` | See [Local development](local_development.md) — `CSRF_TRUSTED_ORIGINS`, `USE_X_FORWARDED_HOST`, `DEFAULT_DEV_MIDDLEWARE`. |
| `useContext is not a function` in the browser | Restart `run_reflex` after compile; see [Local development](local_development.md#troubleshooting). |
| Slow reload after every Python edit | Use `--skip-rebuild` for pure Python changes, or `--with-vite` for hot-reload on Reflex pages. |

---

**Next:** [AppState — your bridge to Django →](state_management.md) · [Or: add to an existing Django project →](existing_django_project.md)
