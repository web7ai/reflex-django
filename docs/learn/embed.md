# Embed

Embed runs Django HTTP inside the Reflex backend process. In local development, this lets one `reflex run` command serve both the Reflex event backend and Django-owned routes such as `/admin/` and `/api/`.

Think of embed as the process-level integration piece. It decides whether Django is inside the Reflex backend process or running somewhere else.

## Default

With `profile: "integrated"`, embed is on:

```python
ReflexDjangoPlugin(config={
    "settings_module": "config.settings",
    "profile": "integrated",
})
```

Run:

```bash
reflex run
```

In this mode, the Reflex backend process can dispatch normal Django HTTP requests. You do not need a separate `python manage.py runserver` for local admin/API access.

## Options

| Option | Default from profile | Purpose |
|:---|:---|:---|
| `embed.enabled` | `True` in `integrated`, `False` in `split_dev` and `reflex_only` | Run Django HTTP inside the Reflex backend process |

The profile sets the default. An explicit `embed` block overrides the profile:

```python
ReflexDjangoPlugin(config={
    "settings_module": "config.settings",
    "profile": "integrated",
    "embed": {"enabled": False},
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

Use `profile: "split_dev"`:

```python
ReflexDjangoPlugin(config={
    "settings_module": "config.settings",
    "profile": "split_dev",
    "proxy": {"server": "http://127.0.0.1:8000"},
})
```

Or configure the pillar directly:

```python
ReflexDjangoPlugin(config={
    "settings_module": "config.settings",
    "embed": {"enabled": False},
    "proxy": {"server": "http://127.0.0.1:8000"},
})
```

Then run both processes:

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
