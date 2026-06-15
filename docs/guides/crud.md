---
level: intermediate
tags: [crud, database]
---

# CRUD patterns

This guide covers four ways to build list, create, edit, and delete flows in reflex-django. Pick the section that matches how much control you want. For mixins and serializers, see [Mixins](mixins.md) and [Serializers](serializers.md).


---

## CRUD the manual way {#manual}

**What you'll learn:** How to build a full list, create, edit, and delete page with plain `AppState` and the async ORM, so every query and check is visible in your code.

**When you need this:**

- The workflow is unusual (multi-step, conditional fields, or rules that do not fit declarative CRUD).
- You want to read every database call line by line before reaching for helpers.

<div class="rd-instructor" markdown>

Think of this page as writing Django views by hand, except the "view" is a Reflex state class and the browser updates reactively when you change state fields.

</div>

`reflex-django` ships declarative helpers (`ModelState`, `ModelCRUDView`) that generate most CRUD wiring for you. This page walks through the same product inventory feature without them. When you are done, you will know exactly what those helpers automate.

!!! tip "Prefer less code later?"
    After this page, [CRUD with ModelState](crud.md#modelstate) covers the same feature in a fraction of the lines.

---

## What we are building

A page at `/inventory` where a logged-in user manages their own products. Each user only sees their own rows.

- List with pagination
- Search by name, SKU, or category
- Create and edit (one form, edit mode toggled by `editing_id`)
- Delete with an ownership check on every read and write

Every database call uses the async ORM (`acreate`, `aget`, `asave`, `adelete`, `async for`, `acount`).

---

## 1. The model

```python
# inventory/models.py
from django.conf import settings
from django.db import models


class Product(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inventory_products",
    )
    name = models.CharField(max_length=128)
    sku = models.CharField(max_length=64, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=64, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.sku})"
```

Run migrations:

```bash
python manage.py makemigrations inventory
python manage.py migrate
```

---

## 2. The serializer

Reflex state fields are JSON-encoded before they reach the browser. `Decimal` and `datetime` need conversion. A serializer is the easiest path:

```python
# inventory/serializers.py
from reflex_django.serializers import ReflexDjangoModelSerializer
from inventory.models import Product


class ProductSerializer(ReflexDjangoModelSerializer):
    class Meta:
        model = Product
        fields = ("id", "name", "sku", "price", "category", "is_active", "created_at")
        read_only_fields = ("id", "created_at")
```

`await ProductSerializer(qs, many=True).adata()` turns a queryset into a JSON-safe list of dicts. More detail in [Model serializers](serializers.md).

---

## 3. The state shell

```python
# inventory/views.py
import reflex as rx
from django.db.models import Q
from reflex_django.pages.decorators import page
from reflex_django.states import AppState
from inventory.models import Product
from inventory.serializers import ProductSerializer


class InventoryState(AppState):
    products: list[dict] = []
    error: str = ""

    name: str = ""
    sku: str = ""
    price: str = ""
    category: str = ""
    is_active: bool = True

    editing_id: int = -1

    search_query: str = ""
    page: int = 1
    page_size: int = 8
    total_pages: int = 1
```

`InventoryState(AppState)` gives you `self.request.user` inside handlers. The fields above are reactive: assigning to them on the server updates the browser.

---

## 4. Scoped queryset helper

Centralize "current user plus search" once. Every other method calls this helper:

```python
    def _filtered_qs(self):
        user = self.request.user
        if not user.is_authenticated:
            raise PermissionError("Sign in first.")
        qs = Product.objects.filter(owner=user)
        q = self.search_query.strip()
        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(sku__icontains=q)
                | Q(category__icontains=q)
            )
        return qs.order_by("-created_at")
```

`filter(owner=user)` is the security boundary. As long as every read and write goes through this queryset (or repeats the same `owner=` filter), users cannot touch each other's rows by forging IDs.

---

## 5. Load and paginate

```python
    @rx.event
    async def load(self):
        self.error = ""
        try:
            qs = self._filtered_qs()
            total = await qs.acount()
            self.total_pages = max(1, (total + self.page_size - 1) // self.page_size)
            self.page = min(self.page, self.total_pages)
            start = (self.page - 1) * self.page_size
            page_qs = qs[start : start + self.page_size]
            self.products = await ProductSerializer(page_qs, many=True).adata()
        except PermissionError as e:
            self.error = str(e)
            self.products = []
        except Exception as e:
            self.error = f"Could not load: {e}"

    @rx.event
    async def set_search(self, value: str):
        self.search_query = value
        self.page = 1
        await self.load()

    @rx.event
    async def next_page(self):
        if self.page < self.total_pages:
            self.page += 1
            await self.load()

    @rx.event
    async def prev_page(self):
        if self.page > 1:
            self.page -= 1
            await self.load()
```

!!! warning "Stay async in handlers"
    Use `await qs.acount()`, not `qs.count()`. Blocking ORM calls inside `async def` handlers stall the event loop for every connected user.

---

## 6. Create and update

```python
    def _validation_error(self) -> str | None:
        if not self.name.strip():
            return "Name is required."
        if not self.sku.strip():
            return "SKU is required."
        try:
            if float(self.price) <= 0:
                return "Price must be positive."
        except ValueError:
            return "Price must be a number."
        return None

    @rx.event
    async def save(self):
        self.error = ""
        user = self.request.user
        if not user.is_authenticated:
            return rx.toast.error("Please log in.")

        err = self._validation_error()
        if err:
            self.error = err
            return

        data = {
            "name": self.name.strip(),
            "sku": self.sku.strip().upper(),
            "price": self.price,
            "category": self.category.strip(),
            "is_active": self.is_active,
        }

        try:
            if self.editing_id >= 0:
                product = await Product.objects.aget(pk=self.editing_id, owner=user)
                for k, v in data.items():
                    setattr(product, k, v)
                await product.asave()
                yield rx.toast.success(f"Updated '{product.name}'.")
            else:
                new = await Product.objects.acreate(owner=user, **data)
                yield rx.toast.success(f"Added '{new.name}'.")

            self.reset_form()
            await self.load()
        except Exception as e:
            self.error = f"Save failed: {e}"

    @rx.event
    def reset_form(self):
        self.name = ""
        self.sku = ""
        self.price = ""
        self.category = ""
        self.is_active = True
        self.editing_id = -1
        self.error = ""
```

On update, `aget(pk=..., owner=user)` ensures foreign IDs cannot be edited. On create, `owner=user` is always set server-side.

---

## 7. Edit and delete

```python
    @rx.event
    async def start_editing(self, product_id: int):
        try:
            p = await Product.objects.aget(pk=product_id, owner=self.request.user)
        except Product.DoesNotExist:
            return rx.toast.error("Not found.")
        self.editing_id = p.id
        self.name = p.name
        self.sku = p.sku
        self.price = str(p.price)
        self.category = p.category
        self.is_active = p.is_active

    @rx.event
    async def delete(self, product_id: int):
        try:
            p = await Product.objects.aget(pk=product_id, owner=self.request.user)
            name = p.name
            await p.adelete()
            yield rx.toast.success(f"Deleted '{name}'.")
            await self.load()
        except Product.DoesNotExist:
            return rx.toast.error("Not found.")
```

The form binds `price` as a string while the database stores `Decimal`. Convert at the boundary (`str(p.price)` when loading, string in `data` when saving).

---

## 8. The UI and page registration

```python
def inventory_page() -> rx.Component:
    return rx.container(
        rx.heading("My Inventory", size="8"),
        rx.cond(
            InventoryState.error != "",
            rx.callout(InventoryState.error, color_scheme="red"),
        ),
        rx.grid(form_card(), list_card(), columns="2", spacing="6"),
        padding="2rem",
    )


@page(route="/inventory", title="Inventory", on_load=InventoryState.load)
def index() -> rx.Component:
    return inventory_page()
```

Wire inputs with `value=` and `on_change=` to your state fields, and hook buttons to `InventoryState.save`, `start_editing`, and `delete`. That is the whole feature in one `views.py`.

---

## Manual vs declarative (preview)

| You write | Manual `AppState` | `ModelState` |
|:---|:---|:---|
| `load` handler | Yes | Generated |
| `save` / `delete` | Yes | Generated |
| Per-field state vars | Yes | Generated from `fields` |
| Pagination | Yes | `paginate_by = N` |
| Owner scoping | Yes (`_filtered_qs`) | `scope_field` or hooks |
| The UI components | Yes | Yes (still your job) |

Both styles can live in the same project. Use manual code when the page is unusual; use `ModelState` when it is standard CRUD.

---

## What just happened?

You built list, search, pagination, create, edit, and delete with explicit async ORM calls and per-user scoping. Every security check and validation path is in your file, which is the baseline the declarative CRUD helpers automate next.

**Next up:** [CRUD with ModelState →](crud.md#modelstate)
---

## CRUD with ModelState {#modelstate}

**What you'll learn:** How `ModelState` declares a Django model and field list, then generates reactive vars, handlers, pagination, search, and validation hooks for a standard CRUD page.

**When you need this:**

- Your page is mostly one model with list, edit, save, and delete.
- You want less boilerplate than the manual approach in [CRUD the manual way](crud.md#manual).

`ModelState` is the declarative version of the inventory page you wrote by hand. You declare `model` and `fields`; the framework generates state variables, `load`/`save`/`delete` handlers, and list refresh logic. You still write the UI.

---

## The smallest CRUD state

```python
# shop/views.py
from reflex_django.states import ModelState
from shop.models import Product


class ProductState(ModelState):
    model = Product
    fields = ["name", "price", "sku", "is_active"]
    ordering = ("-created_at",)
    list_var = "products"
```

From those lines you get:

- Reactive list: `ProductState.products` (or `ProductState.data` if you omit `list_var`)
- Form fields: `name`, `price`, `sku`, `is_active` with `set_<field>` setters
- Handlers: `refresh`, `load`, `save`, `create`, `delete`, `cancel_edit`, `filter`, `paginate`
- Tracking vars: `editing_id`, `form_reset_key`, `error`, `search`

You write components; `ModelState` writes the wiring.

---

## How assembly works (briefly)

When Python defines `class ProductState(ModelState):`, a small assembly step runs:

1. **Build a serializer** from `model` + `fields` (unless you pass `serializer_class`).
2. **Declare state fields** with Python types matching Django fields.
3. **Inject handlers** for list load, save, delete, and edit mode.
4. **Register helper vars** (`editing_id`, pagination, search) when configured.

At runtime, each event goes through a dispatch pipeline: bind request context, check permissions, validate, hit the database, update reactive vars, send the diff to the browser. Override hooks at any stage.

---

## A complete catalog page

### Model

```python
# shop/models.py
from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=120)
    sku = models.CharField(max_length=32, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
```

### State

```python
# shop/views.py
import reflex as rx
from reflex_django.pages.decorators import page
from reflex_django.states import ModelState
from shop.models import Product


class ProductState(ModelState):
    model = Product
    fields = ["name", "price", "sku", "is_active"]
    ordering = ("-created_at",)
    search_fields = ("name", "sku")
    list_var = "products"
    paginate_by = 10
    structured_errors = True
    run_model_validation = True
    reset_after_save = True
```

!!! tip "Class body vs inner Meta"
    Prefer settings on the class body (`paginate_by = 10`) for IDE autocomplete. An inner `class Meta(ModelCRUDMeta):` still works for overrides.

### UI (excerpt)

```python
def products_page() -> rx.Component:
    errs = ProductState.field_errors
    return rx.vstack(
        rx.heading("Catalog"),
        rx.hstack(
            rx.input(
                placeholder="Search",
                value=ProductState.search,
                on_change=ProductState.set_search,
            ),
            rx.button("Refresh", on_click=ProductState.refresh),
            rx.button("Add new", on_click=ProductState.create),
        ),
        rx.cond(
            ProductState.editing_id != -1,
            rx.form(
                rx.vstack(
                    rx.input(value=ProductState.name, on_change=ProductState.set_name),
                    rx.cond(errs["name"] != "", rx.text(errs["name"], color="red", size="1")),
                    rx.button("Save", on_click=ProductState.save),
                    rx.button("Cancel", on_click=ProductState.cancel_edit, variant="ghost"),
                ),
                key=ProductState.form_reset_key,
            ),
        ),
        rx.foreach(ProductState.products, product_row),
        spacing="4",
        padding="2em",
    )


def product_row(row: dict) -> rx.Component:
    return rx.hstack(
        rx.text(row["name"], weight="bold"),
        rx.badge(row["sku"]),
        rx.spacer(),
        rx.button("Edit", on_click=ProductState.load(row["id"])),
        rx.button("Delete", on_click=ProductState.delete(row["id"]), color_scheme="red"),
    )


@page(route="/products", title="Products", on_load=ProductState.refresh)
def index() -> rx.Component:
    return products_page()
```

With `structured_errors = True`, per-field messages live in `ProductState.field_errors` (the default name when `list_var` is customized, assembly sets `field_errors_var` accordingly).

---

## Handlers and variables you get for free

| Handler | What it does |
|:---|:---|
| `refresh()` | Reload the list with current search, filter, and page |
| `create()` | Enter "new row" mode and save on next `save()` |
| `load(pk)` | Enter edit mode for one row |
| `save()` | Validate, create or update, reload list |
| `delete(pk)` | Delete one row and reload |
| `cancel_edit()` | Leave edit mode and clear the form |
| `filter(**kwargs)` | Apply ORM filter kwargs and reload |
| `clear_filter()` | Clear stored filter and reload |
| `paginate(page=..., page_size=...)` | Jump page when `paginate_by` is set |

| Variable | What it is |
|:---|:---|
| `products` (or `data`) | Current page of serialized rows |
| `editing_id` | PK being edited, or `-1` for new |
| `error` | Top-level error message |
| `search` | Current search string |
| `form_reset_key` | Bump on `<form key=...>` to remount inputs |
| `field_errors` | Per-field errors when `structured_errors = True` |
| `page`, `page_size`, `total_count`, `page_count` | Pagination when enabled |

---

## Pagination and search

Set `paginate_by = 10` on the class body. That enables `page`, `page_size`, `total_count`, `page_count`, plus `paginate`, `next_page`, and `prev_page`.

Set `search_fields = ("name", "sku")` for case-insensitive `icontains` search combined with `OR`. Bind `ProductState.search` in the UI and call `refresh()` after the user searches.

For richer filters, override `filter_queryset`:

```python
class ProductState(ModelState):
    model = Product
    fields = ["name", "price", "is_active"]
    only_active: bool = True

    def filter_queryset(self, qs):
        qs = super().filter_queryset(qs)
        if self.only_active:
            qs = qs.filter(is_active=True)
        return qs
```

---

## Validation hooks

Every save runs three stages (opt in where noted):

```text
get_state_data()
     |
clean_<field>  (return an error string, or "" when valid)
     |
validate_state(ctx, data)  (return a dict of field errors)
     |
clean_state(data)  (normalize values before save)
     |
full_clean()  (when run_model_validation = True)
     |
await instance.asave()
```

Example:

```python
class ProductState(ModelState):
    model = Product
    fields = ["name", "price", "sku", "is_active"]
    structured_errors = True
    run_model_validation = True

    def clean_price(self, value) -> str:
        try:
            if float(value) < 0:
                return "Price cannot be negative."
        except (TypeError, ValueError):
            return "Price must be a number."
        return ""

    def clean_state(self, data: dict) -> dict:
        data = dict(data)
        if isinstance(data.get("sku"), str):
            data["sku"] = data["sku"].strip().upper()
        return data

    def validate_state(self, ctx, data: dict) -> dict[str, str]:
        errors: dict[str, str] = {}
        if data.get("is_active") and not data.get("sku"):
            errors["sku"] = "Active products need a SKU."
        return errors
```

Use `clean_<field>` for quick per-field checks. Use `clean_state` to normalize. Use `validate_state` for cross-field rules.

---

## User-scoped rows

Override three hooks, or use `UserScopedMixin`:

```python
from reflex_django.state.mixins import UserScopedMixin


class TodoState(UserScopedMixin, ModelState):
    model = Todo
    fields = ["title", "done"]
    scope_field = "owner_id"   # FK column name; use "owner" for the relation field
    list_var = "todos"
```

`UserScopedMixin` filters `get_queryset`, `get_object_lookup`, and `get_create_kwargs` by the logged-in user. See [Mixins](mixins.md) for manual composition.

---

## Read-only lists

When you only need a list (no form, no save), use `ModelListView`:

```python
from reflex_django.states import AppState
from reflex_django.state import ModelListView


class CatalogState(AppState, ModelListView):
    model = Product
    fields = ["name", "price", "sku"]
    search_fields = ("name",)
    paginate_by = 20
    list_var = "products"
```

---

## When ModelState is not the right fit

- Multi-model forms or wizards
- Lists built from heavy aggregations
- Pages where CRUD is not the main job

For those, stay with plain `AppState` as in [CRUD the manual way](crud.md#manual). If you need an explicit serializer class or named handlers like `save_post`, see [ModelCRUDView](crud.md#modelcrudview).

---

## Troubleshooting

| Symptom | Likely cause |
|:---|:---|
| List stays empty after save | Check `list_var` matches what the UI binds (`data` is the default). |
| Field errors do not show | Set `structured_errors = True` and bind `field_errors`. |
| Form keeps stale values | Put `key=State.form_reset_key` on `rx.form`. |
| Users see each other's rows | Add scoping hooks or `UserScopedMixin`. |

---

## What just happened?

You declared `model` and `fields` once, got generated handlers and reactive vars, and learned the validation and scoping hooks you will override in real projects. That is the recommended default for standard CRUD pages.

**Next up:** [ModelCRUDView with serializers →](crud.md#modelcrudview)
---

## ModelCRUDView with serializers {#modelcrudview}

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

Full comparison: [Choosing ModelState vs ModelCRUDView](crud.md#choosing).

---

## What just happened?

You composed `AppState` with `ModelCRUDView`, wired an explicit serializer, and scoped rows to the logged-in user. The same dispatch pipeline and hooks as `ModelState` apply; only naming and serializer sourcing differ.

**Next up:** [Choosing ModelState vs ModelCRUDView →](crud.md#choosing)
---

## ModelState vs ModelCRUDView {#choosing}

**What you'll learn:** Which declarative CRUD class to pick for a new page, and how small a refactor is if you switch later.

**When you need this:**

- You have seen both `ModelState` and `ModelCRUDView` and want one decision page.
- You are planning several CRUD screens and want consistent naming across the project.

Both classes run the same dispatch pipeline, validation hooks, and `Meta` options. Switching later is a small rename refactor, not a rewrite.

---

## Side by side

```python
# ModelState (recommended for most new pages)
from reflex_django.states import ModelState


class ProductState(ModelState):
    model = Product
    fields = ["name", "price", "sku"]
    list_var = "products"
```

```python
# ModelCRUDView (explicit serializer + named handlers)
from reflex_django.states import AppState
from reflex_django.state import ModelCRUDView


class ProductState(AppState, ModelCRUDView):
    model = Product
    serializer_class = ProductSerializer
    list_var = "products"
    save_event = "save_product"
    delete_event = "delete_product"
```

| | `ModelState` | `ModelCRUDView` |
|:---|:---|:---|
| Inheritance | One parent: `ModelState` | Compose: `AppState, ModelCRUDView` |
| Serializer | Auto-built from `fields` | You provide `serializer_class` |
| Default list var | `data` | plural model name (e.g. `products`) |
| Default save | `save()` | `save_product` (model-dependent) |
| Default delete | `delete(pk)` | `delete_product(pk)` |
| Trade-off | Less explicit, fewer files | More explicit API surface |

---

## Feature parity

These work the same on both classes:

- Pagination (`paginate_by`), search (`search_fields`), structured errors
- Hooks: `get_queryset`, `filter_queryset`, `get_object_lookup`, `get_create_kwargs`
- Validation: `clean_<field>`, `validate_state`, `clean_state`, `run_model_validation`
- Lifecycle: `before_save`, `after_save`, `before_delete`, `after_delete`
- Mixins from `reflex_django.state.mixins` (see [Mixins](mixins.md))

Nothing is exclusive to one class.

---

## When ModelState is the better choice

- No serializer exists yet for this model.
- The page is a one-off prototype.
- Generic handler names (`save`, `delete`) are fine.

```python
class TaskState(ModelState):
    model = Task
    fields = ["title", "done"]
    list_var = "tasks"
```

Five lines of declaration, then your UI.

---

## When ModelCRUDView is the better choice

- You already maintain a `ReflexDjangoModelSerializer` (or want one file per model schema).
- Many CRUD states share a module and verb-noun names reduce confusion (`save_order` vs six different `save` methods).
- You want to compose a subset of CRUD mixins (list + create only, for example).
- The same field list also backs an HTTP API and you want one serializer definition for Reflex.

```python
class OrderState(AppState, ModelCRUDView):
    model = Order
    serializer_class = OrderSerializer
    list_var = "orders"
    save_event = "save_order"
    delete_event = "delete_order"
```

---

## Read-only lists

Both stacks support read-only list states via `ModelListView`:

```python
from reflex_django.states import AppState
from reflex_django.state import ModelListView


class CatalogState(AppState, ModelListView):
    model = Product
    fields = ["name", "price"]
    search_fields = ("name",)
    paginate_by = 20
    list_var = "products"
```

No form fields, no save or delete handlers. Good for public catalogs and audit views.

---

## Decision tree

```text
Need a CRUD page?
|
+-- Standard list / edit / save / delete?
|   +-- No serializer yet, generic names OK     -> ModelState
|   +-- Explicit serializer or named handlers     -> ModelCRUDView
|
+-- Read-only list?                               -> ModelListView
|
+-- Wizard, multi-model, or unusual workflow?     -> AppState + manual handlers
|                                                  (see CRUD the manual way)
|
+-- Only some CRUD actions (e.g. list + create)?  -> ModelCRUDView + mixins
```

---

## Switching between them

```python
# Before
class TaskState(ModelState):
    model = Task
    fields = ["title", "done"]
    list_var = "tasks"


# After
class TaskState(AppState, ModelCRUDView):
    model = Task
    serializer_class = TaskSerializer
    list_var = "tasks"
    save_event = "save_task"
    delete_event = "delete_task"
```

Update UI call sites (`TaskState.save()` becomes `TaskState.save_task()` if you use named events). Hooks and `Meta` options stay the same.

---

## What just happened?

You compared the two declarative CRUD classes on naming, serializers, and composition. For most new pages, start with `ModelState`; reach for `ModelCRUDView` when explicit schemas or handler names matter.

**Next up:** [Mixins: compose your own state →](mixins.md)