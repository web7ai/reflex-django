# What's new in reflex-django

**What you will learn:** What changed in recent releases and where to read the full release notes.

**When you need this:**

- You are upgrading from an older version.
- You want a quick summary before reading a migration guide.

---

## v3 (mount-only, unreleased)

v3 removes composed ASGI routing (`django_outer`, `reflex_outer`, `reflex_django.asgi.entry`). Production Django uses plain `get_asgi_application()`. Dev uses `manage.py run_reflex` with Django mounted in the Reflex backend via `make_dispatcher`.

### Highlights

| Area | v3 behavior |
|:---|:---|
| **Production ASGI** | `get_asgi_application()` in `config/asgi.py` |
| **Dev** | `run_reflex` → Vite + Reflex backend; Django in-process (no `RXDJANGO_PROXY_SERVER` required) |
| **Optional dev split** | `RXDJANGO_PROXY_SERVER` when Django runs on separate `runserver` |
| **Removed** | `REFLEX_DJANGO_URL_ROUTING`, `REFLEX_DJANGO_HTTP_*`, `asgi.entry` |
| **Restored** | `make_dispatcher` for in-process Django on Reflex backend |
| **Performance** | Tiered event bridge (`smart` mode), Django event cache, `lean` preset, opt-in metrics — see [Scaling](scaling.md) |

### Upgrade path

**[Migrating to mount-only →](migration/v3_mount_only.md)**

---

## v2.0 (2026-06-12)

!!! note "Superseded by v3 for ASGI"
    v3 removed `reflex_django.asgi.entry`. If you are on v2+, read **[Migrating to mount-only](migration/v3_mount_only.md)** for current ASGI and dev workflow.

v2.0 reorganizes the Python package into domain subpackages (`asgi/`, `runtime/`, `bridge/`, `django/`, `dev/`, `setup/`, …). Most user-facing imports stay the same; string-based Django settings paths and a few module paths changed.

### Highlights

| Area | v2.0 behavior |
|:---|:---|
| **ASGI** | `from reflex_django.asgi.entry import application` (was `asgi_entry`) |
| **Django URLs** | `reflex_django.django.urls` for `ROOT_URLCONF` defaults and `reflex_mount` |
| **Streaming middleware** | `reflex_django.bridge.streaming.AsyncStreamingMiddleware` |
| **Dev middleware** | `reflex_django.dev.django_middleware.DEFAULT_DEV_MIDDLEWARE` |
| **Package layout** | Root contains only `__init__.py`; see [v2 module paths](migration/v2_module_paths.md) |
| **`auth_state`** | `DjangoUserState` still lives in `reflex_django.auth_state` for stable compiled event keys |

### Breaking changes (short list)

- Update `config/asgi.py` to import from `reflex_django.asgi.entry`.
- Update `MIDDLEWARE` and `ROOT_URLCONF` strings if you copied defaults from older docs.
- Remove any `reflex_django.django_led_app` imports (use `from reflex_django import app`).

### Upgrade path

**[Migrating to v2.0 →](migration/v2_module_paths.md)**

---

## v1.0 (2026-06-07)

!!! note "Historical release"
    v1.0 introduced `django_outer` / `reflex_outer` routing and `reflex_django.asgi.entry`, both **removed in v3**. This section documents v1.0 only for upgrades from v0.x.

reflex-django v1.0 is a **Django-first** integration release. Configuration, ASGI boot, and dev orchestration all assume Django owns project settings and `manage.py run_reflex` is the primary dev entry.

### Highlights

| Area | v1.0 behavior |
|:---|:---|
| **Routing** | Two supported modes: `django_outer` (default) and `reflex_outer`. Legacy `reflex_led` / `django_led` removed. |
| **Config** | `REFLEX_DJANGO_RX_CONFIG` in `settings.py` replaces disk `rxconfig.py`. `ReflexDjangoPlugin` auto-injection removed. |
| **ASGI** | Use `reflex_django.asgi.entry.application`. `make_dispatcher` removed. |
| **Packages** | New modules: `core`, `bootstrap`, `bridge`, `dev`, `mount.spa_paths`, `errors`. |
| **Dev** | `RunPlan` drives `run_reflex` flags. Two-port Vite + backend remains the default workflow. |
| **Docs** | Migration guide, routing reference, architecture overview, and pytest CI for the doc site. |

### Breaking changes (short list)

- Set `REFLEX_DJANGO_URL_ROUTING` to `django_outer` or `reflex_outer` (not `django_led` / `reflex_led`).
- Move Reflex config into Django settings. Delete or stop relying on `rxconfig.py`.
- Replace `reflex_django.asgi.make_dispatcher` with `build_django_outer_application` / `asgi.entry.application`.
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

You saw headline changes for v3, v2, and v1 and where to find exhaustive release notes.

**Next up:** [Migrating to mount-only](migration/v3_mount_only.md) if you are upgrading, or [What's in the box](index.md) if you are starting fresh.
