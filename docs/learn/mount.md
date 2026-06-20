# Mount

Mount tells Django which URL paths it owns and adds a catch-all so the Reflex SPA loads for everything else.

## Default

With `profile: "integrated"`, mount is on. reflex-django auto-detects prefixes like `/admin` and `/api` from your `urlpatterns` and appends a SPA catch-all.

## Explicit prefixes

Override when auto-detection misses a path:

```python
ReflexDjangoPlugin(config={
    "settings_module": "config.settings",
    "mount": {
        "django_prefix": ("/admin", "/api"),
        "mount_prefix": "/",
    },
})
```

## urls.py

List Django routes first. Do not add `path()` entries for SPA pages. Register those with `app.add_page` in `{app_name}/{app_name}.py` (or optional `@page` in `{app_name}/views.py`).

```python
--8<-- "snippets/minimal_urls.py"
```

## Turn mount off

```python
"mount": {"enabled": False}
```

No auto catch-all. Wire URLs yourself in `urls.py`. Rare for normal apps.

**Next:** [Proxy](proxy.md)
