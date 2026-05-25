# Deployment

You deploy a `reflex-django` app the same way you deploy any modern Django + ASGI app, with one extra build step: the SPA bundle.

This page covers the production basics — one container, one ASGI server, one reverse proxy — and a few common platforms.

---

## What you ship

The artifact is just your Python project plus the compiled SPA. There's no separate frontend image.

```text
your-project/
├── manage.py
├── pyproject.toml / uv.lock
├── config/
│   ├── settings.py
│   ├── urls.py
│   └── asgi.py
├── shop/
│   ├── models.py
│   └── views.py
└── staticfiles/         ← created by collectstatic in CI
    └── _reflex/         ← the compiled SPA, staged by export_reflex
```

In production, an ASGI server runs `reflex_django.asgi_entry:application`. A reverse proxy (Nginx, Caddy, your platform's edge) serves `/static/` from `staticfiles/`. Everything else hits the ASGI process.

---

## The build pipeline

Every deploy runs these in CI (or a Dockerfile build step):

```bash
uv sync --frozen
python manage.py migrate --noinput
python manage.py export_reflex --frontend-only --no-zip --stage-to-static-root
python manage.py collectstatic --noinput
```

What each does:

| Step | Effect |
|:---|:---|
| `uv sync --frozen` | Install Python deps. |
| `migrate` | Apply Django migrations. |
| `export_reflex` | Build the Reflex SPA and stage it into `STATIC_ROOT/_reflex/`. |
| `collectstatic` | Gather your admin static files + the SPA bundle into `STATIC_ROOT`. |

After this, your container/image has `staticfiles/` ready to serve and the Python deps installed. Now you boot the ASGI server.

---

## ASGI server choices

`reflex-django` is just an ASGI app. Use whichever server you like.

### uvicorn

```bash
uv run uvicorn reflex_django.asgi_entry:application \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 4
```

### gunicorn + uvicorn worker

```bash
uv run gunicorn reflex_django.asgi_entry:application \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000
```

### granian

```bash
uv run granian \
    --interface asgi \
    --workers 4 \
    --host 0.0.0.0 \
    --port 8000 \
    reflex_django.asgi_entry:application
```

### hypercorn

```bash
uv run hypercorn reflex_django.asgi_entry:application \
    --workers 4 \
    --bind 0.0.0.0:8000
```

All four are fine. Most projects start with uvicorn or gunicorn+uvicorn worker.

---

## Required settings

```python
# config/production.py (or similar)
from .settings import *    # base settings

DEBUG = False

ALLOWED_HOSTS = ["yourdomain.com", "www.yourdomain.com"]
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]   # never commit a real key

CSRF_TRUSTED_ORIGINS = ["https://yourdomain.com"]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

STATIC_ROOT = BASE_DIR / "staticfiles"

# Use a real database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["DB_NAME"],
        "USER": os.environ["DB_USER"],
        "PASSWORD": os.environ["DB_PASSWORD"],
        "HOST": os.environ["DB_HOST"],
        "PORT": os.environ.get("DB_PORT", "5432"),
        "CONN_MAX_AGE": 600,
    }
}
```

Set `DJANGO_SETTINGS_MODULE=config.production` in the container.

### Don't rely on `default_settings`

`reflex_django.default_settings` is a development convenience. It has an insecure `SECRET_KEY` and `DEBUG = True`. **Never** use it in production. Always point `DJANGO_SETTINGS_MODULE` at your real module.

---

## A reasonable Dockerfile

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.production

# uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# install deps first (cache layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# copy the rest of the project
COPY . .

# build the SPA and gather static files
RUN uv run python manage.py export_reflex \
        --frontend-only --no-zip --stage-to-static-root \
    && uv run python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["uv", "run", "uvicorn", \
     "reflex_django.asgi_entry:application", \
     "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

Two notes:

- We don't run `migrate` in the Dockerfile. Run it as a one-off command on first deploy, then in a deploy hook.
- Node toolchain is needed to build the SPA. If your base image doesn't have it, install `nodejs` and `npm` before `export_reflex`. Reflex bundles its own JS runtime in newer versions; check your installed version.

---

## A reasonable docker-compose

For local prod-like testing:

```yaml
# docker-compose.yml
services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      DJANGO_SETTINGS_MODULE: config.production
      DJANGO_SECRET_KEY: ${DJANGO_SECRET_KEY}
      DB_NAME: shop
      DB_USER: shop
      DB_PASSWORD: shop
      DB_HOST: db
    depends_on:
      - db

  db:
    image: postgres:16
    environment:
      POSTGRES_DB: shop
      POSTGRES_USER: shop
      POSTGRES_PASSWORD: shop
    volumes:
      - dbdata:/var/lib/postgresql/data

volumes:
  dbdata:
```

---

## Nginx in front of your app

A typical reverse-proxy block:

```nginx
upstream app {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    client_max_body_size 50M;

    # Static files served directly by Nginx
    location /static/ {
        alias /app/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # The Reflex WebSocket
    location /_event {
        proxy_pass http://app;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }

    # Everything else
    location / {
        proxy_pass http://app;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Three things matter:

- **`/_event` needs WebSocket upgrade headers.** That's where Reflex talks.
- **`/static/` served by Nginx** offloads asset traffic from the Python process.
- **`X-Forwarded-Proto: $scheme`** so Django's `SECURE_PROXY_SSL_HEADER` detects HTTPS.

---

## Caddy alternative

If you prefer Caddy:

```caddyfile
yourdomain.com {
    encode gzip

    handle_path /static/* {
        root * /app/staticfiles
        file_server
    }

    reverse_proxy /_event* 127.0.0.1:8000 {
        flush_interval -1
    }

    reverse_proxy /* 127.0.0.1:8000
}
```

Caddy auto-handles WebSocket upgrades and TLS certificates.

---

## Health checks

The dispatcher exposes a `/_health` endpoint (and `/ping`) that's safe for load balancers. It returns a small JSON `{"status": "ok"}` without touching the database.

```yaml
# Kubernetes
livenessProbe:
  httpGet:
    path: /_health
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /_health
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
```

---

## State manager: in-memory vs Redis

By default, Reflex stores per-tab state in process memory. That's fine for one process. If you scale to multiple workers and need state to be sticky, point Reflex at Redis:

```python
# urls.py
reflex_mount(
    app_name="shop",
    rx_config={
        "backend_port": 8000,
        "redis_url": os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    },
)
```

With Redis, state is pickled and shared across workers. Sticky sessions on the load balancer are still simpler though — for most apps, sticky session affinity + in-memory state is the right choice.

---

## Worker count

Rule of thumb: `2 * num_cores + 1` for ASGI workers. Async views and event handlers benefit from concurrency *within* a worker, so you don't need as many workers as you would for sync Django.

For most apps: 2-4 workers, sticky session affinity if you have more than one worker.

---

## Database connections

Each worker keeps its own pool. With `CONN_MAX_AGE = 600`, each worker holds connections for up to 10 minutes before recycling. Multiply by the number of workers and add the admin's connections to estimate your peak.

For Postgres, a connection pooler (PgBouncer) in transaction mode is the usual answer for high-concurrency apps.

---

## Platform-specific notes

### Fly.io

Fly's ASGI handling and WebSocket support are excellent out of the box. Use a `fly.toml` with `internal_port = 8000`, expose the standard ports, and Fly handles TLS.

### Railway / Render

Similar: point them at a Dockerfile (or detect Python automatically), set `DJANGO_SETTINGS_MODULE`, and they'll handle the rest. Make sure WebSocket support is enabled for your service (it usually is by default).

### AWS / GCP / Azure (container services)

Use ECS Fargate, Cloud Run, or App Service Containers with a custom Docker image. Front with an ALB / Cloud Load Balancer / Application Gateway that supports WebSocket. Increase the idle timeout to at least 300 seconds so Reflex's WebSocket doesn't get dropped.

### Heroku

Heroku supports WebSocket on dynos. Use a `Procfile`:

```text
release: python manage.py migrate --noinput
web: uvicorn reflex_django.asgi_entry:application --host 0.0.0.0 --port $PORT
```

Add a buildpack for Node if your Reflex version still needs it, and run `export_reflex` in `release` (or in a build hook).

### Bare VPS

The Nginx config above + systemd unit + Let's Encrypt + Postgres + a deploy script. Old-school but it works great.

```ini
# /etc/systemd/system/myshop.service
[Unit]
Description=My Shop
After=network.target

[Service]
User=www-data
WorkingDirectory=/srv/myshop
Environment="DJANGO_SETTINGS_MODULE=config.production"
EnvironmentFile=/etc/myshop.env
ExecStart=/srv/myshop/.venv/bin/uvicorn reflex_django.asgi_entry:application \
          --host 127.0.0.1 --port 8000 --workers 4
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

---

## Zero-downtime deploys

The minimal pattern:

1. Build a new image with the new code.
2. Run migrations: `docker run --rm new-image python manage.py migrate`.
3. Start the new container; wait for `/_health` to return 200.
4. Switch the reverse proxy to the new container.
5. Stop the old container.

Most platforms do steps 3-5 for you. The tricky part is making sure migrations are backwards-compatible with the old code (the standard Django zero-downtime advice applies).

---

## Logging

Use `LOGGING` in settings the standard Django way. Pipe both Django and uvicorn logs to stdout/stderr; let the platform aggregate them.

```python
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"format": '{"time":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","msg":"%(message)s"}'},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "json"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
```

---

## Common production gotchas

| Symptom | Cause | Fix |
|:---|:---|:---|
| WebSocket disconnects after 60s | Reverse proxy timeout too low | Bump `proxy_read_timeout` / idle timeout to 600s+ |
| `CSRF verification failed` on admin | Missing `X-Forwarded-Proto` | Set `SECURE_PROXY_SSL_HEADER` and ensure your proxy sends the header |
| Browser shows old SPA after deploy | Bundle cache | Add `expires` + `immutable` to `/static/`. Reflex bundles are content-hashed. |
| Sessions reset between requests | Multiple workers without sticky sessions | Enable sticky sessions on the load balancer or use a shared session backend |
| Reflex events 500 with no useful logs | Custom middleware blowing up | Set `LOGGING` level to DEBUG, restart, reproduce |
| `503` from health check | Worker count too low | Scale workers, or increase the readiness `initialDelaySeconds` |

---

**Next:** [Best practices →](best_practices.md)
