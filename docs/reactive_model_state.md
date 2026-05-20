# Reactive ModelState

The **`ModelState`** class is the high-productivity engine of `reflex-django`. It completely automates the boilerplate of database-driven forms, lists, search, pagination, and validation. By subclassing `ModelState` and declaring a Django model alongside the desired writable fields, the package dynamically compiles data schemas, registers reactive state variables, and attaches a canonical set of CRUD event handlers at **class definition time**. 

This allows you to build sophisticated, secure, and fully reactive administration screens, dashboards, and portals with virtually zero boilerplate.

---

## 1. How ModelState Works Under the Hood

To appreciate the simplicity of `ModelState`, it is important to understand its two distinct lifecycles: **Import-Time Assembly** and **Runtime Event Dispatching**.

```mermaid
flowchart TD
    subgraph Import Time (Assembly)
        A[Class Declaration] --> B[Metaclass Execution]
        B --> C[Resolve Serializer]
        B --> D[Declare Reactive State Vars]
        B --> E[Inject Canonical Handlers]
    end
    
    subgraph Runtime (Client Event)
        F[UI Event: on_click/on_mount] --> G[Trigger Event Handler]
        G --> H[Dispatch Pipeline]
        H --> I[Bind Request Context]
        H --> J[Run Permissions & Decs]
        J --> K[Execute Pre-Save Hooks & Validation]
        K --> L[Django Async ORM Query]
        L --> M[Hydrate Reactive State Vars]
        M --> N[Re-render UI]
    end
```

### Import-Time Assembly
When your application loads and imports your state file, the metaclass (`AppStateMeta`) automatically performs the following configuration steps:
1. **Compiles the Serializer**: It either uses your explicitly provided `serializer_class` or dynamically builds a `ReflexDjangoModelSerializer` matching your `model` and `fields`.
2. **Declares Writable State Fields**: For each field listed in `fields`, the engine automatically declares a corresponding Reflex reactive variable (e.g. `title: str = ""` or `price: decimal.Decimal = 0.0`) and its standard setter (e.g. `set_title`).
3. **Injects Default CRUD Handlers**: It scans the class definition. If you have not explicitly overridden them, it injects canonical event handlers: `load`, `save`, `create`, `delete`, `refresh`, `filter`, `clear_filter`, `paginate`, and `cancel_edit`.
4. **Initializes Helper States**: It registers management variables like `editing_id` (representing the primary key currently being edited, or `-1` for a new record) and `form_reset_key` (an integer used to force-refresh the client-side DOM).

### Runtime Event Dispatching
When a user interacts with the UI (e.g. clicking a **Save** or **Delete** button):
1. The client invokes the generated handler, which calls `self.dispatch(<action_name>)`.
2. The dispatch pipeline wraps the call in `bind_request_context` to safely expose `self.request` and `self.request.user` to the state.
3. It performs permission checks (evaluating `Meta.permission_classes` or checking if `@login_required` wraps the handler).
4. It fires database querysets and operations asynchronously using Django's thread-safe async ORM primitives.
5. Upon completion, it updates the local state variables (such as list variables, validation error buffers, and input fields) which seamlessly propagates changes to the browser DOM.

---

## 2. Complete CRUD Guide: Product Catalog

Let's build a secure, fully functional product inventory manager with a list, search filters, editing forms, and input validation.

### Step 1: Define the Django Model

Ensure your Django model has appropriate field types. We will use a standard model representing inventory products.

```python
# shop/models.py
from django.db import models

class Product(models.Model):
    name = models.CharField(max_length=120, help_text="Common name of the item")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    sku = models.CharField(max_length=32, unique=True, help_text="Stock keeping unit identifier")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.sku})"
```

### Step 2: Declare the Reactive ModelState

Subclass `ModelState` to manage our database schema and UI bindings. We will configure text search, default sorting, and enable automatic validation.

