# Troubleshooting

Symptom-first fixes for local dev and first deploys.

## 502 from Vite on port 3000

Reflex backend on `:8000` is not ready, or split dev Django is not running.

```bash
reflex run
```

Wait for Vite on `:3000` and backend on `:8000`. For split dev, confirm `runserver` is up at `proxy.server`.

## HMR or dev proxy loops

If Vite hot reload connects to the wrong backend, confirm `frontend_port`, `backend_port`, and `proxy.server`. In split dev, Django should be running separately and `embed.enabled` should be off. If you intentionally serve a compiled build in dev, set `RX_DEV_PROXY=0` or `RX_SERVE_FROM_BUILD=True`.

## CSRF 403 from port 3000

Add both ports to trusted origins:

```python
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
```

See [Proxy](../learn/proxy.md).

## Blank page or missing routes

Confirm `app_name` in `rxconfig.py` matches `{app_name}/{app_name}.py` and you registered pages with `app.add_page` (or `@page` in `{app_name}/views.py` if that file exists). Restart `reflex run`. If still broken, delete `.web/` and run again. See [Pages and state](pages-and-state.md).

## Admin 404

Put Django routes first in `urlpatterns`. Set explicit prefixes if needed:

```python
ReflexDjangoPlugin(config={
    "mount": {"django_prefix": ("/admin", "/api")},
})
```

## WebSocket / events fail

Browse `:3000` in dev. In production, ensure your proxy forwards `Upgrade` headers on `/_event` with idle timeout >= 300s.

## Production insecure configuration warning

`reflex run --env prod` warns when fallback or unsafe Django settings are active. Set a real `DJANGO_SETTINGS_MODULE`, stable `SECRET_KEY`/`RX_SECRET_KEY`, `DEBUG=False`, strict `ALLOWED_HOSTS`, and HTTPS cookie settings. See [Security](security.md).

## Reflex version warning

reflex-django monkeypatches several Reflex internals. If startup warns that the installed Reflex version or a patch target is unsupported, use a Reflex version in the supported range (`>=0.9.4,<1.0`) and rerun tests. See the compatibility checks in `reflex_django.core.compat`.

## Scaffold errors

`reflex django scaffold app.Model` expects an installed Django model label. If `--fields` includes an unknown or read-only field, the command reports the valid editable fields. Use `--force` when overwriting an existing output file.

## Middleware failed during an event

The bridge catches some middleware-chain failures to avoid breaking the event loop. Enable `RX_BRIDGE_DEBUG=True` to log full tracebacks while debugging, then turn it off again.

## Other quick fixes

| Symptom | Fix |
|:---|:---|
| `ModuleNotFoundError: shop.shop` | Create `shop/shop.py` with `app = rx.App()` |
| `AppRegistryNotReady` | Import models inside handlers |
| Anonymous user in handlers | Use `AppState`, check middleware order |
| SPA bundle not found | Run `reflex run` or `reflex export` |
| Still logged out after admin | Check `SessionMiddleware` and `AuthenticationMiddleware` |
| Upload works in dev but not prod | Proxy `/_upload` to the Reflex backend |
| Event has no request context | Check bridge mode, `_rx_bridge`, and custom resolver |
| HMR connects to the wrong port | Check `frontend_port`, `backend_port`, and proxy config |

## FAQ

**What dev command?** `reflex run`. Browse `:3000`.

**Where is config?** `ReflexDjangoPlugin` in `rxconfig.py`. See [Config reference](config.md).

**How do ports work?** Vite `:3000`, backend `:8000`. See [Proxy](../learn/proxy.md).
