# Proxy

Proxy connects Vite on port 3000 to your backends during local dev. You browse one URL while admin, API, events, and the SPA each reach the right process.

Think of proxy as the development traffic router. It is not the production reverse proxy. It exists so local Vite/HMR, Django admin/API, Reflex events, and uploads work from the browser without hand-written proxy rules.

## Default ports

| Server | Port | Role |
|:---|:---|:---|
| Vite | 3000 | Reflex UI with hot reload. Open this for frontend work. |
| Reflex backend | 8000 | Django paths, `/_event`, `/_upload`. Proxied from Vite. |

```bash
reflex run
```

Browse **http://localhost:3000/**.

In the integrated profile, the Reflex backend on port 8000 also has embedded Django HTTP available. Vite forwards Django-owned paths, events, and uploads to that backend while keeping hot reload for the frontend.

## Options

| Option | Default from profile | Purpose |
|:---|:---|:---|
| `proxy.enabled` | `True` in all built-in profiles | Install reflex-django's local Vite/Django proxy wiring |
| `proxy.server` | unset | External Django server to send Django-owned paths to |
| `proxy.separate_dev_ports` | `False` | Keep Reflex's native separate frontend/backend dev layout |

Disable `proxy.enabled` only when you provide your own dev routing or run a production-style local stack.

## Split dev

Run Django on `runserver` in another terminal:

```python
ReflexDjangoPlugin(config={
    "settings_module": "config.settings",
    "profile": "split_dev",
    "proxy": {"server": "http://127.0.0.1:8000"},
})
```

| | Integrated | Split dev |
|:---|:---|:---|
| embed | on | off |
| Commands | `reflex run` | `runserver` + `reflex run` |

Vite still serves the SPA on port 3000. Admin and API go to your Django server.

Setting `RX_PROXY_SERVER` can also point Vite/Django proxying at an external Django server. Prefer the explicit `split_dev` profile in new projects so embed/proxy intent is visible in `rxconfig.py`.

Use split dev when:

- You want to debug Django with the normal `runserver` process.
- Another service already owns Django HTTP.
- You want Reflex dev reload and Django dev reload to run independently.

Use integrated dev when:

- You want one command.
- Django admin/API are fine inside the Reflex backend process.
- You do not need a separate Django HTTP process.

## Separate dev ports

`proxy.separate_dev_ports` or `RX_SEPARATE_DEV_PORTS=True` keeps the native Reflex layout: browse Vite on the frontend port, while the backend port serves Django-owned paths plus `/_event` and `/_upload`.

Use `RX_DEV_PROXY=0` when you want Django to serve the compiled SPA instead of proxying to Vite. Use `RX_SERVE_FROM_BUILD=True` for a pre-built bundle and `RX_COMPILE_DEV=1` for compile-only dev workflows.

## Development serving modes

| Need | Setting |
|:---|:---|
| Normal Vite HMR | `RX_DEV_PROXY=True`, `RX_SERVE_FROM_BUILD=False` |
| External Django in split dev | `profile: "split_dev"` and `proxy.server` |
| Native Reflex two-port behavior | `proxy.separate_dev_ports=True` |
| Serve an exported bundle from disk | `RX_SERVE_FROM_BUILD=True` |
| Compile-only dev without Vite catch-all | `RX_COMPILE_DEV=1` and `RX_DEV_PROXY=0` |
| Tell Django a frontend already exists | `RX_FRONTEND_PRESENT=1` |

## CSRF from port 3000

When you use admin from `:3000`, add both ports to `CSRF_TRUSTED_ORIGINS`. See [Troubleshooting](../advanced/troubleshooting.md).

## Custom ports

```python
config = rx.Config(
    app_name="shop",
    frontend_port=3000,
    backend_port=8000,
    plugins=[ReflexDjangoPlugin(config={...})],
)
```

## What proxy does not do

Proxy does not add Django request context to Reflex event handlers. That is [Bridge](bridge.md). Proxy also does not decide route ownership. That is [Mount](mount.md).

Proxy is dev only. Production uses your edge reverse proxy, such as Nginx, Caddy, a cloud load balancer, or platform routing. In split production, route `/_event` and `/_upload` to Reflex and send Django/admin/API/SPA shell traffic to Django.

**Next:** [Bridge](bridge.md)
