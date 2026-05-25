# ModelCRUDView with serializers

`ModelCRUDView` is the second declarative CRUD class in `reflex-django`. It does the same job as `ModelState` — list/save/delete with reactive vars — but with two important differences:

1. You provide an **explicit serializer class** instead of letting one be auto-built.
2. The generated state variables and handlers use the **plural model name** (`posts`, `save_post`, `delete_post`) instead of generic `data` / `save` / `delete`.

If you're integrating with an existing DRF schema, or you want each CRUD state to have a clearly-named API, this is the class for you. Otherwise, [`ModelState`](reactive_model_state.md) is shorter and just as powerful.

---

## When you'd reach for this

- You already have `BlogPostSerializer` from DRF and you want to reuse it.
- Your project has many CRUD pages and you'd rather see `state.posts` and `state.save_post()` than `state.data` and `state.save()`.
- You want the option to compose CRUD behavior from explicit [mixins](reflex_django_mixins.md) (e.g. only list + create, no delete).

---

## The smallest example

```python
# blog/serializers.py
from reflex_django.serializers import ReflexDjangoModelSerializer
from blog.models import BlogPost


class BlogPostSerializer(ReflexDjangoModelSerializer):
    class Meta:
        model = BlogPost
        fields = ("id", "title", "content", "is_published", "created_at")
```

```python
# blog/views.py
import reflex as rx
from reflex_django import template
from reflex_django.state import ModelCRUDView, AppState
from blog.models import BlogPost
from blog.serializers import BlogPostSerializer


class BlogPostState(AppState, ModelCRUDView):
    model = BlogPost
    serializer_class = BlogPostSerializer

    class Meta:
        list_var = "posts"
        save_event = "save_post"
        delete_event = "delete_post"
        ordering = ("-created_at",)
```

What you get:

| Reactive var / handler | What it is |
|:---|:---|
| `BlogPostState.posts` | List of dicts (the current page) |
| `BlogPostState.editing_id` | PK being edited, or `-1` |
| `BlogPostState.error` | Top-level error |
| `BlogPostState.on_load_posts()` | Initial load |
| `BlogPostState.save_post()` | Validate + create or update |
| `BlogPostState.delete_post(pk)` | Delete a row |
| `BlogPostState.start_editing(pk)` | Enter edit mode |
| `BlogPostState.cancel_edit()` | Leave edit mode |
| `BlogPostState.title`, `content`, `is_published` | One per writable serializer field |
| `BlogPostState.set_title(value)`, etc. | Setters for each field |

The naming follows your `Meta` — that's the main visible difference from `ModelState`.

---

## A complete CRUD page

### The model

```python
# blog/models.py
from django.conf import settings
from django.db import models


class BlogPost(models.Model):
    title         = models.CharField(max_length=200)
    content       = models.TextField(blank=True)
    is_published  = models.BooleanField(default=False)
    author        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blog_posts",
    )
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
```

### The serializer

```python
# blog/serializers.py
from reflex_django.serializers import ReflexDjangoModelSerializer
from blog.models import BlogPost


class BlogPostSerializer(ReflexDjangoModelSerializer):
    class Meta:
        model = BlogPost
        fields = ("id", "title", "content", "is_published", "author_id", "created_at")
        read_only_fields = ("id", "author_id", "created_at")
```

### The state

```python
# blog/views.py
import reflex as rx
from reflex_django import template
from reflex_django.state import ModelCRUDView, AppState
from blog.models import BlogPost
from blog.serializers import BlogPostSerializer


class BlogPostState(AppState, ModelCRUDView):
    model = BlogPost
    serializer_class = BlogPostSerializer

    class Meta:
        list_var = "posts"
        save_event = "save_post"
        delete_event = "delete_post"
        ordering = ("-created_at",)
        run_model_validation = True
        structured_errors = True

    # Scope all reads to the logged-in user
    def get_queryset(self):
        return BlogPost.objects.filter(author=self.request.user)

    def get_object_lookup(self, pk: int) -> dict:
        return {"pk": pk, "author": self.request.user}

    def get_create_kwargs(self, state_data: dict) -> dict:
        return {**state_data, "author": self.request.user}
```

`AppState` first in the MRO means `self.request.user` works in `get_queryset` and the rest of the hooks. The order matters.

### The UI

