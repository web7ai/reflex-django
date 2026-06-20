# Live updates

`LiveListMixin` keeps a `ModelState` list var in sync with Django model changes from other requests or browser tabs. It listens to Django `post_save` and `post_delete` signals, broadcasts a small change event inside the process, and reuses the same incremental list patch helpers as local CRUD mutations.

## Basic usage

```python
from reflex_django.live import LiveListMixin
from reflex_django.states import ModelState


class ProductState(LiveListMixin, ModelState):
    model = Product
    fields = ["name", "price", "active"]
    incremental_updates = True
```

Start the background subscription from page load:

```python
app.add_page(
    products_page,
    route="/products",
    on_load=[ProductState.load, ProductState.live_subscribe],
)
```

`live_subscribe` registers model signals if needed, subscribes to the model's change stream, and patches the current list as changes arrive.

## Patch behavior

| Change | Behavior |
|:---|:---|
| Create | Inserts the serialized row when pagination is disabled |
| Update | Replaces the row if it is on the current page |
| Delete | Removes the row from the current list |
| Out of scope | Removes the row if the scoped queryset no longer returns it |

If pagination makes a correct insert ambiguous, use `refresh_list` or reload after a create.

## Scope and permissions

Live updates call `get_scoped_queryset()` before serializing changed rows. User-scoped states only show rows the current state is allowed to see.

If your queryset requires a fully bound request object, prefer a periodic refresh or an explicit event handler. Background live subscriptions run for the connection lifetime and may not have the same request context assumptions as a foreground event.

## Public API

```python
from reflex_django.live import (
    ACTION_CREATED,
    ACTION_DELETED,
    ACTION_UPDATED,
    LiveBroadcaster,
    LiveListMixin,
    ModelChange,
    is_live_model,
    live_broadcaster,
    model_label,
    register_live_model,
    unregister_live_model,
)
```

| API | Purpose |
|:---|:---|
| `register_live_model(Model)` | Connect `post_save` / `post_delete` signals |
| `unregister_live_model(Model)` | Disconnect signals, mainly tests/teardown |
| `is_live_model(Model)` | Check registration |
| `model_label(Model)` | Return `app_label.model_name` |
| `ModelChange` | Broadcast payload: `model_label`, `action`, `pk` |
| `live_broadcaster()` | Process-wide broadcaster singleton |

## Customizing changes

Override `apply_live_change` when a state needs custom serialization, denormalized rows, or a different refresh strategy:

```python
class ProductState(LiveListMixin, ModelState):
    model = Product
    fields = ["name", "price"]

    async def apply_live_change(self, change):
        if change.is_delete:
            self.remove_list_row(self.get_options(), change.pk)
            return
        await self.refresh()
```

## Broadcaster extension

The built-in `LiveBroadcaster` is process-local. It is useful for single-worker apps, development, and tests. Multi-process deployments need a shared fan-out layer.

A Redis or Postgres listener can translate shared events into local publishes:

```python
from reflex_django.live import ModelChange, live_broadcaster

live_broadcaster().publish(
    ModelChange(model_label="shop.product", action="updated", pk=42)
)
```

`subscribe(model_label)` returns an `asyncio.Queue`; `publish(change)` delivers to matching subscribers on their event loops; `unsubscribe(model_label, queue)` cleans up. `live_subscribe` unsubscribes when Reflex cancels the background task on disconnect.

## Deployment note

For multiple workers, add Redis pub/sub, Postgres `LISTEN/NOTIFY`, or another shared transport. Each worker should receive the shared change and call `live_broadcaster().publish(...)` locally.

**Next:** [Model state](model-state.md), [Scaling](scaling.md), and [Security](security.md).
