# Proxy

Proxy connects Vite on port 3000 to your backends during local dev. You browse one URL while admin, API, events, and the SPA each reach the right process.

Think of proxy as the development traffic router. It is not the production reverse proxy. It exists so local Vite/HMR, Django admin/API, Reflex events, and uploads work from the browser without hand-written proxy rules.

See [Profiles](profiles.md) for preset defaults. Proxy is on in all built-in profiles.

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

## Options reference

Allowed keys in the `proxy` block:

| Option | Type | Default by profile | Purpose |
|:---|:---|:---|:---|
| `proxy.enabled` | `bool` | `True` in all profiles | Install reflex-django Vite/Django dev proxy wiring |
| `proxy.server` | `str` | unset | External Django server URL for Django-owned paths (required when embed is off) |
| `proxy.separate_dev_ports` | `bool` | unset (falls back to `RX_SEPARATE_DEV_PORTS`) | Use native Reflex two-port dev layout |

Settings fallbacks: `RX_PROXY_SERVER`, `RX_SEPARATE_DEV_PORTS`. Dev serving matrix: [Config reference](../advanced/config.md).

When `proxy.enabled=False`, reflex-django skips Vite proxy patching at compile time. Use this only when you provide your own dev routing.

## Examples

**Integrated (no external server):**

```python
ReflexDjangoPlugin(config={
    "settings_module": "config.settings",
    "profile": "integrated",
})
```

**Split dev with external Django:**

```python
--8<-- "snippets/profile_split_dev_rxconfig.py"
```

```bash
python manage.py runserver
reflex run
```

**Native Reflex two-port layout:**

```python
ReflexDjangoPlugin(config={
    "settings_module": "config.settings",
    "profile": "integrated",
    "proxy": {"separate_dev_ports": True},
})
```

Browse Vite on the frontend port; the backend port serves Django-owned paths plus `/_event` and `/_upload`.

**Custom ports:**

```python
config = rx.Config(
    app_name="shop",
    frontend_port=3000,
    backend_port=8000,
    plugins=[ReflexDjangoPlugin(config={"settings_module": "config.settings"})],
)
```

**Disable reflex-django proxy wiring:**

```python
ReflexDjangoPlugin(config={
    "settings_module": "config.settings",
    "proxy": {"enabled": False},
})
```

## Integrated vs split dev

| | Integrated | Split dev |
|:---|:---|:---|
| embed | on | off |
| `proxy.server` | not required | required (or `RX_PROXY_SERVER`) |
| Commands | `reflex run` | `runserver` + `reflex run` |

Prefer explicit `profile: "split_dev"` over setting `RX_PROXY_SERVER` alone so embed/proxy intent is visible in `rxconfig.py`.

Use split dev when you want independent Django and Reflex reload cycles. Use integrated when one command is enough.

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

## What proxy does not do

Proxy does not add Django request context to Reflex event handlers. That is [Bridge](bridge.md). Proxy also does not decide route ownership. That is [Mount](mount.md).

Proxy is dev only. Production uses your edge reverse proxy. In split production, route `/_event` and `/_upload` to Reflex and send Django/admin/API/SPA shell traffic to Django.

**Next:** [Bridge](bridge.md)
