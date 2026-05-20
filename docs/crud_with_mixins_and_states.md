# CRUD with Mixins & States

While **`ModelState`** provides a high-speed, zero-boilerplate shortcut for standard database operations, larger applications often demand custom database serialization, pluralized naming patterns, or pre-existing Django Rest Framework (DRF) schemas. 

To support these architectures, `reflex-django` offers a modular, explicit mixin: **`ModelCRUDView`**. When combined with **`AppState`**, it provides developers with absolute control over serializers, relational field optimization, custom lifecycle events, and fine-grained database queries, all while preserving the core benefits of automated CRUD integration.

---

## 1. When to Choose ModelCRUDView

Here is a quick architectural checklist to help you select the ideal paradigm:

| Need | Recommended Class | Details |
|:---|:---|:---|
| **Rapid Prototyping** | `ModelState` | Auto-compiles a schema from `model` and `fields` with generic `data` and `error` parameters. |
| **Custom Schemas** | `ModelCRUDView` | Allows you to pass an explicit `ReflexDjangoModelSerializer` class with nesting or computed fields. |
| **Pluralized Naming** | `ModelCRUDView` | Variables match your database collections (e.g. `self.posts` instead of `self.data`, `self.posts_error` instead of `self.error`). |
| **Read-Only Slices** | `ModelListView` | A stripped-down cousin of `ModelCRUDView` that ignores saving and deleting handlers, perfect for search-only dashboards. |

```text
       ModelState                  ModelCRUDView + AppState
 ┌──────────────────────┐          ┌──────────────────────┐
 │ • Class: ModelState  │          │ • Class: AppState,   │
 │ • Writable: Fields   │          │          ModelCRUDView│
 │ • Serializer: Auto   │   vs.    │ • Serializer: Custom │
 │ • List: self.data    │          │ • List: self.[plural]│
 │ • Error: self.error  │          │ • Error: [plural]_err│
 └──────────────────────┘          └──────────────────────┘
```

---

## 2. Defining the Model & Custom Serializer

Consider a blogging application where each `BlogPost` belongs to an `Author`. We want custom field requirements, read-only audit timestamps, and relational controls.

### Step 1: Define the Django Model
```python
# blog/models.py
from django.conf import settings
from django.db import models

class BlogPost(models.Model):
    title = models.CharField(max_length=200, help_text="Headline of the article")
    slug = models.SlugField(max_length=220, unique=True)
    body = models.TextField(blank=True)
    published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blog_posts"
    )

    def __str__(self):
        return self.title
```

### Step 2: Create the Explicit Serializer
Subclass `ReflexDjangoModelSerializer` to map Python structures to client JSON. This gives us granular control over field constraints and read-only attributes:

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

---

## 3. Declaring the Custom CRUD State

Now, inherit from both `AppState` and `ModelCRUDView`. In this scenario, we override names in the `Meta` options to output pluralized listings (`posts`) and assign custom legacy events:

```python
# blog/states/posts.py
from reflex_django.state import AppState, ModelCRUDView
from blog.serializers import BlogPostSerializer

class PostsState(AppState, ModelCRUDView):
    """Manages the backend context and schema interaction for BlogPosts."""
    serializer_class = BlogPostSerializer
    
    # Optional: Configure database search and sorting attributes
    search_fields = ("title", "slug")
    ordering = ("-created_at",)

    class Meta:
        list_var = "posts"            # Generates self.posts (instead of self.data)
        error_var = "posts_error"      # Generates self.posts_error (instead of self.error)
        save_event = "save_post"       # Attaches legacy event handler save_post()
        delete_event = "delete_post"   # Attaches legacy event handler delete_post()
```

### What Assembly Dynamically Hydrates:
* **Collection Variable**: `posts: list[dict]` holding serialized active records.
* **Error Buffer**: `posts_error: str` holding active operational errors.
* **Input Parameters**: `title`, `slug`, `body`, and `published` (with matching `set_*` setters).
* **Legacy Events**: `on_load_posts` (list load), `save_post` (save), `delete_post(pk)` (delete), and `start_edit(pk)` (hydrates inputs).
* **Canonical API**: Because `use_canonical_api` defaults to `True`, the engine **also** injects clean, generic methods (`refresh`, `save`, `load`, `delete`, `create`, `cancel_edit`). Both legacy and canonical events route through the same underlying logic.

