---
level: intermediate
tags: [integration, legacy]
---

# Add to an existing Reflex project (removed in v4)

The settings-driven integration path was **removed in v4**. reflex-django now uses **`ReflexDjangoPlugin` in `rxconfig.py`** only.

## Use instead

- **[Plugin path](existing_reflex_project_plugin.md)** - keep `rxconfig.py`, `app = rx.App()`, and `reflex run`
- **[Add to an existing Django project](existing_django_project.md)** - brownfield Django projects
- **[v4: Plugin-only migration](../reference/migration/v4_plugin_only.md)** - upgrade checklist from v3
