# Forms & validation

Two things to understand about forms in `reflex-django`:

1. There are **two styles** of binding form inputs to state — pick the one that fits.
2. Validation runs in **three stages** before a save hits the database — and you can hook into each one.

This page covers both, with small examples.

---

## Style 1 — flat reactive binding (default)

Every field on your `ModelState` is a reactive variable. Wire `value` and `on_change` directly:

```python
class ProductState(ModelState):
    model = Product
    fields = ["name", "price", "sku"]


def form_block():
    return rx.vstack(
        rx.input(value=ProductState.name,  on_change=ProductState.set_name),
        rx.input(value=ProductState.price, on_change=ProductState.set_price),
        rx.input(value=ProductState.sku,   on_change=ProductState.set_sku),
        rx.button("Save", on_click=ProductState.save),
    )
```

Every keystroke updates `ProductState.name` on the server. The UI feels real-time. The downside: you ship one WebSocket event per keystroke. For most forms, that's fine.

When to use: small forms, immediate feedback (e.g. live preview), forms where you want each field validated as the user types.

---

## Style 2 — `Meta.use_form_submit`

For larger forms, you can defer the round trip until "Save":

```python
class ProductState(ModelState):
    model = Product
    fields = ["name", "price", "sku"]

    class Meta:
        list_var = "products"
        use_form_submit = True
```

```python
def form_block():
    return rx.form(
        rx.vstack(
            rx.input(name="name",  default_value=ProductState.name),
            rx.input(name="price", default_value=ProductState.price),
            rx.input(name="sku",   default_value=ProductState.sku),
            rx.button("Save", type="submit"),
        ),
        on_submit=ProductState.save,
        key=ProductState.form_reset_key,
    )
```

`on_submit` ships all fields in one event, in one go. Better for big forms, slower live feedback.

When to use: long forms (10+ fields), forms where most validation only happens on submit anyway.

---

## The `form_reset_key` pattern

To reset a form, bump `form_reset_key`:

```python
rx.form(
    ...,
    key=ProductState.form_reset_key,
)
```

`ModelState` increments `form_reset_key` whenever:

- A save succeeds (and `Meta.reset_after_save = True`, which is the default).
- You call `cancel_edit()`.
- You load a different row for editing.
- You manually call `self.reset_form()`.

Reflex uses the `key` to remount the form, which resets any internal `<input>` state (cursor positions, uncontrolled values, etc.).

---

## The three-stage validation pipeline

Every save runs through three checks, in order. Any one of them can stop the save:

```text
state field values
     │
     ▼
[1] clean_<field>(value)         ← per-field cleaning (return cleaned, or raise ValueError)
     │
     ▼
[2] validate_state()             ← cross-field validation (write into self.error or *_field_errors)
     │
     ▼
[3] Django Model.full_clean()    ← unique=True, validators=[], required, max_length, ...
     │
     ▼
await instance.asave()
```

You can use all three, none of them, or just one. Each has its own job.

---

## Stage 1 — `clean_<field>(value)`

Best for: normalizing input (trim, upper, parse to a type) and quick per-field checks.

```python
class ProductState(ModelState):
    model = Product
    fields = ["name", "sku", "price"]

    def clean_sku(self, value: str) -> str:
        return value.strip().upper()

    def clean_price(self, value):
        try:
            n = float(value)
        except (TypeError, ValueError):
            raise ValueError("Price must be a number")
        if n < 0:
            raise ValueError("Price can't be negative")
        return value
```

The cleaned value is what makes it to the database. Raising `ValueError` records a field error and stops the save.

---

## Stage 2 — `validate_state()`

Best for: cross-field rules and state-level checks that depend on more than one input.

```python
class OrderState(ModelState):
    model = Order
    fields = ["start_date", "end_date", "amount"]

    class Meta:
        list_var = "orders"
        structured_errors = True

    def validate_state(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            self.orders_field_errors["end_date"] = "End date must be on or after start date."
        if self.amount and float(self.amount) > 10000 and not self.request.user.is_staff:
            self.error = "Amounts over $10,000 require staff approval."
```

`validate_state` runs *after* all the `clean_<field>` hooks, so by the time it sees the values, they've been normalized. Set `self.error` for global errors and `self.<list_var>_field_errors[field] = "..."` for per-field errors.

