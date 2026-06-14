# Deployment

**What you will learn:** How to build, configure, and serve a reflex-django app in production with Django ASGI, a Reflex backend, and a reverse proxy.

**When you need this:**

- You are shipping your first production deploy.
- You need Nginx, Docker, or platform-specific WebSocket settings.

You deploy reflex-django like any Django ASGI app, with one extra build step for the SPA bundle.

---

## Production checklist

1. **Build the SPA in CI** with `export_reflex --frontend-only --no-zip --stage-to-static-root`, then `collectstatic`.
2. **Use real settings** with `DEBUG = False`, a real `SECRET_KEY`, `ALLOWED_HOSTS`, and `STATIC_ROOT`. Never ship `reflex_django.setup.default_settings`.
3. **Run Django ASGI** with plain `get_asgi_application()` (see `config/asgi.py` snippet).
4. **Run Reflex backend** (or serve static export only) and **reverse-proxy** `/_event`, `/_upload`, etc. to it.
5. **Edge proxy** serves `/static/` from disk and forwards HTTP to Django.

```bash
export DJANGO_SETTINGS_MODULE=config.production
uv sync --frozen
uv run python manage.py migrate --noinput
uv run python manage.py export_reflex --frontend-only --no-zip --stage-to-static-root
uv run python manage.py collectstatic --noinput
uv run uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --workers 4
```

!!! warning "Never use default_settings in production"
    Bundled defaults have an insecure `SECRET_KEY` and `DEBUG = True`. Always point `DJANGO_SETTINGS_MODULE` at your own module.

---

## What you ship

```text
your-project/
├── manage.py
├── config/
│   ├── settings.py
│   ├── urls.py
│   └── asgi.py
├── shop/views.py
└── staticfiles/
    └── _reflex/          ← SPA from export_reflex + collectstatic
```

ASGI runs `config.asgi:application` (plain Django). The proxy serves `/static/` from `STATIC_ROOT`. Forward `/_event` and related paths to your Reflex backend.

### Optional split-process dev

Set `RXDJANGO_PROXY_SERVER` when Django runs on `runserver` and Reflex runs via `run_reflex`. This is a **dev-only** layout; production still uses Django ASGI plus a separate Reflex backend behind your edge proxy. See [Routing](routing.md).

---

## Build pipeline

| Step | Effect |
|:---|:---|
| `uv sync --frozen` | Install Python deps. |
| `migrate` | Apply Django migrations. |
| `export_reflex` | Build SPA into `STATIC_ROOT/_reflex/`. |
| `collectstatic` | Gather admin static + SPA assets. |

### Auto-build on first boot

Pre-build in CI. Do not rely on runtime auto-export in production:

```bash
REFLEX_DJANGO_AUTO_EXPORT_ON_START=0
```

---

## ASGI entry point

--8<-- "snippets/minimal_asgi.py"

### uvicorn

```bash
uv run uvicorn config.asgi:application \
    --host 0.0.0.0 --port 8000 --workers 4
```

Run your Reflex backend separately (or serve static export only) and configure the edge proxy to forward `/_event`, `/_upload`, etc.

### gunicorn + uvicorn worker

```bash
uv run gunicorn config.asgi:application \
    --workers 4 --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000
```

---

## Required production settings

```python
# config/production.py
from .settings import *

DEBUG = False
ALLOWED_HOSTS = ["yourdomain.com"]
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
CSRF_TRUSTED_ORIGINS = ["https://yourdomain.com"]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
STATIC_ROOT = BASE_DIR / "staticfiles"
```

With `DEBUG = False`, the dev proxy is off and the SPA serves from disk. You can also set `REFLEX_DJANGO_DEV_PROXY=0` explicitly. See [Settings reference](settings_reference.md).

---

## Dockerfile sketch

```dockerfile
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.production
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY . .
RUN uv run python manage.py export_reflex \
        --frontend-only --no-zip --stage-to-static-root \
    && uv run python manage.py collectstatic --noinput
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "config.asgi:application",
     "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

Run `migrate` as a deploy hook, not inside every container boot.

---

## Nginx essentials

Three things matter:

- **`/_event` needs WebSocket upgrade headers.**
- **`/static/` and `/media/`** served by Nginx when possible.
- **`X-Forwarded-Proto`** so Django detects HTTPS.

```nginx
location /_event {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 600s;
}
```

Full example blocks and Caddy config are in the repo docs history; see also [Media files](media_files.md) for `/media/`.

---

## Health checks

Use `/_health` (or `/ping`). Returns `{"status": "ok"}` without touching the database.

---

## Scaling notes

- **Workers:** start with 2 to 4; async handlers benefit from concurrency inside a worker.
- **Sticky sessions:** default Reflex state is in-memory per process.
- **Redis:** required for multi-worker Reflex via `REFLEX_DJANGO_RX_CONFIG["redis_url"]`.
- **WebSocket idle timeout:** set proxy timeout to at least 300 seconds.
- **Event bridge:** opt into `"smart"` mode and `"lean"` preset for large apps — see [Scaling and performance](scaling.md).

| Symptom | Likely fix |
|:---|:---|
| WebSocket drops after 60s | Raise proxy idle timeout |
| CSRF on admin behind HTTPS | Set `SECURE_PROXY_SSL_HEADER` |
| Slow first request | Pre-build SPA in CI; disable auto-export on start |
| High event volume | `REFLEX_DJANGO_EVENT_BRIDGE_MODE = "smart"` + per-State `_reflex_django_bridge` |

More: [Troubleshooting](troubleshooting.md), [Scaling and performance](scaling.md).

---

## What just happened?

You have a production path: export SPA in CI, run Django ASGI, run Reflex backend (or static export), put a proxy in front with WebSocket support on `/_event`.

## Next up

[Best practices →](best_practices.md)