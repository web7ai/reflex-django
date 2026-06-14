# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Removed (breaking)

- All `REFLEX_DJANGO_*` Django settings and environment variables. Use `RX_*` instead (`REFLEX_DJANGO_RX_CONFIG` → `RX_CONFIG`, `RXDJANGO_PROXY_SERVER` → `RX_PROXY_SERVER`). No deprecated aliases. See [RX settings rename](docs/reference/migration/rx_settings_rename.md).
- State bridge override `_reflex_django_bridge` → `_rx_bridge`.
- `REFLEX_DJANGO_HTTP_UPSTREAM` / `RX_HTTP_UPSTREAM` (use `RX_PROXY_SERVER`).
- Composed ASGI entry `reflex_django.asgi.entry:application` and outer dispatchers (`django_outer`, `reflex_outer`).
- `RX_URL_ROUTING`, `RX_HTTP_SUBPROCESS`, `RX_HTTP_PORT`, and related HTTP worker settings.
- `build_django_outer_application`, `asgi_application`, and `build_asgi_application` public exports.

### Added

- `RX_PROXY_SERVER` — optional base URL of a separate Django server for Vite dev proxy; when unset, Django is served from the Reflex backend.
- `docs/migration/v3_mount_only.md` — mount-only migration guide.
- **Tiered event bridge** — `RX_EVENT_BRIDGE_MODE` (`full` / `smart` / `none`), per-State `_rx_bridge`, optional `RX_EVENT_BRIDGE_RESOLVER`.
- **Event cache** — Django `CACHES`-backed write-only auth metadata cache (`RX_EVENT_CACHE`, TTL, `invalidate_event_cache()`).
- **`RX_PERFORMANCE_PRESET = "lean"`** — trims mirror/auth-sync defaults when still at library defaults.
- **`RX_EVENT_METRICS`** — opt-in DEBUG timing logs for bridge phases.
- `docs/scaling.md` — settings-first scaling guide for Django + realtime UI.

### Changed (breaking)

- `manage.py run_reflex` runs Reflex with Vite and the native Reflex backend; Django is mounted in the Reflex backend by default. Set `RX_PROXY_SERVER` only when Django runs separately.
- Production Django ASGI uses plain `get_asgi_application()`; reverse-proxy `/_event` to Reflex.

## [2.0.0] - 2026-06-12

### Removed (breaking)

- All v1 root-level module paths (no compatibility shims). See `docs/migration/v2_module_paths.md`.
- `reflex_django.django_led_app` — use `reflex_django.runtime.reflex_app` or `from reflex_django import app`.

### Changed (breaking)

- Package restructure: 53 root modules moved into domain subpackages (`asgi/`, `runtime/`, `mount/`, `bridge/`, `dev/`, `setup/`, `django/`, `cli/`, `states/`, `serializers/`).
- Default `ROOT_URLCONF` is now `reflex_django.django.urls`.
- Default `INSTALLED_APPS` entry is now `reflex_django.django.apps.ReflexDjangoConfig`.
- Default streaming middleware path is now `reflex_django.bridge.streaming.AsyncStreamingMiddleware`.
- ASGI deployment entry: `reflex_django.asgi.entry:application` (was `reflex_django.asgi_entry`).

### Added

- `docs/migration/v2_module_paths.md` — full old-to-new import map.
- `reflex_django.auth_state` kept as the canonical module for `DjangoUserState` so existing compiled frontends keep matching event handler keys (`reflex_django.states.auth` remains a re-export alias).

## [1.0.0] - 2026-06-07

### Removed (breaking)

- Legacy routing modes `reflex_led` and `django_led` — use `django_outer` (default) or `reflex_outer`.
- `ReflexDjangoPlugin` and rxconfig-first setup — use Django-first configuration (see `docs/migration/v0-to-v1.md`).
- `reflex_django.asgi.make_dispatcher` — use `reflex_django.asgi.entry.build_django_outer_application`.

### Added

- `reflex_django.core` — shared constants, env parsing, and user helpers.
- `reflex_django.mount.spa_paths` — unified SPA bundle discovery.
- `reflex_django.dev` — dev orchestration helpers (`run_plan`, `process_utils`, `asgi_runners`).
- `reflex_django.bootstrap` — app setup and patch registry.
- `reflex_django.bridge` — event bridge package layout.
- `reflex_django.setup.errors` — typed configuration exceptions.
- `docs/migration/v0-to-v1.md` and pytest CI workflow.

### Changed

