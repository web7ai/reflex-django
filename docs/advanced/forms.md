# Forms and FieldSpec

`FieldSpec` is a framework-neutral field descriptor used by serializers, scaffolding, and generated state fields. It keeps model, serializer, and form metadata in one place so Reflex forms match Django behavior.

## `FieldSpec`

```python
from reflex_django.schema import FieldSpec

spec = FieldSpec(name="price", kind="decimal", required=True, label="Price")
```

| Attribute | Purpose |
|:---|:---|
| `name` | Field/state var name |
| `kind` | Semantic kind: `str`, `text`, `int`, `float`, `decimal`, `bool`, `date`, `datetime`, `time`, `relation` |
| `required` | Required writable field |
| `read_only` | Excluded from writable state fields by default |
| `max_length` | String length hint |
| `choices` | Choice pairs |
| `relation_to` | Related model label for FK-style fields |
| `help_text` | Help text |
| `label` | Human label |
| `validators` | Server-side validators returning an error string or `None` |
| `var_type` | Reflex state type; decimal/date/time values map to `str` |

## Build from a Django model

```python
from reflex_django.schema import model_field_specs

specs = model_field_specs(Product)
```

Primary keys, `auto_now`, and `auto_now_add` fields are read-only. Foreign keys are represented as `field_id` relation specs.

## Build from a ModelForm

```python
from django import forms
from reflex_django.schema import fieldspecs_from_model_form


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "price", "active"]


specs = fieldspecs_from_model_form(ProductForm)
```

Use this when an existing Django `ModelForm` already defines the editable surface.

## Build from a DRF-style serializer

```python
from reflex_django.schema import fieldspecs_from_drf_serializer

specs = fieldspecs_from_drf_serializer(ProductSerializer)
```

The adapter does not require Django REST Framework at runtime. It reads common serializer field attributes such as `required`, `read_only`, and `max_length`, and maps field class names to `FieldSpec.kind`.

## Helper functions

```python
from reflex_django.schema import (
    field_names,
    required_field_names,
    writable_specs,
)

names = field_names(specs)
writable = writable_specs(specs)
required = required_field_names(specs)
```

## Build state fields

```python
from reflex_django.schema import build_state_fields_from_specs

state_fields = build_state_fields_from_specs(specs)
```

Mapping:

| FieldSpec kind | State field |
|:---|:---|
| `bool` | `BoolStateField` |
| `float` | `FloatStateField` |
| `int`, `relation` | `IntStateField` |
| everything else | `StrStateField` |

Use `state_field_from_spec(spec)` for one field. Read-only specs are skipped by default; pass `writable_only=False` to include them.

## Scaffold widget mapping

`reflex django scaffold` uses the same specs:

| FieldSpec kind | Generated control |
|:---|:---|
| `bool` | `rx.checkbox` |
| `text` | `rx.text_area` |
| `int`, `float`, `decimal`, `relation` | `rx.input(type="number")` |
| date/time/string | `rx.input(type="text")` |

Scaffold filters out read-only specs and generates search fields from text-like widgets unless `--search` is provided.

**Next:** [Model state](model-state.md), [Serializers](serializers.md), and [CLI](cli.md).
