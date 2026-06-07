# What's new in reflex-django

**What you will learn:** What changed in v1.0 and where to read the full release notes.

**When you need this:**

- You are upgrading from 0.x.
- You want a quick summary before reading the migration guide.

---

## v1.0 (2026-06-07)

reflex-django v1.0 is a **Django-first** integration release. Configuration, ASGI boot, and dev orchestration all assume Django owns project settings and `manage.py run_reflex` is the primary dev entry.

### Highlights

| Area | v1.0 behavior |
|:---|:---|
| **Routing** | Two supported modes: `django_outer` (default) and `reflex_outer`. Legacy `reflex_led` / `django_led` removed. |
| **Config** | `REFLEX_DJANGO_RX_CONFIG` in `settings.py` replaces disk `rxconfig.py`. `ReflexDjangoPlugin` auto-injection removed. |
| **ASGI** | Use `reflex_django.asgi_entry.application`. `make_dispatcher` removed. |
| **Packages** | New modules: `core`, `bootstrap`, `bridge`, `dev`, `mount.spa_paths`, `errors`. |
| **Dev** | `RunPlan` drives `run_reflex` flags. Two-port Vite + backend remains the default workflow. |
| **Docs** | Migration guide, routing reference, architecture overview, and pytest CI for the doc site. |

### Breaking changes (short list)

- Set `REFLEX_DJANGO_URL_ROUTING` to `django_outer` or `reflex_outer` (not `django_led` / `reflex_led`).
- Move Reflex config into Django settings. Delete or stop relying on `rxconfig.py`.
- Replace `reflex_django.asgi.make_dispatcher` with `build_django_outer_application` / `asgi_entry.application`.
- Import pages and state from `reflex_django.pages.decorators` and `reflex_django.states`.

### Upgrade path

Follow the step-by-step checklist:

**[Migrating to v1.0 →](migration/v1_migration.md)**

Older links to `migration/v0-to-v1.md` redirect there as well.

---

## Full changelog

Every added, changed, and removed item is recorded in the repository changelog:

**[CHANGELOG.md on GitHub →](https://github.com/web7ai/reflex-django/blob/main/CHANGELOG.md)**

---

## What just happened?

You saw the v1.0 headline changes and where to find exhaustive release notes.

**Next up:** [Migrating to v1.0](migration/v1_migration.md) if you are upgrading, or [What's in the box](index.md) if you are starting fresh.