- `reflex_django.django_led_app` deprecated in favor of `reflex_django.reflex_app`.
- `manage.py run_reflex` uses `RunPlan` for flag resolution.
- Plugin auto-injection in rxconfig merge is a no-op; event bridge installs via `bootstrap.app_setup`.

## [0.5.0] - 2026-06-05

### Removed (breaking)

- **Reflex event context-processor bridge** — removed `collect_reflex_context`, `DjangoContextState`, `builtin_user_context`, `builtin_i18n_context`, and settings `RX_CONTEXT_PROCESSORS`, `RX_AUTO_LOAD_CONTEXT`, `RX_USE_TEMPLATE_CONTEXT_PROCESSORS`.
- **`AppState.django_context`**, **`AppState.load_django_context()`**, **`ModelState.Meta.load_context_processors`**, and **`DjangoStateRequest.context`** (processor-key attribute fallback).
- Doc page `django_context_to_reflex.md`.

**Migration:** use middleware-backed APIs instead — `self.user` / `current_user()`, `self.messages` / `current_messages()`, `current_language()`, `self.csrf_token` / `current_csrf_token()`. For custom cross-cutting data, use explicit Reflex state vars on `AppState`. Django `TEMPLATES` context processors and SPA shell templating (`RX_RENDER_SPA_VIA_TEMPLATE_ENGINE`) are unchanged.

### Added

- **Settings-driven auto-mount** — `RX_AUTO_MOUNT=True` (default) appends the Reflex SPA catch-all to `ROOT_URLCONF` at startup. No `reflex_mount()` line required in `urls.py`.
- **`RX_CONFIG["app_name"]`** — Reflex compile identity moves to settings; `reflex_mount(app_name=...)` is deprecated.
- **`from reflex_django import app`** — native Reflex-style page registration via `app.add_page()` on the `django_led_app` singleton.
- **`reflex_django.mount.auto`** — `maybe_auto_mount()`, `ensure_reflex_mount()`, `register_mount_from_settings()` for boot-time URL wiring.
- Tests: `test_auto_mount.py`, `test_django_led_app_pages.py`, `test_production_entry.py`.

### Changed

- **Docs** — new [mental_model.md](docs/mental_model.md); entry points updated for auto-mount and settings-driven `app_name`.
- **`reflex_mount()`** — returns a URL-only :class:`~reflex_django.mount.auto.ReflexMountHandle` (iterable / `.urlpatterns`); use for URL overrides only, not page registration.
- **`reflex_django.django.urls.urlpatterns`** — default empty list; catch-all comes from auto-mount when enabled.
- **`RX_AUTO_DISCOVER_PAGES`** — still default `True` but emits `DeprecationWarning`; explicit `urls.py` imports recommended until next major.
- **`apply_reflex_plugins_to_app()`** — restores plugins after `rx.App()` clears `get_config().plugins`.

### Added (continued)

- **Two-port dev workflow (default)** — `python manage.py run_reflex` now matches native Reflex:
  open the **frontend port** (`:3000`) for the SPA; the **backend port** (`:8000`) serves Django
  and Reflex endpoints only (admin, API, `/_event`). The SPA's `env.json` points backend paths
  at `:8000`. Pass ``--env dev`` for compile-only single-port dev on `:8000`.
- Setting ``RX_SEPARATE_DEV_PORTS`` and env ``RX_SEPARATE_DEV_PORTS``.
- **Compile dev on one port (`--env dev`)** — sets ``RX_COMPILE_DEV=1``; recompiles
  to ``.web/`` on save and serves from Django on port 8000 (no Vite after first compile).
  Pass ``--with-vite`` to add live HMR on `:3000` again. For Django reverse-proxying Vite on
  one URL, set ``RX_DEV_PROXY=1`` explicitly (no CLI flag).
- **`export_rx_port_env()`** — `reflex_mount()` exports `frontend_port` and `backend_port`
  from `rx_config` into the environment so the dev proxy resolves ports even outside
  `run_reflex`.
- **`RX_FRONTEND_PORT` / `RX_BACKEND_PORT`** — optional Django
  settings (and env vars) for the Vite and ASGI ports; documented in
  [Settings reference](docs/settings_reference.md).
- **`strip_vite_django_dev_proxy()`** — removes stale Vite→Django `server.proxy` rules from
  `.web/` in DJANGO_OUTER mode (bidirectional proxies caused request loops on `:8000`).
- **`run_reflex` port checks** — fails fast when the frontend port is already in use;
  waits for Vite to serve a real SPA document before starting uvicorn (not just a TCP
  connect).
