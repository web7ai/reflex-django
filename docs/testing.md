# Testing Guide

Testing a unified application requires validating three distinct layers: your reactive Reflex state event handlers, your Django database models, and the request-level middleware that bridges the two. 

With standard tools like **`pytest`**, **`pytest-django`**, and **`pytest-asyncio`**, you can write robust, highly performant automated tests. This guide explains how to isolate async operations, mock user sessions, test permission pipelines, and set up continuous integration.

---

## 1. Preparing the Test Environment

To prevent Django from throwing `AppRegistryNotReady` exceptions, you must define your environment settings before any tests or models are imported. 

### Step 1: Create `conftest.py`
Place a `conftest.py` configuration in your project's testing directory (or project root). Assign `DJANGO_SETTINGS_MODULE` explicitly:

```python
# tests/conftest.py
import os
import pytest

# Enforce settings module resolution before importing any Django components
os.environ["DJANGO_SETTINGS_MODULE"] = "my_project.settings"

import django
django.setup()

@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """Automatically grant database access to all tests in the suite."""
    pass
```

### Step 2: Configure Pytest
In your `pyproject.toml` or `pytest.ini`, configure `pytest-asyncio` to run in automatic mode:

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
django_find_project = true
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
```

---

## 2. Unit Testing State Event Handlers

Since `ModelState` and `ModelCRUDView` are standard Reflex states, you can instantiate them in unit tests and invoke their event handlers directly. Because event handlers inside `reflex-django` utilize Django's async ORM, your unit tests must run within an asynchronous test runner.

```python
# tests/test_catalog.py
import pytest
from shop.models import Product
from shop.state import ProductState

@pytest.mark.django_db
async def test_create_product_success():
    # 1. Instantiate the State class
    state = ProductState()
    
    # 2. Simulate user typing inputs
    state.name = "Premium Keyboard"
    state.price = "120.00"
    state.sku = "ELEC-KEY-01"
    state.is_active = True
    
    # 3. Invoke the saving event handler asynchronously
    await state.save()
    
    # 4. Assert reactive state variables updated correctly
    assert state.error == ""
    assert state.editing_id == -1  # Reset to -1 on successful creation
    
    # 5. Verify the record was successfully written to the database
    from shop.models import Product
    db_product = await Product.objects.aget(sku="ELEC-KEY-01")
    assert db_product.name == "Premium Keyboard"
    assert db_product.price == 120.00
```

---

## 3. Mocking Request Contexts & Session Authentication

If your state handlers evaluate permissions, reference `self.request.user`, or restrict views based on active sessions, you must mock the request pipeline. `reflex-django` exposes internal hooks (**`begin_event_request`** and **`end_event_request`**) to mock context parameters:

```python
# tests/test_security.py
import pytest
from django.contrib.auth import get_user_model
from reflex_django.middleware import begin_event_request, end_event_request
from shop.state import ProductState

User = get_user_model()

@pytest.fixture
async def authenticated_user():
    """Create a standard authenticated test user."""
    return await User.objects.acreate(
        username="store_manager",
        email="manager@shop.com"
    )

@pytest.mark.django_db
async def test_restricted_action_requires_login(authenticated_user):
    state = ProductState()
    
    # 1. Mock request metadata (cookies, headers, route)
    mock_router_data = {
        "headers": {"cookie": "sessionid=test_session_id"},
        "pathname": "/inventory",
    }
    
    # 2. Bind request context simulating active user session
    begin_event_request(
        state=state,
        user=authenticated_user,
        router_data=mock_router_data
    )
    
    try:
        # 3. Execute state actions that require request context
        assert state.request.user.is_authenticated
        assert state.request.user.username == "store_manager"
        
        state.name = "Manager Item"
        state.sku = "MGR-001"
        await state.save()
        
        assert state.error == ""
        
    finally:
        # 4. Always tear down the request context to clean threadvars
        end_event_request(state)
```

---

## 4. Testing User-Scoped Constraints & Validation

If you use `UserScopedMixin` to scope records to their creators, verify that users are strictly blocked from loading or deleting records owned by other users.

```python
# tests/test_scoping.py
import pytest
from django.contrib.auth import get_user_model
from reflex_django.middleware import begin_event_request, end_event_request
from blog.models import BlogPost
from blog.states import PostsState

User = get_user_model()

@pytest.mark.django_db
async def test_user_cannot_load_foreign_post():
    # 1. Create two separate users and an article
    owner = await User.objects.acreate(username="owner")
    attacker = await User.objects.acreate(username="attacker")
    
    private_post = await BlogPost.objects.acreate(
        title="Owner Secrets",
        slug="secrets",
        author=owner
    )
    
    # 2. Instantiate and bind context simulating the attacker
    state = PostsState()
    begin_event_request(state=state, user=attacker)
    
    try:
        # 3. Attacker attempts to load the private post for editing
        await state.load(private_post.pk)
        
        # 4. Assert that the operation was blocked and form inputs remained empty
        assert state.title == ""
        assert "not found" in state.posts_error.lower()
        
    finally:
        end_event_request(state)
```

---

## 5. Continuous Integration (CI) Workflow

To run your tests automatically on every code push or pull request, add the following workflow file to your repository:

```yaml
# .github/workflows/test.yml
name: Testing Suite

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]

jobs:
  pytest:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4
        
      - name: Install uv Package Manager
        uses: astral-sh/setup-uv@v4
        with:
          enable-cache: true
          
      - name: Setup Python Environment
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          
      - name: Install Project Dependencies
        run: uv sync --all-extras --dev
        
      - name: Execute Tests via Pytest
        run: uv run pytest --maxfail=3 --tb=short
```

---

## 6. Troubleshooting Common Testing Issues

| Symptom | Cause | Solution |
|:---|:---|:---|
| `AppRegistryNotReady` | Django settings were imported after models or execution began. | Ensure `DJANGO_SETTINGS_MODULE` is set at the absolute beginning of your `conftest.py` file. |
| `SynchronousOnlyOperation` | A standard database query was executed within an async test runner. | Prefix database queries with `await` and use async variants (`acreate`, `aget`, `asave`, etc.). |
| State variables do not reset between tests. | The state instance persists across test cases. | Re-instantiate the state class (`state = MyState()`) inside every individual test function. |
| `self.request.user` is `AnonymousUser` | The event request context was not bound. | Use the `begin_event_request` helper within your test block to bind a simulated user context. |
| `fixture loop scope mismatch` | Pytest-asyncio is attempting to use a mismatched event loop scope. | Configure `asyncio_default_fixture_loop_scope = "function"` inside your `pyproject.toml` settings. |

---

**Navigation:** [← Command Line Interface](cli.md) | [Next: Deployment Guide →](deployment.md)
