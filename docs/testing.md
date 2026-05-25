# Testing

Testing a `reflex-django` project means writing two kinds of tests:

1. **Django tests** — same as you always have. Models, views, admin, business logic.
2. **Reflex state tests** — the new part. Test event handlers in isolation, with a mocked Django request.

This page covers the setup, the patterns, and a small CI workflow.

---

## Test stack

We recommend:

- **`pytest`** — the runner.
- **`pytest-django`** — Django integration, fixtures, DB setup.
- **`pytest-asyncio`** — for `async def` tests (most of yours will be async).

```bash
uv add --group dev pytest pytest-django pytest-asyncio
```

---

## Minimal `conftest.py`

```python
# conftest.py
import os
import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
```

And `pytest.ini` (or `pyproject.toml` `[tool.pytest.ini_options]`):

```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
asyncio_mode = auto
python_files = test_*.py
```

`asyncio_mode = auto` means you can write `async def test_...` without decorators. Standard pytest discovery does the rest.

---

## Testing a plain Django model

Same as any Django project:

```python
# tests/test_models.py
import pytest
from shop.models import Product


@pytest.mark.django_db
def test_product_str():
    p = Product.objects.create(name="Coffee", sku="C-1", price=3.50)
    assert str(p) == "Coffee (C-1)"
```

`@pytest.mark.django_db` gives the test access to the test database (rolled back after each test).

---

## Testing an async event handler

The interesting part. A Reflex event handler runs *inside* an event context — it expects `self.request`, `self.user`, etc., to be bound. In a test, you set up that context yourself.

```python
# tests/test_inventory_state.py
import pytest
from django.contrib.auth import get_user_model
from reflex_django.context import begin_event_request, end_event_request
from inventory.views import InventoryState
from inventory.models import Product


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_load_returns_only_my_products():
    User = get_user_model()
    me    = await User.objects.acreate(username="me", password="x")
    other = await User.objects.acreate(username="other", password="x")

    await Product.objects.acreate(owner=me,    name="Mine",  sku="M-1", price=1)
    await Product.objects.acreate(owner=other, name="Theirs", sku="T-1", price=2)

    state = InventoryState()
    token = begin_event_request(user=me, path="/inventory")
    try:
        await state.load()
    finally:
        end_event_request(token)

    assert len(state.products) == 1
    assert state.products[0]["name"] == "Mine"
```

The helpers `begin_event_request` / `end_event_request` set up the per-event `ContextVar` so `self.request.user` works. After the test, you tear down with `end_event_request(token)`.

`begin_event_request` accepts the things a real event would carry:

| Argument | What it does |
|:---|:---|
| `user` | Authenticated user (Django `User` instance or `AnonymousUser`). |
| `path` | URL path (`self.request.path`). |
| `query` | Dict of query params (`self.request.GET`). |
| `cookies` | Dict of cookies. |
| `headers` | Dict of HTTP headers. |
| `session` | Dict of session keys. |

You only need to pass what your handler reads.

---

## Testing validation

```python
@pytest.mark.django_db
@pytest.mark.asyncio
async def test_save_rejects_empty_name():
    user = await get_user_model().objects.acreate(username="u", password="x")
    state = InventoryState()
    state.name = ""
    state.sku = "X-1"
    state.price = "1.00"

    token = begin_event_request(user=user)
    try:
        await state.save()
    finally:
        end_event_request(token)

    assert state.error == "Name is required."
    assert await Product.objects.acount() == 0
```

---

## Testing IDOR / ownership

Make sure users can't edit each other's rows:

```python
@pytest.mark.django_db
@pytest.mark.asyncio
async def test_cant_edit_other_users_product():
    User = get_user_model()
    me    = await User.objects.acreate(username="me", password="x")
    other = await User.objects.acreate(username="other", password="x")
    theirs = await Product.objects.acreate(owner=other, name="Theirs", sku="T", price=1)

    state = InventoryState()
    state.editing_id = theirs.id
    state.name = "Hacked"
    state.sku = "T"
    state.price = "999"

    token = begin_event_request(user=me)
    try:
        await state.save()
    finally:
        end_event_request(token)

    await theirs.arefresh_from_db()
    assert theirs.name == "Theirs"           # not "Hacked"
    assert state.error                       # the handler set an error
```

---

## Testing with the live event bridge

If you want to test through the actual bridge (not just the context vars), use Django's async client:

```python
from django.test import AsyncClient

@pytest.mark.django_db
@pytest.mark.asyncio
async def test_admin_login_session_is_visible_to_reflex():
    client = AsyncClient()
    await client.alogin(username="me", password="x")    # set session cookie

    # ... (open the WebSocket, send an event, check the response)
    # In practice, most projects mock the bridge with ContextVars
    # instead of opening a real WebSocket for unit tests.
```

For *integration* tests that exercise the full WebSocket, you can run the dev server in a subprocess and connect with a real Socket.IO client. That's slow and brittle for unit tests; reserve it for end-to-end suites.

---

## Mocking the user model

If your handler only reads a few user fields, you can mock instead of hitting the DB:

```python
from unittest.mock import MagicMock

def make_user(**kwargs):
    u = MagicMock()
    u.is_authenticated = kwargs.get("authenticated", True)
    u.username = kwargs.get("username", "test")
    u.is_staff = kwargs.get("is_staff", False)
    u.pk = kwargs.get("pk", 1)
    return u


@pytest.mark.asyncio
async def test_handler_without_db():
    state = InventoryState()
    token = begin_event_request(user=make_user(username="alice"))
    try:
        await state.greet()
    finally:
        end_event_request(token)

    assert state.greeting == "Hi, alice!"
```

This avoids the test database — useful for fast unit tests on pure logic. Use the real user for tests that touch ORM scoping.

---

## A GitHub Actions workflow

A minimal CI that runs migrations, tests, and an SPA build:

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3

      - name: Set up Python
        run: uv python install 3.12

      - name: Install deps
        run: uv sync --frozen

      - name: Run migrations
        run: uv run python manage.py migrate --noinput

      - name: Build SPA bundle
        run: uv run python manage.py export_reflex --frontend-only --no-zip --stage-to-static-root

      - name: Run tests
        run: uv run pytest -v
```

---

## Pytest tips

### Run a single test file

```bash
uv run pytest tests/test_inventory_state.py -v
```

### Run a specific test

```bash
uv run pytest tests/test_inventory_state.py::test_load_returns_only_my_products -v
```

### Show print output

```bash
uv run pytest -s
```

### Reuse the test database between runs

```bash
uv run pytest --reuse-db
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|:---|:---|:---|
| `AppRegistryNotReady` in tests | `django.setup()` didn't run | Ensure `conftest.py` has `django.setup()` and `DJANGO_SETTINGS_MODULE` is set. |
| `SynchronousOnlyOperation` | Sync ORM call in an async test | Use `acreate`, `aget`, `asave` — or wrap with `await sync_to_async(...)`. |
| `RuntimeError: no current event loop` | Forgot the asyncio plugin or `@pytest.mark.asyncio` | Set `asyncio_mode = auto` in `pytest.ini`, or decorate the test. |
| `self.request` is None in tests | `begin_event_request` wasn't called | Wrap the handler call in `begin/end_event_request`. |
| Fixture loop scope mismatch | Async fixtures aren't matched to test scope | Use `asyncio_mode = auto`; or decorate fixtures with `@pytest_asyncio.fixture`. |

---

**Next:** [Deployment →](deployment.md)
