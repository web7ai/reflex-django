# Deployment Guide

Running a unified `reflex-django` application in production simplifies operational complexity. Instead of deploying, scaling, and managing separate frontend and backend servers, your entire stack—including your Reflex interactive UI, Django database APIs, and Django Administration portal—runs within a **single, unified ASGI process**.

This guide provides a comprehensive roadmap for configuring environment settings, serving static assets, setting up reverse proxies, and deploying with Docker and systemd.

---

## 1. Production Architecture Overview

In a production environment, your application is typically deployed behind a reverse proxy (like Nginx or Caddy) which handles SSL/TLS termination and serves static assets. The proxy forwards dynamic web traffic and WebSocket channels directly to your unified ASGI application runner:

```text
  Internet (HTTPS / WSS)
             │
             ▼
      Reverse Proxy (Nginx / Caddy)
     ┌────────────────────────────────────────────────────────┐
     │ • Terminates SSL/TLS                                   │
     │ • Serves Static Assets (/static/ and /_static/)        │
     └───────┬────────────────────────────────────────┬───────┘
             │ (HTTP Proxy)                           │ (WebSocket Proxy)
             ▼                                        ▼
    Dynamic HTTP API (/admin, /api)          Reflex State Channel (/_event)
     ┌────────────────────────────────────────────────────────┐
     │                Unified ASGI Process                    │
     │       (Reflex Server + Django Backend Router)          │
     └────────────────────────────────────────────────────────┘
```

---

## 2. Pre-Deployment Checklist

Before booting your application in a production environment, ensure the following checklist is completed:

| Checklist Item | Action | Production Requirement |
|:---|:---|:---|
| **Settings Module** | Define settings module | Set `DJANGO_SETTINGS_MODULE="my_project.settings"` explicitly in your environment. |
| **Debug Mode** | Disable debugger | Ensure `DEBUG = False` is set inside your Django settings. |
| **Secret Key** | Persist secret keys | Load `SECRET_KEY` from secure environment variables. **Never** use auto-generated keys. |
| **Allowed Hosts** | Restrict host traffic | Configure `ALLOWED_HOSTS` to match your domain (e.g. `['shop.com']`). |
| **Static Assets** | Collect static assets | Execute `collectstatic` to compile Django admin styles and resources. |
| **Database Migrations** | Apply migrations | Execute `migrate` inside your build pipeline before starting the app process. |
| **Autoload Settings** | Disable autoloading | Ensure `REFLEX_DJANGO_AUTO_SETTINGS = False` is set in production to enforce strict settings control. |

---

## 3. Static Asset Compilation & Routing

Django Admin templates and various standard package components require static asset serving. In development, `reflex-django` serves these automatically. In production, you should compile and delegate them to a high-performance web server.

### Step 1: Compile Static Assets
Run the collection command within your build or CI/CD pipeline:

```bash
uv run reflex django collectstatic --noinput
```

By default, this compiles and outputs static assets into the `.reflex-django/staticfiles/` directory.

### Step 2: Configure Proxy Serving
Instruct Nginx or your reverse proxy to intercept and serve requests to `/static/` directly from your compiled directory to bypass the Python application thread completely:

```nginx
# Nginx Static Serving Block
location /static/ {
    alias /app/.reflex-django/staticfiles/;
    expires 30d;
    add_header Cache-Control "public, no-transform";
}
```

---

## 4. Reverse Proxy Configuration (Nginx)

Below is a complete, production-hardened Nginx server block configured to handle SSL termination, static asset serving, and WebSocket connections (`/_event`) for Reflex state synchronization:

