# Bridge

Bridge runs Django request/session/auth logic around Reflex events and attaches the synthetic Django request to the handler state when bridge is enabled and the resolved tier is `full` or `auth_only`. Use it when an event handler needs `self.request`, `self.request.user`, sessions, messages, locale, CSRF, or middleware redirects.

Think of bridge as the event-context layer. [Embed](embed.md) handles Django HTTP in the backend process, [Mount](mount.md) handles URL ownership, and [Proxy](proxy.md) handles local dev traffic. Bridge handles what happens after the browser sends a Reflex event.

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

## Options

| Option | Default from profile | Purpose |
|:---|:---|:---|
| `bridge.enabled` | `True` in `integrated` and `split_dev`, `False` in `reflex_only` | Enable Django request context for eligible Reflex events |
| `bridge.mode` | `full` | Global mode: `full`, `smart`, or `none` |
| `bridge.run_middleware_chain` | `True` | Run Django middleware on synthetic event requests |
| `bridge.resolver` | unset | Dotted callable or callable that returns the tier for each event |

Example:

```python
ReflexDjangoPlugin(config={
    "settings_module": "config.settings",
    "bridge": {
        "enabled": True,
        "mode": "smart",
        "run_middleware_chain": True,
        "resolver": "shop.bridge.resolve_bridge_tier",
    },
})
```

Plugin bridge options are applied during bootstrap and update the corresponding Django settings.

## Bridge tiers

Every event resolves to one tier:

| Tier | What runs | Use |
|:---|:---|:---|
| `full` | Full Django middleware chain except configured skips | Default, safest for auth/CSRF/custom middleware |
| `auth_only` | `RX_AUTH_ONLY_MIDDLEWARE` (session + auth by default) | Uploads or events that only need user/session |
| `none` | No Django request binding | Hot UI-only state |

`full` preserves Django-like behavior. Middleware can short-circuit with a redirect; by default reflex-django converts 3xx responses into `rx.redirect(...)`.

When bridge is disabled (`bridge.enabled: false`) or an event resolves to `none`, `self.request` and `current_request()` are not available for that event.

## Modes

Set a global bridge mode in plugin config:

```python
ReflexDjangoPlugin(config={
    "settings_module": "config.settings",
    "bridge": {"mode": "smart"},
})
```

| Mode | Resolution |
|:---|:---|
| `full` | All events use `full` |
| `none` | All events use `none`, except uploads are raised to `auth_only` |
| `smart` | Django-aware state uses `full`; plain `rx.State` uses `none`; uploads are at least `auth_only` |

Django-aware state means `AppState`, `DjangoUserState`, or `ModelState`.

Choose `full` first when correctness matters. Choose `smart` when you have UI-only state classes that do not need Django. Choose `none` only when Reflex events should not use Django request context by default.

## Per-class override

For hot UI-only state:

```python
class FilterState(rx.State):
    _rx_bridge = "none"
```

`rx_bridge = "none"` is also accepted. Per-class overrides beat the global mode, but upload events are still raised to at least `auth_only`.

Use overrides for state classes that are called frequently and do not need Django, such as local filters, expanded rows, modal state, theme toggles, or client-side UI controls.

## Custom resolver

For advanced routing, set `bridge.resolver` in plugin config or `RX_EVENT_BRIDGE_RESOLVER` in Django settings. The callable receives `(handler_state_cls, event)` and returns `"full"`, `"auth_only"`, or `"none"`.

```python
def resolve_bridge_tier(handler_state_cls, event):
    if handler_state_cls.__name__.endswith("FilterState"):
        return "none"
    return "full"
```

Resolver result has highest precedence, followed by class override, then global mode. Upload events keep the same safety floor and cannot go below `auth_only`.

Use a resolver when class-level rules are not enough, for example when one state has both security-sensitive handlers and hot UI-only handlers.

## Middleware behavior

