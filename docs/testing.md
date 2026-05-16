# Testing

Test reflex-django apps with **pytest**, stub Reflex events, and the patterns in **`reflex_django_tests/`**.

---

## Prerequisites

- [Installation](installation.md)

---

## Test settings

Package tests use `reflex_django_tests/django_settings.py` (in-memory SQLite, contrib apps). In **your** project:

```python
# conftest.py
import os

os.environ["DJANGO_SETTINGS_MODULE"] = "myproject.test_settings"
```

Assign with `=` (not `setdefault`) before Django imports, matching `reflex_django_tests/conftest.py`.

---

## Run package tests

From the package root:

```bash
pytest
```

Configured in `pyproject.toml`: `testpaths = ["reflex_django_tests"]`, `asyncio_mode = auto`.

---

## Stub Reflex events (event bridge)

From `test_event_bridge.py`:

```python
class _StubEvent:
    def __init__(self, router_data: dict | None = None) -> None:
        self.router_data = router_data or {}

# router_data with cookies, headers, path → preprocess → current_user()
```

Use `contextvars.copy_context()` for async test isolation when binding requests.

---

## Test `ModelCRUDView`

See `test_model_state.py`:

- Assembly generates `on_load_*`, `save_*`  
- `UserScopedMixin` scoping  
- Override `save_*` in subclass  
- `use_form_submit`, `reset_after_save=False`

Use Django test DB and async ORM (`acreate`, etc.).

---

## Test dispatcher routing

`test_dispatcher.py` — path prefix vs Reflex reserved paths.

---

## Test auth

`test_auth_*.py`, `test_mixins_session_auth.py` — registry, decorators, login fields, password reset.

---

## Example CI (GitHub Actions)

*Example only—the package repo may not ship this workflow.*

```yaml
name: test
on: [push, pull_request]
jobs:
  pytest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --dev
      - run: uv run pytest
```

---

## Advanced usage

- Call `begin_event_request` / `end_event_request` around synchronous unit tests of helpers.  
- Mock `collect_reflex_context` when testing UI states without processors.

---

## Common mistakes

- `AppRegistryNotReady` — set `DJANGO_SETTINGS_MODULE` before importing models.  
- Tests pass `manage.py` settings but app uses `rxconfig` paths.

---

## Developer notes

- Test layout: `reflex_django_tests/` at package root.

---

## See also

- [Django middleware to Reflex](django_middleware_to_reflex.md)  
- [FAQ](faq.md)

---

**Navigation:** [← Deployment](deployment.md) | [Next: Best practices →](best_practices.md)