```python
# shop/state.py
from reflex_django.state import ModelState
from shop.models import Product

class ProductState(ModelState):
    """Manages the backend data-flow and UI interaction for the Product model."""
    model = Product
    fields = ["name", "price", "sku", "is_active"]
    ordering = ("-created_at",)
    
    # Built-in search configuration (enables search variable + database Q filters)
    search_fields = ("name", "sku")
    
    class Meta:
        list_var = "products"       # Overrides default generic 'data' listing to 'products'
        reset_after_save = True     # Safely reset form input fields after successful save
        run_model_validation = True # Automatically execute Django's full_clean() validation
        structured_errors = True    # Populate a dict of field-level errors (products_field_errors)
```

### Step 3: Build the Reflex Page Component

Now, let's assemble the frontend page. We will bind our inputs to the auto-generated properties, render any field validation errors, and wrap our inputs in an `rx.form` bound to the `form_reset_key` to ensure clean state resets.

```python
# shop/pages.py
import reflex as rx
from shop.state import ProductState

def product_form_field(label: str, input_component: rx.Component, error_var: rx.Var) -> rx.Component:
    """Helper to render form inputs with validation error messages."""
    return rx.vstack(
        rx.text(label, size="2", weight="medium", color="gray"),
        input_component,
        rx.cond(
            error_var != "",
            rx.text(error_var, size="1", color="red", weight="medium"),
        ),
        spacing="1",
        width="100%",
    )

def products_page() -> rx.Component:
    return rx.vstack(
        rx.heading("Inventory Catalog", size="7", weight="bold"),
        rx.text("Manage store items, update price details, and track SKU inventory.", size="3", color="gray"),
        rx.divider(),
        
        # Action Bar: Search input and Create button
        rx.hstack(
            rx.input(
                placeholder="Search products by name or SKU...",
                value=ProductState.search,
                on_change=ProductState.set_search,
                width="300px",
            ),
            rx.button("Search", on_click=ProductState.refresh),
            rx.button("Clear", variant="outline", on_click=ProductState.clear_filter),
            rx.spacer(),
            rx.button(
                "Add New Item", 
                color_scheme="teal",
                on_click=ProductState.create,
            ),
            width="100%",
            spacing="3",
        ),
        
        # Display global processing error
        rx.cond(
            ProductState.error != "",
            rx.callout(
                ProductState.error, 
                color_scheme="red", 
                icon="alert_triangle",
                width="100%",
            ),
        ),
        
        # Products List Table
        rx.cond(
            ProductState.products.length() > 0,
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Name"),
                        rx.table.column_header_cell("SKU"),
                        rx.table.column_header_cell("Price"),
                        rx.table.column_header_cell("Status"),
                        rx.table.column_header_cell("Actions", text_align="right"),
                    )
                ),
                rx.table.body(
                    rx.foreach(
                        ProductState.products,
                        lambda row: rx.table.row(
                            rx.table.cell(row["name"], weight="bold"),
                            rx.table.cell(row["sku"]),
                            rx.table.cell(f"${row['price']}"),
                            rx.table.cell(
                                rx.cond(
                                    row["is_active"],
                                    rx.badge("Active", color_scheme="green"),
                                    rx.badge("Inactive", color_scheme="gray"),
                                )
                            ),
                            rx.table.cell(
                                rx.hstack(
                                    rx.button(
                                        "Edit",
                                        size="1",
                                        variant="soft",
                                        on_click=ProductState.load(row["id"]),
                                    ),
                                    rx.button(
                                        "Delete",
                                        size="1",
                                        color_scheme="red",
                                        variant="soft",
                                        on_click=ProductState.delete(row["id"]),
                                    ),
                                    spacing="2",
                                    justify="end",
                                ),
                                text_align="right",
                            ),
                        )
                    )
                ),
                width="100%",
            ),
            rx.center(
                rx.vstack(
                    rx.text("No products match your query.", color="gray", size="3"),
                    rx.button("Reset Filters", variant="ghost", on_click=ProductState.clear_filter),
                    spacing="2",
                    padding="4em",
                ),
                width="100%",
            ),
        ),
        
        rx.divider(),
        
        # Writable Form (displays dynamically for edits or additions)
        rx.cond(
            (ProductState.editing_id >= 0) | (ProductState.name != "") | (ProductState.sku != ""),
            rx.vstack(
                rx.hstack(
                    rx.heading(
                        rx.cond(
                            ProductState.editing_id >= 0,
                            f"Edit Product (ID: #{ProductState.editing_id})",
                            "Register New Product",
                        ),
                        size="5",
                    ),
                    rx.spacer(),
                    rx.button("Cancel", variant="ghost", color_scheme="gray", on_click=ProductState.cancel_edit),
                ),
                
                # Wrap input fields in form and bind key to form_reset_key to force UI remounts
                rx.form(
                    rx.vstack(
                        rx.grid(
                            product_form_field(
                                "Product Name",
                                rx.input(
                                    value=ProductState.name,
                                    on_change=ProductState.set_name,
                                    placeholder="Enter premium name...",
                                ),
                                ProductState.field_errors.get("name", ""),
                            ),
                            product_form_field(
                                "SKU Identifer",
                                rx.input(
                                    value=ProductState.sku,
                                    on_change=ProductState.set_sku,
                                    placeholder="e.g. ELEC-TV-4K",
                                ),
                                ProductState.field_errors.get("sku", ""),
                            ),
                            product_form_field(
                                "Price ($ USD)",
                                rx.input(
                                    value=ProductState.price.to(str),
                                    on_change=ProductState.set_price,
                                    placeholder="0.00",
                                ),
                                ProductState.field_errors.get("price", ""),
                            ),
                            columns="3",
                            spacing="4",
                            width="100%",
                        ),
                        rx.hstack(
                            rx.checkbox(
                                "Available in Catalog (Active)",
                                checked=ProductState.is_active,
                                on_change=ProductState.set_is_active,
                            ),
                            rx.spacer(),
                            rx.button("Save Item", color_scheme="teal", on_click=ProductState.save),
                            spacing="4",
                            width="100%",
                            padding_top="2",
                        ),
                        spacing="3",
                        width="100%",
                    ),
                    key=ProductState.form_reset_key,
                    width="100%",
                ),
                padding="1.5em",
                border="1px solid var(--gray-5)",
                border_radius="8px",
                width="100%",
                background="var(--gray-2)",
            ),
        ),
        
        spacing="5",
        width="100%",
        max_width="64em",
        padding="2em",
        on_mount=ProductState.refresh,
    )
```

