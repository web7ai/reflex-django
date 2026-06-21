# Mount

Mount tells Django which URL paths it owns and adds a catch-all so the Reflex SPA loads for everything else.

Think of mount as the URL ownership layer. It does not run Django inside Reflex, and it does not add request context to events. It only decides how incoming HTTP paths are routed between Django-owned views and the Reflex SPA shell.

See [Profiles](profiles.md) for preset defaults. Mount is on in `integrated` and `split_dev`, off in `reflex_only`.

## Default

With `profile: "integrated"`, mount is on. reflex-django auto-detects prefixes like `/admin` and `/api` from your `urlpatterns` and appends a SPA catch-all.

Typical result:

| Path | Owner |
|:---|:---|
| `/admin/` | Django |
| `/api/` | Django |
| `/_event` | Reflex backend |
| `/_upload` | Reflex backend |
| `/dashboard` | Reflex SPA shell |
| `/products/123` | Reflex SPA shell |

Register Reflex pages on the Reflex app, not in Django `urls.py`:

```python
app.add_page(dashboard, route="/dashboard")
```

The Django URLConf should keep Django routes such as admin and API.

## Options reference

Allowed keys in the `mount` block:

| Option | Type | Default by profile | Purpose |
|:---|:---|:---|:---|
| `mount.enabled` | `bool` | `True` in `integrated` and `split_dev`; `False` in `reflex_only` | Add automatic SPA catch-all wiring |
| `mount.mount_prefix` | `str` | `/` at runtime when unset | URL prefix where the Reflex SPA shell is mounted |
| `mount.django_prefix` | `str` or tuple of `str` | auto-detected from `urlpatterns` when unset | Prefixes Django owns (not forwarded to the SPA catch-all) |

Legacy flat plugin keys still accepted: `auto_mount` (maps to `mount.enabled`), `mount_prefix`, `django_prefix`. Prefer the nested `mount` block in new projects.

Settings fallbacks when plugin values are omitted: `RX_AUTO_MOUNT`, `RX_MOUNT_PREFIX`, `RX_DJANGO_PREFIX`. Full list: [Config reference](../advanced/config.md).

## Examples

**Auto-detect prefixes (default integrated):**

```python
ReflexDjangoPlugin(config={
    "settings_module": "config.settings",
    "profile": "integrated",
})
```

**Explicit Django-owned prefixes:**

```python
--8<-- "snippets/pillar_mount_explicit.py"
```

Use explicit prefixes when auto-detection misses a path, for example `/billing` or `/accounts`, or when a Django route falls through to the SPA.

**Non-root SPA mount:**

```python
ReflexDjangoPlugin(config={
    "settings_module": "config.settings",
    "mount": {
        "mount_prefix": "/app/",
        "django_prefix": ("/admin", "/api"),
    },
})
```

**Disable automatic mount:**

```python
ReflexDjangoPlugin(config={
    "settings_module": "config.settings",
    "mount": {"enabled": False},
})
```

When mount is off, you must wire URLs yourself in `urls.py`. Django will not automatically serve deep links for Reflex pages unless your custom URLConf returns the SPA shell for client-side routes.

## urls.py

List Django routes first. Do not add `path()` entries for SPA pages. Register those with `app.add_page` in `{app_name}/{app_name}.py` (or optional `@page` in `{app_name}/views.py`).

```python
--8<-- "snippets/minimal_urls.py"
```

## SPA shell rendering

By default, Django can post-process the exported Reflex `index.html` shell through Django's template engine:

```python
RX_RENDER_SPA_VIA_TEMPLATE_ENGINE = True
```

This does not turn Reflex components into Django templates. Reflex is still a compiled SPA. Mount only takes the final HTML shell response and, when it is `text/html`, renders that string with Django's active request context before sending it to the browser.

Use this when your exported shell intentionally contains Django template tags. Set it to `False` when you want Reflex output served byte-for-byte:

```python
RX_RENDER_SPA_VIA_TEMPLATE_ENGINE = False
```

JavaScript, CSS, source maps, images, Reflex event handling, and Reflex component rendering are never processed by Django's template engine.

## Deep links and builds

The catch-all can resolve exported deep links such as `path.html` and `path/index.html` before falling back to the SPA shell. If no built SPA is available, reflex-django raises a bundle-not-found error; run `reflex run` in dev or `reflex export` in CI/deploy.

Use `RX_SERVE_FROM_BUILD=True` when you want to serve an existing build from disk instead of Vite in development. See [Config reference](../advanced/config.md) for mount-related settings.

**Next:** [Proxy](proxy.md)
