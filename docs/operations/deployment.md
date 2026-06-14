# Deployment

**What you will learn:** How to build, configure, and serve a reflex-django app in production: either as a single Reflex backend process or as split Django ASGI + Reflex behind a proxy.

**When you need this:**

- You are shipping your first production deploy.
- You need Nginx, Docker, or platform-specific WebSocket settings.

Both paths share the same build step: export the SPA in CI, then run with production settings.

!!! warning "Never use default_settings in production"
    Bundled defaults have an insecure `SECRET_KEY` and `DEBUG = True`. Always point `DJANGO_SETTINGS_MODULE` at your own module.

---

## Which path?

| | **Path A: single-process** | **Path B: split** |
|:---|:---|:---|
| **Run command** | `manage.py run_reflex --env prod` | `uvicorn config.asgi:application` + separate Reflex backend |
| **Processes** | One (Reflex backend; Django mounted in-process) | Two or more (Django ASGI + Reflex + optional proxy) |
| **Ports** | One (default `:8000`) for SPA, admin, API, `/_event` | Django HTTP on one port; Reflex on another; proxy routes traffic |
| **Django workers** | Reflex backend process (not uvicorn Django workers) | uvicorn/gunicorn workers on plain Django ASGI |
| **Proxy complexity** | Optional (TLS/termination only) | Required to split `/_event` from Django HTTP |
| **Good for** | Simpler ops, single container, staging, prod-like local validation | Independent scaling, Django worker pools, large teams |

See [CLI reference](cli.md) for all `run_reflex` flags.

---

## Shared build pipeline

Both paths use the same CI build:

| Step | Effect |
|:---|:---|
| `uv sync --frozen` | Install Python deps. |
| `migrate` | Apply Django migrations. |
| `export_reflex` | Build SPA into `STATIC_ROOT/_reflex/`. |
| `collectstatic` | Gather admin static + SPA assets. |

```bash
export DJANGO_SETTINGS_MODULE=config.production
uv sync --frozen
uv run python manage.py migrate --noinput
uv run python manage.py export_reflex --frontend-only --no-zip --stage-to-static-root
uv run python manage.py collectstatic --noinput
```

Pre-build in CI. Do not rely on runtime auto-export in production:

```bash
RX_AUTO_EXPORT_ON_START=0
```

---

## Path A: single-process (`run_reflex --env prod`)

Run the Reflex backend on **one port** with Django admin/API mounted in-process (same routing model as dev, without Vite). SPA, `/_event`, admin, and API all hit the same process.

### When to use

- Simpler deployments (single container, staging, small production)
- Prod-like local validation before ship
- You want the same in-process Django dispatch as `run_reflex` dev, without maintaining a split proxy layout

### Run

After the shared build pipeline:

```bash
export DJANGO_SETTINGS_MODULE=config.production
uv run python manage.py run_reflex --env prod --no-reload --skip-rebuild
```

Browse **`http://localhost:8000/`** (or your configured `backend_port`) for everything: SPA, admin, API, and WebSocket events.

| Flag | Why in production |
|:---|:---|
| `--env prod` | Serves compiled bundle from disk; sets `REFLEX_ENV=prod`; single port |
| `--no-reload` | Disables file watching |
| `--skip-rebuild` | Uses SPA built in CI; no export at container boot |

`run_reflex --env prod` also sets `RX_DEBUG=0`. If your settings derive `DEBUG` from that env var, ensure production settings still set `DEBUG = False` explicitly.

### Dockerfile sketch (single-process)

```dockerfile
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.production \
    RX_AUTO_EXPORT_ON_START=0
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY . .
RUN uv run python manage.py export_reflex \
        --frontend-only --no-zip --stage-to-static-root \
    && uv run python manage.py collectstatic --noinput
EXPOSE 8000
CMD ["uv", "run", "python", "manage.py", "run_reflex",
     "--env", "prod", "--no-reload", "--skip-rebuild",
     "--backend-host", "0.0.0.0", "--backend-port", "8000"]
```

Run `migrate` as a deploy hook, not inside every container boot.

### Scaling Path A

