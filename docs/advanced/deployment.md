# Deploy

Ship reflex-django in one of two ways. **Option 1** uses Reflex production commands (`reflex deploy` or `reflex run --env prod`). **Option 2** runs Django and Reflex as separate services with explicit plugin config.

## Option 1: Reflex deploy (integrated)

One integrated stack: Django admin, API, SPA, and Reflex events. Set `profile: "integrated"` in production `rxconfig.py`:

```python
--8<-- "snippets/deploy_integrated_rxconfig.py"
```

Run migrations before every deploy:

```bash
export DJANGO_SETTINGS_MODULE=config.production
reflex django migrate --noinput
```

### A. Reflex Cloud

Deploy to [Reflex Hosting](https://reflex.dev/docs/hosting/deploy-quick-start/):

```bash
reflex deploy
```

Use a project config file if you have one (`reflex deploy --config cloud.yml`). Your Django settings and database must be reachable from the hosted environment.

### B. Self-hosted (`reflex run --env prod`)

Production build and run on your own server:

```bash
reflex run --env prod
```

Browse the app on port **3000** (frontend) and **8000** (backend) by default. For a single backend port behind your own reverse proxy:

```bash
reflex run --env prod --backend-only --backend-port 8000
```

Set `redis_url` in `rx.Config` when you run multiple Reflex workers. Set `RX_AUTO_EXPORT_ON_START=0` in Django settings so the app does not rebuild on every boot.

### When to pick Option 1

- Simplest path: one deploy command or one `reflex run`
- Single VPS, container, or Reflex Cloud
- Typical reflex-django apps

---

## Option 2: Separate Django and Reflex

Two production services plus an edge reverse proxy:

| Path | Service |
|:---|:---|
| `/admin/`, `/api/`, SPA shell (HTML) | Django |
| `/_event`, `/_upload` | Reflex backend |

### Django service config

Keep normal Django production settings (`INSTALLED_APPS`, `AsyncStreamingMiddleware` last). Build the SPA bundle once so Django can serve the shell:

```bash
export DJANGO_SETTINGS_MODULE=config.production
reflex django migrate --noinput
reflex export
reflex django collectstatic --noinput
uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --workers 4
```

Django does not run `reflex run` in this layout. It serves admin, API, and the exported SPA via reflex-django mount.

### Reflex service config

Turn **embed off** (Django is not inside the Reflex process). Keep **mount** and **bridge** on. Disable **proxy** (your edge proxy replaces dev Vite proxy):

```python
--8<-- "snippets/deploy_split_rxconfig.py"
```

Run the Reflex backend:

```bash
export DJANGO_SETTINGS_MODULE=config.production
export REDIS_URL=redis://redis:6379/0
reflex run --env prod --backend-only --backend-port 8001
```

### Reverse proxy

Route `/_event` (long WebSocket timeout) and `/_upload` to the Reflex upstream. Send everything else to Django.

Example: [`docs/examples/deploy/nginx.conf`](../examples/deploy/nginx.conf)

Full layout: [`docs/examples/docker-compose.scaling.yml`](../examples/docker-compose.scaling.yml)

### Split checklist

1. `embed.enabled: false` in the Reflex service `rxconfig.py`
2. `proxy.enabled: false` in production
3. `bridge.enabled: true` so handlers keep `self.request.user`
4. Same `DJANGO_SETTINGS_MODULE` on both services
5. Shared `REDIS_URL` and cache-backed sessions ([Scaling](scaling.md))

### When to pick Option 2

- Scale Django and Reflex workers independently
- Django on an existing platform (Kubernetes, PaaS) plus a Reflex worker pool
- Different deploy cadence for API vs event backend

---

## Docker sketches

**Option 1 (integrated):**

```dockerfile
RUN reflex django migrate --noinput
CMD ["reflex", "run", "--env", "prod", "--backend-only", "--backend-port", "8000"]
```

**Option 2:** see [`docker-compose.scaling.yml`](../examples/docker-compose.scaling.yml) (django + reflex + nginx + redis).

## Commands

| Command | Use |
|:---|:---|
| `reflex run` | Dev (integrated profile) |
| `reflex run --env prod` | Self-hosted production |
| `reflex deploy` | Reflex Cloud |
| `reflex export` | Build SPA static files (split Django service) |
| `reflex django migrate` | Database migrations |

See [Scaling](scaling.md) for Redis and multi-worker tuning.

**Next:** [Troubleshooting](troubleshooting.md)