```python
def field_input(label: str, input_: rx.Component, err: rx.Var) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="2"),
        input_,
        rx.cond(err != "", rx.text(err, size="1", color="red")),
        spacing="1",
    )


def blog_page() -> rx.Component:
    errs = BlogPostState.posts_field_errors
    return rx.vstack(
        rx.heading("My Blog Posts"),

        rx.hstack(
            rx.button("New post", on_click=BlogPostState.create),
            rx.spacer(),
            rx.text(f"Total: {BlogPostState.posts.length()}"),
        ),

        # form (only when editing)
        rx.cond(
            BlogPostState.editing_id != -1,
            rx.form(
                rx.vstack(
                    field_input("Title", rx.input(value=BlogPostState.title, on_change=BlogPostState.set_title), errs["title"]),
                    field_input("Content", rx.text_area(value=BlogPostState.content, on_change=BlogPostState.set_content), errs["content"]),
                    rx.hstack(
                        rx.text("Published"),
                        rx.switch(checked=BlogPostState.is_published, on_change=BlogPostState.set_is_published),
                    ),
                    rx.hstack(
                        rx.button("Save",   on_click=BlogPostState.save_post),
                        rx.button("Cancel", on_click=BlogPostState.cancel_edit, variant="ghost"),
                    ),
                ),
                key=BlogPostState.form_reset_key,
            ),
        ),

        rx.foreach(BlogPostState.posts, post_row),
        spacing="3",
        padding="2em",
    )


def post_row(row: dict) -> rx.Component:
    return rx.hstack(
        rx.text(row["title"], weight="bold"),
        rx.spacer(),
        rx.cond(row["is_published"], rx.badge("Published", color_scheme="green"), rx.badge("Draft")),
        rx.button("Edit",   on_click=BlogPostState.start_editing(row["id"])),
        rx.button("Delete", on_click=BlogPostState.delete_post(row["id"]), color_scheme="red"),
        padding="0.5em",
        border_bottom="1px solid rgba(0,0,0,0.08)",
    )


@template(route="/blog", title="Blog", on_load=BlogPostState.on_load_posts)
def index() -> rx.Component:
    return blog_page()
```

That's a CRUD page with explicit serializer, custom-named handlers (`save_post`, `delete_post`), and per-user scoping in about 100 lines including the UI.

---

## `Meta` options

The `Meta` inner class controls naming and behavior:

| Option | Default | What it does |
|:---|:---|:---|
| `list_var` | derived from model (e.g. `blog_posts`) | Name of the reactive list variable. |
| `save_event` | `"save"` | Name of the save handler. |
| `delete_event` | `"delete"` | Name of the delete handler. |
| `ordering` | `()` | Tuple of ORM ordering fields (same as `Model.Meta.ordering`). |
| `paginate_by` | `0` (off) | Rows per page. Set a positive number to enable pagination. |
| `reset_after_save` | `True` | Clear the form after a successful save. |
| `run_model_validation` | `True` | Call Django's `full_clean()` before save. |
| `structured_errors` | `True` | Populate `<list_var>_field_errors` dict for per-field UI. |
| `queryset_select_related` | `()` | Apply `select_related(...)` on every list query. |
| `queryset_prefetch` | `()` | Apply `prefetch_related(...)` on every list query. |
| `permission_classes` | `()` | DRF-style permission classes (see [mixins](reflex_django_mixins.md)). |
| `search_fields` | `()` | Fields to include in `?search=` filter. |
| `auto_refresh` | `False` | Refresh the list on every event automatically. |
| `owner_field` | `None` | Used by `UserScopedMixin` to identify the FK to scope by. |

---

## Hooks you can override

| Hook | What it controls |
|:---|:---|
| `get_queryset()` | Base queryset for list and `get_object`. |
| `filter_queryset(qs)` | Apply search/filter to the queryset. |
| `get_object_lookup(pk)` | Kwargs for finding one row (scope check). |
| `get_create_kwargs(state_data)` | Extra kwargs for creating a new row. |
| `clean_<field>(value)` | Per-field cleaning (return cleaned value or raise). |
| `validate_state()` | Cross-field validation in state. |
| `before_save(instance)` | Called right before `await instance.asave()`. |
| `after_save(instance)` | Called after a successful save. |
| `before_delete(instance)` | Called before `await instance.adelete()`. |
| `after_delete(instance)` | Called after a successful delete. |

Hooks are normal methods. `async` if they touch the database, `def` if they're just data shaping.

---

## Optimizing query joins

For tables with foreign keys or many-to-many fields, declare them so you don't get N+1:

```python
class Meta:
    list_var = "posts"
    queryset_select_related = ("author",)         # FK joined in one SQL query
    queryset_prefetch = ("tags", "comments")      # many-to-many / reverse FK batched
```

---

## `ModelState` vs `ModelCRUDView` — which one?

Both are declarative CRUD. The difference is mostly naming and how the serializer is sourced.

| | `ModelState` | `ModelCRUDView` |
|:---|:---|:---|
| Inheritance | already an `AppState` | mix in with `AppState` yourself |
| Serializer | auto-built from `model` + `fields` | you write a `serializer_class` |
| List variable | `state.data` (or custom via `Meta.list_var`) | plural model name (or custom) |
| Save handler | `state.save()` | `state.save_<model>()` (or custom) |
| Delete handler | `state.delete(pk)` | `state.delete_<model>(pk)` (or custom) |
| Best for | New CRUD pages, fast iteration | Sharing a DRF serializer or wanting explicit names |

Both classes share the same dispatch pipeline under the hood, so any pattern you learn (validation, scoping, hooks) applies to both. See [Choosing ModelState vs ModelCRUDView](model_state_and_crud_view.md) for a side-by-side.

---

## Pagination, search, validation

The patterns are identical to [`ModelState`](reactive_model_state.md). Add `paginate_by` to `Meta` for pagination. Add `search_fields` for search. Override `clean_<field>` and `validate_state` for validation. Same hooks, same behavior, just different default names.

---

**Next:** [Choosing ModelState vs ModelCRUDView →](model_state_and_crud_view.md) · [Or: Mixins →](reflex_django_mixins.md)
