# Settings reference

Django `RX_*` settings for reflex-django tuning. **Reflex runtime config** (ports, plugins, `app_name`) lives in **`rxconfig.py`**, not here.

---

## Reflex config (`rxconfig.py`)

| Field | Purpose |
|:---|:---|
| `app_name` | Compile label; matches `{app_name}/{app_name}.py` |
| `frontend_port` / `backend_port` | Dev ports (default 3000 / 8000) |
| `plugins` | Include `ReflexDjangoPlugin` and Reflex UI plugins |
| `redis_url` | Required for multi-worker Reflex |

See [Configuration](../getting-started/configuration.md).

### `ReflexDjangoPlugin` config

| Key | Default | Purpose |
|:---|:---|:---|
| `settings_module` | from `manage.py` | `DJANGO_SETTINGS_MODULE` |
| `django_prefix` | auto | `/admin`, `/api`, ... |
| `mount_prefix` | `/` | SPA catch-all |
| `auto_mount` | `True` | Append `reflex_mount` |

---

## Django mount settings

| Setting | Type | Default | Purpose |
|:---|:---|:---|:---|
| `RX_AUTO_MOUNT` | bool | `True` | Auto append SPA catch-all |
| `RX_MOUNT_PREFIX` | str | `/` | SPA mount prefix |
| `RX_DJANGO_PREFIX` | tuple | auto | Override Django URL prefixes |
| `RX_RESERVED_REFLEX_PREFIXES` | tuple | Reflex internals | Rare override |

---

## Dev workflow

| Setting / env | Default | Purpose |
|:---|:---|:---|
| `RX_SEPARATE_DEV_PORTS` | `True` when `reflex run` | Vite on :3000, backend on :8000 |
| `RX_DEV_PROXY` | `False` | Django reverse-proxy to Vite (advanced) |
| `RX_PROXY_SERVER` | unset | Base URL of a separate Django HTTP server in dev (e.g. `http://127.0.0.1:8000`). When set, Vite proxies `django_prefix` paths there; when unset, Django runs in-process on the Reflex backend. Dev-only. |
| `RX_FRONTEND_PORT` / `RX_BACKEND_PORT` | env | Override `rx.Config` ports |
| `RX_COMPILE_DEV` | unset | Set by Reflex compile-dev modes |
| `RX_SERVE_FROM_BUILD` | `False` | Serve pre-built SPA without Vite |

---

## Pages

| Setting | Default | Purpose |
|:---|:---|:---|
| `RX_PAGE_MODULE` | `views` | Default page module suffix |
| `RX_PAGE_PACKAGES` | `[]` | Explicit compile-time page imports |

---

## Event bridge and auth

See source in `reflex_django/core/settings_names.py` for `RX_AUTH`, `RX_EVENT_BRIDGE_MODE`, `RX_EVENT_CACHE`, and related settings.

---

## Removed in v4

| Removed | Use instead |
|:---|:---|
| Settings `RX_CONFIG` dict | `rx.Config` in `rxconfig.py` |
| Settings-based plugin list | `plugins=[...]` in `rx.Config` |
| Django `run_reflex` command | `reflex run` |
| Django `export_reflex` command | `reflex export` |
