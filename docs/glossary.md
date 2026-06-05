# Glossary

Definitions of every term in these docs, in one place. If you've forgotten what a name means, look here first.

---

### `add_auth_pages()`
A helper from `reflex_django.auth` that registers the built-in `/login`, `/register`, `/password_reset`, and `/password_reset_confirm` pages in one call.

### `AnonymousUser`
Django's stand-in for "no logged-in user". When a request has no valid session, `request.user` is an `AnonymousUser` instance. `is_authenticated` is `False`.

### `AppState`
The `reflex-django` base class for Reflex states that need Django context. Subclassing it gives `self.request`, `self.user`, `self.session`, plus reactive snapshot variables. ([Details](state_management.md).)

### `ASGI`
Asynchronous Server Gateway Interface — the modern, async-capable replacement for WSGI. The protocol that lets one Python process handle both HTTP requests and WebSocket connections. `reflex-django` runs as a single ASGI app.

### `ASGIStaticFilesHandler`
Django's helper that serves files from `STATIC_URL` during development. Wraps your ASGI app so static assets work without a separate web server.

### `AsyncStreamingMiddleware`
A small Django middleware shipped with `reflex-django` that adapts sync streaming responses to be async-safe under ASGI. Add it at the end of `MIDDLEWARE`. ([Details](async_streaming_middleware.md).)

---

### `BaseModelState`
The minimum a CRUD state needs (model, Meta, dispatch). The bottom of the CRUD class hierarchy. Almost never used directly — always wrapped with mixins or extended by `ModelState`/`ModelCRUDView`.

### `begin_event_request` / `end_event_request`
Helpers from `reflex_django.context` for setting up a synthetic event context in tests. Use them to populate `self.request.user` when calling a handler directly.

### `ContextVar`
A Python primitive (from `contextvars`) that carries per-task state through async code. `reflex-django` uses one to attach the per-event request to the current async task, so `self.request.user` works even though we're in an async event loop.

### `CRUD`
Create, Read, Update, Delete — the four standard operations on a database row. `ModelState` and `ModelCRUDView` are declarative CRUD helpers.

### `CSRF`
Cross-Site Request Forgery — an attack where a third-party site tricks the user's browser into submitting a form to your site with their cookies. Django's `CsrfViewMiddleware` defends against it. CSRF is skipped on Reflex WebSocket events because the attack shape doesn't apply.

---

### `DjangoEventBridge`
The `reflex-django` component that intercepts every Reflex event, builds a synthetic `HttpRequest`, runs `settings.MIDDLEWARE`, and binds the result to the handler. The reason `self.request.user` works. ([Details](websocket_event_pipeline.md).)

### `DjangoUserState`
A small reactive Reflex state that exposes JSON-safe user snapshot fields (`is_authenticated`, `username`, `email`, `messages`, `csrf_token`, `language`). Used in UI components. Inherited transparently by `AppState`.

### `DjangoOuterDispatcher`
The outer ASGI callable that owns port 8000. It decides, per incoming scope, whether to send it to Django or to Reflex's inner ASGI.

### `django_led_app`
A built-in module (`reflex_django.django_led_app`) that auto-imports `{app}/views.py` for every entry in `INSTALLED_APPS` and builds the `rx.App()` instance. Replaces the `{app}/{app}.py` file you'd write in plain Reflex.

### `django_prefix`
The list of URL prefixes Django owns (e.g. `/admin`, `/api`). Used by the SPA catch-all and Vite dev proxy so backend routes are not treated as SPA pages. **By default, reflex-django infers this from your `urlpatterns`** when you call `reflex_mount()` last — you only pass `django_prefix=(...)` when you need to override auto-detection (e.g. bare `re_path()` routes).

### `Dispatch pipeline`
The run-loop inside `ModelState`/`ModelCRUDView` that wraps a CRUD operation with permission checks, validation hooks, the ORM call, and reactive var updates. Provided by `DispatchMixin`.

---

### `Event handler`
A method on a Reflex state, decorated with `@rx.event`. Called when the SPA fires an event. In `reflex-django`, handlers usually have access to `self.request.user`.

### `EventMiddlewareHandler`
A Django `BaseHandler` subclass that runs `settings.MIDDLEWARE` against a request without trying to dispatch to a view. Used by the bridge.

