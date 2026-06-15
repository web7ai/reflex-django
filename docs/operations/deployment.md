# Deployment

Build the SPA in CI, collect static files, and serve with Django ASGI or a split Reflex backend.

!!! warning "Never use default_settings in production"
    Always set `DJANGO_SETTINGS_MODULE` to your production settings module.

---

## Build pipeline (CI)

```bash
export DJANGO_SETTINGS_MODULE=config.production
uv sync --frozen
reflex django migrate --noinput
reflex export
reflex django collectstatic --noinput
```

Set `RX_AUTO_EXPORT_ON_START=0` in production so the app does not rebuild at boot.

---

## Path A: Django ASGI (recommended)

Serve HTTP through plain Django ASGI. The plugin mounts the compiled SPA and dispatches `/_event` during compile/export.

```bash
uvicorn config.asgi:application --host 0.0.0.0 --port 8000
```

Ensure `ReflexDjangoPlugin` is in `rxconfig.py` and the SPA was exported to `STATIC_ROOT/_reflex/`.

---

## Path B: Split Reflex backend

Run Django on one port and Reflex on another. Set `RX_PROXY_SERVER` in dev; in production use a reverse proxy that routes `/_event` to Reflex and Django paths to Django.

See [Routing](../internals/routing.md).

---

## Docker sketch

```dockerfile
RUN reflex export
RUN reflex django collectstatic --noinput
CMD ["uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Scaling

Multi-worker Reflex needs Redis. Set `redis_url` in `rx.Config` in `rxconfig.py`. See [Scaling](scaling.md).

---

**Next:** [Troubleshooting](troubleshooting.md)