- **Vite `strictPort: true`** — injected via `frontend_stability` so Vite does not silently
  hop to `:3001` when `:3000` is busy.
- **`reflex_django.dev.django_middleware`** — optional Django HTTP middleware for Vite
  dev (`EnsureRequestBodyAttrsMiddleware`, `DevViteProxyHostMiddleware`, and
  ``DEFAULT_DEV_MIDDLEWARE`` for settings). Documented in
  [Local development](docs/local_development.md).
- **`reflex_django.dev.frontend_stability`** — post-compile patches for
  ``EventLoopContext``, generated components, and Vite ``resolve.dedupe`` (fixes
  ``useContext is not a function or its return value is not iterable`` without
  breaking ``react/jsx-runtime``).
- Vite proxy plugin forwards ``x-forwarded-host`` / ``x-forwarded-proto`` to the
  Django backend during local dev.
- Tests: ``test_django_dev_middleware``, ``test_frontend_stability``.

### Changed

- **Dev docs and defaults** — installation, CLI, FAQ, and local-development guides now
  describe default two-port dev (`:3000` for SPA, `:8000` for backend) and ``--env dev`` for
  compile-only single-port dev. Legacy ``--single-port`` CLI flag removed; use ``--env dev`` or
  ``RX_DEV_PROXY=1`` instead.
- **`ReflexDjangoPlugin.pre_compile`** — skips injecting Vite→Django proxy rules in
  DJANGO_OUTER mode; `post_compile` strips any stale proxy block instead.
- **`ReflexMountView`** — when `RX_DEV_PROXY=1` (set by `run_reflex`), Vite
  outages return **503** with a clear message instead of serving a broken disk bundle.
- **`_resolve_frontend_port_from_config()`** — reads ports from Django settings and the
  `reflex_mount()` registry, not only `rx.Config` and env.
- **Breaking:** public API reorganized. Built-in State classes now live under
  ``reflex_django.states`` (``from reflex_django.states import AppState,
  DjangoUserState, DjangoAuthState, DjangoI18nState, DjangoContextState,
  ModelState``). The page decorator moved to ``reflex_django.pages.decorators``
  (``from reflex_django.pages.decorators import page``) and the layout decorator
  moved to ``reflex_django.pages.decorators.templates`` as ``centered_template``
  (``from reflex_django.pages.decorators.templates import centered_template as
  template``).

### Removed

- **Breaking:** removed the old import paths. ``reflex_django.decorators`` and
  ``reflex_django.ui`` are gone, and the top-level ``reflex_django.{page,
  template, AppState, ModelState, DjangoUserState, DjangoAuthState,
  DjangoI18nState, DjangoContextState}`` re-exports no longer exist. Import these
  from ``reflex_django.states`` and ``reflex_django.pages.decorators`` instead.

### Fixed

- **Dev proxy loop on `:8000`** — stale bidirectional Vite/Django proxies and disk fallback
  to an incomplete `.web` bundle could make the browser spin on static assets; DJANGO_OUTER
  now strips Vite-side proxies and avoids disk fallback while the dev proxy is explicitly on.
- **"Reflex SPA bundle not found" in dev** — clearer 404 text when the dev proxy is off
  (e.g. `runserver` / bare `uvicorn` without Vite); port env export and settings help
  `run_reflex` find the right Vite target.
- **Vite port mismatch** — when `:3000` was occupied, Vite could bind to `:3001` while
  Django still proxied to `:3000`; `strictPort` and pre-flight port checks address this.
- Frontend dev: ``useContext(EventLoopContext)`` destructuring on ``null`` default
  context; Vite ``react`` → ``index.js`` aliases that broke ``react/jsx-runtime``
  pre-bundling.
- Django admin CSRF / POST body: dev middleware only stubs ``_body`` when
  ``CONTENT_LENGTH`` is 0 (documented; use ``django_dev_middleware`` instead of
  project-local copies).

- ``dispatch is not a function``: patch ``reflex.page`` to bucket decorators under
  ``reflex_mount()`` ``app_name``; run ``prepare_pages_for_compile()`` before compile
  (and recompile once when ``.web/utils/context.js`` dispatchers are stale); dedupe
  ``DECORATED_PAGES`` by route; skip duplicate ``_apply_decorated_pages`` on cached apps.
