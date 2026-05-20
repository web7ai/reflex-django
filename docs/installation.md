# Installation

This guide will walk you through setting up **reflex-django** and its core dependencies. You can integrate it into a brand-new project or add it to an existing project virtual environment.

---

## System Requirements

Before getting started, make sure your local environment meets these version requirements (as defined in `pyproject.toml`):

| Component | Minimum Version | Supported Range |
|:---|:---|:---|
| **Python** | `3.12` | `>= 3.12, < 4.0` |
| **Django** | `6.0` | `>= 6.0, < 7.0` |
| **Reflex** | `0.9.2` | `>= 0.9.2, < 1.0` |

---

## 1. Install Dependencies

First, install `reflex` and `reflex-django` inside your project's active virtual environment. We highly recommend using **uv** for its incredible speed and modern dependency locking, though traditional **pip** is fully supported.

=== "Using uv (Recommended)"

    ```bash
    uv add reflex reflex-django
    ```

=== "Using pip"

    ```bash
    pip install reflex reflex-django
    ```

This single command installs the core libraries along with `asgiref` and the appropriate system-level dependencies.

---

## 2. Register with Django (`INSTALLED_APPS`)

To use the library's pre-built features (such as `ModelCRUDView`, automatic admin dashboard registration, built-in login pages, and states), you need to add `"reflex_django"` to your Django settings file.

Open your `settings.py` file (typically located under your Django project package folder) and include the following:

```python
# backend/settings.py or config/settings.py

INSTALLED_APPS = [
    # Core Django apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    
    # Add reflex-django here
    "reflex_django",
    
    # Your custom application apps
    "shop",
]
```

> [!NOTE]
> **Minimalist Mode:** If you only plan to use the `ReflexDjangoPlugin` inside `rxconfig.py` to route HTTP endpoints and manually import custom APIs, you *can* omit `"reflex_django"` from `INSTALLED_APPS`. However, advanced features (like automatic app registration or bundled auth pages) require it to be registered to initialize Django app configs properly.

---

## 3. Configure the Reflex Plugin (`rxconfig.py`)

Every Reflex project has an `rxconfig.py` configuration file at its root directory. This config is loaded by the Reflex CLI during compilation and running. 

To bridge the two frameworks, initialize the **`ReflexDjangoPlugin`** and pass it the dotted Python path to your Django settings module:

```python
# rxconfig.py
import reflex as rx
from reflex_django import ReflexDjangoPlugin

config = rx.Config(
    app_name="frontend",  # Must match your Reflex code directory name
    plugins=[
        ReflexDjangoPlugin(
            settings_module="backend.settings",  # Dotted path to settings.py
        ),
    ],
)
```

Replace `"backend.settings"` with the dotted path to your own Django settings module (e.g., `"config.settings"` or `"myproject.settings.development"`).

---

## 4. Verify the Installation

To verify that the integration is configured correctly and that the Django app registry is loaded, run the following CLI command:

```bash
uv run reflex django help
```

This command acts as a wrapper: it loads `rxconfig.py`, initializes the `ReflexDjangoPlugin`, calls `configure_django()`, and then forwards the remainder of the arguments to Django's standard management utility. You should see a list of all available Django management commands.

---

## Production Security Warning

> [!WARNING]
> By default, if the plugin does not find an active settings module, it will fall back to a built-in development settings file (`reflex_django.default_settings`). This is extremely useful for fast local prototyping, but it is **highly insecure** for production.
>
> In production, you must explicitly set `REFLEX_DJANGO_AUTO_SETTINGS = False` in your environment or settings file, and provide your own `settings.py` file with:
> * A secure, secret `SECRET_KEY`
> * `DEBUG = False`
> * A restricted `ALLOWED_HOSTS` whitelist
>
> See [Configuration](configuration.md) and [Deployment](deployment.md) for step-by-step checklists.

---

## Common Pitfalls & Troubleshooting

### Circular Imports and Registry Errors
* **Symptom:** `django.core.exceptions.AppRegistryNotReady: Apps aren't loaded yet.`
* **Cause:** This occurs if you attempt to import Django database models at the global module level of your Reflex files *before* the plugin has finished initializing Django.
* **Solution:** Always import Django database models *inside* your state methods, or ensure they are imported after the initial Reflex bootstrap is completed.

### Settings Precedence Conflict
* **Symptom:** The database or configuration changes you make in `settings.py` are ignored by the CLI.
* **Cause:** The environment variable `DJANGO_SETTINGS_MODULE` is already defined in your terminal or `.env` file, overriding your plugin's `settings_module` parameter.
* **Solution:** Check your active environment variables:
  ```bash
  # Windows (PowerShell)
  $env:DJANGO_SETTINGS_MODULE
  
  # macOS/Linux
  echo $DJANGO_SETTINGS_MODULE
  ```
  Ensure it is either unset or points to the exact same file as your `rxconfig.py` file.

---

**Navigation:** [← Introduction](introduction.md) | [Next: Configuration →](configuration.md)
