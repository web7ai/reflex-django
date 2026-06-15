# Glossary

### `ReflexDjangoPlugin`

Reflex plugin in `rxconfig.py` that bootstraps Django integration (mount config, event bridge, compile hooks).

### `app_name`

Compile label in `rx.Config`. Matches `{app_name}/{app_name}.py`.

### `reflex run`

Primary dev command: Vite + Reflex backend with Django mounted in-process.

### `reflex export`

Production frontend build command (replaces the removed Django export command).

### `reflex django`

CLI group forwarding to Django `manage.py`.

### `RX_PAGE_PACKAGES`

Optional Django setting listing page modules to import at compile time.

### `RX_PROXY_SERVER`

Optional Django setting (or env var). When **unset** (default), Django is mounted in the Reflex backend during `reflex run`. When **set** to a base URL like `http://127.0.0.1:8000`, Vite proxies `/admin` and `/api` to that external Django server instead; Reflex paths still hit the Reflex backend. Dev-only — not used in production.

### `RX_SEPARATE_DEV_PORTS`

When true, browse `:3000` for SPA; backend on `:8000`.