---

## 3. The `form_reset_key` Remounting Pattern

A common challenge in reactive web frameworks is clearing stale text and error indicators from browser-side DOM inputs. In Reflex, modifying python variables in the state clears the state variables on the server. However, unless the client elements completely reload, browsers can retain uncommitted user text (especially inside `rx.text_area` or native HTML `<input>` structures).

`ModelState` solves this elegantly by exposing an auto-incrementing integer: **`form_reset_key`**.

### The Lifecyle of Form Clears
* **Save Complete**: When a row is saved (and `Meta.reset_after_save` is `True`), the state variables are reset to their default values, and the engine automatically increments `form_reset_key` by 1.
* **Edit Start**: When you invoke `.load(pk)`, the engine retrieves the row, populates the state inputs, and increments `form_reset_key`.
* **Cancel Edit**: When you invoke `.cancel_edit()`, the fields are cleared to their empty defaults, and the engine increments `form_reset_key`.

By binding `key=YourState.form_reset_key` to the parent component, React detects the key change as a new component instance and **remounts the DOM subtree**, forcing all form inputs to discard old client-side state and align with your fresh server-side values.

> [!TIP]
> Always place your **Save / Cancel / Add** buttons *outside* or *within* the form depending on submission type. If you use custom click events (`on_click=State.save`), you do not need standard form post submission behavior.

---

## 4. The Validation Pipeline

`ModelState` provides a rigorous multi-stage validation pipeline that integrates with Django's model-level validators before committing changes to the database.

```text
State Inputs (Client)
        │
        ▼
   Clean Hook  ──────►  Runs clean_{field}() methods to normalize input formats
        │
        ▼
 Validate Hook ──────►  Executes validate_state() for cross-field business logic
        │
        ▼
 Django Clean  ──────►  Triggers Django full_clean() model validation (if configured)
        │
        ▼
Database Commit
```

### Stage 1: Field-Specific Normalization (`clean_{field_name}`)
Before general validation runs, the engine checks for methods following the `clean_<field_name>(self, value)` pattern. Use this to format strings, strip empty spaces, or normalize casing.

