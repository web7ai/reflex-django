# CRUD with mixins and states

This page focuses on **`ModelCRUDView`** — the declarative CRUD mixin you combine with **`AppState`**. For the recommended **`ModelState`** shortcut (`model` + `fields`, generic `data` / `error` vars), see **[Reactive ModelState](reactive_model_state.md)** and the combined guide **[ModelState and ModelCRUDView](model_state_and_crud_view.md)**.

---

## Which API should I use?

| Need | API |
|------|-----|
| Fastest path for standard CRUD | **`ModelState`** — see [comparison guide](model_state_and_crud_view.md#modelstate--recommended-path) |
| Existing `ReflexDjangoModelSerializer` classes | **`AppState, ModelCRUDView`** |
| Per-model names (`posts`, `posts_error`) | **`ModelCRUDView`** + `Meta.list_var` |
| Read-only tables | **`ModelListView`** or **`ModelState`** (list only) |

**`ModelState` is not a separate engine** — it subclasses `AppState` and `ModelCRUDView` and auto-builds the serializer from `model` + `fields`.

---

## ModelState quick reference (same BlogPost)

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
        list_var = "posts"  # optional: keep plural name instead of default "data"
```

UI: `PostState.refresh`, `PostState.load(id)`, `PostState.save`, `PostState.delete(id)` — full page in [reactive_model_state.md](reactive_model_state.md) and [model_state_and_crud_view.md](model_state_and_crud_view.md).

---

## ModelCRUDView — explicit serializer

Everything below uses **`AppState, ModelCRUDView`**. Hooks, `Meta` options, pagination, and search apply to **`ModelState`** as well.

> Tutorial **`BlogPost`** code is example application code. Tested patterns: `reflex_django_tests/test_reactive_model_state.py`, `test_model_state.py`.

---

## Prerequisites

- [ModelState and ModelCRUDView](model_state_and_crud_view.md) — architecture and when to use each  
- [State management](state_management.md) — `AppState` vs plain `rx.State`  
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

Default ordering is `("-created_at",)` unless you set `ordering` on the state class. Ensure the model has `created_at` or override `ordering` (e.g. `("-id",)`).

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

With default **`use_canonical_api = True`**, you also get `load`, `save`, `refresh`, `create`, `delete`, `cancel_edit`, `filter`, `paginate` — same as `ModelState`.

---

## Canonical vs legacy handlers

| Action | Legacy (`Meta` names) | Canonical (all models) |
|--------|----------------------|-------------------------|
| Load list | `on_load_posts` | `refresh` |
| Save | `save_post` | `save` |
| Edit | `start_edit(id)` | `load(id)` |
| Delete | `delete_post(id)` | `delete(id)` |
| New row | (via `start_edit` / clear) | `create` |

Wire your UI to either set; both call the same `dispatch` pipeline.

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

## Search and pagination

**Built-in search** — set `search_fields` on the class body or `Meta`:

```python
class PostsState(AppState, ModelCRUDView):
    serializer_class = BlogPostSerializer
    search_fields = ("title", "slug")
    paginate_by = 20

    class Meta:
        list_var = "posts"
```

With `list_var = "posts"`, the search var defaults to **`posts_search`** unless you set `search_var`. On **`ModelState`**, search is always **`search`**.

**Custom filter** — override `filter_queryset`:

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

Call `await self.refresh()` (or `await self._load_posts()`) after changing `search` if you use a dedicated search button.

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
        # custom logic, or call await self.dispatch("save")
        ...
```

See `reflex_django_tests/test_model_state.py` (`_CustomSaveState`).

---

## Page wiring

Wrap editable fields in `rx.form(..., key=PostsState.form_reset_key)` so the form clears after save/update and reloads when entering edit mode ([Clearing forms](reactive_model_state.md#clearing-forms-save-edit-cancel)).

```python
import reflex as rx
from blog.states import PostsState

def blog_admin() -> rx.Component:
    return rx.vstack(
        rx.cond(PostsState.posts_error != "", rx.callout(PostsState.posts_error)),
        rx.form(
            rx.vstack(
                rx.input(value=PostsState.title, on_change=PostsState.set_title),
                rx.input(value=PostsState.slug, on_change=PostsState.set_slug),
                rx.text_area(value=PostsState.body, on_change=PostsState.set_body),
                rx.checkbox(
                    "Published",
                    checked=PostsState.published,
                    on_change=PostsState.set_published,
                ),
                spacing="3",
                width="100%",
            ),
            key=PostsState.form_reset_key,
            width="100%",
        ),
        rx.hstack(
            rx.button("Save", on_click=PostsState.save_post),
            rx.button("Save (canonical)", on_click=PostsState.save),
            rx.button("Cancel", on_click=PostsState.cancel_edit),
            spacing="3",
        ),
        rx.foreach(
            PostsState.posts,
            lambda p: rx.hstack(
                rx.text(p["title"]),
                rx.button("Edit", on_click=PostsState.start_edit(p["id"])),
                rx.button("Delete", on_click=PostsState.delete_post(p["id"])),
            ),
        ),
        on_mount=PostsState.on_load_posts,
    )
```

---

## ModelListView (read-only)

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
| `list_var` | `"data"` (`ModelState`); pluralized model name (`ModelCRUDView`) | List state var |
| `error_var` | `"error"` or `{list_var}_error` | Error message var |
| `search_var` | `"search"` or `{list_var}_search` | Search input var |
| `save_event` / `delete_event` | `save_{model}`, `delete_{model}` | Legacy handler names |
| `use_canonical_api` | `True` | Inject `load`, `save`, `refresh`, … |
| `ordering` | `("-created_at",)` or model `Meta.ordering` | Queryset order |
| `paginate_by` | `None` | Page size; enables pagination vars |
| `search_fields` | `()` | Enables search + filter |
| `read_only_fields` | `()` | Extra non-editable fields |
| `state_fields` | writable serializer fields | Explicit editable vars |
| `reset_after_save` | `True` | Clear form after save |
| `form_reset_var` | `"form_reset_key"` | Bind to `rx.form(..., key=...)` |
| `use_form_submit` | `False` | `save_*_form` from `form_data` |
| `run_model_validation` | `False` | `Model.full_clean()` (**Meta only**) |
| `structured_errors` | `False` | Per-field errors var |
| `load_context_processors` | `True` | `collect_reflex_context` |
| `queryset_select_related` / `queryset_prefetch` | `()` | ORM optimization |
| `permission_classes` | `()` | Permission checks |
| `login_required_actions` | load, save, delete, start_edit | Wrapped with login |

---

## Manual vs mixin comparison

| | Manual `rx.State` | `ModelCRUDView` / `ModelState` |
|---|-------------------|--------------------------------|
| Events | Hand-written | Generated (+ overridable) |
| Request binding | You call `current_*` | `dispatch` binds `self.request` |
| Validation | Custom | `validate_state`, `clean_{field}` |
| Time to ship | Slower | Faster for standard CRUD |

---

## Advanced usage

- `permission_classes = (IsAuthenticated,)`  
- `Meta.use_form_submit = True` for `rx.form` submit  
- Import: `from reflex_django.state import ModelState, ModelCRUDView, AppState`

---

## Common mistakes

- Using **`ModelCRUDView` without `AppState`** — no `self.request.user` / login helpers.  
- Missing `created_at` with default `ordering = ("-created_at",)`.  
- Expecting `data` / `error` on `ModelCRUDView` without setting `list_var` — defaults are pluralized.  
- `run_model_validation = True` on the class body — use **`Meta.run_model_validation` only**.

---

## Developer notes

- `ModelState` = `AppState` + `ModelCRUDView` + auto serializer (`state/model_state.py`).  
- Removed APIs: `crud_mixin()`, `ModelCRUDConfig` — see [FAQ](faq.md).

---

## See also

- [ModelState and ModelCRUDView](model_state_and_crud_view.md) — full comparison and examples  
- [Reactive ModelState](reactive_model_state.md) — `ModelState` deep dive  
- [Forms and validation](forms_and_validation.md)  
- [CRUD without mixins](crud_without_mixins.md)

---

**Navigation:** [← reflex-django mixins](reflex_django_mixins.md) | [ModelState vs CRUDView](model_state_and_crud_view.md) | [Next: Forms and validation →](forms_and_validation.md)
