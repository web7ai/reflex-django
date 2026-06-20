# v4 Plugin-Only Migration

v4 makes `rxconfig.py` the integration source of truth. Django settings still hold normal Django configuration, auth branding, sessions, cache, and mirror toggles, but embed/mount/proxy/bridge behavior moves to `ReflexDjangoPlugin`.

## Before

Older projects often used settings-driven integration or management commands such as:

```python
RX_CONFIG = {"app_name": "shop"}
RX_PLUGINS = [...]
RX_PAGE_PACKAGES = [...]
```

```bash
python manage.py run_reflex
python manage.py export_reflex
```

## After

Use `rxconfig.py`:

```python
import reflex as rx
from reflex_django.plugins import ReflexDjangoPlugin

config = rx.Config(
    app_name="shop",
    plugins=[
        ReflexDjangoPlugin(config={
            "settings_module": "config.settings",
            "profile": "integrated",
        }),
    ],
)
```

Use native Reflex commands:

```bash
reflex django migrate
reflex run
reflex export
```

## Replacement map

| Removed pattern | Use |
|:---|:---|
| `manage.py run_reflex` | `reflex run` |
| `manage.py export_reflex` | `reflex export` |
| `from reflex_django import app` | Create `app = rx.App()` in `{app_name}/{app_name}.py` |
| `RX_PAGE_PACKAGES` | Register pages with `app.add_page(...)`, or use `@page` in `{app_name}/views.py` |
| settings-driven `RX_CONFIG` / `RX_PLUGINS` | `ReflexDjangoPlugin(config={...})` in `rxconfig.py` |
| `IntegrationMode` and integration installers | Plugin profiles and pillar blocks |
| `reflex_mount(..., rx_config=, plugins=)` | URL overrides only; use `rxconfig.py` for app config |
| SPA routes in Django `urlpatterns` | Django routes only; Reflex pages live in the Reflex app |

## Profiles

| Profile | Use when |
|:---|:---|
| `integrated` | One `reflex run`; Django is embedded in the Reflex backend during dev |
| `split_dev` | Django `runserver` plus `reflex run`; Vite proxies Django paths |
| `reflex_only` | Reflex UI only; no Django HTTP embedding |

You can override individual pillars after choosing a profile:

```python
ReflexDjangoPlugin(config={
    "settings_module": "config.settings",
    "profile": "integrated",
    "bridge": {"mode": "smart"},
    "mount": {"django_prefix": ("/admin", "/api")},
})
```

## Page migration

Create `{app_name}/{app_name}.py`:

```python
import reflex as rx
from shop.views import index

app = rx.App()
app.add_page(index, route="/")
```

Do not add Reflex SPA routes to Django `urlpatterns`. Keep Django routes such as admin and APIs in `urls.py`; the mount layer handles the SPA catch-all.

## Checklist

1. Add `ReflexDjangoPlugin` to `rxconfig.py`.
2. Move integration profile/pillar configuration out of Django settings.
3. Create `{app_name}/{app_name}.py` with `app = rx.App()`.
4. Register pages with `app.add_page(...)` or `@page` in `{app_name}/views.py`.
5. Replace `manage.py run_reflex` with `reflex run`.
6. Replace `manage.py export_reflex` with `reflex export`.
7. Keep `reflex_django` in `INSTALLED_APPS` and `AsyncStreamingMiddleware` last in `MIDDLEWARE`.
8. Run your app and check Django-owned paths (`/admin/`, `/api/`) plus Reflex pages from `http://localhost:3000/`.

**Next:** [Integration](../../learn/integration.md), [Config reference](../../advanced/config.md), and [Troubleshooting](../../advanced/troubleshooting.md).
