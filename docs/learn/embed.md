# Embed

Embed runs Django HTTP inside the Reflex backend process. In local development, this lets one `reflex run` command serve both the Reflex event backend and Django-owned routes such as `/admin/` and `/api/`.

Think of embed as the process-level integration piece. It decides whether Django is inside the Reflex backend process or running somewhere else.

See [Profiles](profiles.md) for preset defaults. Profile `integrated` turns embed on; `split_dev` and `reflex_only` turn it off.

## Options reference

Allowed keys in the `embed` block:

| Option | Type | Default by profile | Purpose |
|:---|:---|:---|:---|
| `embed.enabled` | `bool` | `True` in `integrated`; `False` in `split_dev` and `reflex_only` | Run Django HTTP inside the Reflex backend process |

Embed has no Django `RX_*` setting. It is configured only through the plugin.

When no explicit `embed` block is supplied and `RX_PROXY_SERVER` (or the `RX_PROXY_SERVER` env var) is set, reflex-django treats Django as external and sets embed off. Prefer explicit `profile: "split_dev"` for clarity.

## Examples

**Default integrated (embed on):**

```python
ReflexDjangoPlugin(config={
    "settings_module": "config.settings",
    "profile": "integrated",
})
```

```bash
reflex run
```

**Split dev (embed off, external Django):**

```python
--8<-- "snippets/profile_split_dev_rxconfig.py"
```

**Override integrated profile to disable embed:**

```python
ReflexDjangoPlugin(config={
    "settings_module": "config.settings",
    "profile": "integrated",
    "embed": {"enabled": False},
    "proxy": {"server": "http://127.0.0.1:8000"},
})
```

If you turn embed off, configure [Proxy](proxy.md) so the dev frontend knows where Django is running.

## What embed does

When embed is enabled, reflex-django installs Django ASGI dispatch into the Reflex backend. Requests for Django-owned paths can be handled by Django from the same backend process that handles Reflex events and uploads.

Embed does not decide which paths are Django paths. That is [Mount](mount.md). Embed only decides whether Django HTTP is available inside the Reflex backend process.

## Use embed when

- You want the simplest local workflow.
- You want one command, `reflex run`.
- You want Django admin/API available during Reflex development without a second terminal.
- You are using `profile: "integrated"`.

## Turn embed off

Turn embed off when Django runs separately, for example through `runserver`, uvicorn, Docker, or another development service.

Use `profile: "split_dev"` or set `"embed": {"enabled": False}` with `proxy.server`. Then run both processes:

```bash
python manage.py runserver
reflex run
```

In split dev, Vite still serves the Reflex UI, but Django-owned routes are sent to the external Django server configured by `proxy.server`.

## Production guidance

Embed is mainly a local development convenience. In production, use your deployment shape deliberately:

- Integrated production can use `reflex run --env prod` or Reflex deploy.
- Split production should run Django and Reflex as separate services behind a real reverse proxy.
- Do not rely on the dev Vite proxy as a production edge proxy.

See [Deploy](../advanced/deployment.md) for production layouts.

**Next:** [Mount](mount.md)
