# Installation

Install **reflex-django** alongside **Reflex** and an existing or new **Django** project.

---

## Requirements

| Component | Version (from `pyproject.toml`) |
|-----------|----------------------------------|
| Python | `>=3.12,<4.0` |
| Django | `>=6.0,<7.0` |
| Reflex | `>=0.9.2,<1.0` |

---

## Install dependencies

With **uv** (recommended in the package README):

```bash
uv add reflex reflex-django
```

With **pip**:

```bash
pip install reflex reflex-django
```

---

## Django `INSTALLED_APPS`

Include the Django contrib apps you need (`auth`, `sessions`, `admin`, `staticfiles`, …).

Add **`reflex_django`** when you use bundled helpers (`ModelCRUDView`, `register_admin`, canned auth pages, etc.):

```python
INSTALLED_APPS = [
    # ...
    "reflex_django",
]
```

> **Note:** You can run the plugin without listing `reflex_django` in `INSTALLED_APPS` if you only use `ReflexDjangoPlugin` and import APIs from the `reflex_django` package—but helpers that expect the Django app config may not autoload.

---

## Minimal `rxconfig.py`

```python
import reflex as rx
from reflex_django import ReflexDjangoPlugin

config = rx.Config(
    app_name="myapp",
    plugins=[
        ReflexDjangoPlugin(settings_module="backend.settings"),
    ],
)
```

Replace `backend.settings` with your dotted settings path.

Full plugin and environment options: [Configuration](configuration.md).

---

## Production settings

Do **not** rely on bundled `reflex_django.default_settings` in production. The plugin warns when `REFLEX_DJANGO_AUTO_SETTINGS` is true.

Use your own `settings.py` with a stable `SECRET_KEY`, `DEBUG=False`, and explicit `ALLOWED_HOSTS`. See [Configuration](configuration.md) and [Deployment](deployment.md).

---

## Verify installation

```bash
uv run reflex django help
```

This loads `rxconfig`, runs `configure_django()`, and forwards to Django management commands. Details: [CLI](cli.md).

---

## Common mistakes

- **Wrong `settings_module`** — must match `DJANGO_SETTINGS_MODULE` / your `manage.py` default.
- **Skipping migrations** — run `reflex django migrate` before first `reflex run`.
- **Importing models before Django setup** — let the plugin bootstrap via `rxconfig`; avoid circular imports at module top level.

---

## Troubleshooting

| Symptom | Check |
|---------|--------|
| `django.core.exceptions.AppRegistryNotReady` | Plugin not in `rxconfig` or `configure_django()` not run |
| CLI uses wrong database | `rxconfig` not loaded; env `DJANGO_SETTINGS_MODULE` |

---

## See also

- [Configuration](configuration.md)  
- [Quickstart](quickstart.md) | [Existing Django project](existing_django_project.md)  
- [CLI](cli.md)

---

**Navigation:** [← Introduction](introduction.md) | [Next: Configuration →](configuration.md)
