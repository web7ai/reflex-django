# Forms & Validation

Building production-ready forms requires more than simple text synchronization. Developers must prevent input lag on fast typists, prevent DOM data caching, validate input fields using complex business logic, and render structured errors back to users.

To achieve this, `reflex-django` provides an advanced, state-driven validation framework that connects Reflex interactive inputs with Django's native field constraints and validation pipelines.

---

## 1. Choosing Your Input Style

`reflex-django` supports two input styles. Choose the style that best fits your design and performance requirements:

```text
    1. Flat Bindings (Real-time Sync)       2. Form Submit (Debounced Sync)
       ┌────────────────────────┐              ┌────────────────────────┐
       │   value=State.title    │              │      name="title"      │
       │ on_change=set_title    │              │                        │
       │ (High reactivity)      │              │ (Zero typing overhead) │
       └────────────────────────┘              └────────────────────────┘
```

### Style A: Flat Bindings (Reactivity-First)
Inputs are directly bound to state fields on the server. The state is updated in real time as the user types.

* **Pros**: Real-time styling, instant character counting, and immediate client-side feedback.
* **Cons**: Network round-trips for every keystroke (can be optimized using debounce settings).

```python
rx.input(
    value=ProductState.name,
    on_change=ProductState.set_name,
    placeholder="Enter product title..."
)
```

### Style B: Form Submit (Performance-First)
Inputs are treated as standard un-bound HTML fields. The data is only transmitted to the server when the user clicks **Submit**.

* **Pros**: Zero typing latency, resilient over high-latency networks.
* **Cons**: No real-time server-side validation as the user types.

```python
# Enable form submit processing in your state configuration
class ProductState(ModelState):
    class Meta:
        use_form_submit = True
        
# Bind the submission handler to your form
rx.form(
    rx.vstack(
        rx.input(name="name", placeholder="Product name..."),
        rx.input(name="price", placeholder="0.00"),
        rx.button("Save Item", type="submit"),
    ),
    on_submit=ProductState.save_form,  # Auto-generated submission handler
    reset_on_submit=False,
    key=ProductState.form_reset_key,
)
```

> [!IMPORTANT]
> When using `use_form_submit`, ensure that the `name=` attribute of each `rx.input` matches the corresponding field name in your Django serializer.

---

## 2. Form Remounting & Caching Prevention

A common bug in reactive single-page applications (SPAs) is **cached browser data**. When you save or cancel a form, the server resets the variables. However, the browser may retain the user's typed text inside input fields.

To solve this, `reflex-django` uses an auto-incrementing integer: **`form_reset_key`**.

```text
           Form Actions (Save / Cancel / Load Edit)
                             │
                             ▼
             Server Resets State Variables
                             │
                             ▼
            Server Increments form_reset_key
                             │
                             ▼
         React Detects Key Change in the Client
                             │
                             ▼
        Remounts DOM Form Subtree (Discards Caches)
```

### The Form Reset Lifecycle
The engine automatically manages the `form_reset_key` during different user actions:

| Action / Handler | Resets Python Variables? | Increments `form_reset_key`? | Best For |
|:---|:---|:---|:---|
| **`cancel_edit()`** | Yes | Yes | Dismissing the editor. |
| **`load(pk)`** | Hydrates with row data | Yes | Entering edit mode. |
| **`save()` (Success)** | Yes (when `reset_after_save=True`)| Yes | Finalizing record writes. |
| **`reset_state_fields()`**| Yes | Yes | Manually clearing all inputs. |
| **`bump_form_reset_key()`**| No | Yes | Clearing browser text manually without changing state data. |

To enforce this, always assign the key to your form container:

```python
rx.form(
    rx.vstack(
        rx.input(value=State.title, on_change=State.set_title),
        # All inputs inside this form are cleanly remounted when key changes
    ),
    key=State.form_reset_key,
)
```

---

## 3. The Multi-Stage Validation Pipeline

Before data is saved to the database, `reflex-django` routes values through a structured validation pipeline:

### Step 1: Normalization (`clean_{field_name}`)
Define `clean_<field>` methods to normalize and validate individual fields. These methods should return the cleaned value or raise a `serializers.ValidationError`:

```python
class PostState(ModelState):
    model = BlogPost
    fields = ["title", "slug"]

    def clean_slug(self, value: str) -> str:
        """Normalize URL slug formats: strip whitespace, lowercase, and replace spaces."""
        cleaned = value.strip().lower().replace(" ", "-")
        if not cleaned:
            raise serializers.ValidationError("Slug cannot be empty.")
        return cleaned
```

### Step 2: Cross-Field Validation (`validate_state`)
Override the async `validate_state(self, ctx)` hook to perform cross-field validation. Return a dictionary mapping field names to error messages:

```python
class RegisterState(AppState):
    password: str = ""
    confirm_password: str = ""

    async def validate_state(self, ctx) -> dict[str, str]:
        errors = await super().validate_state(ctx)
        
        if self.password != self.confirm_password:
            errors["confirm_password"] = "Passwords do not match."
            
        return errors
```

### Step 3: Model-Level Constraints (`run_model_validation`)
Enable `run_model_validation = True` in your `Meta` class to automatically execute Django's native field constraints and `.full_clean()` validations:

