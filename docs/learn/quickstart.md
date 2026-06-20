# Tutorial: your first app

Build a todo list at `/` with `app.add_page`, `AppState`, Django auth, and the async ORM. Signed-in users see only their rows. Admin stays at `/admin/`.

Start from [Integration](integration.md) if you have not wired the project yet.

## 1. Create the project

```bash
mkdir myshop && cd myshop
uv init
uv add django reflex reflex-django
uv run django-admin startproject config .
uv run python manage.py startapp shop
```

## 2. Wire Django and Reflex

Follow [Integration](integration.md) for `settings.py`, `rxconfig.py`, `urls.py`, `asgi.py`.

## 3. Todo model

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
```

```bash
reflex django makemigrations
reflex django migrate
reflex django createsuperuser
```

## 4. State, UI, and app entry

```python
# shop/views.py
import reflex as rx
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

Register the page on the app (standard Reflex):

```python
# shop/shop.py
import reflex as rx
from shop.views import TodoState, index

app = rx.App()
app.add_page(
    index,
    route="/",
    title="My Todos",
    on_load=TodoState.on_load,
)
```

Prefer `@page` in `views.py` instead? See [Pages and state](../advanced/pages-and-state.md#option-b-page-in-viewspy-optional).

## 5. Run

--8<-- "snippets/reflex_run_command.md"

1. Visit `/` without logging in. You see the login prompt.
2. Open `/admin/`, sign in.
3. Return to `/`. Add a todo and tick it off.

Stuck? See [Troubleshooting](../advanced/troubleshooting.md).

For cleaner list loading, see [Serializers](../advanced/serializers.md). For declarative CRUD, see [Model state](../advanced/model-state.md).

**Next:** [Pages and state](../advanced/pages-and-state.md)
