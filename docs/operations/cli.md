# CLI reference

**What you will learn:** `reflex run`, `reflex export`, and `reflex django` for reflex-django projects.

---

## Primary commands

| Command | What it does |
|:---|:---|
| `reflex run` | Dev: Vite on `:3000` + Reflex backend with Django mounted in-process |
| `reflex export` | Build the SPA bundle for CI and production |
| `reflex django <args>` | Forward to Django `manage.py` (migrate, createsuperuser, collectstatic, ...) |

Standard Django still works:

```bash
python manage.py migrate
python manage.py collectstatic
```

---

## `reflex run`

Default dev workflow:

1. Loads `rxconfig.py` and bootstraps `ReflexDjangoPlugin`
2. Compiles the SPA if needed
3. Starts Vite on `frontend_port` (default `3000`)
4. Starts the Reflex backend on `backend_port` (default `8000`)
5. Mounts Django ASGI for configured URL prefixes

--8<-- "snippets/reflex_run_command.md"

Browse **`http://localhost:3000/`** for UI work. Admin and API work at **`http://localhost:3000/admin/`** (proxied) or **`http://localhost:8000/admin/`** (direct).

See [Local development](../getting-started/local_development.md).

### Useful Reflex flags

| Flag | Effect |
|:---|:---|
| `--env prod` | Production-like serve from compiled bundle |
| `--loglevel debug` | Verbose Reflex logs |

---

## `reflex export`

Build the frontend for deployment:

```bash
reflex export
```

Run in CI before `collectstatic`. The plugin attaches Django dispatch during export.

---

## `reflex django`

Shorthand for Django management commands:

```bash
reflex django migrate
reflex django createsuperuser
reflex django collectstatic --noinput
```

Equivalent to `python manage.py ...`.

---

## Environment variables

| Variable | Purpose |
|:---|:---|
| `DJANGO_SETTINGS_MODULE` | Django settings (also set via plugin `settings_module`) |
| `RX_FRONTEND_PORT` / `RX_BACKEND_PORT` | Override ports from `rx.Config` |
| `RX_SEPARATE_DEV_PORTS` | Two-port dev (default on) |
| `RX_PROXY_SERVER` | Proxy Django to external dev server |

See [Settings reference](../reference/settings.md).