```python
class ProductState(ModelState):
    model = Product
    fields = ["name", "sku", "price"]

    def clean_sku(self, value: str) -> str:
        """Strip whitespaces and force uppercase format for SKU identifiers."""
        return value.strip().upper()
```

### Stage 2: Cross-Field Business Logic (`validate_state`)
Override the `validate_state(self, ctx)` hook to perform custom validation that requires comparing multiple fields or checking external database rules. This method should return a dictionary mapping field names to error messages (or return an empty dictionary/None if valid).

```python
class ProductState(ModelState):
    model = Product
    fields = ["name", "price", "sku"]

    async def validate_state(self, ctx) -> dict[str, str]:
        # Always run default validator first to inherit basic empty/null checks
        errors = await super().validate_state(ctx)
        
        # Add custom business logic
        if self.price <= 0 and "free" not in self.name.lower():
            errors["price"] = "Price must be greater than zero unless the product name contains 'free'."
            
        return errors
```

### Stage 3: Django Model Validation (`run_model_validation`)
Setting `Meta.run_model_validation = True` configures `reflex-django` to convert the current state values into a temporary Django model instance and call Django's native `.full_clean()` method. 

This automatically executes:
* Any validators defined on model fields (e.g. `EmailValidator`, `MinValueValidator`).
* Custom validation logic defined inside the model's clean method (`Product.clean()`).
* Database constraints (like unique constraints) at the Python validation layer.

```python
# shop/state.py
class ProductState(ModelState):
    model = Product
    fields = ["name", "sku"]
    
    class Meta:
        run_model_validation = True
        structured_errors = True  # Populates a structured field_errors dict
```

> [!WARNING]
> Never declare `run_model_validation = True` on the class body of a State class. That variable name is reserved for the validation execution method on `ModelCRUDView`. Define it **only** within your nested `class Meta:` block.

---

## 5. Pagination, Custom Searches, and User Scoping

### Built-in Search & Pagination
If you have large datasets, enable search and pagination in the `Meta` options. The engine automatically handles page slicing and offsets:

```python
class PostState(ModelState):
    model = BlogPost
    fields = ["title", "slug", "content"]
    
    # Class-level variables are parsed to construct pagination parameters
    paginate_by = 25
    search_fields = ("title", "content")
```

This configuration exposes a complete set of reactive pagination variables and buttons in the frontend:
* `page`: The active page index.
* `page_count`: The total number of pages.
* `next_page`: Increments page and refreshes the data.
* `prev_page`: Decrements page and refreshes the data.
* `paginate(page=X)`: Instantly navigates to a specific page.

```python
# UI Pagination controls
rx.hstack(
    rx.button("Previous", on_click=PostState.prev_page, disabled=PostState.page <= 1),
    rx.text(f"Page {PostState.page} of {PostState.page_count}", size="2"),
    rx.button("Next", on_click=PostState.next_page, disabled=PostState.page >= PostState.page_count),
    spacing="4",
    align="center",
)
```

### Custom Query Filtering
If you need search filters beyond basic text matches (such as date range filters or category drop-downs), override `filter_queryset`:

```python
from django.db.models import Q

class ProductState(ModelState):
    model = Product
    fields = ["name", "price"]
    
    # Custom reactive filter criteria
    selected_category: str = "all"
    max_price: str = ""

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        
        if self.selected_category != "all":
            queryset = queryset.filter(category__slug=self.selected_category)
            
        if self.max_price.strip() != "":
            try:
                queryset = queryset.filter(price__lte=float(self.max_price))
            except ValueError:
                pass
                
        return queryset

    @rx.event
    async def apply_filters(self):
        # Always reset the pagination counter to page 1 before applying new query parameters
        self.reset_page()
        await self.refresh()
```

### User and Tenant Scoping
Security is paramount. You must prevent users from accessing or modifying database records belonging to other users or accounts. You can achieve this by overriding state querysets and record retrieval parameters, or using the built-in `UserScopedMixin`.