- ``dispatch is not a function`` on ``AppState`` pages (e.g. ``HomeState.on_load`` with
  ``self.request``): ``prepare_pages_for_compile()`` re-applies pages before each compile;
  compile validation compares ``context.js`` to the live app state tree (not the global
  state registry); stale ``context.js`` is removed and compile retried on mismatch; auth
  auto-sync is scoped to the event handler substate branch instead of every
  ``DjangoUserState`` / ``DjangoAuthState`` class in the process.
- Auth auto-sync no longer runs for Reflex internal events (e.g.
  ``OnLoadInternalState``), fixing ``SetUndefinedStateVarError`` on ``user_id`` during
  ``on_load_internal``.
- Guest / unauthenticated ``on_load``: auth auto-sync uses
  :func:`~reflex_django.states.auth.apply_auth_snapshot_for_event_handler` so snapshot
  updates only mark the handler branch dirty (avoids deltas for unrelated substates);
  stale ``context.js`` is invalidated before compile when dispatch keys are already missing.
- Guest ``on_load``: skip auth snapshot writes when values are already the anonymous
  defaults (no redundant parent-substate deltas).
- Runtime: filter WebSocket deltas to substates compiled into ``.web/utils/context.js``
  (covers ``hydrate`` and handler events); auth auto-sync runs only for
  ``DjangoUserState`` page handlers, never for root/internal Reflex events.

## [0.4.0] - 2026-05-24

### Changed

- ``python manage.py run_reflex`` no longer writes ``rxconfig.py``; Reflex config is loaded
  from ``reflex_mount()`` via an in-memory ``rxconfig`` module. Auto-generated stubs are
  removed on startup unless ``RX_MATERIALIZE_RXCONFIG=True``.

### Fixed

- Blank page / ``dispatch is not a function``: pages registered under
  ``DECORATED_PAGES[""]`` before ``app_name`` was set are migrated to the
  ``reflex_mount()`` app name before compile; post-compile now warns when
  ``.web/utils/context.js`` dispatchers are missing backend substates; duplicate
  ``views.py`` imports are skipped to avoid page redefinition noise.
- Page ``on_load`` handlers not firing: ``reflex_mount()`` now imports page modules
  immediately; ``sync_page_load_events()`` copies ``on_load`` from decorated pages
  onto the live app; ``@template`` passes ``on_load`` as a handler list.
- ``self.request`` in page substates (e.g. ``HomeState.on_load``): the event bridge now
  binds the synthetic Django request on the handler substate during ``preprocess`` and
  again in the patched ``process_event`` (with a fallback bridge when middleware did not
  run); integration patches are re-applied on every bootstrap; router_data without a
  session cookie is accepted for anonymous users.
- ``reflex_mount()`` no longer catches bare backend prefixes (e.g. ``/admin`` without a
  trailing slash), so Django admin and ``APPEND_SLASH`` redirects work correctly.
- Vite dev proxy rules are written to ``.web/vite.config.js`` in ``post_compile`` when
  missing (fixes ``/admin`` 404 on the frontend port after ``reflex export``).
- WebSocket proxy for ``/_event`` (``ws: true``) and ``env.json`` URLs rewritten to the
  frontend port in ``django_led`` mode (fixes Socket.IO errors when the app runs on port 3000).
- Vite proxy is re-applied automatically after every Reflex compile (compile was overwriting
  ``vite.config.js`` and silenced ``from reflex import prerequisites`` prevented patching).

### Added

- **Django-led URL routing** (``RX_URL_ROUTING = "django_led"``): backend prefixes
  (admin, API, static) go to Django; all other HTTP paths go to Reflex (SPA catch-all).
- :func:`reflex_django.django.urls.reflex_mount` catch-all urlpattern and
  :class:`reflex_django.views.mount.ReflexMountView`.
- ``reflex_mount(plugins=..., rx_config=..., django_plugin=...)`` registers Reflex
  ``rx.Config`` from ``urls.py``; :class:`~reflex_django.ReflexDjangoPlugin` is always
  appended automatically.

### Removed

- ``RX_APP_FACTORY`` — use the built-in :func:`reflex_django.create_app` or
  edit ``{APP_NAME}/{APP_NAME}.py`` for a custom ``rx.App``.
- ``reflex_mount(admin_prefix=...)``, ``api_prefix=...``, and ``include_admin`` —
  wire Django routes in ``urlpatterns`` and list prefixes in ``django_prefix``; optional
  :func:`reflex_django.django.urls.admin_urlpatterns` for admin.
- :mod:`reflex_django.runtime.app_factory` — built-in :func:`reflex_django.create_app` and
  ``RX_PAGE_PACKAGES`` for Django-first page registration.