---

## 4. Advanced User-Scoped Data Protection

Securing multi-tenant or user-scoped applications requires restricting data queries so users can only view or mutate records they own.

### Option A: Custom Lifecycle Hooks (Maximum Flexibility)
Override individual lifecycle methods on your State class to apply query parameters and author mappings dynamically:

```python
class PostsState(AppState, ModelCRUDView):
    serializer_class = BlogPostSerializer

    class Meta:
        list_var = "posts"
        read_only_fields = ("author",)  # Extracted from request, never mapped from user forms

    def get_queryset(self):
        """Query posts belonging strictly to the authenticated request user."""
        return BlogPost.objects.filter(author=self.request.user)

    def get_object_lookup(self, pk: int) -> dict:
        """Enforce owner validation when retrieving single rows for edits or deletes."""
        return {"pk": pk, "author": self.request.user}

    def get_create_kwargs(self, state_data: dict) -> dict:
        """Inject the authenticated user's PK into newly saved BlogPost objects."""
        return {**state_data, "author": self.request.user}
```

### Option B: The `UserScopedMixin` (Declarative Layout)
If you are managing typical user-owned models, mix in `UserScopedMixin` to automatically configure the hooks:

```python
from reflex_django.state.mixins import UserScopedMixin

class PostsState(AppState, ModelCRUDView, UserScopedMixin):
    serializer_class = BlogPostSerializer
    
    # Specify the foreign key database column on BlogPost
    scope_field = "author_id"  

    class Meta:
        list_var = "posts"
```

---

## 5. Query Optimization & Relational Slicing

For tables with foreign keys or many-to-many relationships, triggering standard queries can quickly trigger the dreaded `N+1` database query problem. `ModelCRUDView` provides native performance parameters in `Meta` to execute prefetching and joins directly inside the async database call.

```python
class AdvancedPostsState(AppState, ModelCRUDView):
    serializer_class = BlogPostSerializer

    class Meta:
        list_var = "posts"
        
        # Optimize database joins using select_related for foreign keys
        queryset_select_related = ("author", "category")
        
        # Optimize database queries using prefetch_related for M2M structures
        queryset_prefetch = ("tags",)
```

---

## 6. Complete Implementation: The Blog Portal Page

Here is a full, production-ready admin interface utilizing our `PostsState` class:

```python
# blog/pages.py
import reflex as rx
from blog.states.posts import PostsState

def blog_admin_page() -> rx.Component:
    return rx.vstack(
        rx.heading("Article Publisher", size="7", weight="bold"),
        rx.text("Publish stories, manage drafts, and track user posts.", color="gray"),
        rx.divider(),
        
        # Status Alert Bar
        rx.cond(
            PostsState.posts_error != "",
            rx.callout(
                PostsState.posts_error, 
                color_scheme="red", 
                icon="alert_triangle",
                width="100%",
            )
        ),
        
        # Form Editor Grid (triggers when editing is active or fields contain text)
        rx.cond(
            (PostsState.editing_id >= 0) | (PostsState.title != "") | (PostsState.slug != ""),
            rx.vstack(
                rx.heading(
                    rx.cond(PostsState.editing_id >= 0, "Edit Story Draft", "Write New Post"),
                    size="4",
                ),
                
                # Wrap all editable fields in rx.form and bind key to force input refreshes
                rx.form(
                    rx.vstack(
                        rx.input(
                            placeholder="Draft Title...",
                            value=PostsState.title,
                            on_change=PostsState.set_title,
                        ),
                        rx.input(
                            placeholder="URL slug-format-here...",
                            value=PostsState.slug,
                            on_change=PostsState.set_slug,
                        ),
                        rx.text_area(
                            placeholder="Write your article content here...",
                            value=PostsState.body,
                            on_change=PostsState.set_body,
                            rows="6",
                        ),
                        rx.hstack(
                            rx.checkbox(
                                "Publish Immediately",
                                checked=PostsState.published,
                                on_change=PostsState.set_published,
                            ),
                            rx.spacer(),
                            rx.button("Cancel", variant="outline", on_click=PostsState.cancel_edit),
                            rx.button("Save Article", color_scheme="teal", on_click=PostsState.save_post),
                            width="100%",
                        ),
                        spacing="3",
                    ),
                    key=PostsState.form_reset_key,
                    width="100%",
                ),
                padding="1.5em",
                background="var(--gray-2)",
                border_radius="8px",
                width="100%",
            )
        ),
        
        # Articles Grid List
        rx.cond(
            PostsState.posts.length() > 0,
            rx.grid(
                rx.foreach(
                    PostsState.posts,
                    lambda post: rx.card(
                        rx.vstack(
                            rx.hstack(
                                rx.text(post["title"], weight="bold", size="4"),
                                rx.spacer(),
                                rx.cond(
                                    post["published"],
                                    rx.badge("Published", color_scheme="green"),
                                    rx.badge("Draft", color_scheme="yellow"),
                                )
                            ),
                            rx.text(
                                rx.cond(
                                    post["body"] != "",
                                    post["body"],
                                    "No content provided.",
                                ),
                                size="2", 
                                color="gray",
                                line_clamp=2,
                            ),
                            rx.divider(),
                            rx.hstack(
                                rx.text(f"Created: {post['created_at']}", size="1", color="gray"),
                                rx.spacer(),
                                rx.button(
                                    "Edit", 
                                    size="1", 
                                    variant="soft",
                                    on_click=PostsState.start_edit(post["id"]),
                                ),
                                rx.button(
                                    "Delete", 
                                    size="1", 
                                    color_scheme="red",
                                    variant="soft",
                                    on_click=PostsState.delete_post(post["id"]),
                                ),
                                spacing="2",
                            ),
                            spacing="2",
                            width="100%",
                        )
                    )
                ),
                columns="2",
                spacing="4",
                width="100%",
            ),
            rx.center(
                rx.text("No articles written yet. Write your first story above!", color="gray"),
                width="100%",
                padding="4em",
            )
        ),
        
        spacing="5",
        width="100%",
        max_width="56em",
        on_mount=PostsState.on_load_posts,
    )
```

