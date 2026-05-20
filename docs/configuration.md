# Configuration

This guide provides a comprehensive reference for all configuration options available in **reflex-django**. It covers arguments for the `ReflexDjangoPlugin` initialization and custom `REFLEX_DJANGO_*` Django settings.

---

## The `ReflexDjangoPlugin`

The plugin is registered inside your Reflex configuration file (`rxconfig.py`). It accepts several parameters that control how requests are dispatched and how backend resources are wired.

```python
# rxconfig.py
from reflex_django import ReflexDjangoPlugin

config = rx.Config(
    app_name="frontend",
    plugins=[
        ReflexDjangoPlugin(
            settings_module="backend.settings",
            backend_prefix="/api",
            admin_prefix="/admin",
            extra_prefixes=("/webhooks", "/docs"),
            install_event_bridge=True,
            install_auth_pages=False,
        )
    ]
)
```

### Parameter Reference

| Parameter | Type | Default | Description |
|:---|:---|:---|:---|
| **`settings_module`** | `str` | `None` | Dotted path to your Django settings file (e.g., `"backend.settings"`). Used to set the `DJANGO_SETTINGS_MODULE` environment variable and trigger Django's setup routine. |
| **`backend_prefix`** | `str` | `""` | The HTTP path prefix reserved for your custom Django routes (like APIs or standard views). When specified, sets the `REFLEX_DJANGO_API_PREFIX` env variable. |
| **`admin_prefix`** | `str` | `"/admin"` | The prefix under which the standard Django Admin panel is served. Sets the `REFLEX_DJANGO_ADMIN_PREFIX` env variable. |
| **`extra_prefixes`** | `tuple[str]` | `()` | A tuple of extra path prefixes that should be forwarded directly to the Django ASGI handler instead of Reflex (e.g., webhooks, OAuth callbacks, etc.). |
| **`install_event_bridge`** | `bool` | `True` | Automatically installs the `DjangoEventBridge` middleware. This middleware binds session and `request.user` details to active WebSocket event states. |
| **`install_auth_pages`** | `bool` | `False` | Automatically triggers `reflex_django.auth.autoload()`. Typically, you should leave this as `False` and explicitly call `add_auth_pages(app)` in your app file for better control. |

---

## Django Settings (`REFLEX_DJANGO_*`)

You can declare these variables directly inside your custom Django `settings.py` file to control the integration's behavior.

| Setting | Type | Default | Description |
|:---|:---|:---|:---|
| **`REFLEX_DJANGO_AUTO_SETTINGS`** | `bool` | `True` (default settings) | Set this to `False` in your production settings file to suppress automated configuration fallback warnings. |
| **`REFLEX_DJANGO_ADMIN_PREFIX`** | `str` | `"/admin"` | The mount point of the Django Admin panel. Synced with the plugin's environment variable. |
| **`REFLEX_DJANGO_CONTEXT_PROCESSORS`** | `tuple[str]` | `()` | A list of dotted paths to callables (`(request) -> dict`) that generate context data. Merged results are exposed on `self.request` for active events. Returns must be **JSON-serializable**. |
| **`REFLEX_DJANGO_USE_TEMPLATE_CONTEXT_PROCESSORS`** | `bool` | `True` | If `REFLEX_DJANGO_CONTEXT_PROCESSORS` is empty, this parses your template engine configuration (`TEMPLATES`) and executes their context processors (applying sanitization). |
| **`REFLEX_DJANGO_LOGIN_URL`** | `str` | `"/login"` | The default URL to redirect anonymous users to when they hit handlers wrapped with `@login_required`. |
| **`REFLEX_DJANGO_AUTH`** | `dict` | *See Authentication* | Configures standard credentials, custom messaging, and routes for pre-built authentication page views. |
| **`REFLEX_DJANGO_USER_SNAPSHOT_INCLUDE_GROUPS`** | `bool` | `False` | Includes group membership names in the JSON user snapshot (triggers a database query). |
| **`REFLEX_DJANGO_AUTH_AUTO_SYNC`** | `bool` | `True` | Automatically refreshes all active `AppState` snapshot variables on every WebSocket event. |
| **`REFLEX_DJANGO_I18N_EVENT_BRIDGE`** | `bool` | `True` | Runs language code negotiation based on standard request headers during active WebSocket event pipelines. |

---

## Configuration Resolution Order

When you start your server or run management commands, `reflex-django` boots Django using a structured resolution order:

```text
[1] Is the environment variable DJANGO_SETTINGS_MODULE already set?
    ├── YES --> Initialize Django using that path (Plugin settings_module parameter is IGNORED).
    └── NO  --> [2] Is the settings_module parameter defined in ReflexDjangoPlugin?
                ├── YES --> Set DJANGO_SETTINGS_MODULE to this value and boot.
                └── NO  --> [3] Fall back to the built-in development settings module.
```

> [!TIP]
> **Docker & Production Best Practice:** In production containers or systemd units, always set the environment variable `DJANGO_SETTINGS_MODULE` explicitly to avoid differences between your runtime environments.

---

## Async Streaming Middleware

If you are using Django to serve streaming responses (such as standard admin static files or media downloads), the ASGI server might emit warnings regarding synchronous operations. 

To solve this, `reflex-django` includes a custom middleware class: **`AsyncStreamingMiddleware`**.

### For Hand-Rolled Settings
If you do not import `reflex_django.default_settings.MIDDLEWARE` in your settings, add this class manually at the end of your middleware stack:

```python
# settings.py

MIDDLEWARE = [
    # ... Standard Django Middlewares
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    
    # Custom reflex-django streaming middleware
    "reflex_django.streaming_middleware.AsyncStreamingMiddleware",
]
```

---

## Public API Imports

You can import all major components directly from the package root:

```python
from reflex_django import (
    ReflexDjangoPlugin,
    configure_django,
    current_user,
    current_request,
    AppState,
    ModelState,
    Model,
    ReflexDjangoModelSerializer,
    add_auth_pages,
    login_required,
)
```

---

## Common Pitfalls

### Mount Mismatches
* **Problem:** You set `backend_prefix="/api"` in `rxconfig.py`, but your Django URL patterns define routes under `/v1/`.
* **Fix:** Ensure the prefix declared in your plugin matches the root paths mapped inside your main `urls.py` file:
  ```python
  # urls.py
  urlpatterns = [
      path("api/products/", products_view),  # /api matches backend_prefix
  ]
  ```

### Circular Imports on Startup
* **Problem:** Importing database models inside your page declaration files triggers `AppRegistryNotReady`.
* **Fix:** Move model imports inside your state's event handlers or helper functions so they are evaluated after the Django configuration has successfully executed.

---

**Navigation:** [← Installation](installation.md) | [Next: Quickstart →](quickstart.md)
