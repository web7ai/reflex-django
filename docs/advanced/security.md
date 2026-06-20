# Security

reflex-django keeps local setup easy, but production needs normal Django hardening plus a few Reflex event-bridge decisions.

## Production warning

When `reflex run --env prod` starts, reflex-django audits the active Django settings and warns once per process if it sees unsafe production defaults:

| Check | Why it matters | Fix |
|:---|:---|:---|
| `RX_AUTO_SETTINGS=True` | You are using the bundled fallback settings module | Set `DJANGO_SETTINGS_MODULE=config.production` |
| Random `SECRET_KEY` | Sessions and signatures break across restarts/workers | Set `SECRET_KEY` in your settings or `RX_SECRET_KEY` |
| `DEBUG=True` | Django debug output can leak data | Set `DEBUG=False` or `RX_DEBUG=0` |
| `ALLOWED_HOSTS=["*"]` | Any host header is accepted | Restrict to your domains |
| `SESSION_COOKIE_HTTPONLY=False` | JavaScript can read `sessionid` | Review the cookie-sync trade-off below |
| insecure cookies | Cookies can travel over HTTP | Set `SESSION_COOKIE_SECURE=True` and `CSRF_COOKIE_SECURE=True` |

## Session cookie sync

Reflex events run over WebSocket. Browser WebSocket messages do not apply Django `Set-Cookie` headers the same way HTTP responses do, so built-in login/logout helpers mirror session changes with JavaScript when needed. The bundled default therefore sets:

```python
SESSION_COOKIE_HTTPONLY = False
SESSION_COOKIE_SAMESITE = "Lax"
```

This is convenient for Django-admin-compatible login state, but it means JavaScript can read the session cookie. In production:

```python
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"  # or "Strict" when your flow allows it
```

If your security policy requires `SESSION_COOKIE_HTTPONLY=True`, do not rely on JavaScript cookie sync. Use a dedicated HTTP login/logout/cookie-sync view or redirect through a normal Django view so the browser receives `Set-Cookie` over HTTP.

## Settings module

Use your own Django settings module in production:

```bash
export DJANGO_SETTINGS_MODULE=config.production
export RX_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(50))')"
reflex run --env prod
```

The bundled settings are for development and tests. They generate a per-process `SECRET_KEY`, allow every host, default to SQLite, and enable JavaScript-readable session cookies.

## Event bridge authorization

Authorize from live Django request data in event handlers:

```python
if not self.request.user.has_perm("shop.change_product"):
    return rx.redirect("/login")
```

Reactive snapshot vars such as `self.is_authenticated` and `self.username` are for UI display. They can lag behind the session and must not be the only authorization check in a handler.

## Event cache fast auth

`RX_EVENT_CACHE_FAST_AUTH=True` can skip session/auth middleware on `auth_only` bridge events by reusing a cached auth snapshot within `RX_EVENT_CACHE_TTL`. This reduces per-event work but introduces a small TTL-bound staleness window. Logout invalidates the event cache; keep the TTL short and use full bridge mode for sensitive mutations.

## `.pth` bootstrap

The package installs a `.pth` hook so `reflex django ...` can discover and route Django management commands through Reflex's CLI. Treat this as local developer tooling. In production images, prefer explicit `DJANGO_SETTINGS_MODULE`, explicit commands, and pinned dependencies so startup behavior is predictable.

## Checklist

1. Set `DJANGO_SETTINGS_MODULE` to a production settings module.
2. Set a stable `SECRET_KEY` or `RX_SECRET_KEY`.
3. Set `DEBUG=False`, strict `ALLOWED_HOSTS`, and HTTPS cookie settings.
4. Decide whether JavaScript session cookie sync is acceptable.
5. Use cache-backed sessions and shared Redis when you run multiple workers.
6. Keep authorization in handlers and page guards, not only in UI snapshots.

**Next:** [Deploy](deployment.md), [Auth](auth.md), and [Scaling](scaling.md).
