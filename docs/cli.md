# CLI

Run **Django management commands** through the same settings module as `reflex run`.

---

## Prerequisites

- [Installation](installation.md)  
- [Configuration](configuration.md)

---

## Two entry points

| Command | Description |
|---------|-------------|
| `reflex django <subcommand>` | Django group on the Reflex CLI (`.pth` bootstrap) |
| `reflex-django <subcommand>` | Standalone console script (`pyproject.toml` `[project.scripts]`) |

Both load **`rxconfig`** (when present), call **`configure_django()`**, then forward to `django.core.management.execute_from_command_line`.

---

## Common commands

```bash
uv run reflex django migrate
uv run reflex django makemigrations
uv run reflex django createsuperuser
uv run reflex django shell
uv run reflex django collectstatic
uv run reflex django help
```

Equivalent:

```bash
uv run reflex-django migrate
```

---

## How settings are loaded

1. `_load_rxconfig()` imports Reflex config via `reflex_base.config.get_config()`.
2. `ReflexDjangoPlugin.__post_init__` sets `DJANGO_SETTINGS_MODULE` (setdefault) and path prefix env vars.
3. `configure_django()` runs `django.setup()`.

> **Tip:** Migrations use the **same** database as runtime when `rxconfig` and env agree.

---

## `reflex django init` (beta)

`reflex django init` scaffolds a starter tree. The README treats this as **beta**; prefer [Quickstart](quickstart.md) or [Existing Django project](existing_django_project.md).

---

## Advanced usage

Pass through arbitrary Django args:

```bash
uv run reflex django migrate --plan
uv run reflex django makemigrations catalog --name add_product
```

---

## Common mistakes

- Running `manage.py` directly with a different `DJANGO_SETTINGS_MODULE` than `rxconfig`.  
- Running migrate before creating `rxconfig.py` in a Reflex-only directory (falls back to `default_settings`).

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Wrong database | Ensure `rxconfig` loads; check env `DJANGO_SETTINGS_MODULE` |
| `No module named 'rxconfig'` | Run from project root; standalone `reflex-django` swallows config load errors |

---

## Developer notes

- Implementation: `src/reflex_django/cli.py`, `src/reflex_django/_reflex_cli_bootstrap.py`.

---

## See also

- [Database integration](database_integration.md)  
- [Deployment](deployment.md)

---

**Navigation:** [← API integration](api_integration.md) | [Next: Deployment →](deployment.md) | [Docs index](index.md)
