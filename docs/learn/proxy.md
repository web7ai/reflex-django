# Proxy

Proxy connects Vite on port 3000 to your backends during local dev. You browse one URL while admin, API, events, and the SPA each reach the right process.

## Default ports

| Server | Port | Role |
|:---|:---|:---|
| Vite | 3000 | Reflex UI with hot reload. Open this for frontend work. |
| Reflex backend | 8000 | Django paths, `/_event`, `/_upload`. Proxied from Vite. |

```bash
reflex run
```

Browse **http://localhost:3000/**.

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

Proxy is dev only. Production uses your edge reverse proxy.

**Next:** [Bridge](bridge.md)
