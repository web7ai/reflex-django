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
| A **Django** project (models, admin, API, `manage.py`) | Reflex pages and a reactive SPA | [Add to an existing Django project](existing_django_project.md) |
| A **Reflex** project (`rxconfig.py`, `reflex run`, `{app}/{app}.py`) | Django ORM, admin, auth, migrations | [Add to an existing Reflex project](existing_reflex_project.md) |
| Neither | A new hybrid app from scratch | [Your first app](quickstart.md) |

Both brownfield paths end in the same place: **one origin**, Django session cookies shared with Reflex handlers, and `python manage.py run_reflex` for local dev.

---

## What is the same in both guides

No matter which side you start from, you will:

1. Install `reflex` and `reflex-django`
2. Put Reflex runtime config in `settings.py` (`REFLEX_DJANGO_RX_CONFIG`)
3. Import page modules from `urls.py` so `@page` decorators register
4. Point `config/asgi.py` at `reflex_django.asgi.entry.application`
5. Run `python manage.py run_reflex` instead of juggling separate servers

Your `@page` routes, `@rx.event` handlers, and Django `urlpatterns` for `/admin` and `/api` work together. See [Routing](routing.md) for how URLs are split.

### Choosing a routing mode (v1.0)

```text
Need Django ORM + admin in the same process as Reflex?
  └─ Default: django_outer (one ASGI process)

Heavy Django HTTP load and want Reflex isolated on the public port?
  └─ reflex_outer (Reflex outer + separate Django HTTP worker)
```

v1.0 supports **`django_outer`** and **`reflex_outer`** only. Legacy `reflex_led` / `django_led` modes are removed. See [v1 migration](migration/v1_migration.md) if you are upgrading.

Media and uploads work in both modes once Django media is configured: [Media files](media_files.md), [File uploads](file_uploads.md).

---

## What differs

| Topic | From Django | From Reflex |
|:---|:---|:---|
| Biggest lift | Writing your first `@page` in `views.py` | Adding `manage.py` + Django settings shell |
| Config | Mostly new keys in existing `settings.py` | Move `rxconfig.py` into `settings.py` |
| App entry | No `{app}/{app}.py` needed | Replace `app = rx.App()` with `from reflex_django import app` |
| Default routing | `django_outer` (keep default) | Same unless you need `reflex_outer` |
| Typical motivation | SPA on top of existing API/admin | Database and admin without rebuilding UI |

---

## After integration

- [AppState and Django context](state_management.md)
- [Pages in views.py](pages_in_views.md)
- [Local development](local_development.md)
- [Deployment](deployment.md)
- [django_outer vs reflex_outer](routing.md#choosing-a-mode-django_outer-vs-reflex_outer)

---

## What just happened?

You matched your starting codebase to one of three paths. Django-first teams add Reflex pages inside existing apps. Reflex-first teams wrap the UI in a Django project shell. Both land on the same v1.0 layout: settings-driven config, `@page` in `views.py`, and `run_reflex` for dev.

---

**Next up:** [Add to an existing Django project](existing_django_project.md)
