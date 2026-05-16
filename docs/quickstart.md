# Quickstart

Build a **new** Reflex + Django project from scratch in about 15 minutes.

> Brownfield? See [Existing Django project](existing_django_project.md) instead.

---

## Prerequisites

- [Installation](installation.md)  
- [Configuration](configuration.md) (skim plugin options)

---

## 1. Initialize Python project

```bash
uv init
uv add reflex reflex-django
```

---

## 2. Scaffold Reflex frontend

```bash
uv run reflex init frontend
```

Follow the Reflex CLI prompts for app name and layout.

---

## 3. Create Django project

```bash
uv run django-admin startproject backend .
```

You should have `manage.py`, `backend/settings.py`, and `backend/urls.py`.

---

## 4. Configure `rxconfig.py`

```python
import reflex as rx
from reflex_django import ReflexDjangoPlugin

config = rx.Config(
    app_name="myapp",  # match your Reflex app module name
    plugins=[
        ReflexDjangoPlugin(settings_module="backend.settings"),
    ],
)
```

Add `"reflex_django"` to `INSTALLED_APPS` in `backend/settings.py` if you plan to use bundled helpers.

---

## 5. Migrate and run

```bash
uv run reflex django migrate
uv run reflex run
```

Open the Reflex dev URL (typically port 3000) for the UI. Django admin is at `/admin` when enabled.

---

## 6. First page with Django context

In your Reflex app module:

```python
import reflex as rx
from reflex_django import current_user

class IndexState(rx.State):
    @rx.event
    async def on_load(self):
        user = current_user()
        self.greeting = (
            f"Hello, {user.get_username()}" if user.is_authenticated else "Hello, guest"
        )

    greeting: str = "Loading..."

def index() -> rx.Component:
    return rx.heading(IndexState.greeting)

# app.add_page(index, route="/", on_load=IndexState.on_load)
```

> **Warning:** `current_user()` is populated only when `install_event_bridge=True` (default). See [Django middleware to Reflex](django_middleware_to_reflex.md).

---

## 7. Verify Django admin

1. `uv run reflex django createsuperuser`  
2. Visit `http://localhost:<reflex-port>/admin` (same origin as Reflex dev server; Vite proxies admin in dev—see [Architecture](architecture.md)).

---

## Common mistakes

- Running `django-admin startproject` **twice** in the same directory.  
- `settings_module` not matching your package (`backend.settings`).  
- Expecting Django middleware on Reflex events without the event bridge.

---

## Performance tips

- Use `async def` event handlers when calling Django async ORM APIs.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Admin 404 | Align `admin_prefix` and `ROOT_URLCONF`; see [Routing](routing.md) |
| Anonymous `current_user()` | Event bridge disabled or no session cookie |

---

## See also

- [Project structure](project_structure.md)  
- [Architecture](architecture.md)  
- [Existing Django project](existing_django_project.md)

---

**Navigation:** [← Configuration](configuration.md) | [Next: Existing Django project →](existing_django_project.md) | [Project structure →](project_structure.md)
