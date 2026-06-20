# Bridge

Bridge runs Django middleware on each Reflex event and attaches the request and logged-in user to your state class.

## Default

With `profile: "integrated"`, bridge is on with `mode: "full"`. Your handlers get `self.request` for authorization and a reactive user snapshot for UI.

## Use AppState

Subclass `AppState`, not plain `rx.State`, when you need Django context:

```python
from reflex_django.states import AppState

class TodoState(AppState):
    @rx.event
    async def on_load(self):
        if self.request.user.is_authenticated:
            ...
```

**Authorize with `self.request.user`.** Reactive vars like `self.is_authenticated` and `self.username` are UI snapshots. They can lag behind the session. See [Auth](../advanced/auth.md).

## Bridge modes

| Mode | Use when |
|:---|:---|
| `full` | Auth, CSRF, or custom middleware (default) |
| `smart` | Lighter pass. Plain `rx.State` skips middleware. |
| `none` | No Django context on events |

```python
ReflexDjangoPlugin(config={
    "settings_module": "config.settings",
    "bridge": {"mode": "smart"},
})
```

Per-class override for hot UI-only state:

```python
class FilterState(rx.State):
    _rx_bridge = "none"
```

## Streaming middleware

Add `AsyncStreamingMiddleware` last in `MIDDLEWARE` for streaming from Django HTTP views.

For bridge helpers (`current_user`, session mirrors, and more), see [Bridge utilities](../advanced/bridge-utilities.md).

You finished the core integration path. Build something next:

- [Tutorial](quickstart.md) — todo app walkthrough
- [Pages and state](../advanced/pages-and-state.md)
- [Auth](../advanced/auth.md)

**Next:** [Tutorial](quickstart.md) or [Advanced](../advanced/index.md)
