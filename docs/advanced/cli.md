# CLI

Run Django management commands through Reflex without switching tools.

## reflex django

Forwards any subcommand to Django's management CLI:

```bash
reflex django migrate
reflex django makemigrations
reflex django createsuperuser
reflex django collectstatic --noinput
reflex django shell
```

Equivalent to `python manage.py` when `DJANGO_SETTINGS_MODULE` is set (via plugin or env).

## reflex-django

Standalone console script with the same forwarding:

```bash
reflex-django migrate
```

﻿## Reflex commands

| Command | Purpose |
|:---|:---|
| `reflex run` | Dev: Vite :3000 + backend :8000 (integrated profile) |
| `reflex run --env prod` | Self-hosted production (integrated) |
| `reflex deploy` | Reflex Cloud hosting |
| `reflex export` | Build SPA static files (split Django service) |
| `reflex run --env prod --backend-only` | Reflex backend only (split or behind a proxy) |

## When to use what

| Workflow | Command |
|:---|:---|
| Normal dev (`integrated` profile) | `reflex run` |
| Self-hosted production | `reflex run --env prod` or `reflex deploy` |
| Split dev | `runserver` + `reflex run` with `proxy.server` ([Proxy](../learn/proxy.md)) |
| Split production | See [Deploy](deployment.md) |

See [Deploy](deployment.md) for full production layouts.
**Next:** [Config reference](config.md)