- Optional :func:`reflex_django.decorators.page` (``reflex_page`` alias) / ``reflex_template`` with
  ``PAGE_REGISTRY``.
- Documentation: [django_urls.md](docs/django_urls.md).

## [Unreleased]

### Fixed

- Django-first projects: bootstrap Reflex integration from :func:`configure_django` so
  Granian/Uvicorn reload workers attach ``ReflexDjangoPlugin`` (fixes ``/admin`` 404 on
  port 8000 when using ``python manage.py run_reflex``).

### Changed

- :func:`reflex_django.django.urls.reflex_mount` now registers admin routes and resolves
  ``mount_prefix`` / ``django_prefix``; admin and API prefixes from settings like
  :class:`reflex_django.ReflexDjangoPlugin` (kwargs → env → settings → defaults).
  Returns a list of URL patterns; use ``urlpatterns = reflex_mount(...)`` or
  ``*reflex_mount()`` before other routes.

### Added

- :func:`reflex_django.setup.rxconfig_bridge.ensure_rxconfig_from_django` — load Reflex
  ``Config`` from Django settings / ASGI (no ``rxconfig.py`` on disk by default).
- Auto-discovery of ``@template`` / ``@page`` modules: imports ``{app}.views`` for
  each project app in ``INSTALLED_APPS`` (no ``urls.py`` imports required).
- Django-first mode uses :mod:`reflex_django.runtime.reflex_app` instead of writing
  ``{APP_NAME}/{APP_NAME}.py`` (removed ``ensure_app_module_file`` materialization).
- :mod:`reflex_django.mount.prefixes` — shared prefix resolution for the plugin and
  ``reflex_mount``.
- Built-in :func:`reflex_django.template` layout decorator and ``from reflex_django import template, page``.
- Built-in :func:`reflex_django.create_app` — no custom factory setting; pages default to ``{APP_NAME}.views`` auto-discovery.
- Documentation: [pages_in_views.md](docs/pages_in_views.md).

- **Dual-mode integration**: Reflex-first projects (``rxconfig.py`` + ``reflex run``) and
  Django-first projects (``settings.py`` + ``python manage.py run_reflex``).
- ``python manage.py run_reflex`` management command (requires ``reflex_django`` in
  ``INSTALLED_APPS``).
- Automatic ``DJANGO_SETTINGS_MODULE`` discovery from the nearest ``manage.py``.
- Django-driven Reflex configuration via ``reflex_mount(app_name=..., rx_config={...})``
  in ``urls.py`` (optional override of ``rxconfig.py`` in Django-first mode).
- Auto-injection of ``ReflexDjangoPlugin`` when ``reflex_django`` is installed and
  Django-first mode is detected.