```python
class ProductState(ModelState):
    model = Product
    fields = ["name", "sku", "price"]

    class Meta:
        run_model_validation = True
        structured_errors = True  # Populates field-specific errors
```

This ensures that Django's built-in field validators (e.g. `EmailValidator`, unique constraints) are executed, and any errors are captured and returned to the UI.

---

## 4. Rendering Global & Field-Specific Errors

When validation fails, `reflex-django` updates your state's error variables so you can display them in the UI:

### Global Error Buffer
Available as **`State.error`** (for `ModelState`) or **`State.{list_var}_error`** (for `ModelCRUDView`). It contains a general error summary, perfect for rendering a global banner:

```python
rx.cond(
    ProductState.error != "",
    rx.callout(
        ProductState.error, 
        color_scheme="red", 
        icon="alert_triangle",
    ),
)
```

### Field-Specific Errors
When `Meta.structured_errors = True` is enabled, the engine populates a **`field_errors`** dictionary. You can bind these errors directly to their corresponding inputs:

```python
rx.vstack(
    rx.input(
        value=ProductState.sku,
        on_change=ProductState.set_sku,
        placeholder="Enter SKU code...",
    ),
    # Render error only if it exists for this field
    rx.cond(
        ProductState.field_errors.get("sku", "") != "",
        rx.text(
            ProductState.field_errors.get("sku", ""),
            color="red",
            size="1",
        ),
    ),
)
```

---

## 5. Complete Implementation: Form Validation UI

Here is a complete, production-ready form component showing our validation pipeline in action:

```python
# blog/pages.py
import reflex as rx
from blog.states import BlogPostState

def styled_input_field(label: str, input_field: rx.Component, field_name: str) -> rx.Component:
    """Helper to render labeled inputs with real-time error messages."""
    return rx.vstack(
        rx.text(label, size="2", weight="medium", color="gray"),
        input_field,
        rx.cond(
            BlogPostState.field_errors.get(field_name, "") != "",
            rx.text(
                BlogPostState.field_errors.get(field_name, ""),
                color="red",
                size="1",
                weight="medium",
            ),
        ),
        spacing="1",
        width="100%",
    )

def article_editor_form() -> rx.Component:
    return rx.vstack(
        rx.heading("Article Editor", size="6"),
        rx.text("Draft stories, format slugs, and publish articles.", color="gray"),
        rx.divider(),
        
        # Form Container
        rx.form(
            rx.vstack(
                styled_input_field(
                    "Article Title",
                    rx.input(
                        value=BlogPostState.title,
                        on_change=BlogPostState.set_title,
                        placeholder="Premium Headline...",
                    ),
                    "title",
                ),
                styled_input_field(
                    "URL Slug",
                    rx.input(
                        value=BlogPostState.slug,
                        on_change=BlogPostState.set_slug,
                        placeholder="slug-format-here",
                    ),
                    "slug",
                ),
                styled_input_field(
                    "Content Body",
                    rx.text_area(
                        value=BlogPostState.body,
                        on_change=BlogPostState.set_body,
                        placeholder="Write article...",
                        rows="6",
                    ),
                    "body",
                ),
                rx.hstack(
                    rx.button("Cancel", variant="soft", color_scheme="gray", on_click=BlogPostState.cancel_edit),
                    rx.spacer(),
                    rx.button("Save Draft", color_scheme="teal", on_click=BlogPostState.save),
                    width="100%",
                ),
                spacing="4",
                width="100%",
            ),
            key=BlogPostState.form_reset_key,
            width="100%",
        ),
        spacing="4",
        padding="2em",
        border="1px solid var(--gray-4)",
        border_radius="12px",
        max_width="32em",
    )
```

---

## 6. Authentication Form Validation Rules

`reflex-django`'s session authentication routines also leverage structured validation parameters, which can be configured inside your project's `settings.py` file:

```python
# django_project/settings.py

REFLEX_DJANGO_AUTH = {
    # Password complexity rules
    "PASSWORD_MIN_LENGTH": 8,
    "PASSWORD_REQUIRE_DIGIT": True,
    "PASSWORD_REQUIRE_SPECIAL": True,
    
    # Registration options
    "EMAIL_REQUIRED": True,
    
    # Login parameter keys
    "LOGIN_FIELDS": ("username", "email"),
}
```

The authentication mixins (like `session_auth_mixin`) automatically run these rules during user registration and login, mapping any failures to the global `error` buffer.

---

## 7. Common Form Pitfalls & Solutions

* **Stale Text Inputs**: If you do not assign `key=State.form_reset_key` to your form container, the client's browser may retain previously typed values after a save or cancel action.
* **Typing Keystroke Latency**: If bound inputs feel sluggish or laggy, wrap your inputs in standard HTML fields using the `use_form_submit` option to batch transmissions.
* **Missing Field Declarations**: If you are using `use_form_submit`, ensure that your HTML `name="..."` tags exactly match the fields defined on your Django serializer. Mismatched fields are silently ignored by the deserialization engine.

---

**Navigation:** [← reflex-django Mixins](reflex_django_mixins.md) | [Next: Command Line Interface →](cli.md)
