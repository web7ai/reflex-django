# v2 module path migration

!!! note "v3 ASGI update"
    v3 removed `reflex_django.asgi.entry`. Production uses plain `get_asgi_application()`. Dev uses `run_reflex` with `make_dispatcher`. See **[Migrating to mount-only](v3_mount_only.md)** before applying v2 ASGI snippets below.

**What you will learn:** How to update import paths after the v2 package restructure.

**When you need this:**

- You are upgrading from reflex-django 1.x to 2.0.
- CI or local imports fail with `ModuleNotFoundError` for old module paths.

In v2.0, loose root-level modules were moved into domain subpackages. There are no compatibility shims.

---

## High-impact changes (update first)

| Old path | New path |
|:---|:---|
| `from reflex_django.asgi_entry import application` | v2: `from reflex_django.asgi.entry import application` — **v3:** use `get_asgi_application()` (see [v3 migration](v3_mount_only.md)) |
| `ROOT_URLCONF = "reflex_django.urls"` | `ROOT_URLCONF = "reflex_django.django.urls"` |
| `"reflex_django.apps.ReflexDjangoConfig"` | `"reflex_django.django.apps.ReflexDjangoConfig"` |
| `"reflex_django.streaming_middleware.AsyncStreamingMiddleware"` | `"reflex_django.bridge.streaming.AsyncStreamingMiddleware"` |

### ASGI entry (v2 only — superseded by v3)

```python
# Before (v1)
from reflex_django.asgi_entry import application

# After (v2) — removed again in v3
from reflex_django.asgi.entry import application

# v3 production
from django.core.asgi import get_asgi_application
application = get_asgi_application()
```

### Django URLs and app config

```python
# settings.py (before v1)
ROOT_URLCONF = "reflex_django.urls"
INSTALLED_APPS = [..., "reflex_django.apps.ReflexDjangoConfig"]

# After (v2)
ROOT_URLCONF = "reflex_django.django.urls"
INSTALLED_APPS = [..., "reflex_django.django.apps.ReflexDjangoConfig"]
```

---

## Full path map

| Old path | New path |
|:---|:---|
| `reflex_django.asgi_entry` | v2: `reflex_django.asgi.entry` — **v3:** removed; use `get_asgi_application()` |
| `reflex_django.asgi` | `reflex_django.asgi.app` |
| `reflex_django.urls` | `reflex_django.django.urls` |
| `reflex_django.apps` | `reflex_django.django.apps` |
| `reflex_django.admin` | `reflex_django.django.admin` |
| `reflex_django.model` | `reflex_django.django.model` |
| `reflex_django.conf` | `reflex_django.setup.conf` |
| `reflex_django.default_settings` | `reflex_django.setup.default_settings` |
| `reflex_django.routing` | `reflex_django.setup.routing` |
| `reflex_django.context` | `reflex_django.bridge.context` |
| `reflex_django.request` | `reflex_django.bridge.request` |
| `reflex_django.middleware` | `reflex_django.bridge.django_event` |
| `reflex_django.event_handler` | `reflex_django.bridge.event_handler` |
| `reflex_django.streaming_middleware` | `reflex_django.bridge.streaming` |
| `reflex_django.integration` | `reflex_django.runtime.integration` |
| `reflex_django.app_factory` | `reflex_django.runtime.app_factory` |
| `reflex_django.reflex_app` | `reflex_django.runtime.reflex_app` |
| `reflex_django.django_led_app` | **removed**; use `reflex_django.runtime.reflex_app` |
| `reflex_django.auth_state` | `reflex_django.auth_state` (unchanged; also available as `reflex_django.states.auth`) |
| `reflex_django.i18n_state` | `reflex_django.states.i18n` |
| `reflex_django.mount_config` | `reflex_django.mount.config` |
| `reflex_django.auto_mount` | `reflex_django.mount.auto` |
| `reflex_django.dev_proxy` | `reflex_django.dev.proxy` |
| `reflex_django.django_dev_middleware` | `reflex_django.dev.django_middleware` |
| `reflex_django._frontend_runner` | `reflex_django.dev.runners.frontend` |

---

## Unchanged public paths

These imports work the same as in v1:

- `from reflex_django.states import AppState, DjangoUserState, ModelState`
- `from reflex_django.auth_state import DjangoUserState` (canonical module; `states.auth` is an alias)
- `from reflex_django.serializers import ReflexDjangoModelSerializer`
- `from reflex_django import app, create_app, current_user, request`
- `from reflex_django.pages.decorators import page`
- `from reflex_django.auth import add_auth_pages, login_required`

Top-level `reflex_django` lazy attributes are unchanged; only internal module paths moved.

!!! tip "Recompile after upgrading"
    If you see `KeyError: No registered handler found for event` with old module segments like `auth_state` in the handler name, restart the dev server after upgrading. If the error persists, delete `.web/` and run `manage.py run_reflex` to recompile the frontend.

---

## Package layout (v2)

```text
reflex_django/
  asgi/          # make_dispatcher, build_django_asgi
  runtime/       # app factory, integration, reflex_app
  mount/         # URL mounting, prefixes, SPA paths
  bridge/        # Django request bridge, event middleware
  dev/           # Dev proxy, Vite, runners
  setup/         # conf, routing, rxconfig bridge
  django/        # apps, urls, admin, model
  cli/           # console entry
  states/        # public State classes
  auth_state.py  # DjangoUserState (canonical for event handler keys)
  serializers/   # model serializers
  state/         # internal model-state framework
  auth/          # auth pages and decorators
```

---

## Next up

- [Configuration](../configuration.md): settings keys unchanged
- [Deployment](../deployment.md): update `asgi.py` import
