# Configuration

Central reference for **`ReflexDjangoPlugin`** arguments and **`REFLEX_DJANGO_*`** Django settings. Values below exist in `src/reflex_django/plugin.py`, `default_settings.py`, and related modules.

---

## Prerequisites

- [Installation](installation.md)

---

## `ReflexDjangoPlugin`

```python
ReflexDjangoPlugin(
    settings_module="backend.settings",  # optional
    backend_prefix="/api",               # optional
    admin_prefix="/admin",               # default
    extra_prefixes=("/billing",),        # optional
    install_event_bridge=True,           # default
    install_auth_pages=False,            # default
)
```

| Argument | Role |
|----------|------|
| `settings_module` | Dotted path (e.g. `"backend.settings"`). Sets `DJANGO_SETTINGS_MODULE` via `os.environ.setdefault` and calls `configure_django()`. |
| `backend_prefix` | Prefix for **your** Django HTTP routes. Exported to `REFLEX_DJANGO_API_PREFIX` when non-empty. |
| `admin_prefix` | Django admin mount (default `"/admin"`). Sets `REFLEX_DJANGO_ADMIN_PREFIX`. |
| `extra_prefixes` | Additional prefixes forwarded to Django ASGI. |
| `install_event_bridge` | When `True` (default), registers `DjangoEventBridge` so `current_user()` works in events. |
| `install_auth_pages` | When `True`, calls `reflex_django.auth.autoload()`. Prefer explicit `add_auth_pages(app)` in your app module. |

**Static files:** If `django.contrib.staticfiles` is in `INSTALLED_APPS` and `STATIC_URL` is a path (not a `://` CDN URL), the plugin adds that prefix to the dispatcher.

---

## `configure_django()` resolution order

From `reflex_django.conf.configure_django`:

1. If `DJANGO_SETTINGS_MODULE` is **already set** in the environment, it wins (plugin `settings_module` is ignored).
2. Else use the `settings_module` argument from the plugin.
3. Else fall back to `reflex_django.default_settings`.

> **Tip:** In Docker or systemd, set `DJANGO_SETTINGS_MODULE` explicitly so deploy config matches local `rxconfig`.

---

## Environment variables (plugin)

| Variable | Set by |
|----------|--------|
| `REFLEX_DJANGO_API_PREFIX` | `backend_prefix` when non-empty |
| `REFLEX_DJANGO_ADMIN_PREFIX` | `admin_prefix` (default `/admin`) |

---

## Django settings (`REFLEX_DJANGO_*`)

From `reflex_django.default_settings` (override in your `settings.py`):

| Setting | Meaning |
|---------|---------|
| `REFLEX_DJANGO_AUTO_SETTINGS` | `True` in bundled defaults; plugin warns in production—use your own settings module. |
| `REFLEX_DJANGO_ADMIN_PREFIX` | Admin URL prefix; synced with plugin env. |
| `REFLEX_DJANGO_CONTEXT_PROCESSORS` | Tuple of callables `(request) -> dict` (or async). Used by `collect_reflex_context`. Must return **JSON-serializable** dicts. |
| `REFLEX_DJANGO_USE_TEMPLATE_CONTEXT_PROCESSORS` | When context processors tuple is empty and this is `True`, run `TEMPLATES` context processors with sanitization. |
| `REFLEX_DJANGO_LOGIN_URL` | Redirect for `@login_required` on events when anonymous. Legacy fallback for `REFLEX_DJANGO_AUTH["LOGIN_URL"]`. |
| `REFLEX_DJANGO_AUTH` | Dict for canned auth pages (see [Authentication](authentication.md)). |
| `REFLEX_DJANGO_USER_SNAPSHOT_INCLUDE_GROUPS` | Include group names in user snapshots when `True`. |
| `REFLEX_DJANGO_AUTH_AUTO_SYNC` | When `True` (default), refresh `AppState` auth snapshot vars on every Reflex event. |
| `REFLEX_DJANGO_I18N_EVENT_BRIDGE` | When `True` and `USE_I18N`, event bridge runs locale negotiation on synthetic request. |

**Env-backed defaults** (when using bundled settings):

| Env var | Django setting |
|---------|----------------|
| `REFLEX_DJANGO_DATABASE_URL` | `DATABASES` |
| `REFLEX_DJANGO_STATIC_URL` | `STATIC_URL` |
| `REFLEX_DJANGO_STATIC_ROOT` | `STATIC_ROOT` |
| `REFLEX_DJANGO_SECRET_KEY` | `SECRET_KEY` |
| `REFLEX_DJANGO_DEBUG` | `DEBUG` |
| `REFLEX_DJANGO_ALLOWED_HOSTS` | `ALLOWED_HOSTS` (comma-separated) |
| `REFLEX_DJANGO_URLCONF` | `ROOT_URLCONF` |

**Optional (not in bundled defaults as active constants):**

- `REFLEX_DJANGO_SITE_ORIGIN` — absolute origin for password-reset links when no request is bound.

Database URL also falls back from Reflex `config.db_url` to a local SQLite file when using defaults.

---

## Public API imports

Package root (`from reflex_django import …`) — see `__init__.__all__`:

`ReflexDjangoPlugin`, `configure_django`, `build_django_asgi`, `make_dispatcher`, `current_request`, `current_user`, `current_session`, `current_language`, `begin_event_request`, `end_event_request`, `DjangoEventBridge`, `AppState`, `ModelState`, `DjangoUserState`, `DjangoI18nState`, `DjangoContextState`, `collect_reflex_context`, `Model`, `ReflexDjangoModelSerializer`, `add_auth_pages`, `login_required`, `require_login_user`, `register_admin`, `session_cookie_set_js`, …

**Import paths:**

| Symbol | Import |
|--------|--------|
| `ModelCRUDView` | `from reflex_django.state import ModelCRUDView` |
| `ModelState` | Generic reactive ORM state (`ModelState[M]`); lazy on package root |
| `session_auth_mixin` | `from reflex_django.mixins import session_auth_mixin` |

---

## Advanced usage

- Multiple settings modules: set `DJANGO_SETTINGS_MODULE` in the environment before `reflex run`.
- Disable event bridge for stateless public pages: `install_event_bridge=False` (then `current_user()` is not populated by the bridge).

---

## Common mistakes

- **Prefix drift** — `ROOT_URLCONF` paths must match `backend_prefix` / `admin_prefix`.
- **Env overrides plugin** — `DJANGO_SETTINGS_MODULE` already set to a different module than `rxconfig` expects.

---

## Developer notes

- Lazy PEP 562 exports in `reflex_django.__init__` defer ORM-heavy imports until after `django.setup()`.

---

## See also

- [Routing](routing.md)  
- [CLI](cli.md)  
- [Deployment](deployment.md)

---

**Navigation:** [← Installation](installation.md) | [Next: Quickstart →](quickstart.md) | [Existing Django →](existing_django_project.md)