- Auto-materialization of a minimal ``rxconfig.py`` stub in Django-first mode when
  the file is missing (Reflex's CLI requires it on disk).

### Changed

- ``ReflexDjangoPlugin(settings_module=...)`` is deprecated; use ``manage.py`` or
  ``DJANGO_SETTINGS_MODULE`` instead.
- Plugin path prefixes can be set in Django settings
  (``RX_API_PREFIX``, ``RX_ADMIN_PREFIX``,
  ``RX_EXTRA_PREFIXES``).

### Fixed

- Django ASGI no longer warns about synchronous ``StreamingHttpResponse``
  iterators (admin static, ``FileResponse``, etc.) when
  ``reflex_django.bridge.streaming.AsyncStreamingMiddleware`` is enabled
  (included in bundled ``MIDDLEWARE``).
- ``AsyncStreamingMiddleware`` now subclasses
  ``MiddlewareMixin`` with both sync and async support, fixing
  ``'coroutine' object has no attribute 'get'`` and media/static 500s when the
  middleware was placed in ``MIDDLEWARE``.
- Logout now clears session and CSRF cookies in the browser (via
  ``browser_auth_cookies_clear_js``), strips them from the synthetic Django
  request and Reflex ``router_data``, and relies on ``alogout``'s session
  ``flush`` so stale ``sessionid`` values are not reused on the next event.
- Login mirrors the new ``sessionid`` into persisted Reflex ``router_data``
  (symmetric with logout clearing), and the event bridge preserves state
  cookies when merging ``router_data`` so post-login Socket.IO events without
  cookie headers no longer bounce between ``/`` and ``/login``.
- Logout and login navigation now clear Reflex ``sessionStorage`` (including the
  stale websocket ``token``) and logout also clears ``localStorage``, matching
  manual devtools fixes for post-logout redirect loops.
- ``authentication.md`` documents Django ``sessionid`` cookies vs Reflex
  ``sessionStorage`` ``token`` for developers coming from plain Django views.
- Upload handlers (`rx.upload` / `rx.upload_files`) now receive the same
  Django session and ``self.request.user`` as other Reflex events. Reflex
  previously enqueued upload events without ``router_data``; reflex-django
  injects cookies from the ``/_upload`` HTTP request and falls back to persisted
  ``state.router_data`` when needed, so ``@login_required`` on upload handlers
  no longer spuriously redirects logged-in users.

### Added

- `reflex_django.state.ModelState`: declarative CRUD state from a
  `ReflexDjangoModelSerializer` (`Meta.serializer`, flat form fields, combined
  `save_*`, `read_only_fields`). Import with `AppState` from
  `reflex_django.state` or lazy `from reflex_django import ModelState`.
- `ReflexDjangoModelSerializer.Meta.read_only_fields` plus
  `get_read_only_field_names()` and `writable_field_names()` for form vs list
  field split.
- `reflex_django.states.AppState`: abstract base for app domain/routing state
  (subclass instead of mixing auth into CRUD bases).
- `reflex_django.serializers.ReflexDjangoModelSerializer`: DRF-style declarative
  serializers (`Meta.fields` / `exclude`, `.data`, `.adata`) with queryset
  `many=True` (no `djangorestframework`). `ModelCRUDConfig.row_serializer_class`
  integrates with `crud_mixin`.
- `ModelCRUDMeta` / class-level config on `ModelCRUDView` for IDE autocomplete;
  `ModelState.options` alias for resolved `ModelStateOptions`.
- `from reflex_django import request` module proxy for handler-side
  `request.user`, `request.session`, `request.GET`, `request.headers`.

### Changed (breaking)

- **`ModelState` default reactive var names** are generic: `data`, `error`,
  `search`, `total_count`, `page_count`, `on_load_data`, etc. (not pluralized
  model names). **`ModelCRUDView`** without `ModelState` still pluralizes
  (`notes`, `notes_error`, …) unless `Meta.list_var` is set.
- Internal validation method renamed to `validate_model_full_clean()`;
  enable via **`Meta.run_model_validation` only** (not as a class-body attribute).
- Removed `reflex_django.authz`. Auth helpers live under `reflex_django.auth`:
  `require_login_user`, `auser_has_perm`, and `ReflexDjangoAuthError` in
  `reflex_django.auth.shortcuts`; `login_required` in `reflex_django.auth.decorators`.
- Removed `django_login_required`. Use `login_required` for both pages and event
  handlers (Django-style API with optional `login_url=`).

- `DjangoUserState` snapshot field names no longer use a `django_` prefix:
  `django_user_id` → `user_id`, `django_username` → `username`,
  `django_email` → `email`, `django_first_name` → `first_name`,
  `django_last_name` → `last_name`, `django_is_authenticated` → `is_authenticated`,
  `django_is_staff` → `is_staff`, `django_is_superuser` → `is_superuser`,
  `django_group_names` → `group_names`.

### Fixed

- Edit/save form reset: `populate_edit_state` bumps `form_reset_key` so bound
  forms reload row values; `bump_form_reset_key()` is public for custom UIs.
- Pagination: `page_size` is seeded from `Meta.paginate_by` (fixes showing one
  row when `paginate_by > 1`).
- Assembly no longer injects plain Python defaults that shadow `ModelState`
  reactive vars (fixes `list.length()` / `AttributeError` in UI).
- `run_model_validation` class-body config no longer shadows the validation
  method (`'bool' object is not callable` on save).

## [0.1.2] — 2026-05-14

### Added

- `reflex_django.mixins.crud`: declarative `ModelCRUDConfig` and `crud_mixin()` factory
  for Reflex state with Django ORM list + CRUD event handlers (optional `base` state
  class and `state_module` for pickle-safe dynamic subclasses). Re-exported from
  `reflex_django.mixins`.

## [0.1.0] — 2026-05-14

### Added

- Initial PyPI-ready release of `reflex-django`: Django ASGI integration with
  Reflex (`ReflexDjangoPlugin`), `DjangoEventBridge`, auth/session/locale
  bridging, context processors, helpers, and CLI entry point `reflex-django`.

[0.1.2]: https://pypi.org/project/reflex-django/
[0.1.0]: https://pypi.org/project/reflex-django/
