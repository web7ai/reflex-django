# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `reflex_django.states.AppState`: abstract base for app domain/routing state
  (subclass instead of mixing auth into CRUD bases).

### Changed (breaking)

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