### `export_reflex`
The `manage.py` command that builds the Reflex SPA bundle. Run in CI before `collectstatic`. ([CLI reference](cli.md).)

---

### `HttpRequest`
Django's request object. In `reflex-django`, the bridge builds a *synthetic* `HttpRequest` for each WebSocket event so Django middleware can run normally.

### `HttpResponse`
Django's response object. Available as `self.response` in handlers after the middleware chain runs.

---

### `INSTALLED_APPS`
The list in `settings.py` of Django apps. `reflex-django` auto-discovers Reflex pages in every entry's `views.py`.

---

### `LANGUAGE_CODE`
Django setting for the default language. Also a per-request value set by `LocaleMiddleware`. Available as `self.request.LANGUAGE_CODE` and reactively as `DjangoUserState.language`.

### `Lifespan`
ASGI's startup/shutdown protocol. The outer dispatcher forwards lifespan scopes to Reflex's inner ASGI for background-task setup.

### `login_required`
A decorator from `reflex_django.auth` that rejects unauthenticated handler calls. Redirects to `REFLEX_DJANGO_LOGIN_URL`.

---

### `manage.py`
Django's project entry point. `reflex-django` adds two commands: `run_reflex` and `export_reflex`.

### `messages`
Django's flash-message framework. Available as `self.messages` (snapshot) and via `messages.success(self.request, ...)` to write. ([Details](authentication.md#flash-messages).)