---

## 7. Configuration Reference: Meta Options

These attributes represent all available customization fields inside the nested `class Meta` of `ModelCRUDView` or `ModelState`:

| Meta Attribute | Default Value | Role & Description |
|:---|:---|:---|
| **`list_var`** | `"data"` | Name of the state variable holding the serialized records. |
| **`error_var`** | `"error"` | Name of the state variable holding query or operational errors. |
| **`save_event`** | `"save_{model}"` | Legacy event handler name generated to perform saves. |
| **`delete_event`** | `"delete_{model}"` | Legacy event handler name generated to perform deletions. |
| **`use_canonical_api`**| `True` | Automatically inject clean, generic methods (`refresh`, `save`, `load`, `delete`, `create`, `cancel_edit`). |
| **`reset_after_save`** | `True` | Resets all input state variables to their defaults after a successful save. |
| **`form_reset_var`** | `"form_reset_key"` | The variable incremented on cancel, save, and edit to force React form remounts. |
| **`run_model_validation`**| `False` | Performs full model-level validation (runs Django `full_clean()`) prior to saving. |
| **`structured_errors`**| `False` | Generates a structured field errors dictionary (`field_errors`) for UI bindings. |
| **`queryset_select_related`**| `()` | Tuple of relational field names to load in a single database query. |
| **`queryset_prefetch`**| `()` | Tuple of relational fields to load via prefetch queries. |
| **`permission_classes`**| `()` | List of permission authorization classes evaluated during actions. |
| **`login_required_actions`**| `load, save, delete` | Set of actions restricted to authenticated users. |

---

## 8. Common Pitfalls & Anti-Patterns

* **Missing AppState Subclassing**: `ModelCRUDView` is a mixin class. If you do not include `AppState` first (e.g. `class MyState(AppState, ModelCRUDView)`), session mapping and authenticated request parameters will not exist, causing operational crashes during dispatching.
* **Assuming 'data' or 'error' Variables Exist**: Unlike `ModelState`, `ModelCRUDView` relies on pluralized properties by default. If your model is `Product` and you do not set `Meta.list_var`, the variable is named `products` (not `data`) and `products_error` (not `error`).
* **Omitting async def on Customized Handlers**: If you override a generated handler (like `save_post`), always declare the method with `async def` and invoke database commands asynchronously. Sync queries blocks the ASGI execution loop.

---

**Navigation:** [← Reactive ModelState](reactive_model_state.md) | [Next: reflex-django Mixins →](reflex_django_mixins.md)
