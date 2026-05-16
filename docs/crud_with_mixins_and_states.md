# CRUD with mixins and states

For new projects, prefer **[Reactive ModelState](reactive_model_state.md)** — one class per model with `model` + `fields` and canonical **`load` / `save` / `refresh`** handlers.

**Same BlogPost example with `ModelState`:**

```python
from reflex_django.state import ModelState
from reflex_django.state.mixins.scoping import UserScopedMixin
from blog.models import BlogPost

class PostState(ModelState, UserScopedMixin):
    model = BlogPost
    fields = ["title", "slug", "body", "published"]
    scope_field = "author_id"
    ordering = ("-created_at",)

    class Meta:
        list_var = "posts"
```

UI: `PostState.refresh`, `PostState.load(id)`, `PostState.save`, `PostState.delete(id)` — see the [reactive guide](reactive_model_state.md) for full pages, pagination, and validation.

---

This page documents **`ModelCRUDView`** (explicit `serializer_class`) for the same pipeline with legacy event names (`save_post`, `start_edit`, …). Everything below applies to both styles; hooks and `Meta` options are shared.

> Tutorial **`BlogPost`** code is **example application code**. Canonical tested patterns also appear in README (`Note`), `reflex_django_tests/test_reactive_model_state.py`, and `test_model_state.py`.

---

## Prerequisites

- [State management](state_management.md) — when to use `AppState` + `ModelCRUDView` vs plain `rx.State`  
- [reflex-django mixins](reflex_django_mixins.md)  
- [Serializers](serializers.md)  
- [Authentication](authentication.md)

---

## Model and serializer

```python
# blog/models.py
from django.conf import settings
from django.db import models

class BlogPost(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220)
    body = models.TextField(blank=True)
    published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
```

```python
# blog/serializers.py
from reflex_django.serializers import ReflexDjangoModelSerializer
from blog.models import BlogPost

class BlogPostSerializer(ReflexDjangoModelSerializer):
    class Meta:
        model = BlogPost
        fields = ("id", "title", "slug", "body", "published", "created_at")
        read_only_fields = ("id", "created_at")
```

Default mixin ordering uses `("-created_at",)` — `created_at` is required unless you override `ordering` on the state class.

---

## Minimal state

```python
from reflex_django.state import AppState, ModelCRUDView

class PostsState(AppState, ModelCRUDView):
    serializer_class = BlogPostSerializer

    class Meta:
        list_var = "posts"
        save_event = "save_post"
        delete_event = "delete_post"
```

**Generated (example):** `posts`, `posts_error`, `editing_id`, `title`, `slug`, `body`, `published`, `set_*`, `on_load_posts`, `save_post`, `start_edit`, `delete_post`, `cancel_edit`, `reset_state_fields`, `form_reset_key`.

---

## User-scoped posts

**Option A — hooks:**

```python
class PostsState(AppState, ModelCRUDView):
    serializer_class = BlogPostSerializer

    class Meta:
        list_var = "posts"
        read_only_fields = ("author",)

    def get_queryset(self):
        return BlogPost.objects.filter(author=self.request.user)

    def get_object_lookup(self, pk: int) -> dict:
        return {"pk": pk, "author": self.request.user}

    def get_create_kwargs(self, state_data: dict) -> dict:
        return {**state_data, "author": self.request.user}
```

**Option B — `UserScopedMixin`:**

```python
from reflex_django.state.mixins import UserScopedMixin

class PostsState(AppState, ModelCRUDView, UserScopedMixin):
    serializer_class = BlogPostSerializer
    scope_field = "author_id"

    class Meta:
        list_var = "posts"
```

---

## Event flow

```text
on_load_posts  → dispatch("load_list")  → queryset → serialize → posts
save_post      → dispatch("save")       → validate → create|update → refresh
start_edit(id) → dispatch("start_edit") → populate flat vars
delete_post(id)→ dispatch("delete")     → delete → refresh
```

Each `dispatch` binds `self.request` / `self.django_request` when the event bridge is enabled.

---

## Search via `filter_queryset`

Pagination is **not** built in—add state vars and slice, or filter only:

```python
class PostsState(AppState, ModelCRUDView):
    search: str = ""

    @rx.event
    def set_search(self, value: str):
        self.search = value

    def filter_queryset(self, qs):
        q = self.search.strip()
        if q:
            from django.db.models import Q
            qs = qs.filter(Q(title__icontains=q) | Q(slug__icontains=q))
        return qs
```

Call `await self._load_posts()` after changing `search` if you add a dedicated search button.