```nginx
# /etc/nginx/sites-available/my_app
server {
    listen 80;
    server_name shop.com www.shop.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name shop.com www.shop.com;

    # SSL Certificates
    ssl_certificate /etc/letsencrypt/live/shop.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/shop.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Serve Django admin and package static assets
    location /static/ {
        alias /app/.reflex-django/staticfiles/;
        expires 30d;
    }

    # Serve Reflex UI static compiled assets
    location /_static/ {
        alias /app/.web/public/;
        expires 30d;
    }

    # Proxy Reflex WebSocket state synchronization channels
    location /_event {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400; # Keep WebSocket open for inactive channels
    }

    # Proxy all standard dynamic HTTP requests
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 5. Dockerization & Container Orchestration

A multi-stage `Dockerfile` ensures that your production container is lightweight, containing only the compiled assets and runtime dependencies.

### Step 1: Create the `Dockerfile`
```dockerfile
# Stage 1: Build Reflex UI Assets
FROM python:3.11-slim AS builder
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev
COPY . .
# Compile Reflex frontend static assets
RUN uv run reflex export --frontend-only

# Stage 2: Production Container
FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev

# Copy compiled static assets and application code
COPY --from=builder /app/.web/public /app/.web/public
COPY . .

# Environment variables
ENV DJANGO_SETTINGS_MODULE="my_project.settings"
ENV PORT=8000

# Compile Django admin assets
RUN uv run reflex django collectstatic --noinput

# Run migrations and start the unified server
CMD ["sh", "-c", "uv run reflex django migrate && uv run reflex run --env prod --port $PORT"]
```

### Step 2: Create a `docker-compose.yml` file
```yaml
# docker-compose.yml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DJANGO_SETTINGS_MODULE=my_project.settings
      - SECRET_KEY=prod_super_secure_key_here
      - ALLOWED_HOSTS=shop.com,www.shop.com
      - DATABASE_URL=postgres://user:pass@db:5432/shop_db
    depends_on:
      - db

  db:
    image: postgres:15-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=shop_db

volumes:
  postgres_data:
```

---

## 6. Process Management with Systemd

If you are deploying directly to a virtual machine (such as an AWS EC2 instance or a DigitalOcean Droplet), use systemd to manage your application process, handle automatic restarts on failure, and aggregate system logs:

```ini
# /etc/systemd/system/reflex-app.service
[Unit]
Description=Unified Reflex-Django ASGI Application Service
After=network.target

[Service]
User=deploy
WorkingDirectory=/app
Environment=PATH=/app/.venv/bin:/usr/bin:/usr/local/bin
Environment=DJANGO_SETTINGS_MODULE=my_project.settings
Environment=SECRET_KEY=prod_super_secure_key_here
Environment=ALLOWED_HOSTS=shop.com,www.shop.com
Environment=DATABASE_URL=postgres://user:pass@127.0.0.1:5432/shop_db

ExecStart=/app/.venv/bin/reflex run --env prod --port 8000
Restart=always
RestartSec=5

# Logging configurations
StandardOutput=journal
StandardError=journal
SyslogIdentifier=reflex-app

[Install]
WantedBy=multi-user.target
```

To enable and boot your service, execute:

```bash
# Reload systemd configs
sudo systemctl daemon-reload

# Enable service boot on system start
sudo systemctl enable reflex-app

# Start the application process
sudo systemctl start reflex-app

# Monitor runtime logs in real-time
journalctl -u reflex-app -f
```

---

## 7. Troubleshooting Production Issues

| Symptom | Cause | Solution |
|:---|:---|:---|
| Django Admin portal is unstyled (missing CSS/JS). | Static assets were not compiled or Nginx alias is misconfigured. | Run `reflex django collectstatic` and verify that the Nginx `/static/` location alias matches your `STATIC_ROOT` path. |
| The application throws a `400 Bad Request` error. | The incoming domain name does not match the configured `ALLOWED_HOSTS` list. | Verify your domain name is included inside the `ALLOWED_HOSTS` block in your settings file. |
| WebSockets fail to connect with a `502 Bad Gateway` error. | Nginx is not configured to forward the WebSocket upgrade headers. | Ensure your Nginx configuration contains the `Upgrade` and `Connection` header proxy mappings. |
| Application crashes on startup with database connection errors. | The web service attempted to boot before the database was ready to accept queries. | Ensure your Docker containers use `depends_on` or utilize systemd restart parameters (`RestartSec=5`) to handle connection retries. |

---

**Navigation:** [← Testing Guide](testing.md) | [Next: Best Practices →](best_practices.md)