### `Middleware`
A Django concept: a chain of classes that wrap every HTTP request. Each one can read or modify the request, short-circuit with a response, or do nothing. `reflex-django` runs this chain on every Reflex event too. ([Details](how_django_works.md#middleware--the-layered-onion).)

### `ModelCRUDView`
A declarative CRUD class that uses an explicit `serializer_class` and generates named handlers (`save_post`, `delete_post`). ([Details](crud_with_mixins_and_states.md).)

### `ModelListView`
A read-only variant of `ModelState`. List + filter + paginate, no edit, no delete.

### `ModelState`
The most common declarative CRUD class. Auto-builds a serializer from `model + fields`, generates state vars and handlers. ([Details](reactive_model_state.md).)

---

### `on_load`
A page-level event handler passed to `@page(route=..., on_load=...)`. Runs when the user navigates to that route. Use it to fetch data and gate by login.

### `Outer dispatcher`
See `DjangoOuterDispatcher`.

---

### `@page`
The primary decorator from `reflex_django.pages.decorators` that registers a Reflex page. You own the page's outer container.

### `Page`
A Reflex component decorated with `@page` (or `centered_template`) and assigned a URL route. The user navigates to pages; pages render components; components are bound to state.

### `PermissionMixin`
A mixin that wires DRF-style permission classes into the dispatch pipeline. Pass `Meta.permission_classes = (...)` to use it.

### `Plugin (Reflex plugin)`
A Reflex extension point. `reflex-django` registers one — `ReflexDjangoPlugin` — that installs the event bridge, the URL dispatcher, and the SPA-shell rendering pipeline.

### `Preprocess middleware`
A Reflex hook that runs before an event handler. `DjangoEventBridge.preprocess` is registered as a preprocess middleware so the bridge can populate the request context before the handler executes.

---

### `Reactive variable`
A field on a Reflex state class that, when mutated on the server, causes the UI to re-render. `count: int = 0` on a `rx.State` is reactive.

### `Reflex`
The framework that compiles Python states + components into a React SPA, with a server-side state engine and a WebSocket-driven update protocol. [reflex.dev](https://reflex.dev).

### `reflex_mount()`
The single function call in `urls.py` that wires Reflex into Django. ([Configuration](configuration.md).)

### `ReflexDjangoPlugin`
The built-in Reflex plugin that installs all the integration hooks. Always added automatically by `reflex_mount()`.

### `ReflexDjangoModelSerializer`
The DRF-style serializer class shipped with `reflex-django` for turning Django model instances into JSON-safe dicts. ([Details](serializers.md).)

### `ReflexMountView`
The Django view that serves the compiled SPA's `index.html` for the catch-all URL pattern.

### `Reserved Reflex prefixes`
URL prefixes (`/_event`, `/_upload`, `/_health`, `/ping`, `/_all_routes`, `/auth-codespace`) that the outer dispatcher *always* sends to Reflex, regardless of `urls.py`.

### `request.user`
Django's representation of "who is making this request". Set by `AuthenticationMiddleware`. In Reflex events, available as `self.request.user` or `self.user`.

### `RequestProxy`
A module-level proxy (`from reflex_django import request`) that lets non-`AppState` states read the current request without inheritance.

### `Router data`
A dict carried by every Reflex event with the page's path, query, cookies, and headers. The bridge uses it to rebuild the synthetic `HttpRequest`.

### `rx.Component`
The Reflex base type for UI elements. Functions returning `rx.Component` are how you build pages.

### `rx.State`
Reflex's base state class. `AppState` inherits from it.

### `rx.event`
Reflex's decorator that marks a method as an event handler — callable from the SPA over the WebSocket.

### `rx.redirect`
A Reflex event return value that tells the SPA to navigate to a different URL. Middleware redirects are auto-converted to `rx.redirect(...)` by the bridge.

### `rxconfig.py`
A Reflex configuration file at the project root. In `reflex-django`, this file is optional and usually absent — `reflex_mount()` replaces it.

---

### `Serializer`
A class that converts a Python object (typically a Django model instance) into a JSON-safe dict. `reflex-django` ships `ReflexDjangoModelSerializer`; DRF has its own `ModelSerializer`. They're separate classes for separate purposes.

### `Session`
Django's per-user persistent storage, keyed by the `sessionid` cookie. Available as `self.session` in handlers (or `self.request.session`).

### `SessionMiddleware`
Django's middleware that loads the session row from the `sessionid` cookie. Must be in `MIDDLEWARE` for `request.session` (and Reflex auth) to work.

### `Skip list`
The middleware classes the bridge intentionally bypasses on Reflex events. Default: `CsrfViewMiddleware` and `AsyncStreamingMiddleware`. Configurable via `REFLEX_DJANGO_EVENT_MIDDLEWARE_SKIP`.

### `Socket.IO`
The WebSocket protocol Reflex uses on `/_event`. A higher-level layer over raw WebSockets with auto-reconnect and event semantics.

### `SPA`
Single-page application. The compiled JavaScript bundle Reflex builds from your Python code. Loaded once on the first visit; in-page navigation happens client-side.

### `STATIC_ROOT`
The Django setting for where `collectstatic` puts gathered static files. `reflex-django` stages the compiled SPA into `STATIC_ROOT/_reflex/`.

### `Streaming response`
A Django `StreamingHttpResponse` — an iterator of byte chunks. `AsyncStreamingMiddleware` adapts these for ASGI.

### `Synthetic request`
A `django.http.HttpRequest` instance constructed by the bridge from a WebSocket event payload (not from an actual HTTP request). Looks and behaves like a real request to Django middleware.

---

### `centered_template`
An optional decorator from `reflex_django.pages.decorators.templates` for registering a Reflex page wrapped in a centered layout container. Often imported `as template`.

### `UserScopedMixin`
A mixin that auto-scopes CRUD queries to the current user. Replaces three manual hook overrides (`get_queryset`, `get_object_lookup`, `get_create_kwargs`).

---

### `Vite`
The frontend build tool Reflex uses internally. `run_reflex` starts it on the frontend port (default **3000**) for HMR; in DJANGO_OUTER mode Django reverse-proxies SPA traffic to it while you browse **:8000**. See [Local development](local_development.md).

### `DEFAULT_DEV_MIDDLEWARE`
A tuple of dotted middleware paths in `reflex_django.django_dev_middleware` for Vite-port admin and CSRF (`EnsureRequestBodyAttrsMiddleware`, `DevViteProxyHostMiddleware`). Prepend to `MIDDLEWARE` in development settings only.

---

### `views.py`
The conventional Django filename for view functions. In `reflex-django`, also where Reflex pages and `AppState` subclasses live — they coexist with Django views in the same file.

---

### `WebSocket`
A protocol that keeps one TCP connection open and lets the client and server exchange messages bidirectionally. Reflex events travel over a WebSocket to `/_event`.

### `Workers`
ASGI server processes. Multiple workers can serve more concurrent requests. For Reflex state to be consistent across workers, enable sticky sessions on your load balancer or use a Redis state backend.

### `WSGI`
The synchronous predecessor to ASGI. `reflex-django` requires ASGI; you can't run it under a WSGI-only server like classic gunicorn.

---

**Back to:** [Home](index.md) · [FAQ](faq.md)