If `validate_state` records any error, the save is cancelled.

---

## Stage 3 — Django model validation

If `Meta.run_model_validation = True` (the default for `ModelState` and `ModelCRUDView`), the framework calls `instance.full_clean()` before saving. That runs:

- `unique=True` checks
- `validators=[...]` you declared on the model field
- `max_length`, `null=False`, `blank=False` enforcement
- Custom `Model.clean()` you wrote

Errors raised by `full_clean()` become per-field errors in `<list_var>_field_errors` (when `structured_errors = True`) or a single message in `self.error`.

```python
# blog/models.py
from django.core.validators import MinLengthValidator
from django.db import models


class Post(models.Model):
    title = models.CharField(
        max_length=200,
        validators=[MinLengthValidator(5)],   # → "Ensure this value has at least 5 characters."
    )
    slug  = models.SlugField(unique=True)     # → IntegrityError-prevention via full_clean
```

Set `run_model_validation = False` if you only want stages 1 and 2 (rare).

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
errs = ProductState.products_field_errors    # dict of {field: "message"}

rx.vstack(
    rx.input(value=ProductState.name, on_change=ProductState.set_name),
    rx.cond(errs["name"] != "", rx.text(errs["name"], color="red", size="1")),
)
```

The `*_field_errors` dict is keyed by field name and always exists (empty string for fields without an error).

---

## Full example — all three stages

```python
from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import models


class Product(models.Model):
    name  = models.CharField(max_length=120)
    sku   = models.CharField(max_length=32, unique=True)
    price = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(0)],
    )


class ProductState(ModelState):
    model = Product
    fields = ["name", "sku", "price"]

    class Meta:
        list_var = "products"
        run_model_validation = True
        structured_errors = True

    # Stage 1
    def clean_name(self, value: str) -> str:
        return value.strip()

    def clean_sku(self, value: str) -> str:
        return value.strip().upper()

    def clean_price(self, value):
        try:
            Decimal(value)
        except Exception:
            raise ValueError("Price must be a decimal number")
        return value

    # Stage 2
    def validate_state(self):
        if not self.name:
            self.products_field_errors["name"] = "Name is required."
        if self.sku and not self.sku.startswith("PRD-"):
            self.products_field_errors["sku"] = "SKUs must start with PRD-"

    # Stage 3 — automatic via run_model_validation = True
    #   unique=True on sku, MinValueValidator on price, max_length on name
```

---

## A few extra knobs

### Reset form after save

```python
class Meta:
    reset_after_save = True   # default
```

### Don't run Django's full_clean

```python
class Meta:
    run_model_validation = False
```

### Skip a field from validation

Mark it as read-only in your serializer (auto-built or explicit). Read-only fields are never written to the database and not validated.

```python
class ProductSerializer(ReflexDjangoModelSerializer):
    class Meta:
        model = Product
        fields = ("id", "name", "price", "created_at")
        read_only_fields = ("id", "created_at")
```

---

## Auth-specific validation (login & register pages)

If you're using `add_auth_pages()`, the built-in login/register pages have their own validation rules driven by `REFLEX_DJANGO_AUTH`:

```python
REFLEX_DJANGO_AUTH = {
    "min_password_length": 10,
    "min_username_length": 3,
    "password_complexity": {
        "uppercase": True,
        "lowercase": True,
        "digit": True,
        "symbol": False,
    },
    "username_field": "email",
}
```

Errors appear inline next to the relevant field. The same three-stage pipeline applies under the hood.

---

## Summary

| You want to… | Use |
|:---|:---|
| Normalize one field before save | `clean_<field>(value)` |
| Validate that two fields agree | `validate_state()` |
| Enforce `unique=True` / max_length | `run_model_validation = True` (default) |
| Live feedback on every keystroke | Flat reactive binding (Style 1) |
| Defer the round trip until Submit | `Meta.use_form_submit = True` (Style 2) |
| Reset form fields after save | `Meta.reset_after_save = True` + `key=form_reset_key` on `<form>` |
| Show per-field errors | `Meta.structured_errors = True` + bind to `<list_var>_field_errors` |

---

**Next:** [Model serializers →](serializers.md)
