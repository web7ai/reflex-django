# Database integration

Django **ORM**, **migrations**, and the **`DjangoORMBackend`** used by model state.

---

## Prerequisites

- [Configuration](configuration.md)  
- [CLI](cli.md)

---

## `configure_django()`

Called by the plugin and CLI. Idempotent; honors `DJANGO_SETTINGS_MODULE` env first.

Database config:

- Your `settings.DATABASES`, or  
- Bundled defaults from `REFLEX_DJANGO_DATABASE_URL` / Reflex `db_url` / SQLite file.

---

## Migrations

```bash
uv run reflex django makemigrations myapp
uv run reflex django migrate
```

Uses the same settings as `reflex run` when `rxconfig` loads.

---

## Abstract `Model` base

```python
from reflex_django.model import Model

class Tag(Model):
    name = models.CharField(max_length=64)
```

Abstract base with default `BigAutoField` PK—**no** automatic `created_at`; add fields explicitly.

Importing `reflex_django.model` triggers `configure_django()`.

Reflex wire serializer: `serialize_django_model` registered on Django model instances.

---

## `DjangoORMBackend`

`ModelCRUDView` uses `DjangoORMBackend` (`state/backends/django.py`):

- `create` → `perform_create` → `model.objects.acreate`  
- Update/delete via async ORM in mixins  

Override with `Meta.backend_class` for custom persistence (advanced).

---

## Queryset optimization

On `ModelCRUDView.Meta`:

```python
queryset_select_related = ("author",)
queryset_prefetch = ("tags",)
```

Hooks: `get_queryset`, `filter_queryset`, `get_ordering`.

---

## Django Admin

```python
from reflex_django import register_admin
from catalog.models import Product

register_admin(Product)
```

Admin HTTP UI is served at `admin_prefix` (default `/admin`) via the dispatcher—not Reflex pages.

Also: `from reflex_django.admin import site`.

---

## Transactions

Wrap multi-step writes in `async with sync_to_async(transaction.atomic)()` or Django 6+ async atomic APIs when needed—application responsibility.

---

## Advanced usage

- Multi-database: standard Django routers; test carefully with async querysets.  
- Raw SQL: avoid in Reflex state unless serialized to JSON-safe values.

---

## Common mistakes

- Running `manage.py` with different `DJANGO_SETTINGS_MODULE` than Reflex.  
- Default mixin `ordering = ("-created_at",)` on models without `created_at`.

---

## See also

- [Serializers](serializers.md)  
- [CLI](cli.md)

---

**Navigation:** [← Serializers](serializers.md) | [Next: CRUD without mixins →](crud_without_mixins.md)
