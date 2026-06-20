# CLI

reflex-django adds Django-aware commands under Reflex so you can use one tool while developing integrated apps.

## `reflex django`

Forwards Django management subcommands through the active `DJANGO_SETTINGS_MODULE`:

```bash
reflex django migrate
reflex django makemigrations
reflex django createsuperuser
reflex django collectstatic --noinput
reflex django shell
```

This is equivalent to `python manage.py ...` when settings are configured by `ReflexDjangoPlugin` or the environment.

If a Django subcommand needs its own help text, use the Django command after `reflex django`; if Reflex consumes `--help`, use the project-specific `--reflex-help` path where available.

## `reflex-django`

The standalone console script forwards the same management commands:

```bash
reflex-django migrate
```

## `scaffold`

Generate a typed `ModelState` and starter Reflex components from a Django model:

```bash
reflex django scaffold shop.Product \
  --fields name,price,active \
  --serializer \
  --paginate-by 20 \
  --search name \
  --route products \
  --output shop/product_views.py
```

Flags:

| Flag | Purpose |
|:---|:---|
| `model` | Required `app_label.ModelName` |
| `--fields` | Comma-separated editable fields; default is all editable fields |
| `--serializer` | Emit an explicit `ReflexDjangoModelSerializer` |
| `--paginate-by` | Page size; `0` disables pagination |
| `--search` | Comma-separated search fields; default is text fields |
| `--route` | Page route; default is pluralized model name |
| `--output`, `-o` | Write generated source to a file |
| `--force` | Overwrite an existing output file |

Without `--output`, the command prints generated source to stdout.

Generated module structure:

| Symbol | Purpose |
|:---|:---|
| `{Model}State` | `ModelState` subclass |
| optional `{Model}Serializer` | Explicit serializer when `--serializer` is set |
| `{model}_row(row)` | Table row renderer |
| `{model}_form()` | Create/edit form |
| `{model}_list()` | List/search/pagination component |
| `{model}_page()` | Combined page component |

Widget mapping comes from [Forms and FieldSpec](forms.md): booleans use checkboxes, text fields use text areas, numeric/relation fields use number inputs, and strings use text inputs.

## Reflex commands

| Command | Purpose |
|:---|:---|
| `reflex run` | Dev: Vite `:3000` + backend `:8000` in integrated profile |
| `reflex run --env prod` | Self-hosted production |
| `reflex deploy` | Reflex Cloud hosting |
| `reflex export` | Build SPA static files for split Django service |
| `reflex run --env prod --backend-only` | Reflex backend only behind a proxy |

## When to use what

| Workflow | Command |
|:---|:---|
| Normal dev (`integrated` profile) | `reflex run` |
| Django migrations/admin tasks | `reflex django ...` |
| Generate CRUD starter page | `reflex django scaffold app.Model` |
| Self-hosted production | `reflex run --env prod` or `reflex deploy` |
| Split dev | `runserver` + `reflex run` with `proxy.server` |
| Split production | See [Deploy](deployment.md) |

**Next:** [Config reference](config.md), [Model state](model-state.md), and [Deploy](deployment.md).
