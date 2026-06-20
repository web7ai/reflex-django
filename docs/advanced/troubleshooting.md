# Troubleshooting

Symptom-first fixes for local dev and first deploys.

## 502 from Vite on port 3000

Reflex backend on `:8000` is not ready, or split dev Django is not running.

```bash
reflex run
```

Wait for Vite on `:3000` and backend on `:8000`. For split dev, confirm `runserver` is up at `proxy.server`.

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

## Other quick fixes

| Symptom | Fix |
|:---|:---|
| `ModuleNotFoundError: shop.shop` | Create `shop/shop.py` with `app = rx.App()` |
| `AppRegistryNotReady` | Import models inside handlers |
| Anonymous user in handlers | Use `AppState`, check middleware order |
| SPA bundle not found | Run `reflex run` or `reflex export` |
| Still logged out after admin | Check `SessionMiddleware` and `AuthenticationMiddleware` |

## FAQ

**What dev command?** `reflex run`. Browse `:3000`.

**Where is config?** `ReflexDjangoPlugin` in `rxconfig.py`. See [Config reference](config.md).

**How do ports work?** Vite `:3000`, backend `:8000`. See [Proxy](../learn/proxy.md).