---

## Validation hooks

```python
    async def validate_state(self, ctx):
        errors = await super().validate_state(ctx)
        if len(self.title.strip()) < 3:
            errors.setdefault("title", "Title too short.")
        return errors

    def on_state_invalid(self, ctx, errors):
        if isinstance(errors, dict) and errors:
            self.posts_error = "; ".join(f"{k}: {v}" for k, v in errors.items())
        else:
            self.posts_error = str(errors)
```

Enable model-level `full_clean()`:

```python
    class Meta:
        run_model_validation = True
        structured_errors = True  # enables posts_field_errors var
```

---

## Override generated handlers

Define the same name in the class body to replace assembly output:

```python
class PostsState(AppState, ModelCRUDView):
    @rx.event
    async def save_post(self):
        # custom logic, or call into dispatch manually
        ...
```

See `reflex_django_tests/test_model_state.py` (`_CustomSaveState`).

---

## Page wiring

```python
def blog_admin() -> rx.Component:
    return rx.vstack(
        rx.cond(PostsState.posts_error != "", rx.callout(PostsState.posts_error)),
        rx.input(value=PostsState.title, on_change=PostsState.set_title),
        rx.input(value=PostsState.slug, on_change=PostsState.set_slug),
        rx.text_area(value=PostsState.body, on_change=PostsState.set_body),
        rx.checkbox("Published", checked=PostsState.published, on_change=PostsState.set_published),
        rx.button("Save", on_click=PostsState.save_post),
        rx.form(key=PostsState.form_reset_key),
        rx.foreach(
            PostsState.posts,
            lambda p: rx.hstack(
                rx.text(p["title"]),
                rx.button("Edit", on_click=PostsState.start_edit(p["id"])),
                rx.button("Delete", on_click=PostsState.delete_post(p["id"])),
            ),
        ),
    )

# app.add_page(blog_admin, route="/blog", on_load=PostsState.on_load_posts)
```

---

## `ModelListView` (read-only)

```python
from reflex_django.state import AppState, ModelListView

class AuditState(AppState, ModelListView):
    serializer_class = BlogPostSerializer

    class Meta:
        list_var = "entries"
        on_load_event = "on_load_entries"
```

No `save_*` / `delete_*` assembly.

---

## `Meta` options reference

| Option | Default | Role |
|--------|---------|------|
| `list_var` | pluralized model name | List state var |
| `save_event` / `delete_event` | `save_{model}`, `delete_{model}` | Handler names |
| `ordering` | `("-created_at",)` | Queryset order |
| `read_only_fields` | `()` | Extra non-editable fields |
| `state_fields` | writable serializer fields | Explicit editable vars |
| `reset_after_save` | `True` | Clear form after save |
| `use_form_submit` | `False` | `save_*_form` from `form_data` |
| `run_model_validation` | `False` | `Model.full_clean()` |
| `structured_errors` | `False` | `{list_var}_field_errors` |
| `load_context_processors` | `True` | `collect_reflex_context` |
| `queryset_select_related` / `queryset_prefetch` | `()` | ORM optimization |
| `permission_classes` | `()` | Permission checks |
| `login_required_actions` | all except `cancel_edit` | Wrapped with login |

---

## Manual vs mixin comparison

| | Manual | `ModelCRUDView` |
|---|--------|----------------|
| Events | Hand-written | Generated |
| Request binding | You call `current_*` | `dispatch` binds `self.request` |
| Validation | Custom | `validate_state`, `clean_{field}` |
| Time to ship | Slower | Faster for standard CRUD |

---

## Advanced usage

- `permission_classes = (IsAuthenticated,)`  
- `Meta.use_form_submit = True` for `rx.form` submit  
- Import: `from reflex_django.state import ModelCRUDView` or lazy `from reflex_django import ModelState`

---

## Common mistakes

- Missing `created_at` with default ordering.  
- Using `DjangoUserState.is_authenticated` instead of `self.request.user` for ORM filters.  
- Expecting pagination vars from the framework.

---

## Developer notes

- `ModelState` extends `AppState` + `ModelCRUDView` (`state/generic.py`); see [Reactive ModelState](reactive_model_state.md).  
- Removed APIs: `crud_mixin()`, `ModelCRUDConfig` — see [FAQ](faq.md).

---

## See also

- [Forms and validation](forms_and_validation.md)  
- [CRUD without mixins](crud_without_mixins.md)

---

**Navigation:** [← reflex-django mixins](reflex_django_mixins.md) | [Next: Forms and validation →](forms_and_validation.md)