- Default Reflex state is in-memory per process.
- Multi-replica deployments need **Redis** (`RX_CONFIG["redis_url"]`) and **sticky sessions** at the load balancer.
- See [Scaling and performance](scaling.md).

---

## Path B: split (Django ASGI + Reflex + proxy)

Run plain Django ASGI for HTTP (admin, API, static, SPA shell) and a **separate** Reflex backend for `/_event`, `/_upload`, and related paths. Put an edge proxy in front.

### When to use

- Django **uvicorn/gunicorn worker pools** on plain `get_asgi_application()`
- **Independent scaling** of Django HTTP and Reflex WebSocket traffic
- Reference layout: [docker-compose.scaling.yml](../examples/docker-compose.scaling.yml)

### Production checklist

1. **Build the SPA in CI** (shared pipeline above).
2. **Use real settings** with `DEBUG = False`, a real `SECRET_KEY`, `ALLOWED_HOSTS`, and `STATIC_ROOT`.
3. **Run Django ASGI** with plain `get_asgi_application()` (see `config/asgi.py` snippet).
4. **Run Reflex backend** separately and **reverse-proxy** `/_event`, `/_upload`, etc. to it.
5. **Edge proxy** serves `/static/` from disk and forwards HTTP to Django.

```bash
export DJANGO_SETTINGS_MODULE=config.production
uv run uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --workers 4
# Reflex backend on another port (see docker-compose.scaling.yml)
```

### What you ship

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

Set `RX_PROXY_SERVER` when Django runs on `runserver` and Reflex runs via `run_reflex`. This is a **dev-only** layout. See [Routing](../internals/routing.md).

---

## ASGI entry point (Path B)

--8<-- "snippets/minimal_asgi.py"

### uvicorn

```bash
uv run uvicorn config.asgi:application \
    --host 0.0.0.0 --port 8000 --workers 4
```

Run your Reflex backend separately and configure the edge proxy to forward `/_event`, `/_upload`, etc.

### gunicorn + uvicorn worker

```bash
uv run gunicorn config.asgi:application \
    --workers 4 --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000
```

### Dockerfile sketch (split)

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

With `DEBUG = False`, the dev proxy is off and the SPA serves from disk. You can also set `RX_DEV_PROXY=0` explicitly. See [Settings reference](../reference/settings.md).

---

## Nginx essentials (Path B and TLS for Path A)

Three things matter when a reverse proxy sits in front:

- **`/_event` needs WebSocket upgrade headers** (Path B; Path A serves `/_event` on the same upstream).
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

For Path A, point the proxy at the single `run_reflex --env prod` port. For Path B, split Django and Reflex upstreams. Full example blocks and Caddy config are in the repo docs history; see also [Media files](../guides/media.md) for `/media/`.

---

## Health checks

Use `/_health` (or `/ping`). Returns `{"status": "ok"}` without touching the database.

---

## Scaling notes

- **Workers (Path B):** start with 2 to 4; async handlers benefit from concurrency inside a worker.
- **Sticky sessions:** default Reflex state is in-memory per process.
- **Redis:** required for multi-worker or multi-replica Reflex via `RX_CONFIG["redis_url"]`.
- **WebSocket idle timeout:** set proxy timeout to at least 300 seconds.
- **Event bridge:** opt into `"smart"` mode and `"lean"` preset for large apps  -  see [Scaling and performance](scaling.md).

| Symptom | Likely fix |
|:---|:---|
| WebSocket drops after 60s | Raise proxy idle timeout |
| CSRF on admin behind HTTPS | Set `SECURE_PROXY_SSL_HEADER` |
| Slow first request | Pre-build SPA in CI; disable auto-export on start |
| High event volume | `RX_EVENT_BRIDGE_MODE = "smart"` + per-State `_rx_bridge` |

More: [Troubleshooting](troubleshooting.md), [Scaling and performance](scaling.md).

---

## What just happened?

You have two production paths: **Path A** (export SPA in CI, then `run_reflex --env prod` on one port) and **Path B** (export SPA in CI, run Django ASGI with worker pools, run Reflex separately, and put a proxy in front with WebSocket support on `/_event`).

## Next up

[Best practices →](best_practices.md)
