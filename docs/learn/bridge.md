# Bridge

Bridge runs Django request/session/auth logic around Reflex events and attaches the synthetic Django request to the handler state when bridge is enabled and the resolved tier is `full` or `auth_only`. Use it when an event handler needs `self.request`, `self.request.user`, sessions, messages, locale, CSRF, or middleware redirects.

Think of bridge as the event-context layer. [Embed](embed.md) handles Django HTTP in the backend process, [Mount](mount.md) handles URL ownership, and [Proxy](proxy.md) handles local dev traffic. Bridge handles what happens after the browser sends a Reflex event.

See [Profiles](profiles.md) for preset defaults. Bridge is on in `integrated` and `split_dev`, off in `reflex_only`.

## Use `AppState`

Subclass `AppState`, not plain `rx.State`, when handlers need Django context:

```python
from reflex_django.states import AppState


class TodoState(AppState):
    @rx.event
    async def on_load(self):
        if self.request.user.is_authenticated:
            ...
```

Authorize with `self.request.user`. Reactive vars like `self.is_authenticated` and `self.username` are UI snapshots and can lag behind the session. See [Auth](../advanced/auth.md).

Use plain `rx.State` for UI-only state that does not need Django. In `smart` mode, plain `rx.State` can skip Django request binding for faster hot-path events.

## Options reference

Allowed keys in the `bridge` block:

| Option | Type | Default by profile | Purpose |
|:---|:---|:---|:---|
| `bridge.enabled` | `bool` | `True` in `integrated` and `split_dev`; `False` in `reflex_only` | Enable Django request context for eligible Reflex events |
| `bridge.mode` | `str` | `full` | Global mode: `full`, `smart`, or `none` |
| `bridge.run_middleware_chain` | `bool` | `True` | Run Django middleware on synthetic event requests |
| `bridge.resolver` | `str` | unset | Dotted path to `(handler_state_cls, event) -> tier` callable |

When the `bridge` block is omitted, settings fallbacks apply: `RX_EVENT_BRIDGE_MODE`, `RX_RUN_MIDDLEWARE_CHAIN`, `RX_EVENT_BRIDGE_RESOLVER`. Plugin values are synced onto Django settings at bootstrap.

Invalid `bridge.mode` values raise a configuration error at startup.

## Examples

**Full mode (safest default):**

```python
ReflexDjangoPlugin(config={
    "settings_module": "config.settings",
    "bridge": {"mode": "full"},
})
```

**Smart mode for mixed UI-only and Django-aware state:**

```python
--8<-- "snippets/pillar_bridge_smart.py"
```

**Custom resolver:**

```python
ReflexDjangoPlugin(config={
    "settings_module": "config.settings",
    "bridge": {
        "mode": "smart",
        "resolver": "shop.bridge.resolve_bridge_tier",
    },
})
```

```python
# shop/bridge.py
def resolve_bridge_tier(handler_state_cls, event):
    if handler_state_cls.__name__.endswith("FilterState"):
        return "none"
    return "full"
```

**Disable middleware chain (advanced):**

```python
ReflexDjangoPlugin(config={
    "settings_module": "config.settings",
    "bridge": {
        "enabled": True,
        "run_middleware_chain": False,
    },
})
```

**Per-class override for hot UI-only state:**

```python
class FilterState(rx.State):
    _rx_bridge = "none"
```

`rx_bridge = "none"` is also accepted. Per-class overrides beat global mode; upload events still require at least `auth_only`.

## Bridge tiers

Every event resolves to one tier:

| Tier | What runs | Use |
|:---|:---|:---|
| `full` | Full Django middleware chain except configured skips | Default, safest for auth/CSRF/custom middleware |
| `auth_only` | `RX_AUTH_ONLY_MIDDLEWARE` (session + auth by default) | Uploads or events that only need user/session |
| `none` | No Django request binding | Hot UI-only state |

When bridge is disabled or an event resolves to `none`, `self.request` and `current_request()` are not available for that event.

## Modes

| Mode | Resolution |
|:---|:---|
| `full` | All events use `full` |
| `none` | All events use `none`, except uploads are raised to `auth_only` |
| `smart` | Django-aware state uses `full`; plain `rx.State` uses `none`; uploads are at least `auth_only` |

Django-aware state means `AppState`, `DjangoUserState`, `ModelState`, `DjangoAuthState`, or any state class that mixes in `AuthBridgeMixin` (including built-in auth page handlers such as `submit_login_form`).

Choose `full` first when correctness matters. Choose `smart` when you have UI-only state classes that do not need Django.

## Middleware and request binding

With `run_middleware_chain=True`, the bridge builds a synthetic Django request and runs Django middleware for bridge-bound events. Middleware can short-circuit with a redirect; reflex-django converts 3xx responses into `rx.redirect(...)` when `RX_AUTO_REDIRECT_FROM_MIDDLEWARE=True`.

The bridge binds request/response objects to the handler state branch. Inside bridge-bound handlers you can use `self.request`, `self.user`, `self.session`, `self.messages`, `self.csrf_token`, `current_request()`, and `current_user()`.

Do not authorize from UI snapshot vars alone. Use the live Django user or auth decorators.

## Tuning and debugging

Bridge tuning settings (`RX_EVENT_CACHE`, `RX_EVENT_CACHE_FAST_AUTH`, `RX_AUTH_ONLY_MIDDLEWARE`, `RX_DEVTOOLS`, and others) are documented in [Config reference](../advanced/config.md).

Enable [Devtools](../advanced/devtools.md) to inspect resolved tier, handler timing, and query count. For helper APIs, see [Bridge utilities](../advanced/bridge-utilities.md).

Add `AsyncStreamingMiddleware` last in `MIDDLEWARE` for streaming from Django HTTP views. It is skipped on synthetic Reflex event requests.

## Use and avoid

Use bridge when handlers need Django auth, sessions, permissions, messages, language, CSRF, or middleware behavior.

Avoid bridge for purely local UI state. Use `bridge.mode = "smart"` or `_rx_bridge = "none"` on those classes.

**Next:** [Tutorial](quickstart.md) or [Advanced](../advanced/index.md)
