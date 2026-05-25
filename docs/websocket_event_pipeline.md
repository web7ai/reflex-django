# How `/_event` and WebSockets work

Every interactive UI update in a `reflex-django` app — every `@rx.event` call, every reactive var change, every redirect — travels over a single persistent WebSocket connection mounted at **`/_event`**. This document explains, end to end:

- where `/_event` is mounted in the ASGI stack,
- how a browser establishes that connection on port `8000`,
- how Django decides not to touch it,
- how Reflex's inner Socket.IO server speaks to the browser,
- how the synthetic Django request is built from each event,
- how `settings.MIDDLEWARE` runs on every event,
- and how non-`/_event` WebSocket scopes (Vite HMR, stray connections) are handled.

Everything below describes the current implementation; no Django Channels, no second port, no proxy server.

---

## 1. The big picture

```mermaid
sequenceDiagram
    autonumber
    participant Browser
    participant Uvicorn as ASGI server (uvicorn / granian / hypercorn)
    participant Dispatcher as DjangoOuterDispatcher
    participant Django as Django ASGI handler
    participant ReflexAPI as Reflex inner _api<br/>(Starlette + Socket.IO)
    participant Bridge as DjangoEventBridge
    participant Handler as EventMiddlewareHandler
    participant State as @rx.event handler

    Browser->>Uvicorn: HTTP GET /_event/?EIO=4&transport=websocket<br/>Upgrade: websocket
    Uvicorn->>Dispatcher: scope (type=websocket, path=/_event)
    Dispatcher->>Dispatcher: path starts with /_event → reserved
    Dispatcher->>ReflexAPI: scope, receive, send
    ReflexAPI-->>Browser: 101 Switching Protocols<br/>WebSocket open
    Note over Browser,ReflexAPI: Socket.IO handshake completes;<br/>connection stays open

    Browser->>ReflexAPI: socket event (token, state, payload, router_data)
    ReflexAPI->>Bridge: preprocess(app, state, event)
    Bridge->>Bridge: build synthetic HttpRequest from router_data<br/>(cookies, headers, IP, method, scheme)
    Bridge->>Handler: dispatch through settings.MIDDLEWARE
    Handler-->>Bridge: HttpResponse (200 terminal,<br/>or 3xx/4xx/5xx from middleware)
    Bridge->>Bridge: bind request/response/user/session<br/>to AppState + ContextVars
    alt response is 3xx
        Bridge-->>ReflexAPI: rx.redirect(Location) (handler skipped)
    else proceed
        ReflexAPI->>State: invoke @rx.event handler
        State-->>ReflexAPI: state mutations
    end
    ReflexAPI-->>Browser: reactive UI patches
```

The key observation: **Django never sees a WebSocket scope on `/_event`**. The outer dispatcher routes it to Reflex before Django's ASGI handler can complain. Django *does* run on every event — but as a synthetic `HttpRequest` walked through its middleware chain, not via the WebSocket itself.

---

## 2. Where `/_event` is mounted

`/_event` is a reserved prefix in the outer dispatcher:

```40:48:src/reflex_django/django_outer_dispatcher.py
DEFAULT_RESERVED_REFLEX_PREFIXES: tuple[str, ...] = (
    "/_event",
    "/_upload",
    "/_health",
    "/_all_routes",
    "/ping",
    "/auth-codespace",
)
```

When the ASGI server hands a scope to the dispatcher, the dispatcher checks the scope type and path prefix:

```97:127:src/reflex_django/django_outer_dispatcher.py
    async def __call__(
        self,
        scope: ASGIScope,
        receive: ASGIReceive,
        send: ASGISend,
    ) -> None:
        scope_type = scope.get("type")
        if scope_type == "lifespan":
            await self._handle_lifespan(scope, receive, send)
            return

        if scope_type not in ("http", "websocket"):
            return

        path = scope.get("path", "") or "/"
        if self._is_reserved(path):
            await self.reflex(scope, receive, send)
            return

        if scope_type == "websocket":
            await self._handle_websocket(scope, receive, send)
            return

        await self.django(scope, receive, send)
```

For a request to `/_event/`, the dispatcher:

