---
level: intermediate
tags: [forms, validation]
---

# Forms and validation

**What you'll learn:** Two input binding styles for Reflex forms, and the three-stage validation pipeline that runs before a `ModelState` or `ModelCRUDView` save hits the database.

**When you need this:**

- You are wiring inputs to a declarative CRUD state and want errors to show inline.
- You need to choose between live per-keystroke binding and submit-once forms.

---

## Style 1: flat reactive binding (default)

Each field on `ModelState` is a reactive var. Bind `value` and `on_change` directly:

```python
from reflex_django.states import ModelState


class ProductState(ModelState):
    model = Product
    fields = ["name", "price", "sku"]


def form_block():
    return rx.vstack(
        rx.input(value=ProductState.name, on_change=ProductState.set_name),
        rx.input(value=ProductState.price, on_change=ProductState.set_price),
        rx.input(value=ProductState.sku, on_change=ProductState.set_sku),
        rx.button("Save", on_click=ProductState.save),
    )
```

Every keystroke sends a WebSocket event. That feels responsive and works well for small forms.

---

## Style 2: submit once with `use_form_submit`

For longer forms, defer the round trip until the user clicks Save:

```python
class ProductState(ModelState):
    model = Product
    fields = ["name", "price", "sku"]
    use_form_submit = True
    list_var = "products"


def form_block():
    return rx.form(
        rx.vstack(
            rx.input(name="name", default_value=ProductState.name),
            rx.input(name="price", default_value=ProductState.price),
            rx.input(name="sku", default_value=ProductState.sku),
            rx.button("Save", type="submit"),
        ),
        on_submit=ProductState.save,
        key=ProductState.form_reset_key,
    )
```

`on_submit` ships all fields in one event. Better for large forms; less live feedback.

---

## The `form_reset_key` pattern

Wrap fields in `rx.form(..., key=State.form_reset_key)` so Reflex remounts inputs after:

- A successful save (when `reset_after_save = True`, the default)
- `cancel_edit()` or `reset_state_fields()`
- Loading a different row for editing (`bump_form_reset_key()` runs automatically)

Without `key`, controlled inputs can keep stale DOM state even when server vars cleared.

---

## Three-stage validation pipeline

```text
get_state_data()
     |
[1] clean_<field>(value)     return error string, or "" when valid
     |
[2] validate_state(ctx, data)   return dict of field errors
     |
     clean_state(data)        normalize values
     |
[3] full_clean()             when run_model_validation = True
     |
await instance.asave()
```

### Stage 1: `clean_<field>`

Quick per-field checks. Return a non-empty string to record an error for that field.

```python
def clean_price(self, value) -> str:
    try:
        if float(value) < 0:
            return "Price cannot be negative."
    except (TypeError, ValueError):
        return "Price must be a number."
    return ""
```

### Stage 2: `validate_state` and `clean_state`

Cross-field rules and normalization:

```python
def validate_state(self, ctx, data: dict) -> dict[str, str]:
    errors: dict[str, str] = {}
    if data.get("start_date") and data.get("end_date") and data["start_date"] > data["end_date"]:
        errors["end_date"] = "End date must be on or after start date."
    return errors


def clean_state(self, data: dict) -> dict:
    data = dict(data)
    if isinstance(data.get("sku"), str):
        data["sku"] = data["sku"].strip().upper()
    return data
```

### Stage 3: Django model validation

Set `run_model_validation = True` to call `instance.full_clean()` before save. That enforces `unique=True`, field `validators=[...]`, `max_length`, and custom `Model.clean()`.

!!! warning "Defaults are off"
    `structured_errors` and `run_model_validation` default to `False`. Turn them on explicitly when you want per-field UI errors and model-level validation.

---

## Showing errors in the UI

Top-level error:

```python
rx.cond(
    ProductState.error != "",
    rx.callout(ProductState.error, color_scheme="red"),
)
```

Per-field errors (requires `structured_errors = True`):

```python
errs = ProductState.field_errors

rx.vstack(
    rx.input(value=ProductState.name, on_change=ProductState.set_name),
    rx.cond(errs["name"] != "", rx.text(errs["name"], color="red", size="1")),
)
```

With a custom `list_var` on `ModelCRUDView`, the dict may be named `{list_var}_field_errors` (for example `posts_field_errors`).

---

## Read-only fields skip validation

Mark fields read-only in the serializer (auto-built or explicit). Read-only fields are not written and not validated on save.

```python
class ProductSerializer(ReflexDjangoModelSerializer):
    class Meta:
        model = Product
        fields = ("id", "name", "price", "created_at")
        read_only_fields = ("id", "created_at")
```

---

## Auth form validation

Built-in login and register pages (via `add_auth_pages()`) use `REFLEX_DJANGO_AUTH` for password length, username rules, and inline errors. Same pipeline idea, different config surface.

---

## Quick reference

| Goal | Use |
|:---|:---|
| Per-field rule | `clean_<field>` returning error string |
| Two fields must agree | `validate_state(ctx, data)` |
| Trim or normalize | `clean_state(data)` |
| `unique=True` on model | `run_model_validation = True` |
| Live keystroke updates | Flat `value` / `on_change` binding |
| One event on Submit | `use_form_submit = True` + `rx.form` |
| Reset inputs after save | `key=form_reset_key` on `rx.form` |
| File uploads | `rx.upload` (see [File uploads](file_uploads.md)) |

---

## What just happened?

You picked a binding style, learned the validation order for declarative CRUD saves, and saw how to surface errors in components.

**Next up:** [Model serializers →](serializers.md)