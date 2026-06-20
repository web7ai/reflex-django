# Serializers

Turn Django model rows into JSON-friendly dicts for Reflex state. No Django REST framework required.

Use serializers when you write handlers yourself (like the [Tutorial](../learn/quickstart.md)). For full list/create/update/delete with less boilerplate, see [Model state](model-state.md).

## Basic usage

```python
--8<-- "snippets/serializer_example.py"
```

Register the page in `shop/shop.py` with `app.add_page` as usual.

## API

Define a subclass with `Meta.model` and field lists:

| Meta option | Purpose |
|:---|:---|
| `model` | Django model class (required) |
| `fields` | Tuple of field names to include (`id` is always added) |
| `exclude` | Fields to omit |
| `read_only_fields` | Extra read-only names beyond auto-detected timestamps |

| Method | When to use |
|:---|:---|
| `.data` | Sync: one instance or small queryset |
| `.adata()` | Async handlers (preferred in `@rx.event`) |
| `.alist(qs)` | Async class helper for querysets |
| `.list(qs)` | Sync class helper |

Pass `many=True` (default for querysets) to serialize lists:

```python
rows = await ProductSerializer(qs, many=True).adata()
single = ProductSerializer(product).data
```

## Read-only and writable fields

Auto read-only: `id`, `auto_now`, and `auto_now_add` fields. Add more in `Meta.read_only_fields`.

`writable_field_names()` returns editable names. Model state uses this for form fields.

## Shared schema

The unified `FieldSpec` layer can derive field metadata from Django models, ModelForms, and DRF-style serializers:

```python
from reflex_django.schema import (
    fieldspecs_from_drf_serializer,
    fieldspecs_from_model_form,
    model_field_specs,
)
```

Use it when generating forms, scaffolds, or custom state fields. See [Forms and FieldSpec](forms.md).

## When to use what

| Approach | Good for |
|:---|:---|
| Manual dicts in handlers | Tiny examples, one-off shapes |
| **ReflexDjangoModelSerializer** | Custom handlers, partial fields, joins |
| **ModelState** | Standard CRUD lists and forms |

## Import

```python
from reflex_django.serializers import ReflexDjangoModelSerializer
```

Also exported from the package root: `from reflex_django import ReflexDjangoModelSerializer`.

**Next:** [Model state](model-state.md)
