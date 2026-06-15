# v4: Plugin-only integration (breaking)

Pre-v4 migration notes live in the repo archive (`docs/_archive/migration/`).

reflex-django **4.0.0** removes django-first integration, settings-driven `RX_CONFIG`, and `manage.py run_reflex` / `export_reflex`. The only supported path is **`ReflexDjangoPlugin` in `rxconfig.py`** plus normal Django settings.

## Quick migration checklist

1. Add on-disk **`rxconfig.py`** with `ReflexDjangoPlugin` and top-level `rx.Config(...)`.
2. Create **`{app_name}/{app_name}.py`** with `app = rx.App()` (or `create_app()`).
3. Remove **`RX_CONFIG`**, **`RX_PLUGINS`**, and materialization settings from `settings.py`.
4. Configure the plugin with four keys only:

```python
ReflexDjangoPlugin(config={
    "settings_module": "demo.settings",
    "django_prefix": ("/admin", "/api"),
    "mount_prefix": "/",
    "auto_mount": True,
})
```

5. Move ports, `frontend_packages`, and Reflex plugins into **`rx.Config(...)`**, not settings.
6. Dev: **`reflex run`** (not `python manage.py run_reflex`).
7. Build: **`reflex export`** (not `manage.py export_reflex`).
8. Remove **`from reflex_django import app`** - use your app module instead.

## Removed APIs

| Removed | Replacement |
|---------|-------------|
| `IntegrationMode`, django-first bootstrap | `ReflexDjangoPlugin` in `rxconfig.py` |
| `RX_CONFIG`, `RX_PLUGINS` in settings | `rx.Config(...)` in `rxconfig.py` |
| `from reflex_django import app` | `{app}/{app}.py` -> `app` |
| `get_or_create_app()`, app module stubs | `load_native_reflex_app()` / user-owned app module |
| `manage.py run_reflex` | `reflex run` |
| `manage.py export_reflex` | `reflex export` |
| Plugin `urlconf` / `rx_config` keys | `ROOT_URLCONF` + `django_prefix` |
| `reflex_mount(..., rx_config=, plugins=)` | URL overrides only (`mount_prefix`, `django_prefix`) |

## Django tasks

Use **`reflex django migrate`**, **`reflex django createsuperuser`**, etc. (forwards to `manage.py`), or run `manage.py` directly without loading Reflex integration.

## Production

Build with `reflex export`, collect static files, and serve with your Django ASGI app (`uvicorn demo.asgi:application`). The plugin attaches the Django dispatcher during compile/export.