# Glossary

**What you will learn:** Plain definitions for terms used across these docs.

**When you need this:**

- You forgot what a name means mid-tutorial.
- You are onboarding and want a single lookup page.

Terms are alphabetical within each letter group.

---

## A

### `add_auth_pages()`
Helper that registers built-in `/login`, `/register`, and password-reset pages. [Authentication](../guides/authentication.md).

### `AnonymousUser`
Django's stand-in when no session is present. `is_authenticated` is `False`.

### `AppState`
Base Reflex state with Django context: `self.request`, `self.user`, `self.session`, plus reactive snapshots. [State management](../guides/state.md).

### `ASGI`
Asynchronous Server Gateway Interface. One Python process handles HTTP and WebSocket. reflex-django requires ASGI.

### `AsyncStreamingMiddleware`
Django middleware for async-safe streaming responses. Put it last in `MIDDLEWARE`. [Details](../internals/streaming_middleware.md).

---

## B

### `begin_event_request` / `end_event_request`
Test helpers that bind a synthetic request for handler calls. [Testing](../operations/testing.md).

---

## C

### `ContextVar`
Python primitive for per-task state in async code. The bridge uses one for the current event request.

### `CRUD`
Create, Read, Update, Delete. `ModelState` and `ModelCRUDView` automate this pattern.

### `CSRF`
Cross-Site Request Forgery protection for HTML forms. Skipped on Reflex WebSocket events. [Authentication](../guides/authentication.md).

---

## D

### `DjangoEventBridge`
Runs Django middleware for each Reflex event so `self.request.user` works. [WebSocket pipeline](../internals/event_pipeline.md).

### `DjangoUserState`
Reactive snapshot of user, messages, CSRF, and language for UI binding.

### `make_dispatcher`
Path-prefix ASGI transformer in `reflex_django.asgi.app`. Attached to `app.api_transformer` during dev. Routes Django URL prefixes to Django ASGI and Reflex reserved paths to Reflex. [Routing](../internals/routing.md).

### `RX_AUTH`
Dict of built-in auth page settings, including `LOGIN_URL` (where `@login_required` redirects). [Authentication](../guides/authentication.md).

### `ensure_reflex_app_ready`
Internal app-factory helper that loads the Reflex `App`, imports pages, and syncs decorated routes before compile. [App entry and pages](../guides/app_entry_and_pages.md).

### `django_prefix`
URL prefixes Django owns (e.g. `/admin`, `/api`). Auto-detected from `urlpatterns` unless overridden.

### `Dispatch pipeline`
CRUD run-loop inside `ModelState`: permissions, validation, ORM, reactive updates.

### `django_outer` / `reflex_outer`
Historical routing modes from older releases. Removed in v3. Current projects use mount-only: plain `get_asgi_application()` plus `reflex_mount()`. See [Routing](../internals/routing.md).

### `DEV_PROXY` (`RX_DEV_PROXY`)
When true with single-port dev, Django reverse-proxies SPA routes to Vite. Default `run_reflex` sets it false. [Settings reference](settings.md).

---

## E

### Entry module
On-disk file at `{app_name}/{app_name}.py`. Reflex's toolchain imports `{app_name}.{app_name}:app`. Keep it thin; register pages in `{app_name}/views.py` instead. [App entry and pages](../guides/app_entry_and_pages.md).

### `Event handler`
Method decorated with `@rx.event`, called from the SPA over the WebSocket.

### `export_reflex`
Management command that builds the SPA for CI/production. [CLI reference](../operations/cli.md).

---

## H

### `HttpRequest` / `HttpResponse`
Django request/response objects. The bridge builds a synthetic `HttpRequest` per event.

---

## M

### `Middleware`
Django classes that wrap each request. reflex-django runs the chain on Reflex events too.

### `ModelState` / `ModelCRUDView` / `ModelListView`
Declarative CRUD helpers. [Reactive model state](../guides/crud.md#modelstate).

---

## O

### `@page`
Decorator that registers a Reflex page and route. [Pages in views](../guides/pages.md).

---

## P

### Page registry hub
Module (usually `{app_name}/views.py`) that imports every `@page` module so decorators run at import and compile time. [App entry and pages](../guides/app_entry_and_pages.md).

---

## R

### `Reactive variable`
State field that triggers UI updates when mutated on the server.

### `Reflex`
Python-to-React framework with WebSocket-driven updates. [reflex.dev](https://reflex.dev).

### `app_name`
Compile label in `RX_CONFIG`, not necessarily your Django app package name.

### `reflex_mount()`
Optional URL helper for manual catch-all wiring. [Configuration](../getting-started/configuration.md).

### `ReflexMountView`
Django view that serves compiled `index.html` for SPA routes in production URLconf.

### `RX_PAGE_PACKAGES`
Settings list of modules reflex-django imports at compile time. When non-empty, replaces the default `{app_name}.views` import. [App entry and pages](../guides/app_entry_and_pages.md).

### `RX_PROXY_SERVER`
Optional dev setting. When set, Vite proxies Django URL prefixes to a separate `runserver` process. When unset, Django runs in-process on the Reflex backend. [Local development](../getting-started/local_development.md).

### `Reserved Reflex prefixes`
Paths like `/_event`, `/_upload`, `/_health`, `/ping` always handled by Reflex.

### `Router data`
Path, query, cookies, and headers carried with each Reflex event.

### `rx.State` / `rx.event` / `rx.redirect` / `rx.Component`
Core Reflex types: state base, handler decorator, navigation event, UI element.

### `rxconfig.py`
Legacy Reflex config file. Replaced by `RX_CONFIG` in v1.0.

---

## S

### `SEPARATE_DEV_PORTS` (`RX_SEPARATE_DEV_PORTS`)
Two-port dev: Vite on frontend port, backend on ASGI port. Set by default `run_reflex`. [Settings reference](settings.md).

### `Serializer`
Converts models to JSON-safe dicts. See `ReflexDjangoModelSerializer`. [Serializers](../guides/serializers.md).

### `Session` / `SessionMiddleware`
Django session storage keyed by `sessionid` cookie. Required for auth.

### `Skip list`
Middleware classes bypassed on WebSocket events. Default: CSRF and AsyncStreaming.

### `Socket.IO`
Protocol Reflex uses on `/_event`.

### `SPA`
Single-page application: compiled JS bundle from your Python pages.

### `STATIC_ROOT`
Where `collectstatic` puts files; SPA lives under `STATIC_ROOT/_reflex/`.

### `Synthetic request`
`HttpRequest` built by the bridge from a WebSocket payload, not from real HTTP.

---

## V

### `Vite`
Frontend tool Reflex uses. Default dev: browse **`:3000`**. [Local development](../getting-started/local_development.md).

### `views.py`
Django views file; in reflex-django also holds `@page` functions and state classes.

---

## W

### `WebSocket`
Persistent connection for Reflex events at `/_event`.

### `Workers`
ASGI server processes. Use sticky sessions or Redis for multi-worker state.

### `WSGI`
Legacy synchronous gateway. reflex-django requires ASGI.

---

## What just happened?

You have a single alphabetical glossary tied to the docs that explain each concept in depth.

## Next up

[Home →](index.md)