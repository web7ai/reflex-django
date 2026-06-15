# Getting started

Follow these steps in order if you are new. Each link is a self-contained page. Skip ahead only when you already know the earlier step.

1. [Install](installation.md) - add `reflex` and `reflex-django` to your environment
2. [Your first app](quickstart.md) - build a small todo app (pages, state, auth, database)
3. [Project structure](project_structure.md) - where files live and what imports matter
4. [Configuration](configuration.md) - the settings you touch on day one
5. [Local development](local_development.md) - ports, `reflex run`, and optional split-process dev

---

## Brownfield integration

Already have a project? Start with the guide that matches your codebase:

### Existing Django project

You run Django today and want Reflex pages on the same origin. Add `rxconfig.py` with `ReflexDjangoPlugin` and `{app_name}/{app_name}.py`. Dev: `reflex run`.

→ **[Add to an existing Django project](existing_django_project.md)**

### Existing Reflex project

You have `rxconfig.py`, `app = rx.App()`, and pages you want to keep. You add a Django shell for ORM, admin, and `request.user`.

→ **[Plugin path](existing_reflex_project_plugin.md)** — `ReflexDjangoPlugin` in `rxconfig.py`, dev with `reflex run`.

Both paths need `manage.py`, `settings.py`, and `urls.py`. See also [v4 migration](../reference/migration/v4_plugin_only.md) if upgrading from v3.

---

**Stuck?** See [Troubleshooting](../operations/troubleshooting.md).

**Next:** [Guides](../guides/index.md) when you are ready to build features.