#### Option A: Manual Hook Overrides (Fully Custom Control)
```python
class DocumentState(ModelState):
    model = Document
    fields = ["title", "file_path"]

    def get_queryset(self):
        """Restrict list view queries to the authenticated user."""
        return Document.objects.filter(owner=self.request.user)

    def get_object_lookup(self, pk: int) -> dict:
        """Enforce owner constraints on load and delete queries."""
        return {"pk": pk, "owner": self.request.user}

    def get_create_kwargs(self, state_data: dict) -> dict:
        """Inject user context into newly created database objects."""
        return {**state_data, "owner": self.request.user}
```

#### Option B: Utilizing `UserScopedMixin` (High-Productivity Wrapper)
By mixing in `UserScopedMixin`, the package automatically wires `get_queryset`, `get_object_lookup`, and `get_create_kwargs` for you:

```python
from reflex_django.state.mixins.scoping import UserScopedMixin

class DocumentState(ModelState, UserScopedMixin):
    model = Document
    fields = ["title", "file_path"]
    
    # Map the model's user foreign key field name
    scope_field = "owner_id"  
```

---

## 6. Overriding and Customizing Handlers

If you want to perform custom logic before or after a database operation (like creating a log entry, generating a slug, or triggering an email notification), you can intercept actions at different points of the dispatch lifecycle.

### The Canonical API Method Signatures

These are the primary methods available on every `ModelState` subclass:

| Method | Signature | Description |
|:---|:---|:---|
| **`load`** | `load(pk: int)` | Hydrates form inputs with row fields and sets `editing_id` to `pk`. |
| **`save`** | `save()` | Validates inputs, executes creates or updates, and reloads listings. |
| **`create`** | `create()` | Resets form inputs, sets `editing_id = -1`, ready for item creation. |
| **`delete`** | `delete(pk: int)` | Removes the matching database record and refreshes the data array. |
| **`refresh`** | `refresh()` | Slices, searches, filters, and loads the active dataset. |
| **`cancel_edit`** | `cancel_edit()` | Resets all input variables and clears `editing_id` to `-1`. |

### Intercepting with Custom Event Handlers
If you override a method like `.save()` in your subclass, `reflex-django` honors your definition and does not inject the default version. You can write custom logic and manually trigger the internal dispatch pipeline:

```python
from reflex_django.state.constants import ACTION_SAVE
from reflex_django.auth.decorators import login_required

class ArticleState(ModelState):
    model = BlogPost
    fields = ["title", "content"]

    @rx.event
    @login_required # Be sure to re-apply decorators when overriding handlers
    async def save(self):
        # 1. Inject or modify fields before saving
        self.title = self.title.strip().title()
        
        # 2. Trigger the primary saving pipeline
        await self.dispatch(ACTION_SAVE)
        
        # 3. Perform post-save side effects
        if not self.error:
            return rx.toast(f"Successfully saved article: {self.title}")
```

---

## 7. Troubleshooting Common ModelState Issues

| Symptom | Cause | Solution |
|:---|:---|:---|
| `ImproperlyConfigured: Invalid fields...` | A string in the `fields` array does not exist on the Django model. | Verify the spelling of fields on your model class (use the exact database attribute name). |
| Validation errors appear in the console but not in the UI. | `Meta.structured_errors` is disabled, or field errors are not bound in the page component. | Set `structured_errors = True` in your Meta class, and display `ProductState.field_errors.get("field")` in your UI. |
| Changes in the database are not updating the Reflex list. | The list was not instructed to reload. | Trigger `State.refresh` inside the UI or invoke `await self.refresh()` at the end of custom state events. |
| Form inputs remain filled after cancelling or editing. | Stale client-side DOM values are cached in browser memory. | Assign `key=State.form_reset_key` to your `rx.form` container to force a React remount. |
| Overridden handler is not firing. | The UI is referencing the old legacy name (like `save_product`) instead of the canonical `.save`. | Check your buttons and verify that `on_click` references the updated canonical method (`ProductState.save`). |
| `TypeError: 'bool' object is not callable` on validation. | Declaring `run_model_validation = True` on the class body shadowed the system validation method. | Move configuration options like `run_model_validation` into your nested `class Meta:` block. |

---

**Navigation:** [← ModelState vs. ModelCRUDView](model_state_and_crud_view.md) | [Next: CRUD with Mixins & States →](crud_with_mixins_and_states.md)
