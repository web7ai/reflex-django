# Testing

**What you will learn:** How to test Django models and Reflex event handlers with pytest, including the event context helpers.

**When you need this:**

- You want unit tests for `AppState` handlers without opening a real WebSocket.
- You are setting up CI for a reflex-django project.

Testing a reflex-django project means two kinds of tests: normal Django tests, and Reflex state tests with a mocked request context.

---

## Test stack

Recommended tools:

- **`pytest`** for the runner.
- **`pytest-django`** for Django fixtures and DB setup.
- **`pytest-asyncio`** for async handlers.

```bash
uv add --group dev pytest pytest-django pytest-asyncio
```

---

## Minimal setup

```python
# conftest.py
import os
import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
```

`pytest.ini` or `pyproject.toml`:

```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
asyncio_mode = auto
python_files = test_*.py
```

`asyncio_mode = auto` lets you write `async def test_...` without extra decorators.

---

## Testing a Django model

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

---

## Testing an async event handler

Reflex handlers expect `self.request` and `self.user`. In tests, bind a synthetic context:

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
    me = await User.objects.acreate(username="me", password="x")
    other = await User.objects.acreate(username="other", password="x")

    await Product.objects.acreate(owner=me, name="Mine", sku="M-1", price=1)
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

`begin_event_request` accepts:

| Argument | Purpose |
|:---|:---|
| `user` | Authenticated user or `AnonymousUser`. |
| `path` | URL path for `self.request.path`. |
| `query` | Query params dict. |
| `cookies` | Cookie dict. |
| `headers` | Header dict. |
| `session` | Session keys dict. |

Pass only what your handler reads.

---

## Testing validation and ownership

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

Always test IDOR boundaries: one user must not edit another user's rows. See [Best practices](best_practices.md).

---

## Mocking users (no DB)

For pure logic tests:

```python
from unittest.mock import MagicMock

def make_user(**kwargs):
    u = MagicMock()
    u.is_authenticated = kwargs.get("authenticated", True)
    u.username = kwargs.get("username", "test")
    u.is_staff = kwargs.get("is_staff", False)
    u.pk = kwargs.get("pk", 1)
    return u
```

Use real users when tests touch ORM scoping.

!!! tip "Skip WebSockets in unit tests"
    Reserve full WebSocket integration tests for end-to-end suites. Handler tests with `begin_event_request` are faster and more stable.

---

## CI workflow

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
      - uses: astral-sh/setup-uv@v3
      - run: uv python install 3.12
      - run: uv sync --frozen
      - run: uv run python manage.py migrate --noinput
      - run: uv run python manage.py export_reflex --frontend-only --no-zip --stage-to-static-root
      - run: uv run pytest -v
```

---

## Pytest shortcuts

```bash
uv run pytest tests/test_inventory_state.py -v
uv run pytest tests/test_inventory_state.py::test_load_returns_only_my_products -v
uv run pytest -s
uv run pytest --reuse-db
```

---

## Troubleshooting tests

| Symptom | Fix |
|:---|:---|
| `AppRegistryNotReady` | Ensure `django.setup()` in `conftest.py`. |
| `SynchronousOnlyOperation` | Use async ORM (`acreate`, `aget`, …). |
| `self.request` is None | Wrap handler in `begin_event_request` / `end_event_request`. |

More fixes: [Troubleshooting](troubleshooting.md).

---

## What just happened?

You set up pytest for Django plus Reflex handlers, using context helpers to simulate `request.user` without a browser.

## Next up

[Deployment →](deployment.md)