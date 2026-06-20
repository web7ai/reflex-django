# Database

Three ways to load and save Django data in Reflex handlers. Pick by how much boilerplate you want.

## 1. Manual async ORM

Full control. Build dicts yourself. Good for learning and one-off logic.

| Avoid | Use |
|:---|:---|
| `Model.objects.get(...)` | `await Model.objects.aget(...)` |
| `Model.objects.create(...)` | `await Model.objects.acreate(...)` |
| `instance.save()` | `await instance.asave()` |
| `list(qs)` | `[row async for row in qs[:50]]` |

```python
class CatalogState(AppState):
    products: list[dict] = []

    @rx.event
    async def load(self):
        from shop.models import Product
        self.products = [
            {"id": p.id, "name": p.name}
            async for p in Product.objects.all()[:50]
        ]
```

See the [Tutorial](../learn/quickstart.md) for a full CRUD example.

## 2. Serializers

Same handlers, less field plumbing. Declarative `Meta.fields` and `.adata()` / `.alist()`.

→ [Serializers](serializers.md)

## 3. Model state

Declarative CRUD: declare `model` and `fields`, get list/search/pagination/save/create/delete handlers.

→ [Model state](model-state.md)

## Rules for all approaches

- Store **dicts** in state, not model instances.
- Filter by owner in handlers: `await Todo.objects.aget(pk=id, owner=self.request.user)`.
- Wrap blocking libraries in `sync_to_async` when no async API exists.

## Comparison

| | Manual ORM | Serializers | ModelState |
|:---|:---|:---|:---|
| Boilerplate | Most | Medium | Least |
| Custom logic | Easiest | Easy | Override handlers |
| List + forms | You build it | You build UI | Built-in vars |