1. Reads `scope["type"]` — `"websocket"` for the Socket.IO upgrade, `"http"` for the initial polling/handshake fallback.
2. Checks the path against `DEFAULT_RESERVED_REFLEX_PREFIXES`. `/_event/` matches `/_event`.
3. Calls `self.reflex(scope, receive, send)` — Reflex's inner ASGI (`rx_app._api`, wrapped in `rx_app._context_middleware`).

Django is not invoked. Django's `urls.py` is not consulted. Django middleware does not run on the WebSocket scope itself.

---

## 3. What `self.reflex` actually is

`self.reflex` is **Reflex's inner Starlette app** (`rx_app._api`), wrapped in `rx_app._context_middleware` so per-request Reflex contexts are bound:

```47:78:src/reflex_django/asgi_entry.py
def _unwrap_reflex_inner_asgi(rx_app: App) -> ASGIApp:
    """Return Reflex's inner ASGI app (Starlette with Socket.IO etc.) for mounting.

    Reflex normally wraps ``app._api`` in :meth:`reflex.app.App._context_middleware`
    and a top-level Starlette that owns lifespan. In ``DJANGO_OUTER`` mode we
    own lifespan ourselves (see
    :class:`~reflex_django.django_outer_dispatcher.DjangoOuterDispatcher`), so
    we only need the inner Starlette wrapped in the context middleware.
    """
    inner = getattr(rx_app, "_api", None)
    ...
    context_middleware = getattr(rx_app, "_context_middleware", None)
    if not callable(context_middleware):
        return inner
    return context_middleware(inner)
```

`rx_app._api` is a Starlette application that Reflex assembles at startup. It mounts:

| Path | Inside Reflex's `_api` |
|:---|:---|
| `/_event` (HTTP + WebSocket) | Socket.IO ASGI app (the event channel) |
| `/_upload` | Starlette route that accepts file uploads |
| `/_health`, `/ping` | JSON health probes |
| `/_all_routes` | Internal Reflex route enumeration |

The Socket.IO server inside `_api` runs the standard `python-socketio` ASGI handshake on `/_event/`. It speaks Engine.IO over WebSocket (with HTTP long-poll fallback). When the browser upgrades, the ASGI server (uvicorn) keeps the underlying TCP socket open and pipes WebSocket frames between the browser and the Socket.IO server forever — until the user navigates away or the tab closes.

The outer dispatcher does not unwrap, decode, or modify any WebSocket frame. It just delivers `(scope, receive, send)` to `self.reflex` and lets Reflex own the channel.

---

## 4. The browser side

When the Reflex SPA bundle boots in the browser it immediately opens a Socket.IO connection back to the same origin:

```text
GET /_event/?EIO=4&transport=websocket    HTTP/1.1
Host: localhost:8000
Upgrade: websocket
Connection: Upgrade
Cookie: sessionid=abc123; csrftoken=xyz789
```

Because the SPA was served from `http://localhost:8000/`, the WebSocket upgrade targets the **same origin and the same port**. No cross-origin handshake. No separate frontend dev server. Same-site cookies — including Django's `sessionid` and `csrftoken` — ride along on the upgrade request, and Socket.IO holds the cookies for the lifetime of the connection.

When the user fires an event (clicks a button, types in an input bound to a state var, navigates the SPA router), the browser serializes an `Event` to JSON and pushes it through the open socket. The server receives it inside Reflex's Socket.IO handler.

---

## 5. The event payload and `router_data`

Each event Reflex receives on `/_event` carries:

- `name` — the fully-qualified event handler name (e.g. `"shop.HomeState.on_click"`).
- `token` — the client's session token (Reflex's own state ID, not Django's session ID).
- `payload` — the event kwargs (button arguments, form values, etc.).
- `router_data` — a dict describing the originating "request": cookies, headers, client IP, current URL path, query string.

`router_data` is the bridge between the persistent WebSocket and Django's request-shaped world. It contains everything needed to reconstruct an `HttpRequest` for the event:

