---
level: beginner
tags: [integration]
---

# Integration guides

**What you will learn:** Which brownfield guide to follow when you already have Django, Reflex, or neither.

**When you need this:**

- You are not starting from an empty folder and need the right migration path.
- You want to know what is shared between the Django-first and Reflex-first guides before you commit to one.

You already have a codebase. Pick the row that matches you.

---

## Which guide is for me?

| I already have… | I want to add… | Read this |
|:---|:---|:---|
| A **Django** project (models, admin, API, `manage.py`) | Reflex pages and a reactive SPA | [Add to an existing Django project](../getting-started/existing_django_project.md) |
| A **Reflex** project (`rxconfig.py`, `reflex run`, `{app}/{app}.py`) | Django ORM, admin, auth, migrations | [Add to an existing Reflex project](../getting-started/existing_reflex_project.md) |
| Neither | A new hybrid app from scratch | [Your first app](../getting-started/quickstart.md) |

Both brownfield paths end in the same place: **one origin**, Django session cookies shared with Reflex handlers, and `python manage.py run_reflex` for local dev.

---

## What is the same in both guides

No matter which side you start from, you will:

1. Install `reflex` and `reflex-django`
2. Put Reflex runtime config in `settings.py` (`REFLEX_DJANGO_RX_CONFIG`)
3. Import page modules from `urls.py` so `@page` decorators register
4. Point `config/asgi.py` at plain `get_asgi_application()` (see [minimal_asgi.py](snippets/minimal_asgi.py))
5. Run `python manage.py run_reflex` instead of juggling separate servers

Your `@page` routes, `@rx.event` handlers, and Django `urlpatterns` for `/admin` and `/api` work together. See [Routing](../internals/routing.md) for how URLs are split.

### Optional split-process dev

Run Django with `runserver` and set `RXDJANGO_PROXY_SERVER` when you want Django HTTP isolated from the Reflex backend. See [Migrating to mount-only](migration/v3_mount_only.md).

---

## What differs

| Topic | From Django | From Reflex |
|:---|:---|:---|
| Biggest lift | Writing your first `@page` in `views.py` | Adding `manage.py` + Django settings shell |
| Config | Mostly new keys in existing `settings.py` | Move `rxconfig.py` into `settings.py` |
| App entry | No `{app}/{app}.py` needed | Replace `app = rx.App()` with `from reflex_django import app` |
| Default dev | `run_reflex` with Django mounted in Reflex backend | Same; optional `RXDJANGO_PROXY_SERVER` for split Django |
| Typical motivation | SPA on top of existing API/admin | Database and admin without rebuilding UI |

---

## After integration

- [AppState and Django context](../guides/state.md)
- [Pages in views.py](../guides/pages.md)
- [Local development](../getting-started/local_development.md)
- [Deployment](../operations/deployment.md)
- [Migrating to mount-only](migration/v3_mount_only.md)

---

## What just happened?

You matched your starting codebase to one of three paths. Django-first teams add Reflex pages inside existing apps. Reflex-first teams wrap the UI in a Django project shell. Both land on the same v3 layout: settings-driven config, `@page` in `views.py`, and `run_reflex` for dev with Django mounted in the Reflex backend.

---

**Next up:** [Add to an existing Django project](../getting-started/existing_django_project.md)
