# Deployment

Run **reflex-django** in production with your own Django settings and a single ASGI process.

> Generic process manager guidance below is **not** shipped by reflex-django—adapt to your platform.

---

## Prerequisites

- [Configuration](configuration.md)  
- [CLI](cli.md)

---

## Production checklist

| Item | Action |
|------|--------|
| Settings module | Your `settings.py`, not bundled `default_settings` |
| `REFLEX_DJANGO_AUTO_SETTINGS` | Must be `False` / unset in your module |
| `SECRET_KEY` | Stable env var; never regenerate per deploy |
| `DEBUG` | `False` |
| `ALLOWED_HOSTS` | Explicit hosts |
| Database | Production `DATABASES` or `REFLEX_DJANGO_DATABASE_URL` |
| Static files | `reflex django collectstatic` → `STATIC_ROOT` |
| Migrations | `reflex django migrate` in CI/CD |

---

## Run command

```bash
reflex run --env prod
```

Single process: prefix dispatcher + Reflex UI + Django HTTP on configured paths. ASGI **lifespan** is owned by Reflex.

---

## Static files

```bash
uv run reflex django collectstatic --noinput
```

Default `STATIC_ROOT` when using bundled settings: `.reflex-django/staticfiles` (override with `REFLEX_DJANGO_STATIC_ROOT`).

`STATIC_URL` path is forwarded to Django when staticfiles is enabled and URL is not a CDN (`://`).

---

## Session cookies and auth

`session_js.py` may set session keys via `document.cookie` for Reflex login flows. Comments in source note non-HttpOnly cookies—**for hardened production**, prefer Django HTTP views that return `Set-Cookie`, or terminate TLS at the edge and use secure cookie flags in Django settings.

See [Authentication](authentication.md).

---

## Environment variables

Set before start:

- `DJANGO_SETTINGS_MODULE`  
- `REFLEX_DJANGO_SECRET_KEY` (or Django `SECRET_KEY` in settings)  
- `REFLEX_DJANGO_ALLOWED_HOSTS`  
- Database URL if used  

Plugin prefixes via `rxconfig` still export `REFLEX_DJANGO_API_PREFIX` / `REFLEX_DJANGO_ADMIN_PREFIX` at compile time.

---

## Reverse proxy (generic)

Typical stack:

```text
Internet → nginx / Caddy → uvicorn/hypercorn → reflex ASGI app
```

Configure proxy headers and `ALLOWED_HOSTS`. reflex-django does not ship nginx configs.

---

## Advanced usage

- Set `DJANGO_SETTINGS_MODULE` in systemd/Docker **before** `reflex run` so it matches CLI migrations.  
- Separate Reflex and Django processes is **not** the default model—would require custom integration.

---

## Common mistakes

- Deploying with auto-generated `SECRET_KEY` from bundled settings.  
- Forgetting `collectstatic` (broken admin CSS).

---

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Admin unstyled | `collectstatic`, `STATIC_URL`, staticfiles in `INSTALLED_APPS` |
| 400 Bad Request | `ALLOWED_HOSTS` |

---

## See also

- [Routing](routing.md)  
- [Best practices](best_practices.md)

---

**Navigation:** [← CLI](cli.md) | [Next: Testing →](testing.md)