```python
router_data = {
    "headers": {
        "cookie": "sessionid=abc123; csrftoken=xyz789; ...",
        "host": "localhost:8000",
        "user-agent": "...",
        "accept-language": "en-US,en;q=0.9",
    },
    "ip": "127.0.0.1",
    "pathname": "/checkout",
    "query": {"step": "2"},
    "method": "POST",          # optional override; defaults to POST
}
```

---

## 6. `DjangoEventBridge.preprocess` — the heart of the bridge

`DjangoEventBridge` is a Reflex middleware. Its `preprocess` runs **before every event handler**, with `app`, `state`, and `event` in hand:

```542:625:src/reflex_django/middleware.py
class DjangoEventBridge(Middleware):
    """Reflex event middleware that binds a Django request to each event."""

    ...

    async def preprocess(
        self,
        app: App,
        state: BaseState,
        event: Event,
    ) -> StateUpdate | None:
        end_event_request()
        end_event_response()
        bridged = await bridge_request_for_state(state, event)
        if bridged is None:
            ...
            return None
        request, response = bridged

        begin_event_request(request)
        begin_event_response(response)
        ...
        if isinstance(state, _BaseState):
            bind_request_on_state_tree(state, request)
            bind_response_on_state_tree(state, response)
            try:
                handler_state = await state.get_state(event.state_cls)
                bind_request_on_state(handler_state, request)
            except Exception:
                pass
            user = getattr(request, "user", None)
```

Three things happen, in this order:

1. **Clear last event's context.** ContextVars from a previous handler are dropped.
2. **Bridge the event.** `bridge_request_for_state` builds a synthetic Django request from `event.router_data`, walks the middleware chain, and produces both an `HttpRequest` and an `HttpResponse`.
3. **Bind to the state tree.** `request`, `response`, `user`, `session`, `messages`, `csrf_token` are attached to the relevant `AppState` instances and to per-task `ContextVar`s so the handler can read `self.request`, `self.user`, etc.

---

## 7. Building the synthetic `HttpRequest`

`_build_request_from_router_data` constructs a request that looks exactly like one Django would build for a real HTTP hit:

```268:353:src/reflex_django/middleware.py
def _build_request_from_router_data(router_data: dict[str, Any]) -> HttpRequest:
    ...
    request = HttpRequest()
    request.method = method        # default POST, overridable
    request.path = path
    request.path_info = path
    request.GET = get              # parsed from pathname + router_data["query"]
    ...
    cookie_jar.load(cookie_header)
    request.COOKIES = {key: morsel.value for key, morsel in cookie_jar.items()}

    host_header = headers.get("host", "") or headers.get("Host", "")
    server_name, server_port = _split_host_port(host_header)
    scheme = _scheme_from_headers(headers)

    request.META = {
        "REMOTE_ADDR": client_ip or "127.0.0.1",
        "PATH_INFO": path,
        "QUERY_STRING": get.urlencode(),
        "REQUEST_METHOD": method,
        "HTTP_COOKIE": cookie_header,
        "SERVER_NAME": server_name,
        "SERVER_PORT": server_port,
        "wsgi.url_scheme": scheme,
        "HTTP_X_FORWARDED_PROTO": scheme,
    }
    for name, value in headers.items():
        meta_key = "HTTP_" + name.upper().replace("-", "_")
        request.META.setdefault(meta_key, value)
    ...
    _populate_post_from_payload(request, router_data)

    match = _resolve_url_match(path)
    if match is not None:
        request.resolver_match = match
    return request
```

After this function returns, the request has:

| Attribute | Source |
|:---|:---|
| `request.method` | `router_data["method"]` (default `POST`) |
| `request.path` / `request.path_info` | `router_data["pathname"]` |
| `request.GET` | `router_data["pathname"]` query string + `router_data["query"]` |
| `request.POST` | `router_data["payload"]` (only if `REFLEX_DJANGO_EVENT_POST_FROM_PAYLOAD = True`) |
| `request.COOKIES` | Parsed from the `cookie` header |
| `request.headers` | Proxied over `_reflex_django_headers` |
| `request.META` | `REMOTE_ADDR`, `SERVER_NAME`, `SERVER_PORT`, `wsgi.url_scheme`, every `HTTP_*` header |
| `request.scheme` / `request.is_secure()` | Derived from `X-Forwarded-Proto` or `HTTP_HOST` |
| `request.resolver_match` | Best-effort `urls.py` resolution for the SPA path |

