# Deployment

A production `reflex-django` deployment is a single ASGI process serving everything on one port: the Reflex SPA, Django's admin, your API, static files, and the Reflex Socket.IO state channel. Build the SPA bundle in CI, ship it next to your Python code, and run any ASGI server pointed at `reflex_django.asgi_entry:application`.

---

## 1. Production topology

```text
                  Internet (HTTPS / WSS)
                          │
                          ▼
                Reverse proxy (Nginx / Caddy / ALB)
                  ┌─────────────────────────────────────┐
                  │ • SSL/TLS termination               │
                  │ • Optional static-file passthrough  │
                  │ • Optional rate limiting / caching  │
                  └────────────────┬────────────────────┘
                                   │  (HTTP + WebSocket upgrade)
                                   ▼
                Single ASGI process — uvicorn / granian / hypercorn
                  ┌─────────────────────────────────────┐
                  │ reflex_django.asgi_entry:application │
                  │   • DjangoOuterDispatcher           │
                  │   • Django middleware stack         │
                  │   • Reflex inner ASGI (_event, …)   │
                  │   • SPA from STATIC_ROOT/_reflex/   │
                  └─────────────────────────────────────┘
```

You can also expose the ASGI process directly to the internet — TLS terminated by your ASGI server or by a load balancer in front of it. The reverse proxy is convenient (admin static caching, gzip, rate limiting) but not required.

---

## 2. Pre-deploy checklist

| Item | Action |
|:---|:---|
| Settings module | `DJANGO_SETTINGS_MODULE=myproject.settings` in env |
| Debug | `DEBUG = False` |
| Secrets | `SECRET_KEY` from a secret manager / env var (never auto-generated) |
| Allowed hosts | `ALLOWED_HOSTS = ["example.com", "www.example.com"]` |
| Database | Run migrations: `python manage.py migrate` |
| SPA bundle | Build: `python manage.py export_reflex --frontend-only --no-zip --stage-to-static-root` |
| Django assets | Collect: `python manage.py collectstatic --noinput` |
| Auto settings | `REFLEX_DJANGO_AUTO_SETTINGS = False` (force strict, user-provided settings) |

---

## 3. Building the SPA bundle

Build is a one-shot CI step. It produces a static frontend bundle that the ASGI process serves from disk.

```bash
python manage.py export_reflex \
  --frontend-only \
  --no-zip \
  --stage-to-static-root
```

Output is staged into `STATIC_ROOT/_reflex/` (override with `--stage-target`). The SPA index is then picked up by `ReflexMountView` at runtime — no rebuild on first request.

`run_reflex --env prod` does **not** build the bundle automatically. Production servers boot deterministic, prebuilt artifacts; the CI pipeline owns the build step.

---

## 4. ASGI entry point

```python
# config/asgi.py
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
from reflex_django.asgi_entry import application  # noqa: E402,F401
```

Boot with any ASGI server:

```bash
# uvicorn
uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --workers 4

# granian
granian --interface asgi config.asgi:application --host 0.0.0.0 --port 8000 --workers 4

# hypercorn
hypercorn config.asgi:application --bind 0.0.0.0:8000 --workers 4
```

The dispatcher inside `application` handles HTTP, WebSocket, and ASGI lifespan scopes. There is no separate Daphne or Channels layer.

`manage.py run_reflex --env prod` is a convenience wrapper that boots the same `application` callable through uvicorn, with reload off:

```bash
python manage.py run_reflex --env prod --backend-host 0.0.0.0 --backend-port 8000 --no-reload
```

---

## 5. Static asset serving

### Option A — let the ASGI process serve `/static/`

`AsyncStreamingMiddleware` plus Django's staticfiles handler in the ASGI app is enough for low/medium traffic. The compiled Reflex SPA lives under `STATIC_ROOT/_reflex/` and the Django admin assets under `STATIC_ROOT/admin/`.

### Option B — front it with Nginx

Hand `/static/` to Nginx for cache headers and zero-copy sendfile:

```nginx
location /static/ {
    alias /srv/app/staticfiles/;
    expires 30d;
    add_header Cache-Control "public, no-transform";
}
```

Reflex bundle assets are inside the same `/static/_reflex/` directory and benefit from the same caching.

---

## 6. Reverse-proxy template (Nginx)

```nginx
server {
    listen 80;
    server_name example.com www.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name example.com www.example.com;

    ssl_certificate     /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    # Optional — serve compiled assets directly
    location /static/ {
        alias /srv/app/staticfiles/;
        expires 30d;
    }

    # Reflex Socket.IO state channel (WebSocket)
    location /_event {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade            $http_upgrade;
        proxy_set_header   Connection         "upgrade";
        proxy_set_header   Host               $host;
        proxy_set_header   X-Real-IP          $remote_addr;
        proxy_set_header   X-Forwarded-For    $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto  $scheme;
        proxy_read_timeout 86400;
    }

    # Everything else (SPA, /admin, /api, /_upload, /_health, …)
    location / {
        proxy_pass        http://127.0.0.1:8000;
        proxy_set_header  Host               $host;
        proxy_set_header  X-Real-IP          $remote_addr;
        proxy_set_header  X-Forwarded-For    $proxy_add_x_forwarded_for;
        proxy_set_header  X-Forwarded-Proto  $scheme;
    }
}
```