With `run_middleware_chain=True`, the bridge builds a synthetic Django request and runs Django middleware for bridge-bound events. This makes session/auth middleware, locale middleware, message middleware, and custom middleware behave more like they do for Django views.

Configured skips are still respected. CSRF and streaming middleware are skipped for synthetic event requests by default. Middleware can return redirects; reflex-django converts 3xx responses into `rx.redirect(...)` when `RX_AUTO_REDIRECT_FROM_MIDDLEWARE=True`.

## Event cache fast auth

`RX_EVENT_CACHE` stores short-lived event context. With `RX_EVENT_CACHE_FAST_AUTH=True`, `auth_only` events can reuse cached user/session information inside `RX_EVENT_CACHE_TTL` and skip session/auth middleware. This trades lower per-event overhead for a small staleness window; logout invalidates the event cache.

## Request binding

The bridge binds request/response objects to the handler state branch instead of the entire state tree. This keeps unrelated substates lighter while preserving `self.request`, `current_request()`, and `current_user()` for the handler path.

Inside bridge-bound `AppState` handlers you can use:

| API | Purpose |
|:---|:---|
| `self.request` | Synthetic Django request for the event |
| `self.request.user` / `self.user` | Live Django user |
| `self.session` | Django session |
| `self.messages` | Mirrored Django messages |
| `self.csrf_token` | Mirrored CSRF token |
| `current_request()` / `current_user()` | Context helpers outside direct state access |

Do not authorize from UI snapshot vars alone. Use the live Django user or auth decorators.

## Related settings

| Setting | Purpose |
|:---|:---|
| `RX_EVENT_BRIDGE_MODE` | Settings-level global bridge mode |
| `RX_RUN_MIDDLEWARE_CHAIN` | Run Django middleware on event requests |
| `RX_AUTH_ONLY_MIDDLEWARE` | Middleware subset for the `auth_only` tier |
| `RX_EVENT_MIDDLEWARE_SKIP` | Middleware skipped on synthetic event requests |
| `RX_EVENT_BRIDGE_RESOLVER` | Dotted custom resolver |
| `RX_EVENT_RESOLVE_URL` | Populate `request.resolver_match` |
| `RX_EVENT_POST_FROM_PAYLOAD` | Copy event kwargs into synthetic `request.POST` |
| `RX_AUTO_REDIRECT_FROM_MIDDLEWARE` | Convert middleware redirects into Reflex redirects |
| `RX_EVENT_CACHE` / `RX_EVENT_CACHE_TTL` | Cache event context |
| `RX_EVENT_CACHE_FAST_AUTH` | Reuse cached auth for `auth_only` within TTL |
| `RX_EVENT_METRICS` / `RX_EVENT_METRICS_LOGGER` | Log bridge timing |
| `RX_BRIDGE_DEBUG` | Log swallowed bridge hot-path exceptions |
| `RX_DEVTOOLS` | Enable local event/query/state inspection |

## Debugging

Enable [Devtools](../advanced/devtools.md) to see the resolved tier, handler, timing, query count, and bound user:

```python
RX_DEVTOOLS = True
```

For bridge helpers (`current_user`, session mirrors, request lifecycle helpers, and cache invalidation), see [Bridge utilities](../advanced/bridge-utilities.md).

## Streaming middleware

Add `AsyncStreamingMiddleware` last in `MIDDLEWARE` for streaming from Django HTTP views. It is skipped on synthetic Reflex event requests.

## Use and avoid

Use bridge when handlers need Django auth, sessions, permissions, messages, language, CSRF, or middleware behavior.

Avoid bridge for state that is purely local UI state. Use `bridge.mode = "smart"` or `_rx_bridge = "none"` on those classes so they do not pay Django middleware overhead.

You finished the core integration path. Build something next:

- [Tutorial](quickstart.md)
- [Pages and state](../advanced/pages-and-state.md)
- [Auth](../advanced/auth.md)

**Next:** [Tutorial](quickstart.md) or [Advanced](../advanced/index.md)
