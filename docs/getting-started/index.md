# Getting started

Follow these steps in order if you are new. Each link is a self-contained page. Skip ahead only when you already know the earlier step.

1. [Install](installation.md) - add `reflex` and `reflex-django` to your environment
2. [Your first app](quickstart.md) - build a small todo app (pages, state, auth, database)
3. [Project structure](project_structure.md) - where files live and what imports matter
4. [Configuration](configuration.md) - the settings you touch on day one
5. [Local development](local_development.md) - ports, `run_reflex`, and optional split-process dev

---

## Brownfield integration

Already have a project? Start with the guide that matches your codebase:

### Existing Django project

You run Django today and want Reflex pages on the same origin. Config lives in `settings.py` (`RX_CONFIG`). Dev: `python manage.py run_reflex`.

→ **[Add to an existing Django project](existing_django_project.md)**

### Existing Reflex project

You have `rxconfig.py`, `app = rx.App()`, and pages you want to keep. You add a Django shell for ORM, admin, and `request.user`.

| Approach | Config | Dev command | Guide |
|:---|:---|:---|:---|
| **Settings path** | `RX_CONFIG` in `settings.py` | `python manage.py run_reflex` | [Existing Reflex project](existing_reflex_project.md) |
| **Plugin path** | `ReflexDjangoPlugin` in `rxconfig.py` | `reflex run` | [Plugin path](existing_reflex_project_plugin.md) |

Both Reflex paths need `manage.py`, `settings.py`, and `urls.py`. Pick one dev command and stick with it.

---

**Stuck?** See [Troubleshooting](../operations/troubleshooting.md).

**Next:** [Guides](../guides/index.md) when you are ready to build features.