`/_event` needs the WebSocket upgrade headers. Everything else is plain HTTP. The same proxy block also handles `/_upload`, `/_health`, `/ping`, and `/auth-codespace` — all served by the same ASGI process.

---

## 7. Docker

A two-stage Dockerfile keeps the runtime image small. Stage 1 builds the SPA, stage 2 ships the binary + the compiled assets.

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

COPY . .
ENV DJANGO_SETTINGS_MODULE=config.settings
RUN uv run python manage.py export_reflex \
        --frontend-only --no-zip --stage-to-static-root \
 && uv run python manage.py collectstatic --noinput


FROM python:3.12-slim
WORKDIR /app

RUN pip install --no-cache-dir uv
COPY --from=builder /app /app

ENV DJANGO_SETTINGS_MODULE=config.settings
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uv run python manage.py migrate --noinput && uv run uvicorn config.asgi:application --host 0.0.0.0 --port ${PORT} --workers 4"]
```

`docker-compose.yml`:

```yaml
services:
  web:
    build: .
    ports: ["8000:8000"]
    environment:
      DJANGO_SETTINGS_MODULE: config.settings
      SECRET_KEY: ${SECRET_KEY}
      ALLOWED_HOSTS: example.com,www.example.com
      DATABASE_URL: postgres://app:app@db:5432/app
    depends_on: [db]

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
      POSTGRES_DB: app
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data: {}
```

---

## 8. systemd unit

For VM deploys without containers:

```ini
# /etc/systemd/system/myapp.service
[Unit]
Description=reflex-django ASGI app
After=network.target

[Service]
User=deploy
WorkingDirectory=/srv/app
EnvironmentFile=/srv/app/.env
ExecStart=/srv/app/.venv/bin/uvicorn config.asgi:application \
    --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=5

StandardOutput=journal
StandardError=journal
SyslogIdentifier=myapp

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable myapp
sudo systemctl start myapp
journalctl -u myapp -f
```

Build & migrate steps run in your CI pipeline (or as a one-shot `ExecStartPre=` if you really need them on the box).

---

## 9. Health probes

Both endpoints below are mounted by Reflex and bypass Django entirely — useful for load balancer liveness / readiness:

| Endpoint | Use |
|:---|:---|
| `GET /_health` | Returns a JSON OK when the Reflex event processor is alive. |
| `GET /ping` | Plain-text OK; cheap. |

For Django-level readiness (DB reachable, migrations applied), add your own `/healthz` Django view.

---

## 10. Scaling

- **CPU-bound traffic** — increase ASGI worker count (`--workers N`). State manager defaults to in-memory; switch to Redis via `rx_config={"state_manager_mode": "redis", "redis_url": "..."}` when running more than one worker.
- **WebSocket fan-out** — Reflex Socket.IO scales with workers when a shared state manager (Redis) is configured; otherwise each worker keeps its own state and clients pinned to a single worker via sticky sessions.
- **Static files** — put a CDN in front of `/static/`. The SPA bundle is fully cacheable; bust caches with a fresh export.
- **Database** — standard Django: connection pooling (`pgbouncer`, `CONN_MAX_AGE`), read replicas, etc.

---

## 11. Troubleshooting

| Symptom | Likely cause | Fix |
|:---|:---|:---|
| `GET /` returns 404 with "compiled SPA not found" | Bundle not built or not staged. | Run `python manage.py export_reflex --frontend-only --no-zip --stage-to-static-root` and redeploy. |
| Django admin unstyled | `collectstatic` didn't run, or Nginx alias mismatches `STATIC_ROOT`. | Run `collectstatic` and verify the alias path. |
| `400 Bad Request` on every request | Domain not in `ALLOWED_HOSTS`. | Add it. |
| `502 Bad Gateway` on WebSocket | Reverse proxy missing `Upgrade` / `Connection` headers. | Use the Nginx template above. |
| Sessions don't persist across workers | In-memory state manager + multiple workers. | Configure Redis state manager and/or sticky sessions. |
| `SynchronousOnlyOperation` during a Reflex event | Direct ORM call in async code outside the bridge. | Use `await Model.objects.aget(...)` or wrap in `sync_to_async`. The bridge already provides an async-safe `self.user`. |

---

**Navigation:** [← Testing](testing.md) | [Next: Best Practices →](best_practices.md)
