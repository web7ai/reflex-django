---
level: beginner
tags: [configuration, settings, plugin]
---

# Configuration

This page lists what you configure after [Project structure](project_structure.md). Reflex runtime options live in **`rxconfig.py`** with **`ReflexDjangoPlugin`**. Django-only options stay in **`settings.py`**.

For the full flat table of Django `RX_*` settings, see [Settings reference](../reference/settings.md).

---

## Two layers

| Layer | File | What it controls |
|:---|:---|:---|
| **Reflex + integration** | `rxconfig.py` | `app_name`, ports, Reflex plugins, `ReflexDjangoPlugin` mount config |
| **Django** | `settings.py` | `INSTALLED_APPS`, `MIDDLEWARE`, database, optional `RX_*` tuning |

There is no `RX_CONFIG` or `RX_PLUGINS` in settings (removed in v4).

---

## Minimal `rxconfig.py`

```python
--8<-- "snippets/minimal_rxconfig.py"
```

### `ReflexDjangoPlugin` config keys

| Key | Required | Default | Purpose |
|:---|:---|:---|:---|
| `settings_module` | No | from `manage.py` | `DJANGO_SETTINGS_MODULE` |
| `django_prefix` | No | auto from `urlpatterns` | ASGI dispatcher prefixes (`/admin`, `/api`, ...) |
| `mount_prefix` | No | `"/"` | SPA catch-all prefix |
| `auto_mount` | No | `True` | append `reflex_mount` catch-all |

Put Reflex plugins (Radix, Tailwind, and so on) in `rx.Config(plugins=[...])`, not in Django settings.

---

## Minimal Django settings

```python
--8<-- "snippets/minimal_settings.py"
```

```python
--8<-- "snippets/minimal_urls.py"
```

Import every page module in `urls.py` when using `@page` in `views.py`. At compile time, reflex-django imports `{app_name}.views` (or modules listed in `RX_PAGE_PACKAGES`).

`app_name` in `rx.Config` is Reflex's compile label. It should match your `{app_name}/{app_name}.py` module.

---

## App module

Create `{app_name}/{app_name}.py` next to `manage.py`:

```python
import reflex as rx

app = rx.App()
app.add_page(lambda: rx.text("Hello"), route="/")
```

Or register pages with `@page` in Django `views.py`. See [App entry and pages](../guides/app_entry_and_pages.md).

---

## ASGI entry point

```python
--8<-- "snippets/minimal_asgi.py"
```

Production serves through plain Django ASGI. Dev uses `reflex run`, which compiles the SPA and mounts Django inside the Reflex backend.

---

## Optional Django tuning (`RX_*`)

These stay in `settings.py` when you need them:

| Setting | Purpose |
|:---|:---|
| `RX_PAGE_PACKAGES` | Explicit page module paths for compile |
| `RX_PAGE_MODULE` | Suffix for default page module (default `views`) |
| `RX_PROXY_SERVER` | Proxy Django to a separate dev server |
| `RX_DJANGO_PREFIX` | Override auto-detected Django URL prefixes |
| `RX_AUTO_MOUNT` | Disable automatic SPA catch-all when `False` |
| `RX_AUTH`, event-bridge settings | Auth pages and middleware behavior |

See [Settings reference](../reference/settings.md) for the complete list.

---

## Dev and build commands

| Task | Command |
|:---|:---|
| Dev (Vite + backend) | `reflex run` |
| Production build | `reflex export` |
| Django migrate | `reflex django migrate` or `python manage.py migrate` |

Ports are set in `rx.Config(frontend_port=..., backend_port=...)`.

---

## Upgrading from v3?

See [v4: Plugin-only integration](../reference/migration/v4_plugin_only.md).

---

**Next up:** [Local development](local_development.md)