Note: this request is **synthetic**. It is never delivered to a Django view. It exists solely to feed the middleware chain so middleware can populate `request.user`, `request.session`, etc.

---

## 8. Running `settings.MIDDLEWARE` on the event

The bridge then pipes the synthetic request through Django's **own** middleware loader, via a custom `BaseHandler` subclass:

```87:134:src/reflex_django/event_handler.py
    class EventMiddlewareHandler(BaseHandler):
        """A :class:`BaseHandler` that exposes the middleware chain for Socket.IO events.

        Behaves like Django's ASGI handler for middleware loading purposes —
        ``load_middleware(is_async=True)`` builds ``_middleware_chain`` from
        ``settings.MIDDLEWARE`` filtered by
        :func:`~reflex_django.event_handler._settings_skip_list`. The terminal
        "view" (``_get_response_async``) returns an empty 200 ``HttpResponse``
        so the chain has a definite endpoint; if any middleware short-circuits
        before reaching the terminal, that response is returned to the
        bridge and translated into a Reflex action.
        """
        ...
        def load_middleware(self, is_async: bool = False) -> None:
            ...
            skip_set = set(self.skip)
            original = list(getattr(settings, "MIDDLEWARE", ()))
            filtered = [m for m in original if m not in skip_set]
            try:
                settings.MIDDLEWARE = filtered
                super().load_middleware(is_async=is_async)
            finally:
                settings.MIDDLEWARE = original
        ...
        async def _get_response_async(
            self,
            request: HttpRequest,
        ) -> HttpResponse:
            return _terminal_response()
```

What this means in practice:

1. The handler is built once per process (cached as `_async_handler` / `_sync_handler`).
2. It temporarily replaces `settings.MIDDLEWARE` with the filtered list, calls Django's own `super().load_middleware(is_async=True)`, then restores the original list.
3. Django builds an `_middleware_chain` callable that walks every entry in `settings.MIDDLEWARE` in order — same as an HTTP request.
4. The chain's terminal "view" returns an empty `200 OK` `HttpResponse`. That's the placeholder Django needs to thread the chain; the real "work" of the event happens in the `@rx.event` handler *after* preprocess completes.
5. If any middleware returns a response without delegating (e.g. `LoginRequiredMiddleware` returns `HttpResponseRedirect("/login")`), the chain short-circuits with that response — exactly like an HTTP request.

The skip list keeps two middleware out of the event path by default:

```39:42:src/reflex_django/event_handler.py
DEFAULT_EVENT_MIDDLEWARE_SKIP: tuple[str, ...] = (
    "django.middleware.csrf.CsrfViewMiddleware",
    "reflex_django.streaming_middleware.AsyncStreamingMiddleware",
)
```

