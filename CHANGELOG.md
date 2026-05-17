# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Django ASGI no longer warns about synchronous ``StreamingHttpResponse``
  iterators (admin static, ``FileResponse``, etc.) when
  ``reflex_django.streaming_middleware.AsyncStreamingMiddleware`` is enabled
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
