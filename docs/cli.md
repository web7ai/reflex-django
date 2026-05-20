# Command Line Interface (CLI)

Running a unified backend means managing both Reflex web states and Django database structures. Rather than forcing you to jump between separate configuration contexts, `reflex-django` exposes a unified Command Line Interface. 

This enables you to run any native Django management command (such as migrations, superuser registration, or database shells) using the exact same environment and settings module as `reflex run`.

---

## 1. The Two CLI Entry Points

`reflex-django` provides two equivalent entry points to interact with your unified backend:

```text
               1. Integrated Reflex CLI (pth bootstrap)
                  $ uv run reflex django <subcommand>
                                  │
                                  ▼
               2. Standalone Console Script (Direct)
                  $ uv run reflex-django <subcommand>
```

### Entry Point A: The Integrated Reflex CLI
The package automatically integrates itself directly into Reflex's native command-line interface using a custom `.pth` bootstrapper. This is the recommended style as it keeps all commands under the single, unified `reflex` keyword:

```bash
uv run reflex django <subcommand>
```

### Entry Point B: The Standalone CLI Script
If you prefer direct console calls, the package registers a standalone script in `pyproject.toml` under the `[project.scripts]` block. This acts as a direct alias:

```bash
uv run reflex-django <subcommand>
```

Both entry points execute the exact same loader: they locate `rxconfig.py`, initialize your environment variables, boot Django asynchronously, and forward your subcommands straight to Django's native execution pipeline.

---

## 2. Common Operations Guide

Here is a catalog of the most common management tasks and how to execute them within your unified project structure.

### Database Migrations
Always use these commands to generate and execute migrations so that your schema changes target the exact database configuration resolved in your `rxconfig`:

```bash
# Generate database schema migration scripts
uv run reflex django makemigrations

# Apply migrations to your database
uv run reflex django migrate

# Review the SQL statements that will be executed for a migration
uv run reflex django sqlmigrate shop 0001
```

### Creating Administration Accounts
Spawn interactive prompts to register superusers who can access the standard Django Admin panel:

```bash
uv run reflex django createsuperuser
```

### Running Interactive Python Shells
Launch a pre-configured interactive Python shell with the unified Reflex-Django environment and database connections fully booted:

```bash
uv run reflex django shell
```

### Collecting Static Files
Compile and collect Django's admin and model assets into your configured static directory prior to production deployments:

```bash
uv run reflex django collectstatic --noinput
```

---

## 3. How Settings & Bootstrapping Work

To guarantee that your migrations target the same database as your live server, the CLI boots using a precise three-stage initialization sequence:

```text
    Stage 1: Config Parsing
    Locates and imports rxconfig.py using Reflex's native config loaders.
              │
              ▼
    Stage 2: Environment Resolution
    Plugin sets the DJANGO_SETTINGS_MODULE and resolves system path variables.
              │
              ▼
    Stage 3: Django Bootstrapping
    Invokes configure_django() which executes django.setup() in the active thread.
              │
              ▼
    Stage 4: Command Execution
    Forwards terminal arguments directly to Django's execution parser.
```

1. **Config Parsing**: The script invokes `_load_rxconfig()`, which utilizes `reflex_base.config.get_config()` to load the active configuration parameters.
2. **Environment Resolution**: The `ReflexDjangoPlugin` registers your configured backend settings, setting `DJANGO_SETTINGS_MODULE` (defaulting to your custom configuration or falling back to the default package settings).
3. **Django Bootstrapping**: `configure_django()` is triggered, running `django.setup()` to initialize models, apps, and database connections.
4. **Command Execution**: The script hands off argument parsing to Django's `execute_from_command_line` pipeline, ensuring native support for flags, plans, and custom parameters.

---

## 4. Advanced Operations & Parameter Forwarding

Because both entry points are direct passthroughs, you can append any standard Django flags, names, or optional parameters:

### Migration Dry Runs
Examine what migrations will be executed without modifying your database:

```bash
uv run reflex django migrate --plan
```

### Targeted Schema Generation
Generate migrations targeting a specific app with a custom description:

```bash
uv run reflex django makemigrations catalog --name add_discount_field
```

### Running Specific Management Commands
If you register custom Django management commands (inside `<app_name>/management/commands/`), you can execute them directly:

```bash
uv run reflex django my_custom_command --flag-active
```

---

## 5. Troubleshooting CLI Issues

| Symptom | Cause | Solution |
|:---|:---|:---|
| `ModuleNotFoundError: No module named 'rxconfig'` | The command was executed from outside your project root directory. | Ensure your terminal is in the folder containing `rxconfig.py` before running commands. |
| Migrations target the wrong database. | The CLI is reading from default settings rather than your active project settings. | Verify that `DJANGO_SETTINGS_MODULE` is correctly set in your environment or defined in your `rxconfig` plugin options. |
| Custom app models are not being discovered. | The Django app containing the models is missing from your configuration. | Ensure the app is registered within the `INSTALLED_APPS` block of your settings file. |
| `CommandError: You must set settings.ALLOWED_HOSTS` | Production settings are being loaded without host configurations. | Configure environment variables to pass production settings or specify hosts in your active settings file. |

---

**Navigation:** [← Forms & Validation](forms_and_validation.md) | [Next: Testing Guide →](testing.md)
