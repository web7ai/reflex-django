---
level: intermediate
tags: [crud, serializers]
---

# ModelCRUDView with serializers

**What you'll learn:** How `ModelCRUDView` gives you the same declarative CRUD pipeline as `ModelState`, but with an explicit serializer class and model-specific handler names.

**When you need this:**

- You already have (or want) a `ReflexDjangoModelSerializer` shared with other code.
- Several CRUD states live in one module and you want names like `posts` and `save_blogpost` instead of generic `data` and `save`.

`ModelCRUDView` is a mixin stack you combine with `AppState`. It does the same list, save, and delete work as `ModelState`, with two visible differences: you supply `serializer_class`, and default handler names follow the model (`save_blogpost`, `on_load_posts`, etc.).

---

## Smallest example

```python
# blog/serializers.py
from reflex_django.serializers import ReflexDjangoModelSerializer
from blog.models import BlogPost


class BlogPostSerializer(ReflexDjangoModelSerializer):
    class Meta:
        model = BlogPost
        fields = ("id", "title", "content", "is_published", "created_at")
        read_only_fields = ("id", "created_at")
```

```python
# blog/views.py
from reflex_django.states import AppState
from reflex_django.state import ModelCRUDView
from blog.models import BlogPost
from blog.serializers import BlogPostSerializer


class BlogPostState(AppState, ModelCRUDView):
    model = BlogPost
    serializer_class = BlogPostSerializer
    list_var = "posts"
    ordering = ("-created_at",)
```

What you get (defaults shown; override with `save_event`, `delete_event`, `on_load_event`):

| Var / handler | Default |
|:---|:---|
| `BlogPostState.posts` | List of dicts |
| `BlogPostState.on_load_posts()` | Initial list load |
| `BlogPostState.save_blogpost()` | Validate and save |
| `BlogPostState.delete_blogpost(pk)` | Delete one row |
| `BlogPostState.start_edit(pk)` | Enter edit mode |
| `BlogPostState.cancel_edit()` | Leave edit mode |
| `title`, `content`, `is_published` | Writable serializer fields |

The canonical API (`save()`, `load(pk)`, `delete(pk)`, `refresh()`) is also available when `use_canonical_api = True` (the default).

---

## Complete blog page

### Model and serializer

```python
# blog/models.py
from django.conf import settings
from django.db import models


class BlogPost(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField(blank=True)
    is_published = models.BooleanField(default=False)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blog_posts",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
```

```python
# blog/serializers.py
class BlogPostSerializer(ReflexDjangoModelSerializer):
    class Meta:
        model = BlogPost
        fields = ("id", "title", "content", "is_published", "author_id", "created_at")
        read_only_fields = ("id", "author_id", "created_at")
```

### State with per-user scoping

```python
# blog/views.py
import reflex as rx
from reflex_django.pages.decorators import page
from reflex_django.states import AppState
from reflex_django.state import ModelCRUDView


class BlogPostState(AppState, ModelCRUDView):
    model = BlogPost
    serializer_class = BlogPostSerializer
    list_var = "posts"
    structured_errors = True
    run_model_validation = True

    def get_queryset(self):
        return BlogPost.objects.filter(author=self.request.user)

    def get_object_lookup(self, pk: int) -> dict:
        return {"pk": pk, "author": self.request.user}

    def get_create_kwargs(self, state_data: dict) -> dict:
        return {**state_data, "author": self.request.user}
```

Put `AppState` first in the inheritance list so `self.request.user` is available in hooks.

### UI (excerpt)

```python
@page(route="/blog", title="Blog", on_load=BlogPostState.on_load_posts)
def index() -> rx.Component:
    errs = BlogPostState.posts_field_errors
    return rx.vstack(
        rx.button("New post", on_click=BlogPostState.create),
        rx.cond(
            BlogPostState.editing_id != -1,
            rx.form(
                rx.vstack(
                    rx.input(value=BlogPostState.title, on_change=BlogPostState.set_title),
                    rx.cond(errs["title"] != "", rx.text(errs["title"], color="red", size="1")),
                    rx.button("Save", on_click=BlogPostState.save_blogpost),
                    rx.button("Cancel", on_click=BlogPostState.cancel_edit, variant="ghost"),
                ),
                key=BlogPostState.form_reset_key,
            ),
        ),
        rx.foreach(BlogPostState.posts, post_row),
    )
```

With `list_var = "posts"` and `structured_errors = True`, field errors appear in `posts_field_errors`.

---

## Configuration reference

Prefer class-body attributes (IDE-friendly). Inner `Meta(ModelCRUDMeta)` still works.

| Option | Default | Purpose |
|:---|:---|:---|
| `list_var` | plural model name | Reactive list attribute |
| `save_event` | `save_<model_name>` | Save handler name |
| `delete_event` | `delete_<model_name>` | Delete handler name |
| `on_load_event` | `on_load_<list_var>` | Page `on_load` handler |
| `paginate_by` | off | Rows per page |
| `search_fields` | `()` | `icontains` OR search |
| `structured_errors` | `False` | Per-field error dict |
| `run_model_validation` | `False` | Call `full_clean()` before save |
| `reset_after_save` | `True` | Clear form after success |
| `queryset_select_related` | `()` | SQL join optimization |
| `queryset_prefetch` | `()` | Prefetch optimization |
| `permission_classes` | `()` | DRF-style checks per action |

---

## Hooks you can override

| Hook | Controls |
|:---|:---|
| `get_queryset()` | Base queryset for list and lookups |
| `filter_queryset(qs)` | Search and extra filters |
| `get_object_lookup(pk)` | Ownership-safe single-row fetch |
| `get_create_kwargs(state_data)` | Extra fields on create |
| `clean_<field>(value)` | Per-field validation (return error string) |
| `validate_state(ctx, data)` | Cross-field errors |
| `clean_state(data)` | Normalize before save |
| `before_save` / `after_save` | Side effects around `asave()` |
| `before_delete` / `after_delete` | Side effects around `adelete()` |

---

## Optimizing queries

```python
class BlogPostState(AppState, ModelCRUDView):
    queryset_select_related = ("author",)
    queryset_prefetch = ("tags",)
```

Use these when list rows touch foreign keys or many-to-many fields.

---

## ModelState vs ModelCRUDView (preview)

| | `ModelState` | `ModelCRUDView` |
|:---|:---|:---|
| Inheritance | `class X(ModelState)` | `class X(AppState, ModelCRUDView)` |
| Serializer | Auto from `fields` | Explicit `serializer_class` |
| Default list var | `data` | plural model name |
| Default save | `save()` | `save_<model>` |
| Best for | Fast iteration | Shared serializers, explicit names |

Full comparison: [Choosing ModelState vs ModelCRUDView](../guides/crud.md#choosing).

---

## What just happened?

You composed `AppState` with `ModelCRUDView`, wired an explicit serializer, and scoped rows to the logged-in user. The same dispatch pipeline and hooks as `ModelState` apply; only naming and serializer sourcing differ.

**Next up:** [Choosing ModelState vs ModelCRUDView →](../guides/crud.md#choosing)