- `CsrfViewMiddleware` would reject every event with HTTP 403 (Socket.IO events don't carry CSRF tokens in HTTP form).
- `AsyncStreamingMiddleware` only adapts streaming HTTP responses; it has nothing useful to do on a synthetic event.

Override with `REFLEX_DJANGO_EVENT_MIDDLEWARE_SKIP = (...)`.

Every other middleware runs unmodified: `SessionMiddleware` populates `request.session`, `AuthenticationMiddleware` populates `request.user`, `MessageMiddleware` populates `request._messages`, `LocaleMiddleware` activates the right language, and so do all your custom middlewares.

---

## 9. Eagerly resolving `request.user`

`AuthenticationMiddleware` assigns `request.user` to a `SimpleLazyObject` that defers the database query until first access. Lazy users are dangerous in async contexts: the first attribute access from `@rx.event` would crash with `SynchronousOnlyOperation` because `auth.get_user()` hits the DB synchronously.

The bridge resolves the user eagerly using Django's `aget_user` immediately after the middleware chain finishes:

```text
1. Middleware chain runs — request.user = SimpleLazyObject(lambda: get_user(request))
2. Bridge calls django.contrib.auth.aget_user(request) — async-safe DB hit
3. Bridge swaps request.user with the resolved User (or AnonymousUser)
4. @rx.event handler reads self.user — no SynchronousOnlyOperation, no second DB hit
```

After this step, `self.user` inside the handler is the real, resolved `User` instance.

---

## 10. Binding to the handler

The bridge attaches three layers of context:

| Layer | What's exposed |
|:---|:---|
| **`ContextVar`s** (per-task) | `current_request()`, `current_response()`, `current_user()`, `current_messages()`, `current_csrf_token()` — accessible from anywhere in the handler call graph. |
| **State tree attributes** | `state._django_led_request_wrapper`, `state._django_led_response` — set on every `BaseState` instance reachable from the root. |
| **`AppState` API** | `self.request`, `self.user`, `self.session`, `self.messages`, `self.csrf_token`, `self.response`, `self.django_response`, `self.resolver_match`. |

These three layers all point at the same `HttpRequest` and `HttpResponse`. The `ContextVar` layer is what makes `current_user()` work from helper functions called by your handler; the state-tree layer is what makes `self.request` work in the substate model.

Because Reflex pickles state to its state manager periodically, the integration patches `BaseState.__getstate__` to **strip** the transient request/response attributes before serialization. The next event rebuilds them from fresh `router_data`. You never lose access to `self.request`; you just don't ship a Django `HttpRequest` across pickle boundaries.

---

## 11. Middleware redirects → `rx.redirect`

If a middleware short-circuits with a 3xx response, the bridge converts it to a Reflex navigation:

```python
# Inside DjangoEventBridge.preprocess (simplified):

response = await run_middleware_chain(request)

if 300 <= response.status_code < 400 and settings.REFLEX_DJANGO_AUTO_REDIRECT_FROM_MIDDLEWARE:
    location = response["Location"]
    return rx.redirect(location)   # browser navigates, handler does NOT run
```

This means a custom `LoginRequiredMiddleware` that returns `HttpResponseRedirect("/login")` automatically forces the SPA to navigate to `/login` — without you writing any Reflex-specific code. Disable with `REFLEX_DJANGO_AUTO_REDIRECT_FROM_MIDDLEWARE = False`.

---

## 12. After preprocess: the handler runs

Once preprocess returns `None`, Reflex's event processor invokes the actual `@rx.event` handler with the bound state. Inside the handler:

```python
class HomeState(AppState):
    @rx.event
    async def save_profile(self, payload: dict):
        # All of these were populated by the middleware chain that just ran:
        user = self.user                      # request.user (User instance)
        session = self.session                # request.session (async-safe)
        messages = self.messages              # JSON snapshot of contrib.messages
        token = self.csrf_token               # CSRF token for the request
        response = self.response              # HttpResponse from terminal view

        # Use any sync-or-async Django API:
        from django.contrib import messages as dj_messages
        await self.request.session.aset("last_save", time.time())
        dj_messages.success(self.request, "Saved")
        # The next event will see the new flash message in self.messages
```

When the handler returns, Reflex pushes the resulting state mutations down the **same** WebSocket back to the browser. The browser applies the patches reactively (no full page reload). The connection stays open, ready for the next event.

---

## 13. Other reserved endpoints on `/_event`'s neighbours

Reflex's inner `_api` also handles a few sibling endpoints on the same reserved-prefix mechanism:

| Endpoint | Transport | Owned by |
|:---|:---|:---|
| `GET /_event/...` | HTTP polling fallback / handshake | Socket.IO (inside `_api`) |
| `WS /_event/...` | WebSocket | Socket.IO (inside `_api`) |
| `POST /_upload` | HTTP multipart | Reflex Starlette route. The `apply_upload_router_data_patch()` hook (see `DjangoEventBridge.__init__`) ensures the upload request carries usable `router_data` so the bridge can still build a Django request. |
| `GET /_health`, `GET /ping` | HTTP | Reflex JSON probes |
| `GET /_all_routes` | HTTP | Reflex internal |

All five are routed by the **same** outer-dispatcher mechanism. The dispatcher does not care which is HTTP and which is WebSocket — it just sees the reserved prefix and delegates.

---

## 14. Non-`/_event` WebSocket scopes

What happens if some other code tries to open a WebSocket to a different path? The dispatcher handles them too:

```128:165:src/reflex_django/django_outer_dispatcher.py
    async def _handle_websocket(
        self,
        scope: ASGIScope,
        receive: ASGIReceive,
        send: ASGISend,
    ) -> None:
        """Forward a WebSocket scope to Vite (dev) or close it gracefully."""
        try:
            from reflex_django.dev_proxy import (
                _dev_vite_target_or_none,
                proxy_websocket_to_vite,
            )
        except Exception:
            await self._close_websocket(receive, send)
            return

        target = _dev_vite_target_or_none()
        if target is None:
            await self._close_websocket(receive, send)
            return

        try:
            await proxy_websocket_to_vite(scope, receive, send)
        except Exception:
            logger.exception("Vite HMR WebSocket proxy failed for %s", scope.get("path"))
            await self._close_websocket(receive, send)

    @staticmethod
    async def _close_websocket(receive: ASGIReceive, send: ASGISend) -> None:
        """Politely close an incoming WebSocket connection (1011 = server error)."""
        try:
            msg = await receive()
            if msg.get("type") != "websocket.connect":
                return
            await send({"type": "websocket.close", "code": 1011})
        except Exception:
            with contextlib.suppress(Exception):
                await send({"type": "websocket.close", "code": 1011})
```

Decision tree for a non-reserved WebSocket scope:

1. If a Vite dev proxy is active (only true with `manage.py run_reflex --with-vite`), forward the WebSocket frames upstream so Vite's HMR channel works.
2. Otherwise, accept the connection and immediately send `websocket.close` with code `1011` (server error). The browser sees a quick close instead of a hung connection.

This explicit handling matters because Django's ASGI handler raises `ValueError: Django can only handle ASGI/HTTP connections, not websocket` if you hand it a `scope["type"] == "websocket"`. The dispatcher never lets that happen.

---

## 15. Lifespan: the third scope type

ASGI servers also send `scope["type"] == "lifespan"` once at startup and once at shutdown. The dispatcher implements the lifespan protocol against Reflex's lifespan context manager:

```167:213:src/reflex_django/django_outer_dispatcher.py
    async def _handle_lifespan(
        self,
        scope: ASGIScope,
        receive: ASGIReceive,
        send: ASGISend,
    ) -> None:
        """Implement the ASGI lifespan protocol against Reflex's lifespan manager.

        Django's ASGI handler ignores lifespan; only Reflex needs it (event
        processor, background tasks, prerender). If no manager is provided we
        respond with ``startup.complete`` / ``shutdown.complete`` so the server
        does not hang.
        """
        del scope
        cm: contextlib.AbstractAsyncContextManager[None] | None = None
        startup_msg = await receive()
        if startup_msg.get("type") != "lifespan.startup":
            return

        try:
            if self.lifespan_cm is not None:
                cm = self.lifespan_cm(None)
                await cm.__aenter__()
            await send({"type": "lifespan.startup.complete"})
        except Exception as exc:
            ...
            await send({"type": "lifespan.startup.failed", "message": repr(exc)})
            return

        shutdown_msg = await receive()
        if shutdown_msg.get("type") != "lifespan.shutdown":
            return

        try:
            if cm is not None:
                await cm.__aexit__(None, None, None)
            await send({"type": "lifespan.shutdown.complete"})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            ...
            await send({"type": "lifespan.shutdown.failed", "message": repr(exc)})
```

Reflex needs lifespan to start its event processor, prerender pages, and launch any user-registered background tasks. Django's ASGI handler ignores lifespan entirely. The dispatcher bridges both: it calls `rx_app._run_lifespan_tasks` for startup/shutdown and responds with the correct `lifespan.{startup,shutdown}.complete` messages so the ASGI server doesn't hang.

---

## 16. End-to-end: what the user clicks vs what runs

```text
User clicks "Save" button
   │
   ▼
React component dispatches event over open WebSocket → /_event
   │
   ▼
DjangoOuterDispatcher: scope.type=websocket, path=/_event → reserved
   │
   ▼
Reflex inner _api: Socket.IO server decodes the frame, emits Event(...)
   │
   ▼
Reflex event processor: queues Event(...)
   │
   ▼
DjangoEventBridge.preprocess(app, state, event):
   ├── build HttpRequest from event.router_data
   ├── run settings.MIDDLEWARE (full chain) → HttpResponse
   ├── if 3xx → return rx.redirect(Location)  (handler skipped)
   ├── aget_user(request) → real User instance
   └── bind request/response/user/session to state + ContextVars
   │
   ▼
@rx.event handler runs: reads self.request, self.user, self.session, mutates state
   │
   ▼
Reflex serializes state deltas → Socket.IO frame back over the same WebSocket
   │
   ▼
Browser receives patches → React re-renders
```

Every single step happens inside one process, on one port, over one persistent WebSocket. No HTTP round-trip per click. No second TCP connection. No CORS preflight. The only "request/response" in the entire chain is the synthetic one the bridge builds and immediately throws away after the handler reads what it needs.

---

## 17. Why the dispatcher routes WebSockets but Django does not own them

There are three reasons why `/_event` is intercepted *before* it reaches Django's ASGI handler:

1. **Django's ASGI handler does not natively serve WebSockets.** Django Channels would, but the integration deliberately does not depend on Channels — the lifespan model conflicts with Reflex's, and the inter-process layer Channels adds is unnecessary when both halves live in the same Python process.
2. **Reflex's Socket.IO server already implements the WebSocket protocol.** Forwarding the scope to Reflex unchanged lets `python-socketio` handle frames, heartbeats, and reconnects directly.
3. **Django middleware still applies, but on a synthetic request.** The `EventMiddlewareHandler` mechanism gives every middleware the chance to inspect, augment, or short-circuit each event — without inventing a parallel "Reflex middleware" world that mirrors Django's.

The net result: WebSockets are owned by Reflex, but `request.user`, `request.session`, redirects, locale, messages, CSRF, and custom middleware all behave exactly as they would for an HTTP view.

---

## 18. Common questions

**Does Django Channels need to be installed?**

No. The integration implements ASGI lifespan and WebSocket handling itself. Installing Channels is harmless but unnecessary, and you must not put a Channels `URLRouter` in front of `reflex_django.asgi_entry:application`.

**Are Reflex events authenticated like HTTP requests?**

Yes. The browser's cookies — including `sessionid` and `csrftoken` — ride along on the WebSocket upgrade. Every event carries those cookies in `router_data["headers"]["cookie"]`. `SessionMiddleware` loads the session from the cookie, `AuthenticationMiddleware` resolves the user, exactly as for a real HTTP request.

**Can I add my own middleware that should run on Reflex events?**

Yes. Anything in `settings.MIDDLEWARE` runs by default. Add `LoginRequiredMiddleware`, multi-tenancy, rate limiting, audit logging — they apply uniformly. To skip one, add it to `REFLEX_DJANGO_EVENT_MIDDLEWARE_SKIP`.

**What if I want CSRF on Reflex events?**

`CsrfViewMiddleware` is skipped by default because it expects a token in `POST` data. To enforce CSRF on events, write a small middleware that reads a shared-secret token from `event.payload` (the SPA can put one there from `DjangoUserState.csrf_token`) and reject mismatches. Then remove `CsrfViewMiddleware` from `REFLEX_DJANGO_EVENT_MIDDLEWARE_SKIP`.

**What about uploads?**

`POST /_upload` is an HTTP route (not a WebSocket) but lives under the same reserved-prefix mechanism. The integration patches the upload route so each upload request carries usable `router_data`, and the bridge runs the same middleware chain — `request.user`, `request.session`, etc. work identically inside an upload handler.

**Why does my reload sometimes feel slow?**

`manage.py run_reflex` re-exports the SPA on every `.py` change before respawning uvicorn. WebSockets are torn down cleanly and the browser reconnects to `/_event` once the new server is listening. Pass `--skip-rebuild` to skip the per-restart re-export, or `--with-vite` for the legacy HMR loop.

---

**Navigation:** [← Architecture](architecture.md) | [Routing →](routing.md) | [State management →](state_management.md)
