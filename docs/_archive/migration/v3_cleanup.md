> **Historical - pre-v4 only.** Current integration uses ReflexDjangoPlugin in xconfig.py. See [v4 migration](v4_plugin_only.md).

# Migrating to reflex-django 3.0

**Breaking change:** v3 removes legacy plugin/bootstrap APIs, tightens page discovery, and reorganizes internal modules. Most Django-first projects need only import and settings tweaks.

If you are also renaming `REFLEX_DJANGO_*` settings, read [RX settings rename](rx_settings_rename.md) first.

---

## Summary

| Area | Before (v2.x) | After (v3.0) |
|:---|:---|:---|
| Reflex bootstrap | `ReflexDjangoPlugin` in `rxconfig` / `RX_PLUGINS` | `install_reflex_django_integration()` via `run_reflex` / `configure_django` |
| `setup/plugin.py` | Present | **Removed** |
| Page auto-scan | `RX_AUTO_DISCOVER_PAGES=True` walked `INSTALLED_APPS` | **Removed** - import modules in `urls.py` or set `RX_PAGE_PACKAGES` |
| Login redirect setting | `RX_LOGIN_URL` | `RX_AUTH["LOGIN_URL"]` only |
| i18n on events | `RX_I18N_EVENT_BRIDGE` | **Removed** - locale follows middleware when `USE_I18N` |
| Page decorator alias | `reflex_page` | `@page` only (`reflex_template` remains for layouts) |
| `reflex_mount()` kwargs | `app_name=`, `django_plugin=` | **Removed** - use `RX_CONFIG["app_name"]` and settings |
| App factory | `ensure_django_led_app_ready()` | `ensure_reflex_app_ready()` |
| State pickle attrs | `_django_led_request_wrapper`, `_django_led_response` | `_rx_request_wrapper`, `_rx_response` |
| `make_dispatcher` import | `from reflex_django import make_dispatcher` | `from reflex_django.asgi.app import make_dispatcher` |
| Event bridge module | `bridge/django_event.py` (monolith) | `bridge/event/` package (re-export at `bridge.event`) |
| Integration hooks | `runtime/integration.py` (monolith) | `runtime/integration/` package |
| Model state assembly | `state/assembly.py` at package root | `state/assembly/` package |
| `run_reflex` command | Single module file | `management/commands/run_reflex/` package |

---

## 1. Remove `ReflexDjangoPlugin`

**Before:**

```python
# rxconfig.py (legacy)
from reflex_django import ReflexDjangoPlugin

config = rx.Config(
    app_name="shop",
    plugins=[ReflexDjangoPlugin(settings_module="config.settings")],
)
```

**After:**

```python
# config/settings.py
RX_CONFIG = {"app_name": "shop", "frontend_port": 3000, "backend_port": 8000}
INSTALLED_APPS = [..., "reflex_django", "shop"]
```

```bash
python manage.py run_reflex
```

Integration installs automatically from `configure_django()` and `install_reflex_django_integration()`. Do not add a Django plugin to `RX_PLUGINS`.

---

## 2. Import pages explicitly

**Before:**

```python
# settings.py
RX_AUTO_DISCOVER_PAGES = True  # scanned every INSTALLED_APPS app
```

**After:**

```python
# config/urls.py
import shop.views  # noqa: F401
import blog.views  # noqa: F401
```

For pages outside `{app_name}.views`, list modules explicitly:

```python
# settings.py
RX_PAGE_PACKAGES = ["frontend.pages.home", "frontend.pages.dashboard"]
```

At compile time, reflex-django imports `RX_PAGE_PACKAGES` when set; otherwise only `{RX_CONFIG["app_name"]}.views` (or `{app}.{RX_PAGE_MODULE}`).

---

## 3. Login redirect URL

**Before:**

```python
RX_LOGIN_URL = "/accounts/login/"
```

**After:**

```python
RX_AUTH = {
    "ENABLED": True,
    "LOGIN_URL": "/accounts/login/",
}
```

`@login_required` and `LoginRequiredMixin` read `RX_AUTH["LOGIN_URL"]` (default `"/login"`).

---

## 4. `reflex_mount()` arguments

**Before:**

```python
urlpatterns += reflex_mount(
    app_name="shop",
    django_plugin={"install_event_bridge": True},
)
```

**After:**

```python
# settings.py
RX_CONFIG = {"app_name": "shop"}

# urls.py - URL overrides only
urlpatterns += reflex_mount(
    mount_prefix="/",
    django_prefix=("/admin", "/api"),
)
```

`app_name` belongs in `RX_CONFIG`. Event bridge and Django bootstrap are always handled by settings-based integration.

---

## 5. Internal / advanced renames

Library and test code only:

```python
# Before
from reflex_django.runtime.app_factory import ensure_django_led_app_ready

# After
from reflex_django.runtime.app_factory import ensure_reflex_app_ready
```

```python
# Before
from reflex_django import make_dispatcher

# After
from reflex_django.asgi.app import make_dispatcher
```

State serialization strips `_rx_request_wrapper` and `_rx_response` (was `_django_led_*`).

---

## 6. Module layout (import map)

| v2 path | v3 path |
|:---|:---|
| `reflex_django.setup.plugin` | **Removed** - use `runtime.integration` |
| `reflex_django.runtime.integration` (file) | `reflex_django.runtime.integration` (package) |
| `reflex_django.bridge.django_event` | `reflex_django.bridge.event` (re-export shim remains) |
| `reflex_django.state.assembly` (file) | `reflex_django.state.assembly` (package) |
| `reflex_django.management.commands.run_reflex` (file) | `reflex_django.management.commands.run_reflex` (package) |

Public imports documented in [Public API](../api.md) are unchanged unless noted above.

---

## Verification checklist

1. Delete `ReflexDjangoPlugin` from `rxconfig.py` / `RX_PLUGINS`.
2. Add `import {app}.views` (or `RX_PAGE_PACKAGES`) for every page module.
3. Move `RX_LOGIN_URL` into `RX_AUTH["LOGIN_URL"]`.
4. Remove `app_name=` and `django_plugin=` from `reflex_mount()` calls.
5. Update any `ensure_django_led_app_ready` / top-level `make_dispatcher` imports.
6. Run `python manage.py run_reflex` and open `:3000`.
7. Confirm `/admin` and `/_event` work; run `uv run pytest reflex_django_tests -q`.

---

## Related guides

- [RX settings rename](rx_settings_rename.md) - `REFLEX_DJANGO_*` to `RX_*`
- [Configuration](../../getting-started/configuration.md) - current settings model
- [Public API](../api.md) - import paths after v3