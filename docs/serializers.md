# Serializers

**`ReflexDjangoModelSerializer`** turns Django model instances and querysets into **JSON-friendly dicts** for Reflex state—DRF-style declarations without `djangorestframework`.

---

## Prerequisites

- [Database integration](database_integration.md)

---

## Basic usage

*Example application code.*

```python
from django.db import models
from reflex_django.serializers import ReflexDjangoModelSerializer

class Note(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField(blank=True)

class NoteSerializer(ReflexDjangoModelSerializer):
    class Meta:
        model = Note
        fields = ("id", "title", "content")
```

In an async event handler:

```python
from django.db.models import QuerySet

rows = await NoteSerializer(Note.objects.all(), many=True).adata()
# rows: list[dict]
```

Single instance:

```python
row = NoteSerializer(note).data  # sync property
```

---

## `Meta` options

| Option | Role |
|--------|------|
| `model` | Django model class |
| `fields` | Tuple/list of field names (`id` always included when using `fields`) |
| `exclude` | Fields to omit |
| `read_only_fields` | Excluded from writable field lists used by `ModelCRUDView` |
| `datetime_format` / `date_format` | String formats for date/time columns |

Methods on the class:

- `get_read_only_field_names()`  
- `writable_field_names(read_only_fields=...)`

---

## `.data` vs `.adata()`

| API | Use when |
|-----|----------|
| `.data` | Sync access; single instance or iterable already evaluated |
| `.adata()` | **Preferred in async handlers**; supports async querysets |

For querysets, prefer one assignment:

```python
self.notes = await NoteSerializer(qs, many=True).adata()
```

The serializer iterates the queryset internally.

---

## Low-level helper

`serialize_model_row()` in `reflex_django.serialization` (also re-exported from `reflex_django.mixins`) for single-row dicts without a serializer class.

`reflex_django.model.Model` registers a Reflex serializer hook via `@serializer(to=dict)` for wire format.

---

## With `ModelCRUDView`

Declare `serializer_class = NoteSerializer` on your state class. Assembly generates flat vars from **writable** serializer fields. See [CRUD with mixins](crud_with_mixins_and_states.md).

---

## Advanced usage

- Runtime `exclude_fields` on serializer `__init__` for dynamic column sets.
- Combine with `Meta.read_only_fields` on state for owner fields (`user`) not editable in the form.

---

## Performance tips

- Limit `Meta.fields` to what the UI displays.  
- Use queryset `.only()` / `.defer()` before passing to `.adata()` when lists are large.

---

## Common mistakes

- Putting non-JSON values in serialized dicts (Reflex state must be JSON-serializable).  
- Using `.data` on a large queryset in an async handler—use `.adata()`.

---

## Developer notes

- Implementation: `src/reflex_django/serializers.py`, `src/reflex_django/serialization.py`.

---

## See also

- [CRUD without mixins](crud_without_mixins.md)  
- [CRUD with mixins](crud_with_mixins_and_states.md)

---

**Navigation:** [← State management](state_management.md) | [Next: Database integration →](database_integration.md)
