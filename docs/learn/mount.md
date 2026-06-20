# Mount

Mount tells Django which URL paths it owns and adds a catch-all so the Reflex SPA loads for everything else.

Think of mount as the URL ownership layer. It does not run Django inside Reflex, and it does not add request context to events. It only decides how incoming HTTP paths are routed between Django-owned views and the Reflex SPA shell.

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

## Options

| Option | Default from profile | Purpose |
|:---|:---|:---|
| `mount.enabled` | `True` in `integrated` and `split_dev`, `False` in `reflex_only` | Add automatic SPA catch-all wiring |
| `mount.mount_prefix` | `/` | URL prefix where the Reflex SPA shell is mounted |
| `mount.django_prefix` | auto-detected | Prefixes that Django owns and that should not fall through to the SPA |

Legacy flat plugin keys (`auto_mount`, `mount_prefix`, `django_prefix`) are still accepted for upgrades, but new projects should use the nested `mount` block.

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

Use explicit prefixes when:

- You have API routes outside the default detected paths.
- Your Django app owns a nonstandard prefix such as `/billing` or `/accounts`.
- A Django route is accidentally falling through to the Reflex SPA.

## urls.py

List Django routes first. Do not add `path()` entries for SPA pages. Register those with `app.add_page` in `{app_name}/{app_name}.py` (or optional `@page` in `{app_name}/views.py`).

```python
--8<-- "snippets/minimal_urls.py"
```

## Turn mount off

```python
"mount": {"enabled": False}
```

No automatic catch-all is added. You must wire URLs yourself in `urls.py`. This is rare for normal apps and mostly useful for custom hosting or framework experiments.

When mount is off, Django will not automatically serve deep links for Reflex pages. Make sure your external server or custom URLConf still returns the Reflex SPA shell for client-side routes.

## SPA shell rendering

By default, Django can post-process the exported Reflex `index.html` shell through Django's template engine:

```python
RX_RENDER_SPA_VIA_TEMPLATE_ENGINE = True
```

This does not turn Reflex components into Django templates. Reflex is still a compiled SPA. Mount only takes the final HTML shell response and, when it is `text/html`, renders that string with Django's active request context before sending it to the browser.

The flow is:

1. Django receives a route that is not owned by Django, such as `/dashboard`.
2. Mount resolves an exported deep-link HTML file or falls back to the Reflex `index.html` shell.
3. If the response is HTML and `RX_RENDER_SPA_VIA_TEMPLATE_ENGINE=True`, Django template syntax in that shell is evaluated with `RequestContext`.
4. The browser loads the normal Reflex app, JavaScript bundles, CSS, and event connection.

Use this when your exported shell intentionally contains Django template tags, for example `{{ csrf_token }}`, `{{ request.user }}`, messages, `LANGUAGE_CODE`, `{% load static %}`, `{% load i18n %}`, or values from custom context processors.

Do not use it when you want Reflex output served byte-for-byte, when reflex-django should act only as an integration plugin, or when raw `{{ ... }}` / `{% ... %}` strings may appear in the exported shell.

Set it to `False` to keep the Reflex shell untouched:

```python
RX_RENDER_SPA_VIA_TEMPLATE_ENGINE = False
```

You can also override it from the environment:

```bash
RX_RENDER_SPA_VIA_TEMPLATE_ENGINE=0
```

JavaScript, CSS, source maps, images, Reflex event handling, and Reflex component rendering are never processed by Django's template engine.

## Deep links and builds

The catch-all can resolve exported deep links such as `path.html` and `path/index.html` before falling back to the SPA shell. If no built SPA is available, reflex-django raises a bundle-not-found error; run `reflex run` in dev or `reflex export` in CI/deploy.

Use `RX_SERVE_FROM_BUILD=True` when you want to serve an existing build from disk instead of Vite in development.

## Related settings

| Setting | Purpose |
|:---|:---|
| `RX_AUTO_MOUNT` | Global auto-mount switch used by Django settings |
| `RX_MOUNT_PREFIX` | Settings-level SPA mount prefix |
| `RX_DJANGO_PREFIX` | Settings-level Django-owned prefixes |
| `RX_RESERVED_REFLEX_PREFIXES` | Extra protected Reflex prefixes that should not be treated as Django routes |
| `RX_PAGE_MODULE` | Optional decorated-page module suffix, default `views` |
| `RX_RENDER_SPA_VIA_TEMPLATE_ENGINE` | Optional template pass for HTML shell responses only |
| `RX_SERVE_FROM_BUILD` | Serve an existing exported bundle from disk |

Prefer plugin `mount` config for route ownership. Use settings for deployment and serving behavior.

**Next:** [Proxy](proxy.md)
